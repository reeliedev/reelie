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


def _r2_upload(local_path: Path, key: str, content_type: str) -> str:
    """Upload a file to object storage (R2/S3) and return its public URL."""
    import boto3
    from botocore.config import Config as BotoConfig
    client = boto3.client(
        "s3", endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("STORAGE_REGION", "auto"),
        config=BotoConfig(signature_version="s3v4"))
    client.upload_file(str(local_path), os.environ["STORAGE_BUCKET"], key,
                       ExtraArgs={"ContentType": content_type})
    return os.environ["STORAGE_PUBLIC_URL"].rstrip("/") + "/" + key


def _media_clip(page: Page, p) -> tuple[str, str]:
    """Host this product's clip + poster and return their absolute URLs. Uploads
    to object storage (R2/S3) when STORAGE_* is set (prod), else copies to the
    local media root (dev). Empty strings → emoji fallback."""
    if not p.clip:
        return "", ""
    src_dir = config.OUT_PUBLIC / page.handle / page.path_slug
    use_r2 = bool(os.environ.get("STORAGE_ENDPOINT") and os.environ.get("STORAGE_BUCKET")
                  and os.environ.get("STORAGE_PUBLIC_URL"))
    media_root = os.environ.get("REELIE_MEDIA_ROOT")
    base = os.environ.get("REELIE_API_URL", "").rstrip("/")

    def host(rel: str | None, ctype: str) -> str:
        if not rel:
            return ""
        src = src_dir / rel
        if not src.exists():
            return ""
        key = f"clips/{page.handle}/{page.path_slug}/{rel}"
        if use_r2:
            return _r2_upload(src, key, ctype)
        if media_root and base:
            dst = Path(media_root) / page.handle / page.path_slug / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            return f"{base}/media/{page.handle}/{page.path_slug}/{rel}"
        return ""

    return host(p.clip, "video/mp4"), host(p.clip_poster, "image/jpeg")


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
        # Self-serve pages land as drafts for the creator to review + approve.
        # Set REELIE_DRAFT=0 to publish directly (e.g. trusted batch runs).
        "draft": os.environ.get("REELIE_DRAFT", "1") != "0",
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
    headers = {"Content-Type": "application/json"}
    tok = os.environ.get("REELIE_INGEST_TOKEN")
    if tok:
        headers["X-Ingest-Token"] = tok
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.load(resp)
        return f"synced → {url}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"skipped (API unreachable: {e})"
