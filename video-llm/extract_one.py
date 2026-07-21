"""
Extract ONE video into ./output/<id>.json — from a URL (yt-dlp download) or a
local file path. Used by the backend's self-serve "paste a link" flow. Bundles a
static ffmpeg/ffprobe (no Homebrew needed) onto PATH. Prints `VIDEO_ID:<id>` on
success so the caller can hand it to generate.py.

Usage:  python extract_one.py "<youtube-or-file>"
Needs ANTHROPIC_API_KEY (read from .env).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Put the pip-bundled static ffmpeg/ffprobe on PATH for the pipeline's subprocesses.
try:
    from static_ffmpeg import run as _sf
    _bindir = os.path.dirname(_sf.get_or_fetch_platform_executables_else_raise()[0])
    os.environ["PATH"] = _bindir + os.pathsep + os.environ.get("PATH", "")
except Exception as e:  # pragma: no cover
    print(f"ERROR: ffmpeg unavailable ({e})", file=sys.stderr)
    sys.exit(3)

# Deno (JS runtime) unblocks yt-dlp's YouTube extraction. Optional — direct video
# URLs and uploads work without it.
_deno = os.path.expanduser("~/.deno/bin")
if os.path.isdir(_deno):
    os.environ["PATH"] = _deno + os.pathsep + os.environ["PATH"]

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

import anthropic  # noqa: E402
import pipeline  # noqa: E402

HERE = Path(__file__).resolve().parent
VIDEOS = HERE / "videos"
CACHE = HERE / "cache"
OUTPUT = HERE / "output"
MODEL = "claude-sonnet-4-6"


def _download(url: str) -> tuple[Path, str]:
    """Download the video; return (path, title). The title is the platform's own
    video title, used as the page's default name."""
    import yt_dlp
    VIDEOS.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(VIDEOS / "%(id)s.%(ext)s"),
        "format": "mp4/bestvideo[ext=mp4]+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        if path.suffix != ".mp4":
            path = path.with_suffix(".mp4")
        return path, (info.get("title") or "").strip()


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR: pass a URL or file path", file=sys.stderr)
        return 2
    arg = sys.argv[1].strip()

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 4

    title = ""
    try:
        if arg.startswith("http"):
            src, title = _download(arg)
        else:
            src = Path(arg)
    except Exception as e:
        print(f"ERROR: download failed: {e}", file=sys.stderr)
        return 5
    if not src.exists():
        print(f"ERROR: video not found: {src}", file=sys.stderr)
        return 6

    # Background worker: ride out transient network blips instead of failing the
    # whole job. Retries connection/5xx errors with backoff; generous per-request
    # timeout for the large multimodal (frames) request.
    # Force IPv4: large multimodal uploads (video frames) from some container
    # networks stall/reset over a broken IPv6/MTU path — small requests survive,
    # big ones fail with APIConnectionError. Binding to an IPv4 local address
    # pins the connection to IPv4. (Override with REELIE_FORCE_IPV4=0 if ever needed.)
    import httpx
    _kw = {"timeout": httpx.Timeout(180.0, connect=30.0)}
    if os.environ.get("REELIE_FORCE_IPV4", "1").lower() in ("1", "true"):
        _kw["transport"] = httpx.HTTPTransport(local_address="0.0.0.0")
    client = anthropic.Anthropic(api_key=key, max_retries=6, http_client=httpx.Client(**_kw))
    try:
        result = pipeline.process_video(
            src, client, MODEL, cache_dir=CACHE, out_dir=OUTPUT,
            use_api=False, whisper_size="base", title=title)
    except anthropic.APIConnectionError as e:
        # Surface the REAL transport error under the SDK wrapper (httpx ConnectError/
        # ReadError/etc.) — that's what actually explains the failure.
        cause = e.__cause__
        print(f"ERROR: Anthropic connection failed. root_cause={type(cause).__name__}: {cause!r}",
              file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 7
    print(f"VIDEO_ID:{result['video_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
