"""
Run one generation job end-to-end: resolve the source (pasted URL, uploaded mp4,
or a pre-extracted video), extract products, build + publish the page.

Shared by the dev inline path (BackgroundTasks) and the production worker
(worker.py). Needs the pipeline present (video-llm + page-generator + ffmpeg),
so it only runs where config.PIPELINE_AVAILABLE.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

from sqlmodel import Session

from app import config, storage
from app.db import engine
from app.models import Creator, GenerationJob


def _set(job_id: str, **fields) -> None:
    with Session(engine) as s:
        job = s.get(GenerationJob, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        s.add(job)
        s.commit()


def _load_preview(video_id: str) -> tuple[list[dict], float]:
    """Read the extraction output → the products found (for the live reveal) plus
    the video duration (for the scan animation). Empty if not present."""
    f = config.VIDEO_LLM_OUTPUT / f"{video_id}.json"
    if not f.exists():
        return [], 0.0
    try:
        d = json.loads(f.read_text())
    except Exception:
        return [], 0.0
    items = []
    for p in sorted(d.get("products", []), key=lambda x: x.get("timestamp_s") or 0):
        name = (p.get("product_name") or "").strip()
        if not name and not (p.get("brand") or "").strip():
            continue
        items.append({
            "brand": (p.get("brand") or "").strip(),
            "name": name,
            "variant": (p.get("variant_or_shade") or "").strip(),
            "t": round(float(p.get("timestamp_s") or 0), 1),
            "evidence": p.get("evidence_type") or "shown",
        })
    return items, float(d.get("duration_s") or 0)


def _extract(job_id: str, source_arg: str) -> str:
    """Run extract_one on a URL or a local file path → returns the video_id."""
    ex = subprocess.run([config.PYTHON_BIN, str(config.EXTRACT_ONE), source_arg],
                        cwd=str(config.VIDEO_LLM_DIR),
                        capture_output=True, text=True, timeout=1800)
    if ex.returncode != 0:
        # Keep enough of the tail to include the extractor's root_cause line.
        raise RuntimeError("Couldn't process that video. " + (ex.stderr or ex.stdout)[-1200:])
    m = re.search(r"VIDEO_ID:(\S+)", ex.stdout)
    if not m:
        raise RuntimeError("Extraction produced no video.")
    return m.group(1)


def _build(job_id: str, handle: str, display_name: str, video_id: str, title: str) -> None:
    cmd = [config.PYTHON_BIN, str(config.GENERATE_PY),
           "--from-output", video_id, "--handle", handle, "--name", display_name or handle]
    if title:
        cmd += ["--title", title]
    if not config.GENERATE_CLIPS:
        cmd.append("--no-clips")
    if not config.GENERATE_LIVE:
        cmd.append("--mock")
    # Pass storage + ingest creds so the generator uploads clips to R2 and publishes.
    env = {**os.environ,
           "REELIE_API_URL": config.SELF_URL,
           "REELIE_MEDIA_ROOT": str(config.MEDIA_ROOT),
           "REELIE_INGEST_TOKEN": config.INGEST_TOKEN,
           "STORAGE_ENDPOINT": config.STORAGE_ENDPOINT,
           "STORAGE_BUCKET": config.STORAGE_BUCKET,
           "STORAGE_ACCESS_KEY_ID": config.STORAGE_ACCESS_KEY_ID,
           "STORAGE_SECRET_ACCESS_KEY": config.STORAGE_SECRET_ACCESS_KEY,
           "STORAGE_PUBLIC_URL": config.STORAGE_PUBLIC_URL,
           "STORAGE_REGION": config.STORAGE_REGION}
    result = subprocess.run(cmd, cwd=str(config.PAGE_GENERATOR_DIR), env=env,
                            capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout)[-600:])
    m = re.search(rf"{re.escape(handle)}/([a-z0-9\-]+)", result.stdout)
    _set(job_id, status="done", phase="done", stage="Draft ready to review",
         page_slug=m.group(1) if m else None)


def process_job(job_id: str) -> None:
    """The full pipeline for one job, driven entirely by the job row in the DB."""
    with Session(engine) as s:
        job = s.get(GenerationJob, job_id)
        if not job:
            return
        handle, src, video_id, title = job.handle, job.source_url, job.video_id, job.title
        creator = s.get(Creator, handle)
        display_name = creator.display_name if creator else handle

    tmp = None
    try:
        if src.startswith("upload:") or src.startswith("http"):
            _set(job_id, status="running", stage="Watching your video…", phase="analyzing")
            if src.startswith("upload:"):
                key = src[len("upload:"):]
                # Download INTO video-llm/videos/<job_id>.mp4 (not a throwaway temp):
                # process_video sets video_id = sanitize_id(stem) = job_id, and the
                # build step's clip cutter (clips.resolve_source) looks for the source
                # at videos/<video_id>.mp4 — so it must live there through _build.
                videos_dir = config.VIDEO_LLM_DIR / "videos"
                videos_dir.mkdir(parents=True, exist_ok=True)
                tmp = str(videos_dir / f"{job_id}.mp4")
                storage.download_to(key, tmp)
                video_id = _extract(job_id, tmp)
            else:
                video_id = _extract(job_id, src)
        elif not video_id:
            raise RuntimeError("No video source on this job.")

        # Surface the products the moment extraction finishes → the studio reveals
        # them one-by-one over the video while the build/clip step continues.
        preview, dur = _load_preview(video_id)
        n = len(preview)
        _set(job_id, video_id=video_id, phase="found", duration_s=dur,
             preview=json.dumps(preview),
             stage=f"Found {n} product{'' if n == 1 else 's'}")

        _set(job_id, status="running", stage="Pricing & building your page…", phase="building")
        _build(job_id, handle, display_name, video_id, title)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        print(f"[worker] job {job_id} FAILED: {msg[-1500:]}", flush=True)  # full-ish in worker log
        _set(job_id, status="error", stage="Failed", error=msg[-800:])
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
