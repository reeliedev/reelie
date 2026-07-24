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
# .strip() guards against a trailing newline sneaking in when the value is pasted
# into a host's env var field (a very common cause of "database ... does not exist").
_db = os.environ.get("DATABASE_URL", f"sqlite:///{HERE / 'reelie.db'}").strip()
# Managed hosts hand out postgres://… (psycopg2 dialect); we use psycopg3.
if _db.startswith("postgres://"):
    _db = "postgresql+psycopg://" + _db[len("postgres://"):]
elif _db.startswith("postgresql://"):
    _db = "postgresql+psycopg://" + _db[len("postgresql://"):]
DATABASE_URL = _db

# CORS: comma-separated allowed origins. "*" in dev; the reelie.io domains in
# prod by default (override with ALLOWED_ORIGINS for custom/staging origins).
_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://reelie.io,https://www.reelie.io" if IS_PROD else "*")
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]

# Auth provider: 'dev' (local JWT) or 'oidc' (verify a real provider's RS256 token
# via JWKS — works for Supabase / Clerk / Auth0 / Sign in with Apple by pointing
# these at the provider's discovery values).
AUTH_PROVIDER = os.environ.get("AUTH_PROVIDER", "dev")
OIDC_JWKS_URL = os.environ.get("OIDC_JWKS_URL", "")     # e.g. https://<clerk>/.well-known/jwks.json
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "")         # e.g. https://appleid.apple.com
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "")     # your client/app id (Apple) or Clerk aud

# Supabase Auth (recommended for public): brokers Apple + Google + email
# magic-link, headless (our own login UI). Set these two and everything else is
# derived — the provider flips to OIDC and verifies Supabase tokens via its JWKS.
# The anon key is a PUBLIC client key (safe to expose to the browser).
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
if SUPABASE_URL:
    AUTH_PROVIDER = "oidc"
    OIDC_JWKS_URL = OIDC_JWKS_URL or f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    OIDC_ISSUER = OIDC_ISSUER or f"{SUPABASE_URL}/auth/v1"
    OIDC_AUDIENCE = OIDC_AUDIENCE or "authenticated"

# Which process this is: the API/web service ('api', default) or the extraction
# worker ('worker'). The worker only claims jobs and runs the pipeline — it never
# signs/verifies user tokens or serves /admin, so it doesn't need those secrets.
REELIE_ROLE = os.environ.get("REELIE_ROLE", "api").strip().lower()
IS_API = REELIE_ROLE != "worker"

JWT_SECRET = (os.environ.get("JWT_SECRET") or ("dev-only-secret-do-not-use-in-prod" if not IS_PROD else "")).strip()
if IS_PROD and IS_API and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set when REELIE_ENV=prod")
# Fail-closed: the password-less dev auth provider must never run in production.
if IS_PROD and AUTH_PROVIDER == "dev":
    raise RuntimeError("AUTH_PROVIDER must be 'oidc' in prod — set SUPABASE_URL. "
                       "Refusing to boot with the dev (password-less) provider.")

# Internal service token: gates the /ingest write (the generator/worker → API) so
# it's not an open endpoint. Needed by BOTH: the API passes it to the generator
# subprocess, and the worker uses it to publish finished pages back to /ingest.
INGEST_TOKEN = (os.environ.get("INGEST_TOKEN") or ("dev-ingest-token" if not IS_PROD else "")).strip()
if IS_PROD and not INGEST_TOKEN:
    raise RuntimeError("INGEST_TOKEN must be set when REELIE_ENV=prod")

# Admin token: gates the closed-beta review console (/admin) — approve/reject
# creator applications. Keep it secret; anyone with it can approve creators. API-only.
ADMIN_TOKEN = (os.environ.get("ADMIN_TOKEN") or ("dev-admin-token" if not IS_PROD else "")).strip()
if IS_PROD and IS_API and not ADMIN_TOKEN:
    raise RuntimeError("ADMIN_TOKEN must be set when REELIE_ENV=prod")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 60 * 60 * 24 * 30                 # 30 days

BRAND = "Reelie"
TAGLINE = "Every product in your favourite creators' videos — found, priced and linked, automatically."
DEFAULT_AVATAR_GRADIENT = ["#E8E4DA", "#D8D2C4"]

