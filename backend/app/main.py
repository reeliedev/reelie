"""Reelie backend — FastAPI app. Local $0 stack (SQLite + dev auth)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config
from app.db import init_db
from app.routers import (admin, auth, catalog, connections, earnings, feed,
                         generate, ingest, likes, me, pages, payouts, recommend,
                         redirect, site)
from app.seed import seed_if_empty

app = FastAPI(title="Reelie API", version="0.1.0")

# CORS: "*" in dev; a real allow-list in prod (ALLOWED_ORIGINS).
app.add_middleware(
    CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS or ["*"], allow_methods=["*"],
    allow_headers=["*"], allow_credentials=False,
)

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
