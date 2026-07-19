"""
Thin wrapper around the existing extraction pipeline (../pipeline.py).

It does NOT reimplement extraction — it calls the same library functions the CLI
uses (transcribe, load_or_extract_frames, detect_mirror, extract_products, the
description merge) and emits a progress event between each stage so the web UI can
show a live run. Results are written to the same output/{video_id}.json the CLI
produces, which doubles as the "demo cache": if that file already exists we replay
a fast fake progress animation and serve it instantly.
"""

import hashlib
import json
import re
import sys
import threading
import time
import uuid
from pathlib import Path

# Make the pipeline importable (it lives in the repo root, one level up).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ModuleNotFoundError:
    pass

import config as cfg  # noqa: E402  (local package config)

# --------------------------------------------------------------------------
# Friendly progress stages (label shown to the creator, % for the bar)
# --------------------------------------------------------------------------
STAGE_DOWNLOAD = ("download", "Getting your video ready…", 8)
STAGE_TRANSCRIBE = ("transcribe", "Listening to the audio…", 28)
STAGE_FRAMES = ("frames", "Watching your video…", 55)
STAGE_EXTRACT = ("extract", "Finding your products…", 80)
STAGE_ASSEMBLE = ("assemble", "Putting your routine together…", 94)
CACHED_STAGES = [STAGE_DOWNLOAD, STAGE_TRANSCRIBE, STAGE_FRAMES,
                 STAGE_EXTRACT, STAGE_ASSEMBLE]


# --------------------------------------------------------------------------
# Job model + in-memory store
# --------------------------------------------------------------------------
class Job:
    def __init__(self, video_id: str, source_kind: str, title: str,
                 thumbnail: str, youtube_id: str | None):
        self.id = uuid.uuid4().hex[:12]
        self.video_id = video_id
        self.source_kind = source_kind            # "youtube" | "upload"
        self.youtube_id = youtube_id
        self.title = title
        self.thumbnail = thumbnail
        self.state = "queued"                      # queued|running|done|error
        self.cached = False
        self.events: list[dict] = []               # append-only progress log
        self.result: dict | None = None            # normalized approval payload
        self.error: str | None = None
        self.lock = threading.Lock()

    def emit(self, stage: str, label: str, pct: int) -> None:
        with self.lock:
            self.events.append({"stage": stage, "label": label, "pct": pct})

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "video_id": self.video_id,
                "state": self.state,
                "cached": self.cached,
                "source_kind": self.source_kind,
                "youtube_id": self.youtube_id,
                "title": self.title,
                "thumbnail": self.thumbnail,
                "events": list(self.events),
                "result": self.result,
                "error": self.error,
            }


_JOBS: dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()


def get_job(job_id: str) -> Job | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


# --------------------------------------------------------------------------
# Source resolution (URL vs uploaded file) -> a stable video_id
# --------------------------------------------------------------------------
_YT_ID = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|v/))([A-Za-z0-9_-]{11})"
)


def parse_youtube_id(url: str) -> str | None:
    m = _YT_ID.search(url or "")
    if m:
        return m.group(1)
    # bare 11-char id
    s = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    return None


def _friendly_title(video_id: str) -> str:
    """A cached/known title if we have one, else a warm generic header."""
    meta = cfg.CACHE_DIR / video_id / "meta.json"
    if meta.exists():
        try:
            t = json.loads(meta.read_text()).get("title")
            if t:
                return t
        except Exception:
            pass
    return "Your Skincare Routine"


def _save_title(video_id: str, title: str) -> None:
    if not title:
        return
    p = cfg.CACHE_DIR / video_id / "meta.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"title": title}))


def job_from_url(url: str) -> Job:
    yid = parse_youtube_id(url)
    if yid:
        thumb = f"https://img.youtube.com/vi/{yid}/hqdefault.jpg"
        return Job(video_id=yid, source_kind="youtube", title=_friendly_title(yid),
                   thumbnail=thumb, youtube_id=yid)
    # Non-YouTube URL: key by a hash of the URL.
    vid = "url_" + hashlib.sha1(url.encode()).hexdigest()[:11]
    return Job(video_id=vid, source_kind="youtube", title=_friendly_title(vid),
               thumbnail="", youtube_id=None)