# Public site: the domain the crawlable pages + SEO files live at. In prod this
# is the custom domain (https://reelie.io); locally it's the dev server so
# links resolve. Used to build absolute URLs in JSON-LD / sitemap / llms.txt.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", os.environ.get("REELIE_SELF_URL", "http://127.0.0.1:8010")).rstrip("/")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "hello@reelie.io")
# Transactional email via Resend (the reelie.io domain is already verified there).
# Notifications no-op + log when the key is absent, so dev never sends.
# Product-link resolution via DataForSEO Google Shopping (direct buy links).
# Env-gated: no creds → callers keep the Google Shopping search fallback.
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN", "").strip()
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "").strip()
PRODUCT_SEARCH_ENABLED = bool(DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
# Sent from (and, for team alerts, to) marketing@reelie.io by default — both on
# the verified reelie.io domain. Override with EMAIL_FROM / ADMIN_EMAIL if needed.
EMAIL_FROM = os.environ.get("EMAIL_FROM", "Reelie <marketing@reelie.io>").strip()
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "marketing@reelie.io").strip()
# AI crawlers we explicitly invite in robots.txt.
AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web",
               "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended",
               "Applebot-Extended", "CCBot", "Amazonbot", "Bytespider", "Meta-ExternalAgent"]
# Creator handles that would collide with API/site routes — reserved at claim time.
RESERVED_HANDLES = {"me", "auth", "creators", "routines", "recommendations", "ingest",
                    "r", "earnings", "pages", "payouts", "connect", "health", "api",
                    "robots.txt", "llms.txt", "sitemap.xml", "schema-graph.json",
                    "favicon.ico", "static", "assets", "admin", "about", "terms", "privacy",
                    "studio", "media", "login", "signin", "signup", "dashboard",
                    "discover", "browse", "styles.css", "main.js", "try", "home", "likes", "feed"}

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

# The marketing landing page (served as the site home at /). Bundled into the
# image so it ships with the API.
LANDING_DIR = Path(__file__).resolve().parent / "landing"

# --------------------------------------------------------------------------
# Object storage (Cloudflare R2 / S3) — durable home for uploaded videos and
# generated clips (so clips survive redeploys and the feed works in prod). When
# unset, falls back to local /media (dev only). R2 is S3-compatible.
# --------------------------------------------------------------------------
STORAGE_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", "").strip()          # https://<acct>.r2.cloudflarestorage.com
STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "").strip()
STORAGE_ACCESS_KEY_ID = os.environ.get("STORAGE_ACCESS_KEY_ID", "").strip()
STORAGE_SECRET_ACCESS_KEY = os.environ.get("STORAGE_SECRET_ACCESS_KEY", "").strip()
STORAGE_PUBLIC_URL = os.environ.get("STORAGE_PUBLIC_URL", "").strip().rstrip("/")  # https://media.reelie.io or pub-xxx.r2.dev
STORAGE_REGION = os.environ.get("STORAGE_REGION", "auto")                   # 'auto' for R2
STORAGE_ENABLED = bool(STORAGE_ENDPOINT and STORAGE_BUCKET
                       and STORAGE_ACCESS_KEY_ID and STORAGE_SECRET_ACCESS_KEY
                       and STORAGE_PUBLIC_URL)

# Normalize the Anthropic key in-process: strip surrounding whitespace/newlines
# (common when pasted into a host's env UI) and write it back, so every downstream
# consumer — bare `anthropic.Anthropic()` clients and the extraction/build
# subprocesses that inherit this env — gets a clean value. A newline here makes
# httpx reject the auth header, surfacing as a misleading APIConnectionError.
if os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"].strip()

# Mock keeps generation $0 (stub prices, no API key). Set GENERATE_LIVE=1 to use
# the LLM (needs ANTHROPIC_API_KEY on the generator's environment).
GENERATE_LIVE = os.environ.get("GENERATE_LIVE") == "1"

# Cut per-step video clips during generation. On by default: the URL flow
# downloads the source and the generator bundles ffmpeg (via static-ffmpeg), and
# clip-cutting skips gracefully when no source is present. Set GENERATE_CLIPS=0
# to disable (e.g. a minimal worker without the media deps).
GENERATE_CLIPS = os.environ.get("GENERATE_CLIPS", "1") == "1"

# Is the video->page pipeline present in this deployment? The plain API image
# doesn't bundle video-llm / page-generator (or ffmpeg), so self-serve generation
# can't run here — we capture the request instead and build it out-of-band during
# the beta. True locally (files present), False on the API-only prod image.
PIPELINE_AVAILABLE = (os.environ.get("PIPELINE_AVAILABLE", "").lower() in ("1", "true")
                      or (EXTRACT_ONE.exists() and GENERATE_PY.exists()))

# Is a separate extraction worker deployed and polling for jobs? When on, the API
# just enqueues jobs ('queued') and the worker processes them. When off, the API
# runs generation inline (dev, if the pipeline is present) or captures the request.
WORKER_ENABLED = os.environ.get("WORKER_ENABLED", "").lower() in ("1", "true")

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
