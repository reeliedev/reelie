# Routine Extractor — demo app

A one-page web app that wraps the existing extraction pipeline (`../pipeline.py`)
so you can demo it live to creators: paste a video → watch it process → approve
the products it found → preview the public routine page.

It is a **thin wrapper**. It does not reimplement extraction — `runner.py` calls
the same library functions the CLI uses and streams progress between the stages.

## Run it

```bash
# from the repo root, with the project venv active (or let run.sh find it)
pip install -r webapp/requirements.txt      # first time only (fastapi/uvicorn)
./webapp/run.sh
```

Open <http://localhost:8000>. To demo on your **phone**, open
`http://<your-mac-ip>:8000` while on the same wifi (the script binds `0.0.0.0`).

Requires `ANTHROPIC_API_KEY` in `../.env` (already there) and `ffmpeg` on PATH.

## The demo flow

1. **Input** — paste a YouTube URL or upload a video file.
2. **Processing** — live progress ("Watching your video…", "Listening to the
   audio…", "Finding your products…") streamed over SSE, with the thumbnail.
3. **Approval** — product cards in routine order with evidence badges
   (Spoken / Shown / Both). Cards at confidence ≥ `AUTO_APPROVE_THRESHOLD` are
   confirmed with a ✓; cards between `CONFIRM_FLOOR` and that get Yes / No / Edit.
   "Add a product we missed" at the bottom.
4. **Page preview** — a clean mobile mock of the public routine page with fake
   Shop buttons, built from the approved data.

## Demo cache (instant wow)

Results are keyed by video id and written to `../output/{video_id}.json` — the
same file the CLI produces. If that file exists, the app **replays the progress
animation quickly and serves the cached result** (a "⚡ instant demo" pill shows).
So: pre-run a creator's own video once (`python ../extract.py run --urls <URL>`
or just run it once through the app), then "run" it live for an instant, reliable
result. Delete the JSON to force a genuine fresh run.

The 20 videos already in `../output/` are all pre-cached and demo instantly.

## Config — the one knob that matters

Everything tunable lives in [`config.py`](config.py). After recalibration, change
the auto-approve threshold in one place:

```python
AUTO_APPROVE_THRESHOLD = 0.85   # ≥ this → confirmed card
CONFIRM_FLOOR          = 0.70   # this..auto → "Confirm this?"; below → hidden
CACHED_RUN_SECONDS     = 6.0    # how long the fake "live run" takes for cached videos
```

## Corrections — saved every time

Every confirm / reject / edit / add is POSTed to `/api/jobs/{id}/corrections` and
appended to `data/corrections/{session}.jsonl` — labeled corrections, kept even in
demos. One line per action with `before`/`after` for edits. Point your labeling at
that folder.

## Failure

Any pipeline error becomes a friendly "We had trouble with this video." screen —
no stack traces ever reach the creator.

## Deploying to one small server later

- No database, no accounts. State is the filesystem: `videos/`, `cache/`,
  `output/` (results = demo cache), and `webapp/data/` (jobs + corrections).
- `runner.py` uses threads; fine for one-at-a-time demos. For real concurrency,
  swap the in-memory job store for a queue/worker — the pipeline calls already
  cache to disk, so that change is contained.
- `run.sh` binds `0.0.0.0`; put it behind nginx/caddy with TLS and you're up.

## Files

| file | what |
|---|---|
| `config.py` | thresholds, paths, pipeline knobs — the one place to tune |
| `runner.py` | wraps the pipeline, emits progress, demo-cache logic |
| `server.py` | FastAPI: jobs, SSE, corrections, static |
| `static/`   | the single-page app (plain HTML/CSS/JS, no build) |
| `data/`     | runtime: `corrections/*.jsonl` (git-ignore this) |
