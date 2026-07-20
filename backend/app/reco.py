"""
Content-based recommendations over the database — pure joins on shared brands
and shared products (no ML). Mirrors the offline generator's recommend.py but
sources from SQLModel rows.

  similar_creators(handle)     -> creators ranked by shared-brand overlap (Jaccard)
  creators_using(product_key)  -> creators whose routines include that product

Needs a multi-creator corpus to return signal (the seed corpus has one).
"""

from __future__ import annotations

from sqlmodel import Session, select

from app import config
from app.models import Creator, Page, Product


def _creator_index(session: Session) -> dict[str, dict]:
    """One aggregate record per creator: brand set + product-key set."""
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    live_pages = {p.id: p for p in session.exec(select(Page).where(Page.archived == False)).all()}  # noqa: E712
    idx: dict[str, dict] = {}
    for c in creators.values():
        idx[c.handle] = {"handle": c.handle, "name": c.display_name,
                         "avatar_gradient": c.avatar_gradient or config.DEFAULT_AVATAR_GRADIENT,
                         "brands": set(), "product_keys": set()}
    for p in session.exec(select(Product)).all():
        page = live_pages.get(p.page_id)
        if not page:
            continue
        rec = idx.get(page.handle)
        if not rec:
            continue
        if p.brand:
            rec["brands"].add(p.brand)
        if p.product_key:
            rec["product_keys"].add(p.product_key)
    return idx


def similar_creators(session: Session, handle: str, limit: int = 6) -> list[dict]:
    idx = _creator_index(session)
    me = idx.get(handle)
    if not me or not me["brands"]:
        return []
    out = []
    for h, c in idx.items():
        if h == handle:
            continue
        shared = me["brands"] & c["brands"]
        if not shared:
            continue
        score = len(shared) / len(me["brands"] | c["brands"])
        out.append({"handle": h, "name": c["name"], "avatar_gradient": c["avatar_gradient"],
                    "reason": "Also uses " + ", ".join(sorted(shared)[:2]), "score": score})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def creators_using(session: Session, product_key: str, exclude_handle: str | None = None,
                   limit: int = 4) -> list[dict]:
    if not product_key:
        return []
    return _using(_creator_index(session), product_key, exclude_handle, limit)


def _using(idx: dict, product_key: str, exclude_handle: str | None, limit: int) -> list[dict]:
    out = []
    for h, c in idx.items():
        if h == exclude_handle or product_key not in c["product_keys"]:
            continue
        out.append({"handle": h, "name": c["name"], "avatar_gradient": c["avatar_gradient"]})
    return out[:limit]


def page_reco(session: Session, handle: str, products) -> tuple[list[dict], dict[int, list[dict]]]:
    """Both reco surfaces for a routine page, sharing one index build:
    (similar creators, {product.position: [creators also using it]})."""
    idx = _creator_index(session)
    me = idx.get(handle)
    similar: list[dict] = []
    if me and me["brands"]:
        for h, c in idx.items():
            if h == handle:
                continue
            shared = me["brands"] & c["brands"]
            if not shared:
                continue
            similar.append({"handle": h, "name": c["name"], "avatar_gradient": c["avatar_gradient"],
                            "reason": "Also uses " + ", ".join(sorted(shared)[:2]),
                            "score": len(shared) / len(me["brands"] | c["brands"])})
        similar.sort(key=lambda x: -x["score"])
        similar = similar[:6]
    also = {p.position: _using(idx, p.product_key, handle, 4) for p in products}
    return similar, also
