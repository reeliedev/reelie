"""
Central config. Local dev needs no environment at all — it defaults to a local
SQLite file and a fixed dev JWT secret. Production swaps these via env:
DATABASE_URL (Postgres), JWT_SECRET, AUTH_PROVIDER.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

HERE = Path(__file__).resolve().parent.parent      # backend/

# dev | prod. Prod tightens CORS and requires a real JWT secret.
ENV = os.environ.get("REELIE_ENV", "dev")
IS_PROD = ENV == "prod"

# SQLite file in dev (zero setup). Postgres in prod via DATABASE_URL, e.g.
# postgresql+psycopg://user:pass@host:5432/reelie
_db = os.environ.get("DATABASE_URL", f"sqlite:///{HERE / 'reelie.db'}")
# Managed hosts hand out postgres://… (psycopg2 dialect); we use psycopg3.
if _db.startswith("postgres://"):
    _db = "postgresql+psycopg://" + _db[len("postgres://"):]
elif _db.startswith("postgresql://"):
    _db = "postgresql+psycopg://" + _db[len("postgresql://"):]
DATABASE_URL = _db

# CORS: comma-separated allowed origins. "*" in dev; the reelie.shop domains in
# prod by default (override with ALLOWED_ORIGINS for custom/staging origins).
_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://reelie.shop,https://www.reelie.shop" if IS_PROD else "*")
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]

# Auth provider: 'dev' (local JWT) or 'oidc' (verify a real provider's RS256 token
# via JWKS — works for Clerk / Auth0 / Sign in with Apple by pointing these at the
# provider's discovery values).
AUTH_PROVIDER = os.environ.get("AUTH_PROVIDER", "dev")
OIDC_JWKS_URL = os.environ.get("OIDC_JWKS_URL", "")     # e.g. https://<clerk>/.well-known/jwks.json
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "")         # e.g. https://appleid.apple.com
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "")     # your client/app id (Apple) or Clerk aud
JWT_SECRET = os.environ.get("JWT_SECRET") or ("dev-only-secret-do-not-use-in-prod" if not IS_PROD else "")
if IS_PROD and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set when REELIE_ENV=prod")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 60 * 60 * 24 * 30                 # 30 days

BRAND = "Reelie"
TAGLINE = "Every product in your favourite creators' videos — found, priced and linked, automatically."
DEFAULT_AVATAR_GRADIENT = ["#E8E4DA", "#D8D2C4"]

# Public site: the domain the crawlable pages + SEO files live at. In prod this
# is the custom domain (https://reelie.shop); locally it's the dev server so
# links resolve. Used to build absolute URLs in JSON-LD / sitemap / llms.txt.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", os.environ.get("REELIE_SELF_URL", "http://127.0.0.1:8010")).rstrip("/")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "hello@reelie.shop")
# AI crawlers we explicitly invite in robots.txt.
AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web",
               "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended",
               "Applebot-Extended", "CCBot", "Amazonbot", "Bytespider", "Meta-ExternalAgent"]
# Creator handles that would collide with API/site routes — reserved at claim time.
RESERVED_HANDLES = {"me", "auth", "creators", "routines", "recommendations", "ingest",
                    "r", "earnings", "pages", "payouts", "connect", "health", "api",
                    "robots.txt", "llms.txt", "sitemap.xml", "schema-graph.json",
                    "favicon.ico", "static", "assets", "admin", "about", "terms", "privacy"}

# Where to import seed pages from (the web generator's registry), if present.
REPO_ROOT = HERE.parent
PAGES_INDEX = REPO_ROOT / "Reelie App" / "page-generator" / "out" / "pages.json"

# --------------------------------------------------------------------------
# Self-serve generation (Phase 1.3). We orchestrate the existing page-generator
# CLI as a subprocess; it POSTs the finished page back to /ingest.
# --------------------------------------------------------------------------
PAGE_GENERATOR_DIR = REPO_ROOT / "Reelie App" / "page-generator"
GENERATE_PY = PAGE_GENERATOR_DIR / "generate.py"
VIDEO_LLM_DIR = REPO_ROOT / "video-llm"
VIDEO_LLM_OUTPUT = VIDEO_LLM_DIR / "output"
EXTRACT_ONE = VIDEO_LLM_DIR / "extract_one.py"     # URL/file → extraction → output/<id>.json

# Interpreter to run the generator. Prefer the video-llm venv (has anthropic for
# live mode); fall back to whatever runs this service.
def _python_bin() -> str:
    import sys
    venv = REPO_ROOT / "video-llm" / ".venv" / "bin" / "python3"
    return str(venv) if venv.exists() else sys.executable

PYTHON_BIN = _python_bin()

# The generator POSTs the page back to THIS service. Override in prod.
SELF_URL = os.environ.get("REELIE_SELF_URL", "http://127.0.0.1:8010")

# Media (per-step video clips). Served at /media locally; the generator copies
# cut clips here and sends absolute URLs to /ingest. In prod these belong in
# object storage (Cloudflare R2 / S3 + CDN) — swap MEDIA_ROOT/base then.
MEDIA_ROOT = Path(os.environ.get("REELIE_MEDIA_ROOT", str(HERE / "media")))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Mock keeps generation $0 (stub prices, no API key). Set GENERATE_LIVE=1 to use
# the LLM (needs ANTHROPIC_API_KEY on the generator's environment).
GENERATE_LIVE = os.environ.get("GENERATE_LIVE") == "1"

# Cut per-step video clips during generation (needs ffmpeg + the source video —
# the worker, not the plain API image). When on, clips are copied to MEDIA_ROOT
# and their URLs synced to the DB.
GENERATE_CLIPS = os.environ.get("GENERATE_CLIPS") == "1"

# --------------------------------------------------------------------------
# Social OAuth (Pillar 2): connect a creator's YouTube / Instagram so we can
# list their videos. Credential-agnostic — if a platform's client id/secret are
# unset we fall back to a MOCK provider so the whole connect flow is demoable
# locally with no Google/Meta app. Drop the real keys in to activate each one.
# --------------------------------------------------------------------------
# Where providers redirect back after consent (must be an allow-listed HTTPS URL
# in the Google/Meta app config in prod; SELF_URL works for local + deployed).
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", SELF_URL)
# Custom URL scheme the iOS app registers, so the callback can hand control back.
APP_CALLBACK_SCHEME = os.environ.get("APP_CALLBACK_SCHEME", "reelie")

# YouTube = Google OAuth 2.0 + YouTube Data API v3.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# Instagram = Meta app (Instagram API with Instagram Login).
INSTAGRAM_APP_ID = os.environ.get("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET", "")

# Force the mock connect flow even if creds exist (handy for local UI testing).
OAUTH_FORCE_MOCK = os.environ.get("OAUTH_FORCE_MOCK") == "1"
