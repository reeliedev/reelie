"""Reelie backend — FastAPI app. Local $0 stack (SQLite + dev auth)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import config
from app.db import init_db
from app.routers import (admin, auth, catalog, connections, earnings, feed,
                         generate, ingest, likes, me, pages, payouts, recommend,
                         redirect, site)
from app.seed import seed_if_empty

app = FastAPI(title="Reelie API", version="0.1.0")

# Baseline per-IP rate limiting (flood backstop). Client IP is taken from the
# proxy's X-Forwarded-For (uvicorn is run with FORWARDED_ALLOW_IPS so it trusts
# Render's proxy). In-memory per worker — a Redis storage_uri can be added later
# for cross-worker accuracy. The per-creator generation quota (routers/generate)
# is the primary cost-DoS defense.
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS: "*" in dev; a real allow-list in prod (ALLOWED_ORIGINS).
app.add_middleware(
    CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS or ["*"], allow_methods=["*"],
    allow_headers=["*"], allow_credentials=False,
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline hardening headers on every response. SAMEORIGIN (not DENY) so the
    studio's own edit-preview iframe of a public page keeps working. HSTS only in
    prod (dev is http). No CSP yet — the server-rendered pages use inline styles,
    so a strict CSP needs nonces (tracked as a follow-up)."""
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if config.IS_PROD:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(catalog.router)
app.include_router(recommend.router)
app.include_router(ingest.router)
app.include_router(redirect.router)
app.include_router(earnings.router)
app.include_router(generate.router)
app.include_router(pages.router)
app.include_router(payouts.router)
app.include_router(connections.router)
app.include_router(likes.router)
app.include_router(admin.router)
app.include_router(feed.router)

# Per-step video clips (local hosting; object storage in prod).
app.mount("/media", StaticFiles(directory=str(config.MEDIA_ROOT)), name="media")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    if seed_if_empty():
        print("· seeded mock corpus (5 creators)")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "brand": config.BRAND, "auth": config.AUTH_PROVIDER,
            # diagnostics (no secrets — just whether they're configured)
            "email": bool(config.RESEND_API_KEY), "emailTo": config.ADMIN_EMAIL}


# The public site's `/{handle}` routes are greedy — include LAST so every API
# route and /health above resolve first.
app.include_router(site.router)
