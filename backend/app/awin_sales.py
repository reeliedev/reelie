"""
AWIN conversion (transaction) import — the money loop's last mile.

Pulls the publisher's transactions from AWIN's API and turns each into a Sale,
attributed to the creator via the tracking we put on every link:
    clickRef  = the Click id       -> exact page / position / product
    clickRef2 = the creator handle -> which creator drove the sale

Idempotent: upserts by AWIN transaction id (Sale.external_id), so re-running updates
statuses (pending -> approved -> declined) instead of duplicating rows. Two passes —
by transactionDate (new sales) and validationDate (recently approved/declined) — so a
sale validated long after it happened still gets its status update.

Needs AWIN_API_TOKEN (OAuth2 token: AWIN Account -> API credentials) + AWIN_PUBLISHER_ID.
No-op without them.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import Click, Product, Sale, _now

_API = "https://api.awin.com"
# AWIN commissionStatus -> our Sale.state. 'void' (declined/deleted) is forced to
# value 0 below so it never inflates lifetime/period totals (which sum all sales).
_STATE = {"pending": "pending", "approved": "ready", "declined": "void", "deleted": "void"}


def enabled() -> bool:
    return bool(os.environ.get("AWIN_API_TOKEN", "").strip()
                and os.environ.get("AWIN_PUBLISHER_ID", "").strip())


def _fetch(date_type: str, start: datetime, end: datetime) -> list:
    """Transactions of one dateType ('transaction' | 'validation') in [start, end]
    (AWIN caps the range at 31 days)."""
    pub = os.environ["AWIN_PUBLISHER_ID"].strip()
    token = os.environ["AWIN_API_TOKEN"].strip()
    q = urllib.parse.urlencode({
        "startDate": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDate": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "UTC",
        "dateType": date_type,
    })
    url = f"{_API}/publishers/{pub}/transactions/?{q}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed AWIN host
        return json.loads(resp.read().decode("utf-8", "replace")) or []


def _clickrefs(t: dict) -> tuple[str, str]:
    """(clickRef, clickRef2) from a transaction, whether AWIN nests them under
    'clickRefs' or returns them top-level."""
    refs = t.get("clickRefs") or {}
    cr = (refs.get("clickRef") or t.get("clickRef") or "").strip()
    cr2 = (refs.get("clickRef2") or t.get("clickRef2") or "").strip()
    return cr, cr2


def _money(block) -> float:
    try:
        return float((block or {}).get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_dt(v: str | None) -> datetime | None:
    try:
        return datetime.strptime((v or "")[:19], "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def import_sales(days: int = 31) -> dict:
    """Fetch recent transactions and upsert them as Sales. Returns a summary."""
    if not enabled():
        return {"ok": False, "error": "AWIN_API_TOKEN / AWIN_PUBLISHER_ID not set"}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=max(1, min(days, 31)))     # API range cap
    try:
        txns = _fetch("transaction", start, now) + _fetch("validation", start, now)
    except Exception as e:  # noqa: BLE001 — never brick on an API hiccup
        print(f"[awin-sales] fetch failed: {e}", flush=True)
        return {"ok": False, "error": str(e)}

    created = updated = skipped = 0
    seen: set[str] = set()      # the two passes overlap; process each transaction once
    with Session(engine) as s:
        for t in txns:
            ext = str(t.get("id") or "").strip()
            if not ext or ext in seen:
                skipped += 1
                continue
            seen.add(ext)

            cr, cr2 = _clickrefs(t)
            # Attribution: prefer the Click (gives exact page/position/product); fall
            # back to the creator SubID (clickRef2) so a sale still credits the creator
            # even if the click row was pruned.
            click = s.get(Click, cr) if cr else None
            handle = (click.handle if click else "") or cr2
            if not handle:
                skipped += 1          # unattributable — not one of ours
                continue

            state = _STATE.get((t.get("commissionStatus") or "").lower(), "pending")
            commission = _money(t.get("commissionAmount"))
            order = _money(t.get("saleAmount"))
            value = 0.0 if state == "void" else commission

            existing = s.exec(select(Sale).where(Sale.external_id == ext)).first()
            if existing:
                # Never rewrite a sale we've already paid out (a late decline is a
                # clawback handled out-of-band, not a silent zeroing).
                if existing.state != "paid":
                    existing.state = state
                    existing.value = value
                    existing.order_amount = order
                    s.add(existing)
                    updated += 1
                else:
                    skipped += 1
                continue

            product = s.get(Product, click.product_id) if click else None
            name = (f"{product.brand} {product.name}".strip() if product else "AWIN sale")
            s.add(Sale(
                handle=handle,
                page_slug=(click.page_slug if click else ""),
                position=(click.position if click else 0),
                name=name or "AWIN sale",
                emoji=(product.emoji if product else "🛍️"),
                value=value,
                order_amount=order,
                retailer=(product.retailer if product else ""),
                network="awin",
                click_id=cr or None,
                external_id=ext,
                state=state,
                date=(_parse_dt(t.get("transactionDate")) or _now()),
            ))
            created += 1
        s.commit()

    print(f"[awin-sales] {created} new, {updated} updated, {skipped} skipped "
          f"(of {len(txns)} fetched)", flush=True)
    return {"ok": True, "created": created, "updated": updated,
            "skipped": skipped, "fetched": len(txns)}
