"""
Public site (served at reelie.shop) — the crawlable creator pages + SEO files,
rendered dynamically from the database so a page is live the moment it's created.

IMPORTANT: the `/{handle}` and `/{handle}/{slug}` routes are greedy, so this
router MUST be included LAST in main.py (after every API router and /health).
Reserved handles (config.RESERVED_HANDLES) are blocked at creator-claim time so
they can never shadow an API path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlmodel import Session, select

from app import config, public_site
from app.db import get_session
from app.models import Creator, Page, Product

router = APIRouter(tags=["public-site"])


def _rows(session: Session) -> list[dict]:
    """Registry-shaped list of every live page (drives the directory + SEO files)."""
    pages = session.exec(select(Page).where(Page.archived == False)).all()  # noqa: E712
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    out = []
    for pg in pages:
        c = creators.get(pg.handle)
        prods = session.exec(select(Product).where(Product.page_id == pg.id)
                             .order_by(Product.position)).all()
        out.append({
            "handle": pg.handle, "slug": pg.slug,
            "url": public_site.page_url(pg.handle, pg.slug),
            "title": pg.title or pg.slug,
            "creator_name": c.display_name if c else pg.handle,
            "summary": pg.summary or pg.meta or f"{len(prods)} products, each found and linked automatically.",
            "num_products": len(prods),
            "products": [
                {"brand": p.brand, "name": p.name, "retailer": p.retailer,
                 "price_amount": p.price_amount, "price_display": p.price_display,
                 "currency": p.currency}
                for p in prods
            ],
        })
    out.sort(key=lambda r: (r["creator_name"], r["title"]))
    return out


# --- SEO files (domain root) ----------------------------------------------
@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return public_site.robots_txt()


@router.get("/llms.txt", response_class=PlainTextResponse)
def llms(session: Session = Depends(get_session)):
    return public_site.llms_txt(_rows(session))


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)):
    return Response(public_site.sitemap_xml(_rows(session)), media_type="application/xml")


@router.get("/schema-graph.json")
def schema_graph(session: Session = Depends(get_session)):
    return JSONResponse(public_site.site_graph(_rows(session)))


# --- legal ----------------------------------------------------------------
@router.get("/privacy", response_class=HTMLResponse)
def privacy():
    return public_site.privacy_html()


@router.get("/terms", response_class=HTMLResponse)
def terms():
    return public_site.terms_html()


# --- pages ----------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
def directory(session: Session = Depends(get_session)):
    return public_site.directory_html(_rows(session))


@router.get("/{handle}", response_class=HTMLResponse)
def creator_index(handle: str, session: Session = Depends(get_session)):
    if handle in config.RESERVED_HANDLES:
        raise HTTPException(404)
    creator = session.get(Creator, handle)
    if not creator:
        raise HTTPException(404, "No such creator")
    rows = [r for r in _rows(session) if r["handle"] == handle]
    return public_site.creator_html(creator, rows)


@router.get("/{handle}/{slug}", response_class=HTMLResponse)
def routine_page(handle: str, slug: str, session: Session = Depends(get_session)):
    if handle in config.RESERVED_HANDLES:
        raise HTTPException(404)
    page = session.exec(select(Page).where(
        Page.handle == handle, Page.slug == slug, Page.archived == False)).first()  # noqa: E712
    if not page:
        raise HTTPException(404, "No such page")
    creator = session.get(Creator, handle) or Creator(handle=handle, display_name=handle,
                                                       avatar_gradient=config.DEFAULT_AVATAR_GRADIENT)
    products = session.exec(select(Product).where(Product.page_id == page.id)
                            .order_by(Product.position)).all()
    return public_site.page_html(page, creator, products)