def job_from_upload(filename: str, data: bytes) -> tuple[Job, Path]:
    digest = hashlib.sha1(data).hexdigest()[:11]
    video_id = f"up_{digest}"
    suffix = Path(filename).suffix.lower() or ".mp4"
    dest = cfg.VIDEOS_DIR / f"{video_id}{suffix}"
    cfg.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_bytes(data)
    thumb = _extract_thumbnail(dest, video_id)
    job = Job(video_id=video_id, source_kind="upload", title="Your Skincare Routine",
              thumbnail=thumb, youtube_id=None)
    return job, dest


def _extract_thumbnail(video_path: Path, video_id: str) -> str:
    """Grab a frame ~2s in as the waiting/preview thumbnail. Returns a URL path."""
    import subprocess
    out = cfg.JOBS_DIR / f"{video_id}_thumb.jpg"
    if not out.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "2", "-i", str(video_path), "-frames:v", "1",
             "-vf", "scale='min(iw,640)':-2", "-q:v", "4", str(out)],
            capture_output=True,
        )
    return f"/api/thumb/{video_id}" if out.exists() else ""


# --------------------------------------------------------------------------
# Result normalization -> approval payload the frontend renders
# --------------------------------------------------------------------------
def _bucket(conf: float) -> str:
    if conf >= cfg.AUTO_APPROVE_THRESHOLD:
        return "confirmed"
    if conf >= cfg.CONFIRM_FLOOR:
        return "review"
    return "hidden"


_EVIDENCE_LABEL = {
    "spoken": "Spoken", "shown": "Shown", "both": "Both",
    "on-screen-text": "Shown",
}


def normalize_result(result: dict, job: Job) -> dict:
    """Turn a pipeline result dict into the shape the approval screen wants:
    products sorted by timestamp, each bucketed by the confidence thresholds."""
    products = []
    for i, p in enumerate(sorted(result.get("products", []),
                                 key=lambda x: (x.get("timestamp_s") or 0))):
        conf = float(p.get("confidence") or 0)
        products.append({
            "id": i,
            "product_name": p.get("product_name") or "Unnamed product",
            "brand": p.get("brand") or "",
            "variant_or_shade": p.get("variant_or_shade") or "",
            "evidence_type": p.get("evidence_type") or "",
            "evidence_label": _EVIDENCE_LABEL.get(p.get("evidence_type"), "Listed"),
            "timestamp_s": p.get("timestamp_s") or 0,
            "transcript_quote": p.get("transcript_quote") or "",
            "confidence": round(conf, 3),
            "bucket": _bucket(conf),
        })
    return {
        "video_id": result.get("video_id", job.video_id),
        "title": job.title,
        "youtube_id": job.youtube_id,
        "thumbnail": job.thumbnail,
        "duration_s": result.get("duration_s"),
        "num_products": len(products),
        "thresholds": {
            "auto_approve": cfg.AUTO_APPROVE_THRESHOLD,
            "confirm_floor": cfg.CONFIRM_FLOOR,
        },
        "products": products,
    }


# --------------------------------------------------------------------------
# Running a job
# --------------------------------------------------------------------------
def start_job(job: Job, source_path: Path | None, url: str | None) -> Job:
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    t = threading.Thread(target=_run_job, args=(job, source_path, url), daemon=True)
    t.start()
    return job


def _cached_result_path(video_id: str) -> Path:
    return cfg.OUTPUT_DIR / f"{video_id}.json"


def _run_job(job: Job, source_path: Path | None, url: str | None) -> None:
    try:
        cached = _cached_result_path(job.video_id)
        if cached.exists():
            _serve_cached(job, cached)
            return
        _run_fresh(job, source_path, url)
    except Exception as e:  # never surface a stack trace to the UI
        job.state = "error"
        job.error = str(e)[:300]
        job.emit("error", "We had trouble with this video.", 100)


