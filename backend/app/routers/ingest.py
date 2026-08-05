"""
Ingest route — the page-generator POSTs a generated page here so the API becomes
the source of truth (the generator keeps out/pages.json as a local cache). Open
for local dev; would be a creator-authenticated write in production.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app import awin_feed, config, product_search
from app.db import engine, get_session
from app.models import Creator, Page, Product
from app.serialize import normalize_product


def _resolve_links(page_id: str) -> None:
    """Background: turn each product's search link into a direct buy link, skipping
    creator-set 'own' links. Two steps, best-first:
      1. Our approved AWIN merchants' catalogues (awin_feed) — a verified, in-stock,
         already-tracked deep link. Preferred: we know it's carried and it earns.
      2. DataForSEO product search — a direct link for anything the feeds don't carry.
    Each is a no-op without its config, so with neither set this leaves search links."""
    if not (awin_feed.enabled() or product_search.enabled()):
        return
    with Session(engine) as s:
        prods = s.exec(select(Product).where(Product.page_id == page_id)).all()
        targets = [p for p in prods if p.link_kind != "own"]

        # Step 1 — feed match against our merchants' catalogues.
        remaining = targets
        if awin_feed.enabled():
            remaining = []
            for p in targets:
                m = awin_feed.match(p.brand, p.name)
                if m:
                    p.url, p.link_kind, p.retailer = m.deep_link, "auto", m.merchant_name
                    s.add(p)
                else:
                    remaining.append(p)
            s.commit()

        # Step 2 — search fallback for whatever the feeds didn't carry.
        if product_search.enabled() and remaining:
            resolved = product_search.resolve_batch(
                [{"id": p.id, "brand": p.brand, "name": p.name, "variant": p.variant or ""}
                 for p in remaining])
            for p in remaining:
                r = resolved.get(p.id)
                if r:
                    p.url, p.link_kind = r["url"], "auto"
                    s.add(p)
            s.commit()

router = APIRouter(prefix="/ingest", tags=["ingest"])


def require_ingest_token(x_ingest_token: str = Header(default="")) -> None:
    """Only the generator/worker (which holds INGEST_TOKEN) may publish pages."""
    if not config.INGEST_TOKEN or not hmac.compare_digest(x_ingest_token, config.INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


class IngestProduct(BaseModel):
    position: int = 0
    brand: str = ""
    name: str = ""
    emoji: str = "🛍️"
    variant: str | None = None
    evidence: str = "shown"
    timestamp: str = "0:00"
    note: str | None = None
    guide: str | None = None
    retailer: str = ""
    priceDisplay: str | None = None
    priceAmount: float | None = None
    currency: str = "USD"
    priceEstimated: bool = True
    linkKind: str = "reelie"
    rate: int | None = None
    ownLabel: str | None = None
    url: str = ""
    clipUrl: str = ""
    clipPoster: str = ""


class IngestPage(BaseModel):
    handle: str
    creatorName: str = ""
    avatarGradient: list[str] | None = None
    platforms: list[str] | None = None
    slug: str
    title: str = ""
    emoji: str = "🎬"
    meta: str = ""
    intro: str = ""
    summary: str = ""
    disclosure: str = ""
    videoId: str = ""
    draft: bool = False          # self-serve generation sends True → needs approval
    products: list[IngestProduct] = []


@router.post("/page", dependencies=[Depends(require_ingest_token)])
def ingest_page(body: IngestPage, background: BackgroundTasks,
                session: Session = Depends(get_session)):
    # upsert creator
    creator = session.get(Creator, body.handle)
    if creator is None:
        creator = Creator(handle=body.handle, display_name=body.creatorName or body.handle,
                           avatar_gradient=body.avatarGradient or config.DEFAULT_AVATAR_GRADIENT,
                           platforms=body.platforms or [])
        session.add(creator)
    else:
        if body.creatorName:
            creator.display_name = body.creatorName
        if body.avatarGradient:
            creator.avatar_gradient = body.avatarGradient
        if body.platforms:
            creator.platforms = body.platforms
        session.add(creator)

    # upsert page (replace products)
    page = session.exec(select(Page).where(Page.handle == body.handle, Page.slug == body.slug)).first()
    if page is None:
        page = Page(handle=body.handle, slug=body.slug)
    page.title, page.emoji, page.meta = body.title, body.emoji, body.meta
    page.intro, page.summary, page.disclosure = body.intro, body.summary, body.disclosure
    page.video_id = body.videoId
    # A draft generation lands unpublished for review; re-generating a page sends
    # it back to draft so the new version is re-approved before going live.
    if body.draft:
        page.published = False
    session.add(page)
    session.flush()

    session.exec(delete(Product).where(Product.page_id == page.id))
    for p in body.products:
        session.add(Product(
            page_id=page.id, position=p.position, brand=p.brand, name=p.name, emoji=p.emoji,
            variant=p.variant, evidence=p.evidence, timestamp=p.timestamp, note=p.note, guide=p.guide,
            retailer=p.retailer, price_display=p.priceDisplay, price_amount=p.priceAmount,
            currency=p.currency, price_estimated=p.priceEstimated, link_kind=p.linkKind,
            rate=p.rate, own_label=p.ownLabel, url=p.url,
            clip_url=p.clipUrl, clip_poster=p.clipPoster,
            product_key=normalize_product(p.brand, p.name)))

    session.commit()
    # Upgrade search links to direct buy links off-request (draft is already saved).
    background.add_task(_resolve_links, page.id)
    return {"ok": True, "handle": body.handle, "slug": body.slug, "products": len(body.products)}
