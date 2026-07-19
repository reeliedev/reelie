"""
Emit the app-facing JSON. This is a stable, camelCase projection of the canonical
Page that decodes 1:1 into the Swift `GeneratedPageDTO` (see the iOS app's
Models/GeneratedPage.swift). Keeping it a projection (not the full canonical model)
decouples the app from generator-internal fields.
"""

from __future__ import annotations

import json
from pathlib import Path

from models import Page


def to_app_dict(page: Page) -> dict:
    return {
        "id": page.id,
        "title": page.title,
        "emoji": page.emoji,
        "slug": page.slug,
        "customSlug": page.custom_slug,
        "meta": page.meta,
        "handle": page.handle,
        "creatorName": page.creator.display_name,
        "platforms": page.creator.platforms,
        "publicURL": page.url,
        "intro": page.intro,
        "disclosure": page.disclosure,
        "products": [
            {
                "id": p.id,
                "position": p.position,
                "brand": p.brand,
                "name": p.name,
                "emoji": p.emoji,
                "variant": p.variant,
                "evidence": p.evidence,
                "timestamp": p.timestamp,
                "note": p.note,
                "guide": p.guide,
                "retailer": p.retailer,
                "priceDisplay": p.price.display if p.price else None,
                "priceAmount": p.price.amount if p.price else None,
                "currency": p.price.currency if p.price else None,
                "priceEstimated": p.price.estimated if p.price else None,
                "linkKind": p.link.kind,
                "rate": p.link.rate,
                "ownLabel": p.link.label,
                "url": p.link.url,
            }
            for p in page.products
        ],
    }


def write_app_json(page: Page, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(to_app_dict(page), indent=2, ensure_ascii=False))
    return out_path
