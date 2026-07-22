"""
Core pipeline: ingest -> transcript -> keyframes -> extraction -> output.

Throwaway validation prototype. Optimized for getting an accuracy number, not
for architecture. Transcripts and frames are cached on disk so re-running
extraction with a tweaked prompt (edit prompts.py) does NOT redo transcription
or frame extraction.
"""

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import anthropic
import numpy as np

from prompts import (SYSTEM_PROMPT, EXTRACTION_SCHEMA, build_extraction_messages,
                     RECONCILE_SYSTEM_PROMPT, build_reconcile_messages,
                     DESCRIPTION_PARSE_SYSTEM_PROMPT, build_description_parse_messages,
                     MERGE_SYSTEM_PROMPT, build_merge_messages,
                     MIRROR_SCHEMA, MIRROR_DETECT_SYSTEM_PROMPT,
                     build_mirror_detect_messages,
                     RECOVER_SCHEMA, RECOVER_SYSTEM_PROMPT, build_recover_messages)

# Parallelism cap for CPU/ffmpeg work. Deliberately NOT os.cpu_count() — in a
# container that reports the host's cores and oversubscribes the worker (which
# made extraction slower). Tune with REELIE_WORKERS when on a bigger CPU plan.
_POOL = max(1, int(os.environ.get("REELIE_WORKERS", "3") or 3))

# --------------------------------------------------------------------------
# Config / pricing
# --------------------------------------------------------------------------
SONNET_INPUT_PER_MTOK = 3.0      # $/1M input tokens (claude-sonnet-4-6)
SONNET_OUTPUT_PER_MTOK = 15.0    # $/1M output tokens
WHISPER_API_PER_MIN = 0.006      # $/min (OpenAI whisper-1)

SCENE_THRESHOLD = 0.3            # ffmpeg scene-change sensitivity (0-1, lower = more frames)
FLOOR_INTERVAL_S = 30            # guaranteed one frame every N seconds
FRAME_LONG_EDGE = 1280           # downscale frames so the long edge <= this (bounds image tokens)
MAX_FRAMES_PER_CALL = 25         # NO cap on total frames; this only splits API calls for long videos
DEDUPE_THRESHOLD = 88            # fuzzy threshold for cross-chunk product dedupe

# ── "Product held to camera" frame selection ───────────────────────────────
# When a creator holds a product up to show it, the frame goes near-static for a
# beat — that stillness is exactly when the label is legible. freezedetect finds
# those holds; we then pick the SHARPEST instant in each so brand text is readable.
# This lifts brand recall on silent/text-free videos, where the base scene+floor
# sampler mostly lands on mid-motion (blurry) frames.
HOLD_FRAMES = True               # add stillness-based "held product" keyframes
FREEZE_NOISE = "-30dB"           # freezedetect noise tolerance (more negative = stricter)
FREEZE_MIN_DUR = 0.25            # min still duration (s) to count as a hold
HOLD_MERGE_GAP = 0.20            # merge freeze segments closer than this (s) into one hold
HOLD_MAX = 14                    # cap hold frames per video (bounds token cost on long videos)
HOLD_SHARPEST_OF = 3             # sample this many instants per hold; keep the sharpest
SHARP_SIZE = 256                 # grayscale square edge for the Laplacian focus measure

# ── Brand recovery (last-resort identification of brand-null shown products) ──
RECOVER_MAX = 12                 # cap recovery attempts per video (bounds cost)
RECOVER_MIN_CONF = 0.7           # only accept an identification at/above this confidence
RECOVER_NEAR_FRAMES = 3          # send this many nearest frames to the recovery call

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}

_WHISPER_MODEL = None  # lazily-loaded faster-whisper model, reused across videos


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def sanitize_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("_")


