"""
Per-step video clips for the routine guide.

For each product we cut a short clip from the source video around the moment that
product appears, so the public page can show the actual footage next to the
narration. Rendered with **PyAV** (bundled ffmpeg libraries) so no system ffmpeg
binary is required. If the source video isn't available, clip generation is
skipped and the page falls back to emoji tiles — nothing else changes.

The pipeline flags some videos as horizontally mirrored (cache/<id>/mirror.json);
when so, clips are un-flipped so on-product text reads correctly.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import config


# --------------------------------------------------------------------------
# source + mirror resolution
# --------------------------------------------------------------------------
def resolve_source(video_id: str) -> Path | None:
    candidates = [
        config.VIDEO_LLM_VIDEOS / f"{video_id}.mp4",
        config.VIDEO_LLM_VIDEOS / "_processed" / f"{video_id}.mp4",
    ]
    for c in candidates:
        if c.exists():
            return c
    for d in (config.VIDEO_LLM_VIDEOS, config.VIDEO_LLM_VIDEOS / "_processed"):
        if d.exists():
            for ext in ("mp4", "mov", "mkv", "webm", "m4v"):
                hits = list(d.glob(f"{video_id}.{ext}"))
                if hits:
                    return hits[0]
    return None


def is_mirrored(video_id: str) -> bool:
    f = config.VIDEO_LLM_CACHE / video_id / "mirror.json"
    if not f.exists():
        return False
    try:
        return bool(json.loads(f.read_text()).get("mirrored"))
    except Exception:
        return False


# --------------------------------------------------------------------------
# window planning — one [start, end] per product, matched to the guide step
# --------------------------------------------------------------------------
def plan_windows(products, duration: float) -> dict[str, tuple[float, float]]:
    times = sorted({round(p.timestamp_s, 2) for p in products})
    dur = duration or (max(times) + config.CLIP_MAX_S if times else config.CLIP_MAX_S)
    wins: dict[str, tuple[float, float]] = {}
    for p in products:
        start = max(0.0, p.timestamp_s - config.CLIP_LEAD_S)
        nxt = next((t for t in times if t > p.timestamp_s + 0.05), None)
        end = nxt if nxt is not None else dur
        end = min(end, start + config.CLIP_MAX_S, dur)
        if end - start < config.CLIP_MIN_S:            # widen shorts, prefer trailing room
            end = min(dur, start + config.CLIP_MIN_S)
            start = max(0.0, end - config.CLIP_MIN_S)
        wins[p.id] = (round(start, 2), round(end, 2))
    return wins


# --------------------------------------------------------------------------
# rendering (PyAV)
# --------------------------------------------------------------------------
def _even(n: int) -> int:
    return n - (n % 2)


def _target_size(src_w: int, src_h: int) -> tuple[int, int]:
    w = min(config.CLIP_WIDTH, src_w)
    h = int(round(w * src_h / src_w))
    return _even(w), _even(h)


def _write_clip(src: Path, start: float, end: float, out_mp4: Path,
                out_poster: Path, mirror: bool) -> bool:
    import av  # bundled ffmpeg; lazy so --mock has no hard dep

    with av.open(str(src)) as ic:
        vstream = ic.streams.video[0]
        astream = ic.streams.audio[0] if ic.streams.audio else None
        src_w, src_h = vstream.codec_context.width, vstream.codec_context.height
        W, H = _target_size(src_w, src_h)
        fps = vstream.average_rate or Fraction(30, 1)
        rate = max(1, round(float(fps)))

        # seek a little before `start`, then decode forward to it
        if vstream.time_base:
            ic.seek(int(max(0.0, start - 0.5) / vstream.time_base),
                    backward=True, stream=vstream)

        oc = av.open(str(out_mp4), "w", options={"movflags": "+faststart"})
        ostream = oc.add_stream("libx264", rate=rate)
        ostream.width, ostream.height = W, H
        ostream.pix_fmt = "yuv420p"
        ostream.options = {"crf": "30", "preset": "veryfast"}

        # keep the clip's audio so viewers can unmute (clips start muted)
        a_rate = 48000
        aout = resampler = None
        if astream is not None:
            a_rate = astream.rate or 48000
            aout = oc.add_stream("aac", rate=a_rate)
            resampler = av.audio.resampler.AudioResampler(
                format="fltp", layout="stereo", rate=a_rate)

        decode_streams = [s for s in (vstream, astream) if s is not None]
        n = 0                     # video frame counter
        a_samples = 0             # cumulative audio samples (for pts)
        poster_done = False
        v_done = a_done = astream is None
        for frame in ic.decode(*decode_streams):
            t = float(frame.time) if frame.time is not None else 0.0
            if isinstance(frame, av.VideoFrame):
                if t < start:
                    continue
                if t > end:
                    v_done = True
                    if a_done:
                        break
                    continue
                arr = frame.to_ndarray(format="rgb24")
                if mirror:
                    arr = arr[:, ::-1, :].copy()
                vf = av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(
                    width=W, height=H, format="yuv420p")
                vf.pts, vf.time_base = n, Fraction(1, rate)
                n += 1
                for pkt in ostream.encode(vf):
                    oc.mux(pkt)
                if not poster_done:
                    _write_poster(arr, W, H, out_poster)
                    poster_done = True
            else:  # AudioFrame
                if aout is None or t < start:
                    continue
                if t > end:
                    a_done = True
                    if v_done:
                        break
                    continue
                for af in resampler.resample(frame):
                    af.pts, af.time_base = a_samples, Fraction(1, a_rate)
                    a_samples += af.samples
                    for pkt in aout.encode(af):
                        oc.mux(pkt)

        for pkt in ostream.encode():          # flush video
            oc.mux(pkt)
        if aout is not None:                  # flush audio
            for af in resampler.resample(None) or []:
                af.pts, af.time_base = a_samples, Fraction(1, a_rate)
                a_samples += af.samples
                for pkt in aout.encode(af):
                    oc.mux(pkt)
            for pkt in aout.encode():
                oc.mux(pkt)
        oc.close()
        return n > 0


def _write_poster(rgb_arr, W: int, H: int, out_poster: Path) -> None:
    """Single-frame JPEG via PyAV (no Pillow dependency)."""
    import av
    pf = av.VideoFrame.from_ndarray(rgb_arr, format="rgb24").reformat(
        width=W, height=H, format="yuvj420p")
    pc = av.open(str(out_poster), "w")
    ps = pc.add_stream("mjpeg", rate=1)
    ps.width, ps.height, ps.pix_fmt = W, H, "yuvj420p"
    for pkt in ps.encode(pf):
        pc.mux(pkt)
    for pkt in ps.encode():
        pc.mux(pkt)
    pc.close()


# --------------------------------------------------------------------------
# public entry
# --------------------------------------------------------------------------
def make_step_clips(video_id: str, products, duration: float,
                    page_dir: Path) -> int:
    """Cut one clip per product into `page_dir/clips/`, dedup'd by window, and set
    each product's `.clip` / `.clip_poster` (paths relative to the page).
    Returns the number of clip files written. 0 if source/PyAV unavailable."""
    src = resolve_source(video_id)
    if not src:
        return 0
    try:
        import av  # noqa: F401
    except Exception:
        return 0

    mirror = is_mirrored(video_id)
    windows = plan_windows(products, duration)
    clips_dir = page_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # dedupe identical windows -> one file (deterministic stem by first appearance),
    # then cut the unique windows in parallel — each _write_clip opens its own PyAV
    # container (independent) and releases the GIL during encode.
    from concurrent.futures import ThreadPoolExecutor
    stem_of: dict[tuple[float, float], str] = {}
    for p in sorted(products, key=lambda x: x.position):
        win = windows[p.id]
        if win not in stem_of:
            stem_of[win] = f"{len(stem_of) + 1:02d}"

    def _cut(win):
        stem = stem_of[win]
        ok = _write_clip(src, win[0], win[1],
                         clips_dir / f"{stem}.mp4", clips_dir / f"{stem}.jpg", mirror)
        return win, ok

    # Cap concurrency modestly — NOT os.cpu_count() (lies in containers). Tunable
    # via REELIE_WORKERS to match the worker's real CPU plan.
    import os as _os
    _pool = max(1, int(_os.environ.get("REELIE_WORKERS", "3") or 3))
    ok_windows = {}
    if stem_of:
        with ThreadPoolExecutor(max_workers=min(_pool, len(stem_of))) as ex:
            for win, ok in ex.map(_cut, list(stem_of)):
                ok_windows[win] = ok

    written = sum(1 for ok in ok_windows.values() if ok)
    for p in sorted(products, key=lambda x: x.position):
        win = windows[p.id]
        if ok_windows.get(win):
            p.clip = f"clips/{stem_of[win]}.mp4"
            p.clip_poster = f"clips/{stem_of[win]}.jpg"
    return written
