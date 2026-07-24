"""
Self-serve generation. A creator provides a source — a pasted video link, an
uploaded .mp4, or a pre-extracted video — and the pipeline extracts products,
cuts clips, and publishes a shoppable page.

Where it runs:
  • WORKER_ENABLED → the API enqueues the job; the worker (worker.py) processes it.
  • else PIPELINE_AVAILABLE → the API runs it inline (dev).
  • else → the request is captured (status 'received') to build out-of-band.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app import config, pipeline_runner, storage
from app.auth import current_user
from app.db import get_session
from app.models import Creator, GenerationJob, User

router = APIRouter(prefix="/me", tags=["generate"])

# Per-creator generation limits — the pipeline is expensive (yt-dlp + Whisper +
# an LLM call), so cap it to prevent a single account running up compute bills.
_DAILY_GENERATION_CAP = 25
_INFLIGHT_GENERATION_CAP = 3
_ALLOWED_UPLOAD_TYPES = {"video/mp4", "video/quicktime"}


def _validate_source_url(url: str) -> None:
    """Block SSRF: the server fetches this URL, so only allow real, public
    http(s) hosts — reject private / loopback / link-local / metadata targets."""
    try:
        p = urlparse(url)
    except Exception:
        raise HTTPException(400, "Enter a valid video link.")
    if p.scheme not in ("http", "https") or not p.hostname:
        raise HTTPException(400, "Enter a valid video link (http/https).")
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except Exception:
        raise HTTPException(400, "Couldn't resolve that link.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise HTTPException(400, "That link isn't allowed.")


def _enforce_generation_quota(user: User, session: Session) -> None:
    since = datetime.utcnow() - timedelta(hours=24)
    recent = session.exec(select(func.count()).select_from(GenerationJob)
                          .where(GenerationJob.handle == user.handle,
                                 GenerationJob.created_at >= since)).one()
    if recent >= _DAILY_GENERATION_CAP:
        raise HTTPException(429, "Daily generation limit reached — try again tomorrow.")
    inflight = session.exec(select(func.count()).select_from(GenerationJob)
                            .where(GenerationJob.handle == user.handle,
                                   GenerationJob.status.in_(["queued", "running"]))).one()
    if inflight >= _INFLIGHT_GENERATION_CAP:
        raise HTTPException(429, "You already have videos building — let those finish first.")


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


# --- direct-to-storage upload (creator uploads their own mp4) --------------
class PresignBody(BaseModel):
    filename: str = "video.mp4"
    contentType: str = "video/mp4"


@router.post("/uploads/presign")
def presign_upload(body: PresignBody, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    """A presigned URL so the creator uploads their video straight to object
    storage; the returned `key` is then passed to /me/generate as uploadKey."""
    _require_creator(user, session)
    if not storage.enabled():
        raise HTTPException(503, "Video upload isn't enabled on this deployment yet.")
    # Only allow real video uploads — an arbitrary content-type (e.g. text/html)
    # could be served as active content from the media domain.
    ctype = (body.contentType or "video/mp4").strip().lower()
    if ctype not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(400, "Only .mp4 or .mov video uploads are allowed.")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", body.filename)[-60:] or "video.mp4"
    key = f"uploads/{user.handle}/{uuid.uuid4().hex}-{safe}"
    return {"uploadUrl": storage.presign_put(key, content_type=ctype), "key": key}


# --- generation ------------------------------------------------------------
class GenerateBody(BaseModel):
    videoId: str | None = None    # a pre-extracted video, OR
    url: str | None = None        # a pasted video link, OR
    uploadKey: str | None = None  # the storage key of an uploaded mp4
    title: str | None = None      # optional page name


@router.post("/generate")
def start_generation(body: GenerateBody, background: BackgroundTasks,
                     user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
    _require_creator(user, session)
    _enforce_generation_quota(user, session)
    url = (body.url or "").strip()
    upload_key = (body.uploadKey or "").strip()
    if url:
        _validate_source_url(url)   # SSRF guard on the server-fetched link
    if not (url or upload_key or body.videoId):
        raise HTTPException(400, "Provide a video link, upload a video, or pick one.")
    if body.videoId and config.PIPELINE_AVAILABLE and not config.WORKER_ENABLED:
        if not (config.VIDEO_LLM_OUTPUT / f"{body.videoId}.json").exists():
            raise HTTPException(404, "No extraction available for that video.")

    source_url = url or (f"upload:{upload_key}" if upload_key else "")
    title = (body.title or "").strip()

    if config.WORKER_ENABLED:                       # prod: hand to the worker
        status, stage, inline = "queued", "Queued — building your page…", False
    elif config.PIPELINE_AVAILABLE:                 # dev: run inline
        status, stage, inline = "queued", "Queued", True
    else:                                           # no pipeline, no worker: capture
        status, stage, inline = "received", \
            "Got it! Your page is being built — we'll email you when it's live.", False

    job = GenerationJob(handle=user.handle, video_id=body.videoId or "",
                        source_url=source_url, title=title, status=status, stage=stage)
    session.add(job)
    session.commit()
    session.refresh(job)
    if inline:
        background.add_task(pipeline_runner.process_job, job.id)
    return {"jobId": job.id, "status": job.status}


@router.get("/generate/{job_id}")
def generation_status(job_id: str, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    job = session.get(GenerationJob, job_id)
    if not job or job.handle != user.handle:
        raise HTTPException(404, "Job not found")
    try:
        preview = json.loads(job.preview) if job.preview else []
    except Exception:
        preview = []
    return {
        "jobId": job.id, "status": job.status, "stage": job.stage,
        "phase": job.phase, "preview": preview, "durationS": job.duration_s,
        "pageSlug": job.page_slug, "error": job.error,
    }
