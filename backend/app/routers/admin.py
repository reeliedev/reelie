"""
Closed-beta admin console. Review creator applications and approve/reject them.
Gated by ADMIN_TOKEN (sent as X-Admin-Token). GET /admin serves a small review
page whose JS prompts for the token and calls these endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app import admin_page, config
from app.db import get_session
from app.models import (Click, Creator, Favorite, GenerationJob, Page, PageLike,
                        Payout, Product, Sale, SocialConnection, User, _now)

router = APIRouter(tags=["admin"])


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not config.ADMIN_TOKEN or x_admin_token != config.ADMIN_TOKEN:
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
def approve(handle: str, session: Session = Depends(get_session)):
    return _set_status(handle, "approved", session)


@router.post("/admin/applications/{handle}/reject", dependencies=[Depends(require_admin)])
def reject(handle: str, session: Session = Depends(get_session)):
    return _set_status(handle, "rejected", session)


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
