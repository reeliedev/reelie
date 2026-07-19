"""
Single place for demo-app configuration.

The extraction pipeline itself lives one directory up (pipeline.py / prompts.py);
this file only holds knobs the *demo* cares about. Nothing here changes pipeline
behaviour except the frame-sampling settings, which are set to match the values
the real runs were produced with so on-disk caches are reused.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Approval thresholds  ── the one place to change after recalibration
# --------------------------------------------------------------------------
# >= AUTO_APPROVE_THRESHOLD  -> confirmed card (green checkmark, no action needed)
# CONFIRM_FLOOR .. AUTO      -> "Confirm this?" card (Yes / No / Edit)
# < CONFIRM_FLOOR            -> hidden from the approval screen (too noisy to show)
AUTO_APPROVE_THRESHOLD = 0.85
CONFIRM_FLOOR = 0.70

# --------------------------------------------------------------------------
# Paths  (all relative to the repo root, i.e. the parent of this file)
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = ROOT / "videos"          # downloaded / uploaded source videos
CACHE_DIR = ROOT / "cache"            # pipeline's transcript/frame cache (reused)
OUTPUT_DIR = ROOT / "output"          # canonical per-video result JSON = the demo cache
DATA_DIR = ROOT / "webapp" / "data"   # demo-app runtime state
JOBS_DIR = DATA_DIR / "jobs"          # per-job status + progress snapshots
CORRECTIONS_DIR = DATA_DIR / "corrections"  # labeled corrections, one file per session
STATIC_DIR = Path(__file__).resolve().parent / "static"

# --------------------------------------------------------------------------
# Pipeline knobs (match the settings the shipped output/*.json were made with,
# so re-running a known video reuses its cached frames/transcript)
# --------------------------------------------------------------------------
MODEL = "claude-sonnet-4-6"
WHISPER_MODEL = "base"
USE_WHISPER_API = False        # local faster-whisper by default
SCENE_THRESHOLD = 0.15
FLOOR_INTERVAL = 5
HOLD_FRAMES = True

# --------------------------------------------------------------------------
# Demo behaviour
# --------------------------------------------------------------------------
# When a result is served from the demo cache we still play the progress
# animation so a live demo *looks* like a real run. This is the total seconds
# that fake run is stretched over. Set to 0 to reveal cached results instantly.
CACHED_RUN_SECONDS = 6.0


def bootstrap_dirs() -> None:
    for d in (VIDEOS_DIR, CACHE_DIR, OUTPUT_DIR, DATA_DIR, JOBS_DIR, CORRECTIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)