def _run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ffprobe_duration(path: Path) -> float:
    cp = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    try:
        return float(cp.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


# --------------------------------------------------------------------------
# ingest
# --------------------------------------------------------------------------
def discover_local_videos(videos_dir: Path) -> list:
    return sorted(p for p in videos_dir.iterdir()
                  if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


def download_youtube(url: str, videos_dir: Path) -> Path:
    """Download a YouTube URL via yt-dlp. Returns the local path."""
    import yt_dlp
    videos_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "mp4/bestvideo+bestaudio/best",
        "outtmpl": str(videos_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info))


# --------------------------------------------------------------------------
# transcription (cached)
# --------------------------------------------------------------------------
def _get_whisper(size: str):
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        # NB: os.cpu_count() lies in containers (reports host cores, not the cgroup
        # CPU limit) — using it oversubscribed the worker and made things SLOWER.
        # Use a modest, env-tunable thread count instead.
        _WHISPER_MODEL = WhisperModel(size, device="auto", compute_type="int8",
                                      cpu_threads=_POOL)
    return _WHISPER_MODEL


def _extract_audio(path: Path, out: Path) -> Path:
    _run(["ffmpeg", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", str(out)])
    return out


def transcribe(path: Path, video_id: str, cache_dir: Path,
               use_api: bool, whisper_size: str) -> dict:
    cache = cache_dir / video_id / "transcript.json"
    if cache.exists():
        return json.loads(cache.read_text())

    cache.parent.mkdir(parents=True, exist_ok=True)

    if use_api:
        from openai import OpenAI
        audio = _extract_audio(path, cache.parent / "audio.wav")
        oc = OpenAI()
        with open(audio, "rb") as f:
            tr = oc.audio.transcriptions.create(
                model="whisper-1", file=f, response_format="verbose_json",
            )
        segs = [{"start": s.start, "end": s.end, "text": s.text.strip()}
                for s in tr.segments]
        audio.unlink(missing_ok=True)
    else:
        model = _get_whisper(whisper_size)
        # We only use segment-level start/end below, so skip per-word alignment
        # (word_timestamps was ~20-30% wasted work). vad_filter skips silence —
        # faster and reduces hallucinated text over quiet stretches.
        segments, _ = model.transcribe(str(path), vad_filter=True)
        segs = [{"start": s.start, "end": s.end, "text": s.text.strip()}
                for s in segments]

    data = {"segments": segs, "text": " ".join(s["text"] for s in segs)}
    cache.write_text(json.dumps(data, indent=2))
    return data


def format_transcript(segments: list) -> str:
    if not segments:
        return "(no speech detected)"
    return "\n".join(f"[{s['start']:.1f}s] {s['text']}" for s in segments)


# --------------------------------------------------------------------------
# keyframes (cached)
# --------------------------------------------------------------------------
def _scene_timestamps(path: Path, scene_threshold: float) -> list:
    cp = _run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-filter:v", f"select='gt(scene,{scene_threshold})',showinfo",
        "-f", "null", "-",
    ])
    return [float(m) for m in re.findall(r"pts_time:(\d+\.?\d*)", cp.stderr)]


def _freeze_segments(path: Path, noise: str, min_dur: float) -> list:
    """Still segments [(start_s, end_s)] via ffmpeg freezedetect — the moments a
    creator holds something still (typically a product shown to camera)."""
    cp = _run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"freezedetect=n={noise}:d={min_dur},metadata=mode=print:file=-",
        "-an", "-f", "null", "-",
    ])
    blob = (cp.stdout or "") + (cp.stderr or "")
    starts, ends = [], []
    for m in re.finditer(r"freeze_(start|end)=(\d+\.?\d*)", blob):
        (starts if m.group(1) == "start" else ends).append(float(m.group(2)))
    return list(zip(starts, ends))  # freezedetect emits strictly alternating start/end


