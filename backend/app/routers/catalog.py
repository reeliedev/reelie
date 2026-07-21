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
