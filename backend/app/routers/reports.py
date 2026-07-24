"""
Content reporting — the App Store UGC requirement (Guideline 1.2). Any viewer
(guest or signed-in) can flag a routine or creator; the report is stored and the
team is emailed so it can be actioned. Blocking a creator is handled client-side
(the app hides blocked handles); this endpoint is the "report objectionable
content" half.

  POST /reports {kind, ref, reason, detail?, clientId?}  -> {ok: true}
"""

from __future__ import annotations

import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app import notify
from app.auth import optional_user
from app.db import get_session
from app.models import Report, User

router = APIRouter(tags=["reports"])

_REASONS = {"spam", "offensive", "nudity", "violence", "hate", "ip", "other"}


class ReportBody(BaseModel):
    kind: str = "page"
    ref: str
    reason: str = "other"
    detail: str = ""
    clientId: str = ""


@router.post("/reports")
def create_report(body: ReportBody, background: BackgroundTasks,
                  user: User | None = Depends(optional_user),
                  session: Session = Depends(get_session)):
    kind = body.kind if body.kind in ("page", "creator") else "page"
    ref = (body.ref or "").strip()[:200]
    if not ref:
        raise HTTPException(400, "Nothing to report.")
    reason = body.reason if body.reason in _REASONS else "other"
    detail = re.sub(r"\s+", " ", (body.detail or "")).strip()[:1000]

    report = Report(kind=kind, ref=ref, reason=reason, detail=detail,
                    reporter_client=(body.clientId or "").strip()[:100],
                    reporter_user=user.id if user else None)
    session.add(report)
    session.commit()

    # Tell the team out-of-band so a mail outage never blocks the response.
    background.add_task(notify.content_reported, kind, ref, reason, detail,
                        user.email if user else "guest")
    return {"ok": True}
