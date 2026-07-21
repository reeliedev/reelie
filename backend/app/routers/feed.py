"""
Discover feed (JSON) — the reel items the iOS app renders as a native vertical
video feed. Same content as the web /discover Reels feed: one reel per routine
that has a clip, newest first, with the creator + shoppable products.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import config, public_site
from app.db import get_session
from app.models import Creator, Page, Product
from app.routers.likes import like_counts

router = APIRouter(tags=["feed"])


@router.get("/feed")
def feed(session: Session = Depends(get_session)):
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    pages = session.exec(select(Page).where(Page.archived == False, Page.published == True)).all()  # noqa: E712
    pages.sort(key=lambda p: p.created_at, reverse=True)
    counts = like_counts(session)
    out = []
    for page in pages:
        prods = session.exec(select(Product).where(Product.page_id == page.id)
                             .order_by(Product.position)).all()
        lead = next((p for p in prods if p.clip_url), None)
        if not lead:
            continue    # video-first: only routines with a clip
        c = creators.get(page.handle)
        grad = (c.avatar_gradient if c else None) or config.DEFAULT_AVATAR_GRADIENT
        out.append({
            "clipUrl": lead.clip_url,
            "poster": lead.clip_poster,
            "creator": {"name": c.display_name if c else page.handle,
                        "handle": page.handle, "avatarGradient": grad},
            "handle": page.handle, "slug": page.slug, "title": page.title,
            "caption": lead.guide or lead.note or page.title,
            "likes": counts.get(f"{page.handle}/{page.slug}", 0),
            "likeKey": f"{page.handle}/{page.slug}",
            "products": [{
                "brand": p.brand, "name": p.name, "emoji": p.emoji,
                "priceDisplay": p.price_display or (public_site._money(p.price_amount, p.currency)
                                                    if p.price_amount is not None else ""),
                "shopUrl": public_site.shop_url(page.handle, page.slug, p.position),
            } for p in prods],
        })
    return out
