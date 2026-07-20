"""
Guest likes on routines (the Discover feed heart). No account needed — each
browser sends a client id (kept in its localStorage) so a like is deduped and
can be toggled. Counts are shared/real.

  POST /likes/toggle {handle, slug, clientId, liked}  -> {count, liked}
  GET  /likes/{handle}/{slug}                          -> {count}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.models import PageLike

router = APIRouter(prefix="/likes", tags=["likes"])


def _count(session: Session, handle: str, slug: str) -> int:
    return session.exec(
        select(func.count()).select_from(PageLike)
        .where(PageLike.handle == handle, PageLike.slug == slug)).one()


def like_counts(session: Session) -> dict[str, int]:
    """All like counts keyed by 'handle/slug' (for rendering the feed)."""
    rows = session.exec(
        select(PageLike.handle, PageLike.slug, func.count())
        .group_by(PageLike.handle, PageLike.slug)).all()
    return {f"{h}/{s}": n for h, s, n in rows}


class LikeBody(BaseModel):
    handle: str
    slug: str
    clientId: str
    liked: bool


@router.post("/toggle")
def toggle(body: LikeBody, session: Session = Depends(get_session)):
    handle, slug, cid = body.handle, body.slug, body.clientId.strip()
    existing = session.exec(select(PageLike).where(
        PageLike.handle == handle, PageLike.slug == slug,
        PageLike.client_id == cid)).first()
    if body.liked and not existing and cid:
        session.add(PageLike(handle=handle, slug=slug, client_id=cid))
        session.commit()
    elif not body.liked and existing:
        session.delete(existing)
        session.commit()
    return {"count": _count(session, handle, slug), "liked": body.liked}


@router.get("/{handle}/{slug}")
def get_count(handle: str, slug: str, session: Session = Depends(get_session)):
    return {"count": _count(session, handle, slug)}