def _merge_segments(segs: list, gap: float) -> list:
    """Merge freeze segments separated by < gap seconds into continuous holds."""
    merged = []
    for s, e in sorted(segs):
        if merged and s - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _sharpness_at(path: Path, ts: float, size: int = SHARP_SIZE) -> float:
    """Focus measure (variance of the Laplacian) of one grayscale frame at `ts`.
    Higher = sharper / more in-focus. ffmpeg -> raw gray bytes -> numpy; no image
    libs needed. Returns 0.0 if the frame can't be read."""
    cp = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{ts}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale={size}:{size},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True,
    )
    buf = cp.stdout
    if len(buf) < size * size:
        return 0.0
    a = np.frombuffer(buf[:size * size], dtype=np.uint8).astype(np.float32).reshape(size, size)
    lap = (4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1]
           - a[1:-1, :-2] - a[1:-1, 2:])
    return float(lap.var())


def _sharpest_ts(path: Path, start: float, end: float, n: int = HOLD_SHARPEST_OF) -> float:
    """Timestamp of the sharpest frame sampled across a hold window [start, end]."""
    if end <= start or n <= 1:
        return (start + end) / 2
    cands = [start + (end - start) * i / (n - 1) for i in range(n)]
    return max(cands, key=lambda t: _sharpness_at(path, t))


def _hold_timestamps(path: Path, noise: str, min_dur: float) -> list:
    """Sharpest instant of each distinct 'held product' still-window, capped to
    HOLD_MAX (longest holds first — a longer hold = a more deliberate product show).
    Sharpness probes (one ffmpeg each) run in parallel — independent, GIL-released."""
    from concurrent.futures import ThreadPoolExecutor
    holds = _merge_segments(_freeze_segments(path, noise, min_dur), HOLD_MERGE_GAP)
    holds.sort(key=lambda se: se[1] - se[0], reverse=True)
    holds = holds[:HOLD_MAX]
    # Build every (hold, candidate-timestamp) probe, measure all in parallel.
    cand = []
    for hi, (s, e) in enumerate(holds):
        if e <= s or HOLD_SHARPEST_OF <= 1:
            cand.append((hi, (s + e) / 2))
        else:
            for i in range(HOLD_SHARPEST_OF):
                cand.append((hi, s + (e - s) * i / (HOLD_SHARPEST_OF - 1)))
    if not cand:
        return []
    with ThreadPoolExecutor(max_workers=min(_POOL, len(cand))) as ex:
        sharp = list(ex.map(lambda c: _sharpness_at(path, c[1]), cand))
    best: dict[int, tuple[float, float]] = {}
    for (hi, ts), sh in zip(cand, sharp):
        if hi not in best or sh > best[hi][1]:
            best[hi] = (ts, sh)
    return sorted(round(best[hi][0], 2) for hi in best)


# Priority governs which frame survives when two land within 1s of each other:
# a legible "hold" frame must win over a scene-cut or floor frame.
_KIND = {2: "hold", 1: "scene", 0: "floor"}


def _frame_timestamps(path: Path, scene_threshold: float, floor_interval: int,
                      hold: bool = HOLD_FRAMES, freeze_noise: str = FREEZE_NOISE,
                      freeze_min_dur: float = FREEZE_MIN_DUR) -> list:
    """Returns [(timestamp_s, kind)] where kind ∈ {hold, scene, floor}."""
    duration = ffprobe_duration(path)
    scene = _scene_timestamps(path, scene_threshold)
    floor = [min(1.0, duration / 2)] + list(
        range(floor_interval, int(duration) + 1, floor_interval)
    )
    holds = _hold_timestamps(path, freeze_noise, freeze_min_dur) if hold else []

    tagged = ([(t, 2) for t in holds] + [(t, 1) for t in scene]
              + [(t, 0) for t in floor])
    tagged = [(float(t), p) for t, p in tagged if 0 <= t <= max(duration, 1)]
    # Sort by time, higher priority first on ties, then dedupe within 1s keeping
    # the highest-priority frame in each cluster.
    tagged.sort(key=lambda tp: (tp[0], -tp[1]))
    out = []  # [(ts, priority)]
    for t, p in tagged:
        if out and t - out[-1][0] <= 1.0:
            if p > out[-1][1]:
                out[-1] = (round(t, 2), p)
            continue
        out.append((round(t, 2), p))
    return [(t, _KIND[p]) for t, p in out]


