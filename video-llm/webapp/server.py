"""
FastAPI app that wraps the extraction pipeline for a live demo.

Run:  python -m uvicorn webapp.server:app --reload      (from the repo root)
  or: ./webapp/run.sh

Endpoints
  POST /api/jobs                 {url} | multipart file  -> {job_id}
  GET  /api/jobs/{id}            full job snapshot (poll fallback)
  GET  /api/jobs/{id}/events     SSE stream of progress + final result
  POST /api/jobs/{id}/corrections  log a confirm/reject/edit/add action
  GET  /api/thumb/{video_id}     uploaded-video thumbnail
  GET  /                         the single-page demo
"""

import json
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (FileResponse, JSONResponse, PlainTextResponse,
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles

import config as cfg
import runner

cfg.bootstrap_dirs()

app = FastAPI(title="Routine Extractor — Demo")


# --------------------------------------------------------------------------
# Create a job (URL or upload)
# --------------------------------------------------------------------------
@app.post("/api/jobs")
async def create_job(
    request: Request,
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    # Support both multipart (upload) and JSON body (url) posts.
    if url is None and file is None:
        try:
            body = await request.json()
            url = (body or {}).get("url")
        except Exception:
            url = None

    if file is not None:
        data = await file.read()
        if not data:
            raise HTTPException(400, "Empty file.")
        job, path = runner.job_from_upload(file.filename or "upload.mp4", data)
        runner.start_job(job, source_path=path, url=None)
    elif url and url.strip():
        job = runner.job_from_url(url.strip())
        runner.start_job(job, source_path=None, url=url.strip())
    else:
        raise HTTPException(400, "Provide a video URL or upload a file.")

    return {"job_id": job.id, "cached_hint": runner._cached_result_path(job.video_id).exists()}


# --------------------------------------------------------------------------
# Poll snapshot (fallback for clients without SSE)
# --------------------------------------------------------------------------
@app.get("/api/jobs/{job_id}")
async def job_snapshot(job_id: str):
    job = runner.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job.snapshot()


# --------------------------------------------------------------------------
# SSE progress stream
# --------------------------------------------------------------------------
@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = runner.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    def stream():
        sent = 0
        # Emit any events already buffered, then poll for new ones until terminal.
        while True:
            snap = job.snapshot()
            events = snap["events"]
            while sent < len(events):
                ev = events[sent]
                sent += 1
                yield f"event: progress\ndata: {json.dumps(ev)}\n\n"
            if snap["state"] == "done":
                payload = {"result": snap["result"]}
                yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                return
            if snap["state"] == "error":
                payload = {"error": snap["error"] or "Unknown error"}
                yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                return
            time.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------
# Corrections logging  (one JSONL file per session — saved even in demos)
# --------------------------------------------------------------------------
@app.post("/api/jobs/{job_id}/corrections")
async def log_correction(job_id: str, request: Request):
    job = runner.get_job(job_id)
    body = await request.json()
    action = (body or {}).get("action")
    if action not in {"confirm", "reject", "edit", "add"}:
        raise HTTPException(400, "action must be confirm|reject|edit|add")

    session_id = (body or {}).get("session_id") or job_id
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "job_id": job_id,
        "video_id": job.video_id if job else (body or {}).get("video_id"),
        "action": action,
        "product": (body or {}).get("product"),
        "before": (body or {}).get("before"),
        "after": (body or {}).get("after"),
    }
    path = cfg.CORRECTIONS_DIR / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"ok": True, "logged_to": path.name}


# --------------------------------------------------------------------------
# Uploaded-video thumbnail
# --------------------------------------------------------------------------
@app.get("/api/thumb/{video_id}")
async def thumb(video_id: str):
    p = cfg.JOBS_DIR / f"{video_id}_thumb.jpg"
    if not p.exists():
        raise HTTPException(404, "No thumbnail.")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/health")
async def health():
    return {"ok": True, "auto_approve": cfg.AUTO_APPROVE_THRESHOLD,
            "confirm_floor": cfg.CONFIRM_FLOOR}


# --------------------------------------------------------------------------
# Pages  (defined after /api/* so those routes win)
#
#   /       landing / marketing page   (../Landing Page/index.html)
#   /try    the "Try it out!" demo app (webapp/static/index.html)
#
# Only the landing page's three known assets are exposed at the root — we do
# NOT mount the repo root as static, which would leak source and .env.
# The landing page lives in the sibling "Landing Page" folder (Video LLM/ and
# Landing Page/ share the same parent).
# --------------------------------------------------------------------------
LANDING_DIR = cfg.ROOT.parent / "Landing Page"
LANDING_ASSETS = {
    "styles.css": "text/css",
    "main.js": "application/javascript",
}


@app.get("/")
async def landing():
    idx = LANDING_DIR / "index.html"
    if not idx.exists():
        return PlainTextResponse("Landing page not found.", status_code=500)
    return FileResponse(idx)


@app.get("/try")
async def demo_index():
    idx = cfg.STATIC_DIR / "index.html"
    if not idx.exists():
        return PlainTextResponse("Frontend not built yet.", status_code=500)
    return FileResponse(idx)


# Demo assets live under /try/* (app.js, styles.css, …)
app.mount("/try", StaticFiles(directory=str(cfg.STATIC_DIR), html=True), name="demo")


# Landing assets at the root — registered last so /, /try and /api/* win first.
@app.get("/{asset}")
async def landing_asset(asset: str):
    media_type = LANDING_ASSETS.get(asset)
    if media_type is None:
        raise HTTPException(404, "Not found.")
    return FileResponse(LANDING_DIR / asset, media_type=media_type)
