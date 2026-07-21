"""
Creator page management (owner-only). Backs the studio's edit / archive / delete —
these were local-only in the app; now they persist server-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app.auth import current_user
from app.db import get_session
from app.models import Creator, Page, Product, User
from app.serialize import normalize_product, page_app

router = APIRouter(prefix="/me/pages", tags=["pages"])


def _owned(slug: str, user: User, session: Session) -> Page:
    page = session.exec(select(Page).where(Page.handle == user.handle, Page.slug == slug)).first()
    if not page:
        raise HTTPException(404, "Page not found")
    return page


@router.get("")
def my_pages(user: User = Depends(current_user), session: Session = Depends(get_session)):
    """The creator's own pages — INCLUDING archived (with the flag), for the studio."""
    if not user.handle:
        return []
    creator = session.get(Creator, user.handle)
    pages = session.exec(select(Page).where(Page.handle == user.handle)).all()
    out = []
    # Drafts (awaiting approval) first, then live, then archived.
    for p in sorted(pages, key=lambda x: (x.archived, x.published, x.slug)):
        prods = session.exec(select(Product).where(Product.page_id == p.id)).all()
        payload = page_app(p, prods, creator)
        payload["archived"] = p.archived
        payload["published"] = p.published
        out.append(payload)
    return out


class ProductEdit(BaseModel):
    id: str
    name: str | None = None
    note: str | None = None
    guide: str | None = None


class PageEdit(BaseModel):
    title: str | None = None
    intro: str | None = None
    disclosure: str | None = None
    products: list[ProductEdit] | None = None


@router.patch("/{slug}")
def edit_page(slug: str, body: PageEdit, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    page = _owned(slug, user, session)
    if body.title is not None: page.title = body.title
    if body.intro is not None: page.intro = body.intro
    if body.disclosure is not None: page.disclosure = body.disclosure
    session.add(page)

    if body.products:
        by_id = {p.id: p for p in session.exec(select(Product).where(Product.page_id == page.id)).all()}
        for edit in body.products:
            prod = by_id.get(edit.id)
            if not prod:
                continue
            if edit.name is not None:
                prod.name = edit.name
                prod.product_key = normalize_product(prod.brand, prod.name)
            if edit.note is not None: prod.note = edit.note
            if edit.guide is not None: prod.guide = edit.guide
            session.add(prod)

    session.commit()
    creator = session.get(Creator, user.handle)
    prods = session.exec(select(Product).where(Product.page_id == page.id)).all()
    return page_app(page, prods, creator)


@router.post("/{slug}/publish")
def publish_page(slug: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Creator approves a reviewed draft — it goes live on all public surfaces."""
    page = _owned(slug, user, session)
    page.published = True
    session.add(page); session.commit()
    return {"ok": True, "published": True}


@router.post("/{slug}/unpublish")
def unpublish_page(slug: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Take a live page back to draft (unlisted) — e.g. to make more edits."""
    page = _owned(slug, user, session)
    page.published = False
    session.add(page); session.commit()
    return {"ok": True, "published": False}


@router.post("/{slug}/archive")
def archive_page(slug: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    page = _owned(slug, user, session); page.archived = True
    session.add(page); session.commit()
    return {"ok": True, "archived": True}


@router.post("/{slug}/unarchive")
def unarchive_page(slug: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    page = _owned(slug, user, session); page.archived = False
    session.add(page); session.commit()
    return {"ok": True, "archived": False}


@router.delete("/{slug}")
def delete_page(slug: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    page = _owned(slug, user, session)
    session.exec(delete(Product).where(Product.page_id == page.id))
    session.delete(page)
    session.commit()
    return {"ok": True, "deleted": slug}
