"""
Closed-beta admin console. Review creator applications and approve/reject them.
Gated by ADMIN_TOKEN (sent as X-Admin-Token). GET /admin serves a small review
page whose JS prompts for the token and calls these endpoints.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app import admin_page, config, notify
from app.db import get_session
from app.models import (Click, Creator, Favorite, GenerationJob, Page, PageLike,
                        PageView, Payout, Product, Sale, SocialConnection, User, _now)

router = APIRouter(tags=["admin"])


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not config.ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


class Wipe(BaseModel):
    confirm: str = ""


@router.post("/admin/wipe", dependencies=[Depends(require_admin)])
def wipe_accounts(body: Wipe, session: Session = Depends(get_session)):
    """Delete ALL accounts + their content — a clean slate for beta re-testing.
    NB: this only clears Reelie's own DB. Supabase Auth users live in Supabase;
    delete those in the Supabase dashboard (Authentication → Users) so the same
    email can sign up fresh. Guarded by the exact confirm string."""
    if body.confirm != "DELETE ALL":
        raise HTTPException(400, 'To wipe, send {"confirm": "DELETE ALL"}.')
    counts = {}
    # children first to respect foreign keys
    for Model in (Click, Sale, Payout, Favorite, PageLike, SocialConnection,
                  Product, Page, GenerationJob, Creator, User):
        counts[Model.__name__] = len(session.exec(select(Model)).all())
        session.exec(delete(Model))
    session.commit()
    return {"ok": True, "deleted": counts}


@router.get("/admin", response_class=HTMLResponse)
def admin_console():
    return admin_page.admin_html()


@router.get("/admin/applications", dependencies=[Depends(require_admin)])
def list_applications(status: str | None = None, session: Session = Depends(get_session)):
    q = select(Creator)
    if status:
        q = q.where(Creator.status == status)
    creators = session.exec(q).all()
    emails = {u.handle: u.email for u in session.exec(select(User).where(User.handle != None)).all()}  # noqa: E711
    rows = [{
        "handle": c.handle, "displayName": c.display_name, "status": c.status,
        "instagram": c.instagram, "youtube": c.youtube,
        "email": emails.get(c.handle, ""),
        "appliedAt": c.applied_at.isoformat() if c.applied_at else None,
    } for c in creators]
    # pending first, then newest
    rows.sort(key=lambda r: (r["status"] != "pending", r["appliedAt"] or ""), reverse=False)
    return rows


def _set_status(handle: str, status: str, session: Session) -> dict:
    c = session.get(Creator, handle)
    if not c:
        raise HTTPException(404, "No such creator")
    c.status = status
    c.reviewed_at = _now()
    session.add(c)
    session.commit()
    return {"ok": True, "handle": handle, "status": status}


@router.post("/admin/applications/{handle}/approve", dependencies=[Depends(require_admin)])
def approve(handle: str, background: BackgroundTasks, session: Session = Depends(get_session)):
    c = session.get(Creator, handle)
    was_approved = bool(c and c.status == "approved")
    result = _set_status(handle, "approved", session)
    # Only email on a real pending/rejected → approved transition, so re-clicking
    # approve on an already-approved creator doesn't re-send the welcome.
    if not was_approved:
        user = session.exec(select(User).where(User.handle == handle)).first()
        if user and user.email:
            background.add_task(notify.creator_approved, user.email, c.display_name, handle)
    return result


@router.post("/admin/applications/{handle}/reject", dependencies=[Depends(require_admin)])
def reject(handle: str, session: Session = Depends(get_session)):
    return _set_status(handle, "rejected", session)


@router.post("/admin/applications/{handle}/delete", dependencies=[Depends(require_admin)])
def delete_creator(handle: str, session: Session = Depends(get_session)):
    """Permanently remove one creator and all their data — for beta cleanup.
    NB: like /admin/wipe, this only clears Reelie's DB. The Supabase Auth user
    still exists; delete it in Supabase (Authentication → Users) to free the
    email for a fresh signup."""
    c = session.get(Creator, handle)
    if not c:
        raise HTTPException(404, "No such creator")
    page_ids = [p.id for p in session.exec(select(Page).where(Page.handle == handle)).all()]
    user = session.exec(select(User).where(User.handle == handle)).first()
    deleted: dict[str, int] = {}

    def _del(model, clause) -> None:
        rows = session.exec(select(model).where(clause)).all()
        for r in rows:
            session.delete(r)
        if rows:
            deleted[model.__name__] = len(rows)

    # children first to respect foreign keys
    if page_ids:
        _del(Product, Product.page_id.in_(page_ids))
    _del(Click, Click.handle == handle)
    _del(PageView, PageView.handle == handle)
    _del(Sale, Sale.handle == handle)
    _del(Payout, Payout.handle == handle)
    _del(PageLike, PageLike.handle == handle)
    _del(GenerationJob, GenerationJob.handle == handle)
    _del(Page, Page.handle == handle)
    if user:
        _del(SocialConnection, SocialConnection.user_id == user.id)
        _del(Favorite, Favorite.user_id == user.id)
    session.delete(c)
    deleted["Creator"] = 1
    if user:
        session.delete(user)
        deleted["User"] = 1
    session.commit()
    return {"ok": True, "handle": handle, "deleted": deleted}


@router.get("/admin/requests", dependencies=[Depends(require_admin)])
def list_requests(session: Session = Depends(get_session)):
    """Page-generation requests captured during the beta (build these out-of-band)."""
    jobs = session.exec(select(GenerationJob)
                        .where(GenerationJob.status == "received")).all()
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return [{"handle": j.handle, "url": j.source_url, "videoId": j.video_id,
             "at": j.created_at.isoformat()} for j in jobs]


@router.post("/admin/requests/{job_id}/done", dependencies=[Depends(require_admin)])
def mark_request_done(job_id: str, session: Session = Depends(get_session)):
    j = session.get(GenerationJob, job_id)
    if j:
        j.status = "done"
        session.add(j)
        session.commit()
    return {"ok": True}
