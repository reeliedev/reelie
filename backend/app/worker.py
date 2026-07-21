"""
Extraction worker. Polls the job queue (Postgres) for 'queued' generation jobs,
claims one at a time, and runs the full pipeline (download / transcribe /
keyframes / Claude / clips / publish) via pipeline_runner.

Runs as its own Render service (see render.yaml) with the pipeline + ffmpeg in
its image. Single-worker-safe via SELECT ... FOR UPDATE SKIP LOCKED.

Start:  python -m app.worker
"""

from __future__ import annotations

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