def load_or_extract_frames(path: Path, video_id: str, cache_dir: Path,
                           scene_threshold: float = SCENE_THRESHOLD,
                           floor_interval: int = FLOOR_INTERVAL_S,
                           hold: bool = HOLD_FRAMES) -> list:
    """Returns [{'timestamp_s': float, 'path': str, 'kind': str}] with disk caching.
    Cache dir is keyed by the selection settings so different settings coexist."""
    fdir = cache_dir / video_id / f"frames_s{scene_threshold}_f{floor_interval}_h{int(hold)}"
    manifest = fdir / "frames.json"
    if manifest.exists():
        return json.loads(manifest.read_text())

    fdir.mkdir(parents=True, exist_ok=True)
    timestamps = _frame_timestamps(path, scene_threshold, floor_interval, hold)
    scale = (f"scale='if(gt(iw,ih),min(iw,{FRAME_LONG_EDGE}),-2)'"
             f":'if(gt(iw,ih),-2,min(ih,{FRAME_LONG_EDGE}))'")

    # Each frame is an independent ffmpeg seek+decode — extract them in parallel
    # (subprocess releases the GIL) instead of one process spawn at a time.
    def _one(job):
        i, ts, kind = job
        fp = fdir / f"frame_{i:03d}_{ts:.1f}s_{kind}.jpg"
        _run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(path),
              "-frames:v", "1", "-vf", scale, "-q:v", "3", str(fp)])
        if fp.exists() and fp.stat().st_size > 0:
            return {"timestamp_s": ts, "path": str(fp), "kind": kind}
        return None

    from concurrent.futures import ThreadPoolExecutor
    jobs = [(i, ts, kind) for i, (ts, kind) in enumerate(timestamps)]
    with ThreadPoolExecutor(max_workers=min(_POOL, len(jobs) or 1)) as ex:
        results = list(ex.map(_one, jobs))     # ex.map preserves input (timestamp) order
    frames = [r for r in results if r]

    manifest.write_text(json.dumps(frames, indent=2))
    return frames


def _encode_frame(fp: str) -> dict:
    data = base64.standard_b64encode(Path(fp).read_bytes()).decode("utf-8")
    return {"media_type": "image/jpeg", "data": data}


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------
def _chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def reconcile_products(client: anthropic.Anthropic, model: str,
                       products: list) -> tuple:
    """Final LLM pass: merge ASR-variant duplicates, fix misheard brands, drop
    noise. Returns (cleaned products, usage dict)."""
    usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    if len(products) < 2:
        return products, usage
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=RECONCILE_SYSTEM_PROMPT,
        messages=build_reconcile_messages(products),
        output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
    )
    usage = {"input_tokens": resp.usage.input_tokens,
             "output_tokens": resp.usage.output_tokens, "api_calls": 1}
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    out = json.loads(text).get("products", [])
    for p in out:
        p["confidence"] = max(0.0, min(1.0, float(p.get("confidence", 0))))
    return out, usage


