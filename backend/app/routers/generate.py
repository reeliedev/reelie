"""
Self-serve generation (Phase 1.3). An authenticated creator picks a video and the
server runs the existing page-generator pipeline as a subprocess; the generator
POSTs the finished page back to /ingest, so it lands in the creator's account and
shows up in the catalogue. Job status is polled by the client.

Locally this runs in --mock mode ($0, no API key). Set GENERATE_LIVE=1 for the
real LLM pipeline. The full video→extraction step (needs ffmpeg) plugs in behind
the same job; today we generate from already-extracted videos.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app import config
from app.auth import current_user
from app.db import engine, get_session
from app.models import Creator, GenerationJob, User

router = APIRouter(prefix="/me", tags=["generate"])


def _require_creator(user: User, session: Session) -> None:
    """Closed beta: must be an approved creator to see videos or generate."""
    if user.role not in ("creator", "both") or not user.handle:
        raise HTTPException(403, "Become a creator first.")
    creator = session.get(Creator, user.handle)
    if not creator or creator.status != "approved":
        raise HTTPException(403, "Your creator application is under review — "
                                 "you'll be able to publish once it's approved.")


@router.get("/videos")
def available_videos(user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
    """Videos the creator can generate a page from (already-extracted sources)."""
    _require_creator(user, session)
    out = config.VIDEO_LLM_OUTPUT
    videos = []
    if out.exists():
        for f in sorted(out.glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue
            videos.append({
                "videoId": d.get("video_id", f.stem),
                "title": d.get("video_title") or f.stem,
                "numProducts": len(d.get("products", [])),
                "durationS": d.get("duration_s", 0),
            })
    return videos


class GenerateBody(BaseModel):
    videoId: str | None = None   # generate from an already-extracted video, OR…
    url: str | None = None       # …a video link the creator pastes (extract, then build)
    title: str | None = None     # optional: the creator's chosen page name


@router.post("/generate")
def start_generation(body: GenerateBody, background: BackgroundTasks,
                     user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
    _require_creator(user, session)
    url = (body.url or "").strip()
    if url:
        if not url.startswith("http"):
            raise HTTPException(400, "Enter a valid video link.")
    elif body.videoId:
        if not (config.VIDEO_LLM_OUTPUT / f"{body.videoId}.json").exists():
            raise HTTPException(404, "No extraction available for that video.")
    else:
        raise HTTPException(400, "Provide a video link or pick a video.")

    job = GenerationJob(handle=user.handle, video_id=body.videoId or "",
                        status="queued", stage="Queued")
    session.add(job)
    session.commit()
    session.refresh(job)

    background.add_task(_run_generation, job.id, user.handle, user.display_name,
                        body.videoId, url or None, (body.title or "").strip() or None)
    return {"jobId": job.id, "status": job.status}


@router.get("/generate/{job_id}")
def generation_status(job_id: str, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    job = session.get(GenerationJob, job_id)
    if not job or job.handle != user.handle:
        raise HTTPException(404, "Job not found")
    return {
        "jobId": job.id, "status": job.status, "stage": job.stage,
        "pageSlug": job.page_slug, "error": job.error,
    }


# --------------------------------------------------------------------------
# background runner
# --------------------------------------------------------------------------
def _set(job_id: str, **fields) -> None:
    with Session(engine) as s:
        job = s.get(GenerationJob, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        s.add(job)
        s.commit()


def _run_generation(job_id: str, handle: str, display_name: str,
                    video_id: str | None, url: str | None = None,
                    title: str | None = None) -> None:
    try:
        # 1) If the creator pasted a link, extract it first (download → transcribe →
        #    keyframes → find products) into an output/<id>.json.
        if url:
            _set(job_id, status="running", stage="Fetching your video")
            ex = subprocess.run([config.PYTHON_BIN, str(config.EXTRACT_ONE), url],
                                cwd=str(config.VIDEO_LLM_DIR),
                                capture_output=True, text=True, timeout=900)
            if ex.returncode != 0:
                raise RuntimeError("Couldn't process that link — try uploading the file. "
                                   + (ex.stderr or ex.stdout)[-300:])
            m = re.search(r"VIDEO_ID:(\S+)", ex.stdout)
            if not m:
                raise RuntimeError("Extraction produced no video.")
            video_id = m.group(1)
            _set(job_id, video_id=video_id, stage="Found your products")

        # 2) Build + publish the page from the extraction.
        _set(job_id, status="running", stage="Building your page")
        cmd = [config.PYTHON_BIN, str(config.GENERATE_PY),
               "--from-output", video_id, "--handle", handle,
               "--name", display_name or handle]
        if title:
            cmd += ["--title", title]
        if not config.GENERATE_CLIPS:
            cmd.append("--no-clips")   # minimal worker without ffmpeg/source video
        if not config.GENERATE_LIVE:
            cmd.append("--mock")
        env = {**os.environ, "REELIE_API_URL": config.SELF_URL,
               "REELIE_MEDIA_ROOT": str(config.MEDIA_ROOT),
               "REELIE_INGEST_TOKEN": config.INGEST_TOKEN}
        result = subprocess.run(cmd, cwd=str(config.PAGE_GENERATOR_DIR), env=env,
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout)[-600:])
        m = re.search(rf"{re.escape(handle)}/([a-z0-9\-]+)", result.stdout)
        _set(job_id, status="done", stage="Published", page_slug=m.group(1) if m else None)
    except Exception as e:  # noqa: BLE001
        _set(job_id, status="error", stage="Failed", error=str(e))
