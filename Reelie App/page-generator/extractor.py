"""
Adapter over the video-llm pipeline. Two entry points:

  load_extraction(video_id)  — read an already-produced output/{id}.json (+ cached
                               transcript/description). Primary path: no ffmpeg,
                               no video file, no re-extraction needed.
  run_extraction(video_path) — full extraction via ../../video-llm/pipeline
                               (needs ffmpeg + ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import config


class Extraction:
    """Normalised view of one video's extraction, whatever the source."""

    def __init__(self, video_id: str, products: list, transcript_text: str = "",
                 description: str = "", duration_s: float = 0.0,
                 title: str = "", source_file: str = ""):
        self.video_id = video_id
        self.products = products
        self.transcript_text = transcript_text
        self.description = description
        self.duration_s = duration_s
        self.title = title
        self.source_file = source_file


def _read_transcript(video_id: str) -> str:
    cache = config.VIDEO_LLM_CACHE / video_id / "transcript.json"
    if not cache.exists():
        return ""
    data = json.loads(cache.read_text())
    segs = data.get("segments", [])
    return "\n".join(f"[{s['start']:.1f}s] {s['text']}" for s in segs) or data.get("text", "")


def _read_description(video_id: str) -> str:
    cache = config.VIDEO_LLM_CACHE / video_id / "description.txt"
    return cache.read_text() if cache.exists() else ""


def load_extraction(source: str) -> Extraction:
    """`source` may be a video_id or a path to an output JSON."""
    path = Path(source)
    if not path.exists():
        path = config.VIDEO_LLM_OUTPUT / f"{source}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No extraction found for '{source}'. Expected a video id in "
            f"{config.VIDEO_LLM_OUTPUT} or a path to an output JSON."
        )
    data = json.loads(path.read_text())
    video_id = data.get("video_id", path.stem)
    return Extraction(
        video_id=video_id,
        products=data.get("products", []),
        transcript_text=_read_transcript(video_id),
        description=_read_description(video_id),
        duration_s=data.get("duration_s", 0.0),
        title=data.get("video_title", ""),
        source_file=data.get("source_file", ""),
    )


def run_extraction(video_path: str, client, model: str = config.MODEL) -> Extraction:
    """Full pipeline via video-llm (imports lazily so the loader path has no
    ffmpeg/whisper dependency)."""
    sys.path.insert(0, str(config.VIDEO_LLM_DIR))
    import pipeline  # noqa: E402  (video-llm/pipeline.py)

    path = Path(video_path)
    result = pipeline.process_video(
        path, client, model,
        cache_dir=config.VIDEO_LLM_CACHE, out_dir=config.VIDEO_LLM_OUTPUT,
        use_api=False, whisper_size="base",
    )
    video_id = result["video_id"]
    return Extraction(
        video_id=video_id,
        products=result.get("products", []),
        transcript_text=_read_transcript(video_id),
        description=_read_description(video_id),
        duration_s=result.get("duration_s", 0.0),
        source_file=result.get("source_file", ""),
    )
