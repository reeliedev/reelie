"""
Optional backend sync. When REELIE_API_URL is set, POST a generated page to the
API's /ingest/page so the API is the source of truth (out/pages.json stays as a
local cache). Never fatal — a down/absent API just logs and continues. Uses only
the stdlib (urllib) so the generator gains no dependency.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import config
from models import Page


def _media_clip(page: Page, p) -> tuple[str, str]:
    """If clip hosting is on (REELIE_MEDIA_ROOT set) and this product has a clip,
    copy the clip + poster into the media root and return their absolute URLs.
    Otherwise returns empty strings (emoji fallback)."""
    media_root = os.environ.get("REELIE_MEDIA_ROOT")
    base = os.environ.get("REELIE_API_URL", "").rstrip("/")
    if not (media_root and base and p.clip):
        return "", ""
    src_dir = config.OUT_PUBLIC / page.handle / page.path_slug
    dest_dir = Path(media_root) / page.handle / page.path_slug

    def cp(rel: str | None) -> str:
        if not rel:
            return ""
        src = src_dir / rel
        if not src.exists():
            return ""
        dst = dest_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return f"{base}/media/{page.handle}/{page.path_slug}/{rel}"

    return cp(p.clip), cp(p.clip_poster)


def _payload(page: Page) -> dict:
    return {
        "handle": page.handle,
        "creatorName": page.creator.display_name,
        "avatarGradient": page.creator.avatar_gradient,
        "platforms": page.creator.platforms,
        "slug": page.path_slug,
        "title": page.title,
        "emoji": page.emoji,
        "meta": page.meta,
        "intro": page.intro,
        "summary": page.summary,
        "disclosure": page.disclosure,
        "videoId": page.video_id,
        "products": [
            {
                "position": p.position, "brand": p.brand, "name": p.name, "emoji": p.emoji,
                "variant": p.variant, "evidence": p.evidence, "timestamp": p.timestamp,
                "note": p.note, "guide": p.guide, "retailer": p.retailer,
                "priceDisplay": p.price.display if p.price else None,
                "priceAmount": p.price.amount if p.price else None,
                "currency": p.price.currency if p.price else "USD",
                "priceEstimated": p.price.estimated if p.price else True,
                "linkKind": p.link.kind, "rate": p.link.rate, "ownLabel": p.link.label,
                "url": p.link.url,
                **(lambda c: {"clipUrl": c[0], "clipPoster": c[1]})(_media_clip(page, p)),
            }
            for p in page.products
        ],
    }


def sync_page(page: Page) -> str | None:
    """POST the page to the API if REELIE_API_URL is set. Returns a status string
    for the CLI, or None if syncing is disabled."""
    base = os.environ.get("REELIE_API_URL")
    if not base:
        return None
    url = base.rstrip("/") + "/ingest/page"
    data = json.dumps(_payload(page)).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.load(resp)
        return f"synced → {url}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"skipped (API unreachable: {e})"