def _serve_cached(job: Job, cached: Path) -> None:
    """Replay the progress animation over CACHED_RUN_SECONDS, then reveal."""
    job.cached = True
    job.state = "running"
    result = json.loads(cached.read_text())
    per = (cfg.CACHED_RUN_SECONDS / len(CACHED_STAGES)) if cfg.CACHED_RUN_SECONDS else 0
    for stage, label, pct in CACHED_STAGES:
        job.emit(stage, label, pct)
        if per:
            time.sleep(per)
    job.result = normalize_result(result, job)
    job.state = "done"
    job.emit("done", "Here's your routine!", 100)


def _run_fresh(job: Job, source_path: Path | None, url: str | None) -> None:
    import anthropic
    from pipeline import (sanitize_id, download_youtube, ffprobe_duration,
                          transcribe, format_transcript, load_or_extract_frames,
                          detect_mirror, flip_frames, extract_products,
                          get_description, parse_description,
                          merge_video_and_description, _tag_sources,
                          extraction_cost)

    job.state = "running"

    # 1. Obtain a local video file.
    job.emit(*STAGE_DOWNLOAD)
    if source_path is None:
        source_path = download_youtube(url, cfg.VIDEOS_DIR)
        # capture the real title for a nicer header, best-effort
        _save_title(job.video_id, source_path.stem)
    path = Path(source_path)
    video_id = job.video_id
    duration = ffprobe_duration(path)

    client = anthropic.Anthropic()

    # 2. Transcribe (cached on disk by the pipeline).
    job.emit(*STAGE_TRANSCRIBE)
    tx = transcribe(path, video_id, cfg.CACHE_DIR, cfg.USE_WHISPER_API, cfg.WHISPER_MODEL)
    transcript_text = format_transcript(tx["segments"])

    # 3. Keyframes (+ mirror correction), cached on disk by the pipeline.
    job.emit(*STAGE_FRAMES)
    frames = load_or_extract_frames(path, video_id, cfg.CACHE_DIR,
                                    cfg.SCENE_THRESHOLD, cfg.FLOOR_INTERVAL,
                                    cfg.HOLD_FRAMES)
    usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    mirrored = False
    if frames:
        mirror = detect_mirror(client, cfg.MODEL, frames, cfg.CACHE_DIR, video_id)
        for k in usage:
            usage[k] += mirror["usage"][k]
        mirrored = mirror["mirrored"]
        if mirrored:
            frames = flip_frames(frames, cfg.CACHE_DIR, video_id)

    # 4. Extract products (chunked multimodal Claude calls + reconciliation).
    job.emit(*STAGE_EXTRACT)
    products, e_usage = extract_products(client, cfg.MODEL, transcript_text,
                                         frames, reconcile=True)
    for k in usage:
        usage[k] += e_usage[k]

    # 5. Merge in the creator's description list, then assemble + cache result.
    job.emit(*STAGE_ASSEMBLE)
    n_video = len(products)
    n_desc = 0
    if job.source_kind == "youtube":
        desc_text = get_description(video_id, cfg.CACHE_DIR)
        if desc_text.strip():
            desc_products, d_usage = parse_description(client, cfg.MODEL, desc_text)
            n_desc = len(desc_products)
            for k in usage:
                usage[k] += d_usage[k]
            if desc_products:
                video_products = products
                products, m_usage = merge_video_and_description(
                    client, cfg.MODEL, video_products, desc_products)
                for k in usage:
                    usage[k] += m_usage[k]
                products = _tag_sources(products, video_products, desc_products)

    ext_cost = extraction_cost(usage)
    result = {
        "video_id": video_id,
        "source_file": path.name,
        "duration_s": round(duration, 1),
        "num_frames": len(frames),
        "num_products": len(products),
        "num_video_products": n_video,
        "num_description_products": n_desc,
        "mirrored": mirrored,
        "model": cfg.MODEL,
        "usage": usage,
        "cost_usd": {"transcription": 0.0, "extraction": round(ext_cost, 6),
                     "total": round(ext_cost, 6)},
        "products": products,
    }
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _cached_result_path(video_id).write_text(json.dumps(result, indent=2))

    job.result = normalize_result(result, job)
    job.state = "done"
    job.emit("done", "Here's your routine!", 100)
