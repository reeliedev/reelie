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
    import shutil as _shutil
    import yt_dlp
    VIDEOS.mkdir(parents=True, exist_ok=True)
    # Confirm a JS runtime is actually on PATH for the download subprocess — yt-dlp
    # needs it to run the EJS n-challenge solver that unlocks 720p/1080p.
    print(f"[extract] js-runtime deno={_shutil.which('deno')} node={_shutil.which('node')} "
          f"yt-dlp={yt_dlp.version.__version__}", flush=True)

    # Forward yt-dlp's own warnings/errors (normally stderr, hidden by the worker)
    # to stdout with an [extract] marker so we can see WHY the challenge fails.
    class _YtLog:
        def debug(self, m):
            m = str(m)
            if any(k in m.lower() for k in ("challenge", "ejs", "remote component", "nsig", "n-sig")):
                print(f"[extract] yt: {m[:220]}", flush=True)
        def info(self, m): pass
        def warning(self, m): print(f"[extract] yt-WARN: {str(m)[:220]}", flush=True)
        def error(self, m): print(f"[extract] yt-ERR: {str(m)[:220]}", flush=True)

    opts = {
        "outtmpl": str(VIDEOS / "%(id)s.%(ext)s"),
        # Best video up to 1080p + best audio (H.264 preferred), NOT the 360p
        # progressive "mp4" stream. See download_youtube in pipeline.py.
        "format": ("bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/"
                   "bestvideo[height<=1080]+bestaudio/"
                   "best[height<=1080]/best"),
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "logger": _YtLog(),
        # YouTube gates 720p/1080p behind a JS "n-challenge". yt-dlp only solves it
        # with the EJS solver + a JS runtime (Deno is in the worker image). Without
        # this, YouTube serves <=480p — too low-res to read product packaging text.
        "remote_components": ["ejs:github"],
    }
    # Auth to get past YouTube's bot-check (proxy / cookies / player-client from env).
    # Self-contained (no import) so it can never be silently skipped, and it logs
    # whether a proxy/cookies were applied — check the worker logs to confirm.
    import os as _os
    import sys as _sys
    import tempfile as _tempfile
    _cf = _os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if _cf and _os.path.exists(_cf):
        opts["cookiefile"] = _cf
    elif _os.environ.get("YTDLP_COOKIES", "").strip():
        _tf = _tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        _tf.write(_os.environ["YTDLP_COOKIES"])
        _tf.close()
        opts["cookiefile"] = _tf.name
    _proxy_tmpl = _os.environ.get("YTDLP_PROXY", "").strip()
    _clients = _os.environ.get("YTDLP_PLAYER_CLIENT", "").strip()
    if _clients:
        opts.setdefault("extractor_args", {})["youtube"] = {
            "player_client": [c.strip() for c in _clients.split(",") if c.strip()]
        }
    print(f"[extract] yt auth — proxy:{'yes' if _proxy_tmpl else 'NO'} "
          f"cookies:{'yes' if opts.get('cookiefile') else 'no'} "
          f"client:{_clients or 'default'}", file=_sys.stderr, flush=True)

    # YouTube bot-checks SOME residential IPs at random. A fresh proxy session gives
    # a NEW IP, and most are clean — so on a bot-check (or a 403/connection blip,
    # also IP-related) we rotate the IP and retry. Only retriable when the proxy URL
    # has a {session} placeholder to vary.
    import uuid as _uuid
    _rotatable = bool(_proxy_tmpl) and "{session}" in _proxy_tmpl
    _attempts = 6 if _rotatable else 1
    _last = None
    for _i in range(_attempts):
        if _proxy_tmpl:
            opts["proxy"] = (_proxy_tmpl.replace("{session}", _uuid.uuid4().hex[:12])
                             if _rotatable else _proxy_tmpl)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info))
                if path.suffix != ".mp4":
                    path = path.with_suffix(".mp4")
                # STDOUT (not stderr) + [extract] marker so it survives the worker's
                # log filter — tells us the real download resolution.
                print(f"[extract] downloaded {info.get('width')}x{info.get('height')} "
                      f"fmt={info.get('format_id')}", flush=True)
                return path, (info.get("title") or "").strip()
        except Exception as e:  # noqa: BLE001
            _last = e
            _m = str(e).lower()
            _retriable = ("not a bot" in _m or "sign in to confirm" in _m
                          or "http error 403" in _m or "forbidden" in _m
                          or "connection" in _m or "timed out" in _m)
            if _retriable and _rotatable and _i < _attempts - 1:
                print(f"[extract] blocked on attempt {_i + 1}/{_attempts} — "
                      f"rotating proxy IP and retrying", file=_sys.stderr, flush=True)
                continue
            raise
    raise _last


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR: pass a URL or file path", file=sys.stderr)
        return 2
    arg = sys.argv[1].strip()

    # .strip(): a trailing newline (common when pasting the key into a host's env
    # UI) makes httpx reject the auth header as an "illegal header value", which
    # surfaces confusingly as APIConnectionError.
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
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
        # ReadError/WriteError/etc.) — that's what actually explains the failure.
        # Print the traceback FIRST and the root_cause line LAST so it survives the
        # caller's tail-truncation of stderr.
        import traceback
        traceback.print_exc()
        cause = e.__cause__
        inner = getattr(cause, "__cause__", None)
        print(f"ROOT_CAUSE: {type(cause).__name__}: {cause!r} :: "
              f"inner={type(inner).__name__ if inner else None}: {inner!r}", file=sys.stderr)
        return 7
    print(f"VIDEO_ID:{result['video_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
