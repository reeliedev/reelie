"""
Monetization core (Phase 3):
- GET  /r/{handle}/{slug}/{nn}  — the affiliate redirect. Logs a Click, resolves
  a destination via the AffiliateNetwork (stubbed → retailer search), 302s there.
- POST /r/postback             — a conversion report. In prod this is the affiliate
  network's server-to-server postback; here it's how a sale is recorded.
- POST /r/simulate             — dev helper: fabricate clicks + a few conversions
  so the earnings dashboard has live movement to demo.
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app import config
from app.db import get_session
from app.integrations import affiliate
from app.models import Click, Page, Product, Sale
from app.routers.ingest import require_ingest_token

router = APIRouter(prefix="/r", tags=["redirect"])


def _product_at(session: Session, handle: str, slug: str, position: int) -> tuple[Page, Product]:
    page = session.exec(select(Page).where(Page.handle == handle, Page.slug == slug)).first()
    if not page:
        raise HTTPException(404, "Page not found")
    product = session.exec(select(Product).where(
        Product.page_id == page.id, Product.position == position)).first()
    if not product:
        raise HTTPException(404, "Product not found")
    return page, product


@router.get("/{handle}/{slug}/{nn}")
def redirect(handle: str, slug: str, nn: str, request: Request,
             session: Session = Depends(get_session),
             user_agent: str = Header(default=""), referer: str = Header(default="")):
    try:
        position = int(nn)
    except ValueError:
        raise HTTPException(400, "Bad product index")
    page, product = _product_at(session, handle, slug, position)

    session.add(Click(
        handle=handle, page_slug=slug, position=position, product_id=product.id,
        session=request.query_params.get("s"), user_agent=user_agent, referer=referer))
    session.commit()

    dest = affiliate.resolve_link(product.brand, product.name, product.retailer)["url"]
    return RedirectResponse(dest, status_code=302)


class Postback(BaseModel):
    handle: str
    slug: str
    position: int
    orderAmount: float
    network: str = "mock"
    clickId: str | None = None


# Conversion callback. Protected by the internal token for now (records earnings,
# so it must not be open). When a real affiliate network is wired, replace this
# with the network's signature verification.
@router.post("/postback", dependencies=[Depends(require_ingest_token)])
def postback(body: Postback, session: Session = Depends(get_session)):
    page, product = _product_at(session, body.handle, body.slug, body.position)
    rate = product.rate or 8
    commission = round(body.orderAmount * rate / 100.0, 2)
    sale = Sale(
        handle=body.handle, page_slug=body.slug, position=body.position,
        name=f"{product.brand} {product.name}".strip(), emoji=product.emoji,
        value=commission, order_amount=body.orderAmount, retailer=product.retailer,
        network=body.network, click_id=body.clickId, state="pending")
    session.add(sale)
    session.commit()
    return {"ok": True, "commission": commission, "state": "pending"}


class Simulate(BaseModel):
    handle: str
    clicks: int = 40
    conversions: int = 6


@router.post("/simulate")
def simulate(body: Simulate, session: Session = Depends(get_session)):
    """Dev-only: generate believable click + conversion traffic for a creator."""
    if config.IS_PROD:
        raise HTTPException(404)   # never expose fabricated traffic in production
    products = session.exec(
        select(Product, Page).join(Page, Product.page_id == Page.id)
        .where(Page.handle == body.handle)).all()
    if not products:
        raise HTTPException(404, "No products for that creator")

    made_clicks = 0
    for _ in range(body.clicks):
        product, page = random.choice(products)
        session.add(Click(handle=body.handle, page_slug=page.slug,
                           position=product.position, product_id=product.id,
                           user_agent="sim"))
        made_clicks += 1

    made_sales = 0
    for _ in range(body.conversions):
        product, page = random.choice(products)
        amount = round(random.uniform(12, 60), 2)
        rate = product.rate or 8
        session.add(Sale(
            handle=body.handle, page_slug=page.slug, position=product.position,
            name=f"{product.brand} {product.name}".strip(), emoji=product.emoji,
            value=round(amount * rate / 100.0, 2), order_amount=amount,
            retailer=product.retailer, network="mock",
            state=random.choice(["pending", "ready", "ready", "paid"])))
        made_sales += 1

    session.commit()
    return {"ok": True, "clicks": made_clicks, "conversions": made_sales}
