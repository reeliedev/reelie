"""
Earnings aggregation — the real numbers behind the creator dashboard, built from
Click + Sale events (replaces the app's hardcoded strings).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.db import get_session
from app.models import Click, Page, Sale

router = APIRouter(prefix="/creators", tags=["earnings"])


@router.get("/{handle}/earnings")
def earnings(handle: str, session: Session = Depends(get_session)):
    sales = session.exec(select(Sale).where(Sale.handle == handle)).all()
    now = datetime.now(timezone.utc)

    def _naive(d: datetime) -> datetime:
        return d.replace(tzinfo=None) if d.tzinfo else d

    week_cut = _naive(now - timedelta(days=7))
    month_cut = _naive(now - timedelta(days=30))

    def total(items) -> float:
        return round(sum(s.value for s in items), 2)

    lifetime = total(sales)
    this_week = total([s for s in sales if _naive(s.date) >= week_cut])
    this_month = total([s for s in sales if _naive(s.date) >= month_cut])
    pending = total([s for s in sales if s.state == "pending"])
    ready = total([s for s in sales if s.state == "ready"])
    paid = total([s for s in sales if s.state == "paid"])

    clicks = session.exec(select(func.count()).select_from(Click).where(Click.handle == handle)).one()

    # per-page rollup
    titles = {p.slug: p.title for p in session.exec(select(Page).where(Page.handle == handle)).all()}
    by_page: dict[str, float] = {}
    for s in sales:
        by_page[s.page_slug] = round(by_page.get(s.page_slug, 0) + s.value, 2)
    by_page_list = sorted(
        [{"slug": k, "title": titles.get(k, k), "total": v} for k, v in by_page.items()],
        key=lambda x: -x["total"])

    recent = sorted(sales, key=lambda s: s.date, reverse=True)[:8]
    recent_sales = [{
        "name": s.name,
        "emoji": s.emoji,
        "page": f"{titles.get(s.page_slug, s.page_slug)} · {s.retailer}".strip(" ·"),
        "value": s.value,
        "state": "ready" if s.state in ("ready", "paid") else "pending",
    } for s in recent]

    return {
        "handle": handle,
        "lifetime": lifetime,
        "thisWeek": this_week,
        "thisMonth": this_month,
        "pending": pending,
        "ready": ready,
        "readyToPayout": ready,
        "paidSoFar": paid,
        "clicks": clicks,
        "conversions": len(sales),
        "byPage": by_page_list,
        "recentSales": recent_sales,
    }
