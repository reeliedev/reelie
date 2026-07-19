"""
Content-based recommendations over the DB — the same joins the static generator
does, now served: similar creators (shared-brand Jaccard) and creators-using
(shared normalized product). Cheap enough to compute per request at this scale;
becomes a served/precomputed index in a later phase.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import Creator, Page, Product


def _brands_by_handle(session: Session) -> dict[str, set[str]]:
    rows = session.exec(select(Page.handle, Product.brand).join(Product, Product.page_id == Page.id)).all()
    out: dict[str, set[str]] = {}
    for handle, brand in rows:
        if brand:
            out.setdefault(handle, set()).add(brand)
    return out


def similar_creators(handle: str, session: Session, limit: int = 6) -> list[dict]:
    brands = _brands_by_handle(session)
    mine = brands.get(handle, set())
    if not mine:
        return []
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    scored = []
    for h, other in brands.items():
        if h == handle or not other:
            continue
        shared = mine & other
        if not shared:
            continue
        score = len(shared) / len(mine | other)
        c = creators.get(h)
        scored.append({
            "handle": h,
            "displayName": c.display_name if c else h,
            "avatarGradient": (c.avatar_gradient if c else []) or [],
            "reason": "Also uses " + ", ".join(sorted(shared)[:2]),
            "score": round(score, 4),
        })
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def creators_using(product_key: str, session: Session,
                   exclude_handle: str | None = None, limit: int = 6) -> list[dict]:
    rows = session.exec(
        select(Page.handle).join(Product, Product.page_id == Page.id)
        .where(Product.product_key == product_key)
    ).all()
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    seen, out = set(), []
    for handle in rows:
        if handle == exclude_handle or handle in seen:
            continue
        seen.add(handle)
        c = creators.get(handle)
        out.append({
            "handle": handle,
            "displayName": c.display_name if c else handle,
            "avatarGradient": (c.avatar_gradient if c else []) or [],
        })
        if len(out) >= limit:
            break
    return out
