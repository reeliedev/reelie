"""
Payouts (Phase 4). Ready earnings → the creator's bank. The PayoutProvider is
stubbed (mock); Stripe Connect swaps in behind it. Withdrawing marks the covered
'ready' sales as 'paid' and records a Payout.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.integrations import payouts as provider
from app.models import Payout, Sale, User

router = APIRouter(prefix="/me/payouts", tags=["payouts"])


def _require_creator(user: User) -> None:
    if user.role not in ("creator", "both") or not user.handle:
        raise HTTPException(403, "Become a creator first.")


@router.get("")
def payouts_overview(user: User = Depends(current_user), session: Session = Depends(get_session)):
    _require_creator(user)
    sales = session.exec(select(Sale).where(Sale.handle == user.handle)).all()
    ready = round(sum(s.value for s in sales if s.state == "ready"), 2)
    pending = round(sum(s.value for s in sales if s.state == "pending"), 2)
    paid = round(sum(s.value for s in sales if s.state == "paid"), 2)
    history = session.exec(select(Payout).where(Payout.handle == user.handle)).all()
    history = sorted(history, key=lambda p: p.created_at, reverse=True)
    return {
        "connected": provider.is_connected(user.handle),
        "ready": ready,
        "pending": pending,
        "paidSoFar": paid,
        "history": [{"id": p.id, "amount": p.amount, "status": p.status,
                     "date": p.created_at.isoformat()} for p in history],
    }


@router.post("/connect")
def connect(user: User = Depends(current_user)):
    _require_creator(user)
    return {"url": provider.onboarding_url(user.handle)}


@router.post("/withdraw")
def withdraw(user: User = Depends(current_user), session: Session = Depends(get_session)):
    _require_creator(user)
    if not provider.is_connected(user.handle):
        raise HTTPException(400, "Connect a payout account first.")
    ready_sales = session.exec(select(Sale).where(
        Sale.handle == user.handle, Sale.state == "ready")).all()
    amount = round(sum(s.value for s in ready_sales), 2)
    if amount <= 0:
        raise HTTPException(400, "Nothing available to pay out.")

    result = provider.create_payout(user.handle, amount)
    for s in ready_sales:          # ready → paid
        s.state = "paid"
        session.add(s)
    payout = Payout(handle=user.handle, amount=amount, status=result.get("status", "paid"),
                    provider="mock", provider_ref=result.get("ref"))
    session.add(payout)
    session.commit()
    return {"ok": True, "amount": amount, "status": payout.status}
