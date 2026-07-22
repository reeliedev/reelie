"""
Public site (served at reelie.io) — the crawlable creator pages + SEO files,
rendered dynamically from the database so a page is live the moment it's created.

IMPORTANT: the `/{handle}` and `/{handle}/{slug}` routes are greedy, so this
router MUST be included LAST in main.py (after every API router and /health).
Reserved handles (config.RESERVED_HANDLES) are blocked at creator-claim time so
they can never shadow an API path.
"""

from __future__ import annotations

from fastapi import (APIRouter, BackgroundTasks, Depends, Header, HTTPException,
                     Request, Response)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from sqlmodel import Session, select

from app import analytics, config, landing_page, public_site, reco, studio
from app.db import get_session
from app.models import Creator, Page, Product
from app.routers.likes import like_counts

router = APIRouter(tags=["public-site"])


def _rows(session: Session) -> list[dict]:
    """Registry-shaped list of every live page (drives the directory + SEO files)."""
    pages = session.exec(select(Page).where(Page.archived == False, Page.published == True)).all()  # noqa: E712
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


# --- creator studio (authenticated client-side; JS calls the API) ---------
@router.get("/studio", response_class=HTMLResponse)
def creator_studio():
    return studio.studio_html()


# --- legal ----------------------------------------------------------------
@router.get("/privacy", response_class=HTMLResponse)
def privacy():
    return public_site.privacy_html()


@router.get("/terms", response_class=HTMLResponse)
def terms():
    return public_site.terms_html()


# --- home (marketing landing) + its assets --------------------------------
@router.get("/", response_class=HTMLResponse)
def home():
    return landing_page.home_html()


@router.get("/styles.css")
def landing_css():
    return FileResponse(config.LANDING_DIR / "styles.css", media_type="text/css")


@router.get("/main.js")
def landing_js():
    return FileResponse(config.LANDING_DIR / "main.js", media_type="application/javascript")


# --- discover: vertical Reels/Shorts feed of creator clips ----------------
@router.get("/discover", response_class=HTMLResponse)
def discover(session: Session = Depends(get_session)):
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    pages = session.exec(select(Page).where(Page.archived == False, Page.published == True)).all()  # noqa: E712
    pages.sort(key=lambda p: p.created_at, reverse=True)   # newest first
    counts = like_counts(session)
    items = []
    for page in pages:
        prods = session.exec(select(Product).where(Product.page_id == page.id)
                             .order_by(Product.position)).all()
        lead = next((p for p in prods if p.clip_url), None)
        if not lead:
            continue    # feed is video-first — only routines with a clip
        c = creators.get(page.handle)
        grad = (c.avatar_gradient if c else None) or config.DEFAULT_AVATAR_GRADIENT
        amounts = [p.price_amount for p in prods if p.price_amount is not None]
        total = public_site._money(sum(amounts), prods[0].currency) if amounts else ""
        items.append({
            "clip_url": lead.clip_url, "clip_poster": lead.clip_poster, "emoji": lead.emoji,
            "creator": {"handle": page.handle, "name": c.display_name if c else page.handle,
                        "g0": grad[0], "g1": grad[1] if len(grad) > 1 else grad[0],
                        "platforms": c.platforms if c else []},
            "page_url": public_site.page_url(page.handle, page.slug),
            "page_title": page.title,
            "handle": page.handle, "slug": page.slug,
            "likes": counts.get(f"{page.handle}/{page.slug}", 0),
            "total_display": total,
            "products": [
                {"brand": p.brand, "name": p.name, "emoji": p.emoji,
                 "price_display": p.price_display or (public_site._money(p.price_amount, p.currency)
                                                      if p.price_amount is not None else ""),
                 "shop_url": public_site.shop_url(page.handle, page.slug, p.position)}
                for p in prods
            ],
        })
    return public_site.discover_feed_html(items)


# --- full routine directory (kept for completeness) -----------------------
@router.get("/browse", response_class=HTMLResponse)
def browse(session: Session = Depends(get_session)):
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
def routine_page(handle: str, slug: str, request: Request, background: BackgroundTasks,
                 user_agent: str = Header(default=""), referer: str = Header(default=""),
                 session: Session = Depends(get_session)):
    if handle in config.RESERVED_HANDLES:
        raise HTTPException(404)
    page = session.exec(select(Page).where(
        Page.handle == handle, Page.slug == slug, Page.archived == False)).first()  # noqa: E712
    if not page:
        raise HTTPException(404, "No such page")
    # Log the view off-request (real IP is the first X-Forwarded-For hop on Render).
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else ""))
    background.add_task(analytics.log_view, handle, slug, ip, user_agent, referer)
    creator = session.get(Creator, handle) or Creator(handle=handle, display_name=handle,
                                                       avatar_gradient=config.DEFAULT_AVATAR_GRADIENT)
    products = session.exec(select(Product).where(Product.page_id == page.id)
                            .order_by(Product.position)).all()
    similar, also = reco.page_reco(session, handle, products)
    return public_site.page_html(page, creator, products, similar=similar, also=also)
