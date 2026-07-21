"""
Ingest route — the page-generator POSTs a generated page here so the API becomes
the source of truth (the generator keeps out/pages.json as a local cache). Open
for local dev; would be a creator-authenticated write in production.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app import config
from app.db import get_session
from app.models import Creator, Page, Product
from app.serialize import normalize_product

router = APIRouter(prefix="/ingest", tags=["ingest"])


def require_ingest_token(x_ingest_token: str = Header(default="")) -> None:
    """Only the generator/worker (which holds INGEST_TOKEN) may publish pages."""
    if not config.INGEST_TOKEN or x_ingest_token != config.INGEST_TOKEN:
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
def ingest_page(body: IngestPage, session: Session = Depends(get_session)):
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
    return {"ok": True, "handle": body.handle, "slug": body.slug, "products": len(body.products)}
