# Beauty/Skincare Product Extractor — validation prototype

Extracts beauty/skincare products mentioned or shown in creator videos with
`claude-sonnet-4-6` (multimodal), and measures extraction accuracy against
hand-labeled ground truth. This is a throwaway prototype for getting an
accuracy number fast — not production code.

## Pipeline (per video)

1. **Ingest** — local files from `./videos/` (and optionally YouTube URLs via yt-dlp).
2. **Transcript** — `faster-whisper` locally (word timestamps), or the OpenAI
   Whisper API with `--api`.
3. **Keyframes** — `ffmpeg` scene-change detection + one frame every 30s floor,
   **plus "held-product" frames**: `freezedetect` finds the still moments when a
   creator holds a product up to camera (labels are most legible then), and the
   sharpest frame in each hold is kept (numpy Laplacian focus measure). Hold
   frames win dedupe over scene/floor frames. Disable with `--no-hold`. Frames
   downscaled to a 1280px long edge. Measured effect on the labeled set:
   product-level F1 0.66 → 0.73 (recall +7pts, precision +7pts).
4. **Extraction** — transcript + keyframes → Claude, constrained to strict JSON
   via structured outputs. Frames are batched into as few calls as possible;
   long videos are chunked and de-duplicated across chunks.
5. **Output** — `./output/{video_id}.json` and a standalone
   `./output/{video_id}.csv` per video (one row per extracted product). Each
   video is kept in its own files — there is no combined CSV.

Transcripts and frames are **cached on disk** under `./cache/{video_id}/`, so
re-running extraction after editing the prompt does **not** redo transcription
or frame extraction.

The extraction prompt and JSON schema live in **`prompts.py`** — iterate on them
without touching pipeline code.

## Setup

```bash
# 1. ffmpeg (provides ffmpeg + ffprobe)
brew install ffmpeg          # macOS
# sudo apt install ffmpeg    # Debian/Ubuntu

# 2. Python 3.11+ deps (yt-dlp is installed as a Python package here)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. API keys
cp .env.example .env         # then edit: ANTHROPIC_API_KEY (and OPENAI_API_KEY if using --api)
```

First local run downloads a faster-whisper model (a few hundred MB for `base`).

## Usage

```bash
# Process every video in ./videos/
python extract.py run

# Also pull YouTube URLs
python extract.py run --urls "https://youtu.be/XXXX" "https://youtu.be/YYYY"

# Use the OpenAI Whisper API instead of local transcription
python extract.py run --api

# Bigger local whisper model for better transcripts
python extract.py run --whisper-model small

# Score predictions against ground truth (prints tables + writes report.md)
python extract.py score
python extract.py score --threshold 90
```

TikTok / Instagram: just drop the downloaded files into `./videos/` — no
scrapers are built for those.

Each video prints its frame count, token usage, and a running **cost estimate**
(Sonnet at $3/$15 per 1M in/out tokens; Whisper API at $0.006/min).

## Labeling ground truth (`./labels/`)

For each video you want to score, create `./labels/{video_id}.csv` where
`{video_id}` matches the output filename (the sanitized video filename stem, or
the YouTube id). Columns:

```csv
product_name,brand,variant_or_shade
Soft Pinch Liquid Blush,Rare Beauty,Happy
Glow Recipe Watermelon Toner,Glow Recipe,
Airwrap,Dyson,
```

Rules to keep labels consistent with how the model is asked to extract:
- **One row per distinct product** the creator actually uses/recommends
  (exclude sponsor bumpers, channel merch, and products they say they *don't* use).
- Put the **brand** in its own column; leave it blank if the video never states
  or clearly shows it.
- `variant_or_shade` is the shade/number/size/formulation — blank if not stated.
- Matching is case-insensitive and fuzzy, so exact punctuation/casing don't matter.

## Accuracy report

`python extract.py score` prints and writes `report.md` with:
- **Per-video** and **aggregate** precision / recall / F1 at two levels:
  (a) product-level (fuzzy match on brand+product_name), and
  (b) product+variant-level (variant must also match).
- A **confidence-calibration table**: precision within each confidence bucket,
  so you can pick an auto-approve threshold.

Fuzzy matching uses `rapidfuzz` `token_sort_ratio`; the threshold is tunable
with `--threshold` (default 85).

## Files

| file | purpose |
|---|---|
| `prompts.py`   | extraction prompt + JSON schema (iterate here) |
| `pipeline.py`  | ingest, transcribe, keyframes, extraction, caching, cost, output |
| `scoring.py`   | fuzzy matching + precision/recall/F1 + calibration |
| `extract.py`   | CLI (`run`, `score`) |
| `cache/`       | cached transcripts + frames per video |
| `videos/` `labels/` `output/` | inputs, ground truth, results |