def extract_products(client: anthropic.Anthropic, model: str,
                     transcript_text: str, frames: list,
                     reconcile: bool = True) -> tuple:
    """Returns (products list, usage dict). Chunks frames across API calls,
    then optionally runs a final LLM reconciliation pass."""
    all_products = []
    usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

    frame_chunks = list(_chunk(frames, MAX_FRAMES_PER_CALL)) or [[]]
    multi = len(frame_chunks) > 1

    for ci, chunk in enumerate(frame_chunks):
        payload = [{
            "timestamp_s": fr["timestamp_s"],
            **_encode_frame(fr["path"]),
        } for fr in chunk]

        note = None
        if multi and chunk:
            note = (f"This is part {ci + 1} of {len(frame_chunks)}; the frames "
                    f"below cover roughly {chunk[0]['timestamp_s']:.0f}s to "
                    f"{chunk[-1]['timestamp_s']:.0f}s of the video.")

        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=build_extraction_messages(transcript_text, payload, note),
            output_config={"format": {"type": "json_schema",
                                      "schema": EXTRACTION_SCHEMA}},
        )
        usage["input_tokens"] += resp.usage.input_tokens
        usage["output_tokens"] += resp.usage.output_tokens
        usage["api_calls"] += 1

        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        parsed = json.loads(text)
        for p in parsed.get("products", []):
            p["confidence"] = max(0.0, min(1.0, float(p.get("confidence", 0))))
            all_products.append(p)

    products = dedupe_products(all_products)
    if reconcile and len(products) > 1:
        products, r_usage = reconcile_products(client, model, products)
        for k in usage:
            usage[k] += r_usage[k]
    return products, usage


def dedupe_products(products: list) -> list:
    """Merge duplicates of the same product across chunks."""
    from rapidfuzz import fuzz

    def key(p):
        return f"{(p.get('brand') or '').lower()} {(p.get('product_name') or '').lower()}".strip()

    kept = []
    for p in products:
        k = key(p)
        match = None
        for q in kept:
            if fuzz.token_sort_ratio(k, key(q)) >= DEDUPE_THRESHOLD:
                match = q
                break
        if match is None:
            kept.append(p)
            continue
        # merge into existing: earliest timestamp, richest evidence, max confidence
        if p["timestamp_s"] < match["timestamp_s"]:
            match["timestamp_s"] = p["timestamp_s"]
        if p.get("evidence_type") != match.get("evidence_type"):
            match["evidence_type"] = "both"
        for fld in ("variant_or_shade", "transcript_quote", "brand"):
            if not match.get(fld) and p.get(fld):
                match[fld] = p[fld]
        match["confidence"] = max(match["confidence"], p["confidence"])
    return kept


