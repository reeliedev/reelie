"""
Creator page management (owner-only). Backs the studio's edit / archive / delete —
these were local-only in the app; now they persist server-side.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app import public_site
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


def _page_faqs(page: Page, creator: Creator | None, products: list[Product]) -> list[dict]:
    """Auto-generated FAQs (read-only) followed by the creator's custom ones."""
    out = [{"q": q, "a": a, "custom": False}
           for q, a in public_site.faqs(page, creator, products)]
    try:
        custom = json.loads(page.custom_faqs) if page.custom_faqs else []
    except Exception:
        custom = []
    out += [{"q": (c.get("q") or "").strip(), "a": (c.get("a") or "").strip(), "custom": True}
            for c in custom if (c.get("q") or "").strip()]
    return out


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
    id: str | None = None          # None → a new product the creator added
    brand: str | None = None
    name: str | None = None
    note: str | None = None
    guide: str | None = None
    url: str | None = None         # creator's own affiliate link (→ link_kind 'own')
    remove: bool = False           # delete this product


class FaqEdit(BaseModel):
    q: str = ""
    a: str = ""


class PageEdit(BaseModel):
    title: str | None = None
    intro: str | None = None
    disclosure: str | None = None
    products: list[ProductEdit] | None = None
    customFaqs: list[FaqEdit] | None = None   # replaces the page's custom-FAQ list


def _apply_link(prod: Product, url: str | None) -> None:
    """A creator-supplied affiliate URL flips the product to an 'own' link; an
    empty value reverts to the default Reelie-resolved link."""
    if url is None:
        return
    url = url.strip()
    if url:
        prod.url = url
        prod.link_kind = "own"
    else:
        prod.url = ""
        prod.link_kind = "reelie"


def _full(page: Page, session: Session, user: User) -> dict:
    creator = session.get(Creator, user.handle)
    prods = session.exec(select(Product).where(Product.page_id == page.id)).all()
    payload = page_app(page, prods, creator)
    payload["archived"] = page.archived
    payload["published"] = page.published
    payload["faqs"] = _page_faqs(page, creator, prods)
    return payload


@router.get("/{slug}")
def get_page(slug: str, user: User = Depends(current_user),
             session: Session = Depends(get_session)):
    """One page in full (products + generated & custom FAQs) — backs the editor."""
    return _full(_owned(slug, user, session), session, user)


@router.patch("/{slug}")
def edit_page(slug: str, body: PageEdit, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    page = _owned(slug, user, session)
    if body.title is not None: page.title = body.title
    if body.intro is not None: page.intro = body.intro
    if body.disclosure is not None: page.disclosure = body.disclosure
    if body.customFaqs is not None:
        page.custom_faqs = json.dumps([{"q": f.q.strip(), "a": f.a.strip()}
                                       for f in body.customFaqs if f.q.strip()])
    session.add(page)

    if body.products is not None:
        by_id = {p.id: p for p in session.exec(select(Product).where(Product.page_id == page.id)).all()}
        next_pos = (max((p.position for p in by_id.values()), default=0)) + 1
        for edit in body.products:
            if edit.remove and edit.id:
                prod = by_id.get(edit.id)
                if prod:
                    session.delete(prod)
                continue
            if edit.id:                                   # update existing
                prod = by_id.get(edit.id)
                if not prod:
                    continue
                if edit.brand is not None: prod.brand = edit.brand
                if edit.name is not None: prod.name = edit.name
                if edit.note is not None: prod.note = edit.note
                if edit.guide is not None: prod.guide = edit.guide
                _apply_link(prod, edit.url)
                prod.product_key = normalize_product(prod.brand, prod.name)
                session.add(prod)
            else:                                         # a new product
                if not ((edit.brand or "").strip() or (edit.name or "").strip()):
                    continue
                prod = Product(page_id=page.id, position=next_pos,
                               brand=(edit.brand or "").strip(), name=(edit.name or "").strip(),
                               note=edit.note, guide=edit.guide,
                               product_key=normalize_product(edit.brand or "", edit.name or ""))
                _apply_link(prod, edit.url)
                session.add(prod)
                next_pos += 1

    session.commit()
    return _full(page, session, user)


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
