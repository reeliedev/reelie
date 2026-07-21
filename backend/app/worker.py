"""
Extraction worker. Polls the job queue (Postgres) for 'queued' generation jobs,
claims one at a time, and runs the full pipeline (download / transcribe /
keyframes / Claude / clips / publish) via pipeline_runner.

Runs as its own Render service (see render.yaml) with the pipeline + ffmpeg in
its image. Single-worker-safe via SELECT ... FOR UPDATE SKIP LOCKED.

Start:  python -m app.worker
"""

from __future__ import annotations

import os
import time

from sqlalchemy import text
from sqlmodel import Session

from app import config, pipeline_runner
from app.db import engine
from app.models import GenerationJob  # noqa: F401  (registers the table)

POLL_SECONDS = 5

# Atomically claim the oldest queued job (skips rows locked by another worker).
_CLAIM = text("""
    UPDATE generationjob SET status='running', stage='Starting…'
    WHERE id = (
        SELECT id FROM generationjob WHERE status='queued'
        ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED
    )
    RETURNING id
""")


def claim_next() -> str | None:
    with Session(engine) as s:
        row = s.execute(_CLAIM).first()
        s.commit()
        return row[0] if row else None


def main() -> None:
    print(f"[worker] starting — pipeline_available={config.PIPELINE_AVAILABLE}, "
          f"storage={config.STORAGE_ENABLED}, live={config.GENERATE_LIVE}", flush=True)
    if not config.PIPELINE_AVAILABLE:
        print("[worker] WARNING: pipeline not present in this image — jobs will fail.", flush=True)
    if not config.STORAGE_ENABLED:
        # Name exactly which STORAGE_* vars are missing/empty (values masked).
        seen = {k: ("set" if os.environ.get(k, "").strip() else "MISSING/EMPTY")
                for k in ("STORAGE_ENDPOINT", "STORAGE_BUCKET", "STORAGE_ACCESS_KEY_ID",
                          "STORAGE_SECRET_ACCESS_KEY", "STORAGE_PUBLIC_URL")}
        print(f"[worker] storage disabled — STORAGE_* seen: {seen}", flush=True)
    # DB the worker actually connected to (host only — never log credentials).
    _db = os.environ.get("DATABASE_URL", "")
    _host = _db.split("@")[-1].split("/")[0] if "@" in _db else ("sqlite (LOCAL — will not see API jobs!)" if not _db else _db[:20])
    print(f"[worker] db → {_host}", flush=True)
    # One-time egress probe: can we reach the Anthropic API over HTTPS? (A 401 here
    # is success — it proves connect+TLS work; the extraction supplies the real key.)
    import urllib.request
    import urllib.error
    print(f"[worker] anthropic_api_key={'set' if os.environ.get('ANTHROPIC_API_KEY','').strip() else 'MISSING/EMPTY'}", flush=True)
    try:
        urllib.request.urlopen("https://api.anthropic.com/v1/messages", timeout=15)
        print("[worker] anthropic reachable: 200", flush=True)
    except urllib.error.HTTPError as e:
        print(f"[worker] anthropic reachable: HTTP {e.code} (connect+TLS OK)", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[worker] anthropic UNREACHABLE: {type(e).__name__}: {e}", flush=True)
    # Deterministic SDK probe: make a real (tiny) messages call via the anthropic
    # client — the SAME transport the extraction uses — so a systematic SDK-level
    # failure reproduces here with its true root cause, no video needed.
    _key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if _key:
        import anthropic
        import httpx

        def _large_probe(label: str, http_client) -> None:
            # ~5 MB payload → forces a multi-packet upload like the frames request.
            # A 4xx here means the UPLOAD succeeded (server rejected on content) =
            # network fine; an APIConnectionError means the upload itself failed.
            try:
                c = anthropic.Anthropic(api_key=_key, max_retries=0, http_client=http_client)
                c.messages.create(model="claude-sonnet-4-6", max_tokens=1,
                                  messages=[{"role": "user", "content": "x" * 5_000_000}])
                print(f"[worker] large probe [{label}]: OK", flush=True)
            except anthropic.APIStatusError as e:
                print(f"[worker] large probe [{label}]: HTTP {e.status_code} — upload OK (network fine)", flush=True)
            except Exception as e:  # noqa: BLE001
                cause = getattr(e, "__cause__", None)
                print(f"[worker] large probe [{label}]: {type(e).__name__}: {e} | "
                      f"root={type(cause).__name__ if cause else None}: {cause!r}", flush=True)

        _large_probe("default", httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0)))
        _large_probe("ipv4", httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0),
                                          transport=httpx.HTTPTransport(local_address="0.0.0.0")))
    while True:
        try:
            job_id = claim_next()
            if job_id:
                print(f"[worker] processing {job_id}", flush=True)
                pipeline_runner.process_job(job_id)
                print(f"[worker] done {job_id}", flush=True)
            else:
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            break
        except Exception as e:  # noqa: BLE001  (keep the loop alive)
            print(f"[worker] loop error: {e}", flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
