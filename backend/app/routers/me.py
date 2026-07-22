"""Account routes: profile, become-creator, favorites."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app import config, notify
from app.auth import current_user
from app.db import get_session
from app.models import (Click, Creator, Favorite, GenerationJob, Page, Payout,
                        Product, Sale, User)
from app.serialize import creator_dict, page_app, user_dict

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return user_dict(user, session)


@router.delete("")
def delete_account(user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Delete the account and all data it owns (App Store / privacy requirement)."""
    session.exec(delete(Favorite).where(Favorite.user_id == user.id))
    handle = user.handle
    if handle:
        page_ids = [p.id for p in session.exec(select(Page).where(Page.handle == handle)).all()]
        for pid in page_ids:
            session.exec(delete(Product).where(Product.page_id == pid))
        session.exec(delete(Page).where(Page.handle == handle))
        session.exec(delete(Sale).where(Sale.handle == handle))
        session.exec(delete(Click).where(Click.handle == handle))
        session.exec(delete(GenerationJob).where(GenerationJob.handle == handle))
        session.exec(delete(Payout).where(Payout.handle == handle))
        creator = session.get(Creator, handle)
        if creator:
            session.delete(creator)
    session.delete(user)
    session.commit()
    return {"ok": True, "deleted": user.id}


class BecomeCreator(BaseModel):
    handle: str
    displayName: str | None = None
    platforms: list[str] | None = None
    instagram: str | None = None       # closed beta: submitted for review
    youtube: str | None = None


@router.post("/become-creator")
def become_creator(body: BecomeCreator, background: BackgroundTasks,
                   user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    """Closed-beta application. Creates the creator in 'pending' — they can sign in
    and see their account, but can't publish until an admin approves them."""
    handle = body.handle.strip().lower().lstrip("@")
    if not handle:
        raise HTTPException(400, "A handle is required.")
    if handle in config.RESERVED_HANDLES or "/" in handle:
        raise HTTPException(409, "That handle isn't available.")
    ig = (body.instagram or "").strip().lstrip("@")
    yt = (body.youtube or "").strip().lstrip("@")
    existing = session.get(Creator, handle)
    is_new = existing is None
    if existing is None:
        session.add(Creator(
            handle=handle,
            display_name=body.displayName or user.display_name,
            avatar_gradient=user.avatar_gradient or config.DEFAULT_AVATAR_GRADIENT,
            platforms=body.platforms or [],
            status="pending", instagram=ig, youtube=yt,
        ))
    elif user.handle != handle:
        raise HTTPException(409, "That handle is taken.")
    else:
        # re-submitting their own application (e.g. adding handles)
        if ig:
            existing.instagram = ig
        if yt:
            existing.youtube = yt
        session.add(existing)
    user.handle = handle
    user.role = "both"
    if body.displayName:
        user.display_name = body.displayName
    session.add(user)
    session.commit()
    session.refresh(user)
    # Notify the team a new creator is awaiting approval (best-effort, off-request).
    if is_new:
        background.add_task(notify.creator_applied, handle,
                            body.displayName or user.display_name or "",
                            user.email or "", ig, yt)
    return user_dict(user, session)


# --- favorites -------------------------------------------------------------
class FavoriteBody(BaseModel):
    kind: str      # "page" | "creator"
    ref: str       # page key "handle/slug" or creator handle


@router.get("/favorites")
def list_favorites(user: User = Depends(current_user), session: Session = Depends(get_session)):
    favs = session.exec(select(Favorite).where(Favorite.user_id == user.id)).all()
    page_refs = [f.ref for f in favs if f.kind == "page"]
    creator_refs = [f.ref for f in favs if f.kind == "creator"]

    pages = []
    for ref in page_refs:
        try:
            handle, slug = ref.split("/", 1)
        except ValueError:
            continue
        page = session.exec(select(Page).where(Page.handle == handle, Page.slug == slug)).first()
        if page:
            prods = session.exec(select(Product).where(Product.page_id == page.id)).all()
            pages.append(page_app(page, prods, session.get(Creator, handle)))

    creators = [creator_dict(c) for h in creator_refs if (c := session.get(Creator, h))]
    return {"pages": pages, "creators": creators,
            "pageKeys": page_refs, "creatorHandles": creator_refs}


@router.post("/favorites")
def add_favorite(body: FavoriteBody, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    if body.kind not in ("page", "creator"):
        raise HTTPException(400, "kind must be 'page' or 'creator'.")
    exists = session.exec(select(Favorite).where(
        Favorite.user_id == user.id, Favorite.kind == body.kind, Favorite.ref == body.ref)).first()
    if not exists:
        session.add(Favorite(user_id=user.id, kind=body.kind, ref=body.ref))
        session.commit()
    return {"ok": True}


@router.delete("/favorites")
def remove_favorite(body: FavoriteBody, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    fav = session.exec(select(Favorite).where(
        Favorite.user_id == user.id, Favorite.kind == body.kind, Favorite.ref == body.ref)).first()
    if fav:
        session.delete(fav)
        session.commit()
    return {"ok": True}