# --------------------------------------------------------------------------
# mirror detection + correction (selfie-camera videos film text backwards)
# --------------------------------------------------------------------------
def detect_mirror(client, model, frames, cache_dir, video_id):
    """Ask the model whether the video is horizontally mirrored (packaging text
    reversed). Cached. Returns {'mirrored': bool, 'reason': str, 'usage': {...}}."""
    cache = cache_dir / video_id / "mirror.json"
    if cache.exists():
        r = json.loads(cache.read_text())
        r.setdefault("usage", {"input_tokens": 0, "output_tokens": 0, "api_calls": 0})
        return r

    # Held-product frames are where physical packaging text is most likely; fall
    # back to an even spread. Cap at 4 to keep the check cheap.
    holds = [f for f in frames if f.get("kind") == "hold"]
    pool = holds or frames
    pick = pool[:4] if len(pool) <= 4 else [pool[i] for i in
            (0, len(pool) // 3, 2 * len(pool) // 3, len(pool) - 1)]
    payload = [{"timestamp_s": f["timestamp_s"], **_encode_frame(f["path"])} for f in pick]

    resp = client.messages.create(
        model=model, max_tokens=500,
        system=MIRROR_DETECT_SYSTEM_PROMPT,
        messages=build_mirror_detect_messages(payload),
        output_config={"format": {"type": "json_schema", "schema": MIRROR_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = json.loads(text)
    result = {
        "mirrored": bool(data.get("mirrored", False)),
        "reason": data.get("reason", ""),
        "usage": {"input_tokens": resp.usage.input_tokens,
                  "output_tokens": resp.usage.output_tokens, "api_calls": 1},
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result


def flip_frames(frames, cache_dir, video_id):
    """Create horizontally-flipped copies and return frames pointing at them."""
    out = []
    for f in frames:
        src = Path(f["path"])
        dst = src.with_name(src.stem + "_flip" + src.suffix)
        if not dst.exists() or dst.stat().st_size == 0:
            _run(["ffmpeg", "-y", "-i", str(src), "-vf", "hflip", str(dst)])
        out.append({**f, "path": str(dst)})
    return out


# --------------------------------------------------------------------------
# brand recovery (identify brand-null shown products via Claude's knowledge)
# --------------------------------------------------------------------------
def recover_brands(client, model, products, frames):
    """For each brand-null product that was SEEN in the video, ask Claude to
    identify the specific product from the nearest frames. Returns (products, usage)."""
    usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    if not frames:
        return products, usage

    targets = [p for p in products
               if not p.get("brand")
               and p.get("evidence_type") in ("shown", "both", "on-screen-text")]
    for p in targets[:RECOVER_MAX]:
        near = sorted(frames, key=lambda f: abs(f["timestamp_s"] - p.get("timestamp_s", 0)))
        near = near[:RECOVER_NEAR_FRAMES]
        payload = [{"timestamp_s": f["timestamp_s"], **_encode_frame(f["path"])}
                   for f in near]
        resp = client.messages.create(
            model=model, max_tokens=600,
            system=RECOVER_SYSTEM_PROMPT,
            messages=build_recover_messages(p, payload),
            output_config={"format": {"type": "json_schema", "schema": RECOVER_SCHEMA}},
        )
        usage["input_tokens"] += resp.usage.input_tokens
        usage["output_tokens"] += resp.usage.output_tokens
        usage["api_calls"] += 1
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        data = json.loads(text)
        conf = max(0.0, min(1.0, float(data.get("confidence", 0))))
        if data.get("identified") and data.get("brand") and conf >= RECOVER_MIN_CONF:
            p["brand"] = data["brand"]
            if data.get("product_name"):
                p["product_name"] = data["product_name"]
            if data.get("variant_or_shade") and not p.get("variant_or_shade"):
                p["variant_or_shade"] = data["variant_or_shade"]
            p["confidence"] = max(p.get("confidence", 0), conf)
            p["recovered"] = True
    return products, usage


# --------------------------------------------------------------------------
# description merge (video products  ∪  creator's description list)
# --------------------------------------------------------------------------
def get_description(video_id: str, cache_dir: Path) -> str:
    """Fetch the YouTube description for a video id (cached). Empty string for
    non-YouTube / no-description videos."""
    cache = cache_dir / video_id / "description.txt"
    if cache.exists():
        return cache.read_text()
    desc = ""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                               "skip_download": True}) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}",
                                    download=False)
        desc = info.get("description") or ""
    except Exception:
        desc = ""
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(desc)
    return desc


def _structured_call(client, model, system, messages):
    resp = client.messages.create(
        model=model, max_tokens=4096, system=system, messages=messages,
        output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
    )
    usage = {"input_tokens": resp.usage.input_tokens,
             "output_tokens": resp.usage.output_tokens, "api_calls": 1}
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    out = json.loads(text).get("products", [])
    for p in out:
        p["confidence"] = max(0.0, min(1.0, float(p.get("confidence", 0))))
    return out, usage


def parse_description(client, model, description_text):
    """Parse the creator's description into products. Returns (products, usage)."""
    if not description_text.strip():
        return [], {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    return _structured_call(client, model, DESCRIPTION_PARSE_SYSTEM_PROMPT,
                            build_description_parse_messages(description_text))


def merge_video_and_description(client, model, video_products, desc_products):
    """Combine video + description into one comprehensive list. (products, usage)."""
    if not desc_products:
        return video_products, {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    return _structured_call(client, model, MERGE_SYSTEM_PROMPT,
                            build_merge_messages(video_products, desc_products))


def _tag_sources(merged, video_products, desc_products):
    """Best-effort label of where each merged product came from: video/description/both."""
    from rapidfuzz import fuzz
    vnames = [(p.get("product_name") or "").lower() for p in video_products]
    dkeys = [f"{(p.get('brand') or '')} {p.get('product_name') or ''}".lower().strip()
             for p in desc_products]
    for p in merged:
        name = (p.get("product_name") or "").lower()
        key = f"{(p.get('brand') or '')} {p.get('product_name') or ''}".lower().strip()
        in_v = any(fuzz.token_set_ratio(name, vn) >= 80 for vn in vnames)
        in_d = any(fuzz.token_set_ratio(key, dk) >= 80 for dk in dkeys)
        p["source"] = "both" if (in_v and in_d) else ("video" if in_v else
                       "description" if in_d else "merged")
    return merged


# --------------------------------------------------------------------------
# cost
# --------------------------------------------------------------------------
def extraction_cost(usage: dict) -> float:
    return (usage["input_tokens"] / 1e6 * SONNET_INPUT_PER_MTOK
            + usage["output_tokens"] / 1e6 * SONNET_OUTPUT_PER_MTOK)


# --------------------------------------------------------------------------
# per-video orchestration
# --------------------------------------------------------------------------
def process_video(path: Path, client: anthropic.Anthropic, model: str,
                  cache_dir: Path, out_dir: Path, use_api: bool,
                  whisper_size: str, reconcile: bool = True,
                  scene_threshold: float = SCENE_THRESHOLD,
                  floor_interval: int = FLOOR_INTERVAL_S,
                  hold: bool = HOLD_FRAMES,
                  use_description: bool = True,
                  auto_mirror: bool = True,
                  recover_brands_flag: bool = False,  # OFF: hallucinates brands
                  title: str = "") -> dict:
    video_id = sanitize_id(path.stem)
    print(f"\n=== {video_id} ({path.name}) ===")

    duration = ffprobe_duration(path)
    print(f"  duration: {duration:.0f}s")

    # Transcription (CPU) and keyframe extraction (ffmpeg) are independent — run
    # them concurrently so wall-clock is the slower of the two, not the sum.
    import time as _time
    from concurrent.futures import ThreadPoolExecutor as _TPE
    print("  transcribing + keyframes (parallel)...")
    def _do_tx():
        _s = _time.time(); r = transcribe(path, video_id, cache_dir, use_api, whisper_size)
        return r, _time.time() - _s
    def _do_fr():
        _s = _time.time(); r = load_or_extract_frames(path, video_id, cache_dir,
                                                      scene_threshold, floor_interval, hold)
        return r, _time.time() - _s
    with _TPE(max_workers=2) as _ex:
        _ftx = _ex.submit(_do_tx); _ffr = _ex.submit(_do_fr)
        tx, _tx_s = _ftx.result()
        frames, _fr_s = _ffr.result()
    transcript_text = format_transcript(tx["segments"])
    n_hold = sum(1 for f in frames if f.get("kind") == "hold")
    print(f"  ⏱ transcript: {_tx_s:.1f}s | frames: {_fr_s:.1f}s (parallel wall {max(_tx_s, _fr_s):.1f}s) · "
          f"{len(frames)} frames" + (f" ({n_hold} held-product)" if hold else ""))

    # Launch the caption/description parse NOW, in parallel with the frame-based
    # extraction below — it only needs the description text, not the video, so it
    # overlaps a full Claude round-trip instead of adding one at the end.
    _desc_future = _desc_ex = None
    _desc_text = get_description(video_id, cache_dir) if use_description else ""
    _t_desc = _time.time()
    if _desc_text.strip():
        _desc_ex = _TPE(max_workers=1)
        _desc_future = _desc_ex.submit(parse_description, client, model, _desc_text)

    # Un-mirror selfie-camera videos so reversed packaging text is legible.
    mirror = {"mirrored": False, "usage": {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}}
    if auto_mirror and frames:
        _t = _time.time()
        mirror = detect_mirror(client, model, frames, cache_dir, video_id)
        print(f"  ⏱ mirror-detect (Claude): {_time.time()-_t:.1f}s")
        if mirror["mirrored"]:
            frames = flip_frames(frames, cache_dir, video_id)
            print(f"  ⤿ mirrored video detected — un-mirroring frames "
                  f"({mirror.get('reason','')[:70]})")

    print("  calling Claude..." + ("  (+ reconciliation pass)" if reconcile else ""))
    _t = _time.time()
    products, usage = extract_products(client, model, transcript_text, frames, reconcile)
    print(f"  ⏱ extract-products (Claude{'x2' if reconcile else ''}): {_time.time()-_t:.1f}s")
    for k in usage:
        usage[k] += mirror["usage"][k]

    # Last-resort brand recovery: identify brand-null SHOWN products from their
    # packaging via Claude's product knowledge.
    if recover_brands_flag:
        products, rec_usage = recover_brands(client, model, products, frames)
        for k in usage:
            usage[k] += rec_usage[k]
        n_rec = sum(1 for p in products if p.get("recovered"))
        if n_rec:
            print(f"  recovered {n_rec} brand(s) via product knowledge")

    # Combine with the creator's description list (union) for the most complete
    # result: the description's brands fill in the video's brand-null generics.
    # (parse_description was launched in parallel above — just join it here.)
    n_video, n_desc = len(products), 0
    if _desc_future is not None:
        desc_products, d_usage = _desc_future.result()
        _desc_ex.shutdown()
        print(f"  ⏱ parse-description (Claude, ran in parallel): {_time.time()-_t_desc:.1f}s")
        n_desc = len(desc_products)
        for k in usage:
            usage[k] += d_usage[k]
        if desc_products:
            video_products = products
            products, m_usage = merge_video_and_description(
                client, model, video_products, desc_products)
            for k in usage:
                usage[k] += m_usage[k]
            products = _tag_sources(products, video_products, desc_products)
            print(f"  description: {n_desc} products  ->  merged comprehensive: "
                  f"{len(products)}  (video alone: {n_video})")

    ext_cost = extraction_cost(usage)
    tx_cost = (duration / 60 * WHISPER_API_PER_MIN) if use_api else 0.0
    total_cost = ext_cost + tx_cost

    result = {
        "video_id": video_id,
        "video_title": title,
        "source_file": path.name,
        "duration_s": round(duration, 1),
        "num_frames": len(frames),
        "num_products": len(products),
        "num_video_products": n_video,
        "num_description_products": n_desc,
        "mirrored": mirror["mirrored"],
        "model": model,
        "usage": usage,
        "cost_usd": {
            "transcription": round(tx_cost, 6),
            "extraction": round(ext_cost, 6),
            "total": round(total_cost, 6),
        },
        "products": products,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{video_id}.json").write_text(json.dumps(result, indent=2))

    print(f"  products: {len(products)}  |  tokens: "
          f"{usage['input_tokens']} in / {usage['output_tokens']} out "
          f"({usage['api_calls']} call(s))")
    print(f"  cost: extraction ${ext_cost:.4f}"
          + (f" + transcription ${tx_cost:.4f}" if use_api else "")
          + f"  =  ${total_cost:.4f}")
    return result


CSV_COLS = ["video_id", "product_name", "brand", "variant_or_shade",
           "evidence_type", "source", "timestamp_s", "transcript_quote", "confidence"]


def _product_rows(result: dict) -> list:
    return [{
        "video_id": result["video_id"],
        "product_name": p.get("product_name", ""),
        "brand": p.get("brand") or "",
        "variant_or_shade": p.get("variant_or_shade") or "",
        "evidence_type": p.get("evidence_type", ""),
        "source": p.get("source", "video"),
        "timestamp_s": p.get("timestamp_s", ""),
        "transcript_quote": p.get("transcript_quote") or "",
        "confidence": p.get("confidence", ""),
    } for p in result["products"]]


def write_video_csv(result: dict, out_dir: Path) -> int:
    """Write one standalone CSV per video: output/{video_id}.csv."""
    import csv
    rows = _product_rows(result)
    with open(out_dir / f"{result['video_id']}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)
