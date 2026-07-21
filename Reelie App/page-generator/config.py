"""
Central config for the page generator. Everything brand/environment-specific
lives here so switching brand, domain, or paths is a one-file change.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Brand / domain (tentative: reelie.io)
# --------------------------------------------------------------------------
BRAND = "Reelie"
DOMAIN = "reelie.io"
BASE_URL = f"https://{DOMAIN}"
TAGLINE = "Every product in your favourite creators' videos — found, priced and linked, automatically."
SUPPORT_EMAIL = f"hello@{DOMAIN}"

# The affiliate redirect base. Reelie links route through our own shortener so we
# can pick the best-rate retailer per click.
REELIE_LINK_BASE = f"{BASE_URL}/r"

# Model + pricing (mirrors video-llm so cost math stays consistent).
MODEL = "claude-sonnet-4-6"

# --------------------------------------------------------------------------
# Paths (relative to this repo layout: "Reelie App/page-generator/")
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent               # /Volumes/LaCie/Retrieva_Creator
VIDEO_LLM_DIR = REPO_ROOT / "video-llm"
VIDEO_LLM_OUTPUT = VIDEO_LLM_DIR / "output"
VIDEO_LLM_CACHE = VIDEO_LLM_DIR / "cache"
# Where source video files live (raw drop-ins, plus the pipeline's _processed copies).
VIDEO_LLM_VIDEOS = VIDEO_LLM_DIR / "videos"

# --------------------------------------------------------------------------
# Per-step video clips (rendered with PyAV — no system ffmpeg needed).
# --------------------------------------------------------------------------
CLIP_WIDTH = 480            # output width in px; height follows source aspect
CLIP_MIN_S = 1.6           # never shorter than this
CLIP_MAX_S = 7.0           # never longer than this
CLIP_LEAD_S = 0.3          # start a touch before the product's timestamp

OUT_DIR = HERE / "out"
OUT_APP = OUT_DIR / "app"                     # app-facing JSON, one per page
OUT_PUBLIC = OUT_DIR / "public"               # public web pages, /<handle>/<slug>/index.html
OUT_SITE = OUT_DIR / "site"                   # robots.txt, llms.txt, schema-graph.json, sitemap.xml

PAGES_INDEX = OUT_DIR / "pages.json"          # registry of every generated page (drives site files)

SAMPLES_DIR = HERE / "samples"

# The "main webpage" whose Schema.org we keep in sync. A managed block is injected
# between markers so re-runs are idempotent and the rest of the file is untouched.
MAIN_SITE_HTML = REPO_ROOT / "Landing Page" / "index.html"
SCHEMA_MARKER_START = "<!-- reelie:schema:start -->"
SCHEMA_MARKER_END = "<!-- reelie:schema:end -->"

# Also drop the app bundle sample here so the iOS app can ship a page standalone.
APP_BUNDLE_SAMPLE = (
    REPO_ROOT / "Reelie App" / "ReelieApp" / "ReelieApp" / "Resources"
    / "sample-generated-page.json"
)

# --------------------------------------------------------------------------
# AI crawler allow-list for robots.txt — we WANT chatbots to read our pages.
# --------------------------------------------------------------------------
AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",   # OpenAI
    "ClaudeBot", "Claude-Web", "anthropic-ai",   # Anthropic
    "PerplexityBot", "Perplexity-User",          # Perplexity
    "Google-Extended",                            # Google AI / Gemini training
    "Applebot-Extended",                          # Apple Intelligence
    "CCBot",                                       # Common Crawl (feeds many LLMs)
    "Amazonbot", "Bytespider", "Meta-ExternalAgent",
]

DEFAULT_CURRENCY = "USD"
# LLM price estimates are marked approximate and expire so nobody treats a stale
# guess as a firm quote.
PRICE_VALID_DAYS = 90


def anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")
