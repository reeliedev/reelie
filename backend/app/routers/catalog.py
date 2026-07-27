"""Public catalogue: creators + routines (the browsable corpus)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Creator, Page, Product
from app.serialize import creator_dict, page_app

router = APIRouter(tags=["catalog"])


def _page_payload(page: Page, session: Session) -> dict:
    prods = session.exec(select(Product).where(Product.page_id == page.id)).all()
    return page_app(page, prods, session.get(Creator, page.handle))


@router.get("/creators")
def list_creators(session: Session = Depends(get_session)):
    return [creator_dict(c) for c in session.exec(select(Creator)).all()]


@router.get("/creators/{handle}")
def get_creator(handle: str, session: Session = Depends(get_session)):
    c = session.get(Creator, handle)
    if not c:
        raise HTTPException(404, "Creator not found")
    return creator_dict(c)


@router.get("/creators/{handle}/routines")
def creator_routines(handle: str, session: Session = Depends(get_session)):
    pages = session.exec(select(Page).where(Page.handle == handle, Page.archived == False, Page.published == True)).all()  # noqa: E712
    return [_page_payload(p, session) for p in sorted(pages, key=lambda x: x.slug)]


@router.get("/search")
def search(q: str = "", session: Session = Depends(get_session)):
    """Search published routines + creators. Matches ALL query tokens against a
    page's title, creator, handle, and its products' brand/name/retailer."""
    tokens = [t for t in (q or "").strip().lower().split() if t]
    if not tokens:
        return {"creators": [], "routines": []}
    creators = {c.handle: c for c in session.exec(select(Creator)).all()}
    pages = session.exec(select(Page).where(Page.archived == False, Page.published == True)).all()  # noqa: E712
    routines = []
    for p in sorted(pages, key=lambda x: (x.handle, x.slug)):
        prods = session.exec(select(Product).where(Product.page_id == p.id)).all()
        c = creators.get(p.handle)
        hay = " ".join([p.title or "", p.handle or "", (c.display_name if c else "")]
                       + [f"{pr.brand} {pr.name} {pr.retailer or ''}" for pr in prods]).lower()
        if all(t in hay for t in tokens):
            routines.append(page_app(p, prods, c))
    matching_creators = [creator_dict(c) for c in creators.values()
                         if all(t in f"{c.display_name} {c.handle}".lower() for t in tokens)]
    return {"creators": matching_creators[:20], "routines": routines[:40]}


@router.get("/routines")
def all_routines(session: Session = Depends(get_session)):
    pages = session.exec(select(Page).where(Page.archived == False, Page.published == True)).all()  # noqa: E712
    return [_page_payload(p, session) for p in sorted(pages, key=lambda x: (x.handle, x.slug))]


@router.get("/routines/{handle}/{slug}")
def get_routine(handle: str, slug: str, session: Session = Depends(get_session)):
    page = session.exec(select(Page).where(
        Page.handle == handle, Page.slug == slug, Page.archived == False, Page.published == True)).first()  # noqa: E712
    if not page:
        raise HTTPException(404, "Routine not found")
    return _page_payload(page, session)
