"""
External-integration seams — defined now, wired later. Nothing here calls a paid
service; these are the swap points for Phase 3 (affiliate) and Phase 4 (payouts).
Mirrors how the generator's PriceResolver already isolates a real feed.
"""

from __future__ import annotations

import json
import os
from typing import Protocol
from urllib.parse import quote, quote_plus

# Retailers whose on-site search reliably lands on the product AND is likely to
# carry it. We only send shoppers to a specific retailer when we're confident;
# everything else goes to Google Shopping (below), which finds the product across
# every store — so the link always works instead of dead-ending at a store that
# doesn't stock it.
_RETAILER_SEARCH = {
    "amazon": "https://www.amazon.com/s?k={q}",
    "sephora": "https://www.sephora.com/search?keyword={q}",
    "target": "https://www.target.com/s?searchTerm={q}",
    "walmart": "https://www.walmart.com/search?q={q}",
}


def is_trusted_retailer(retailer: str) -> bool:
    """True when we link shoppers to this retailer's own search (so the page can
    honestly say 'Shop at <retailer>')."""
    return (retailer or "").strip().lower() in _RETAILER_SEARCH


def retailer_for_url(url: str) -> str:
    """Display name of a known retailer if this URL points there, else ''. Used to
    label a direct/resolved link by where it ACTUALLY goes (not the guessed
    retailer), so 'Shop at Sephora' can't point at a YSL page."""
    from urllib.parse import urlparse
    try:
        dom = urlparse(url).netloc.lower()
    except Exception:
        return ""
    for key in _RETAILER_SEARCH:                 # amazon, sephora, target, walmart
        if key in dom:
            return key.title()
    return ""


def money(amount: float | None, currency: str) -> str:
    """Format a price for display ($24, £12.50). Shared by the web page, the API
    DTO and the feed so a product with a numeric price but no pre-set display
    string still shows a price on every client."""
    if amount is None:
        return ""
    sym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(currency, "")
    if abs(amount - round(amount)) < 0.005:
        return f"{sym}{int(round(amount))}"
    return f"{sym}{amount:,.2f}"


def effective_retailer(p) -> str:
    """The retailer that MATCHES where a product actually links (keeps the label
    honest). Shared by the web page AND the API DTO so every client — web, iOS —
    shows the same, correct retailer instead of the raw guessed one.
      • a resolved own/auto URL → the retailer derived from that URL
      • a trusted guessed retailer for a search link → that retailer
      • otherwise the brand's own store
    Duck-typed on Product (link_kind, url, retailer, brand)."""
    if p.link_kind in ("own", "auto") and (p.url or "").startswith("http"):
        return retailer_for_url(p.url) or (p.brand or "").strip()
    if is_trusted_retailer(p.retailer):
        return (p.retailer or "").strip()
    return (p.brand or "").strip()


def _shopping_search(brand: str, name: str, retailer: str = "") -> str:
    """Google Shopping search for the product — finds it across all retailers, so
    it always resolves to something buyable even when the retailer guess is off."""
    q = quote_plus(" ".join(t for t in (brand, name) if t).strip() or retailer or "product")
    return f"https://www.google.com/search?tbm=shop&q={q}"


def _destination(brand: str, name: str, retailer: str) -> str:
    """Where the shopper should land: a trusted retailer's own search (so we can say
    'Shop at <retailer>' AND it's an AWIN-partnered domain), else Google Shopping."""
    tmpl = _RETAILER_SEARCH.get((retailer or "").strip().lower())
    if tmpl:
        return tmpl.format(q=quote_plus(f"{brand} {name}".strip()))
    return _shopping_search(brand, name, retailer)


class AffiliateNetwork(Protocol):
    """Resolve a product to a best-rate buy link + commission. Phase 3.
    `clickref` is an opaque token (we pass the Click id) the network echoes back on a
    conversion so the sale can be attributed to the right creator/page. `country` is
    the SHOPPER's ISO country (from the click) for geo-aware regional links."""
    def resolve_link(self, brand: str, name: str, retailer: str,
                     clickref: str = "", country: str = "") -> dict: ...


class MockAffiliateNetwork:
    """No real network. Prefer a trusted retailer's search when we're confident it
    carries the item; otherwise Google Shopping so the link always works. No tracking."""
    def resolve_link(self, brand: str, name: str, retailer: str,
                     clickref: str = "", country: str = "") -> dict:
        return {"url": _destination(brand, name, retailer), "rate": 8,
                "retailer": retailer, "network": "mock"}


def _awin_config() -> dict:
    """Parse AWIN_MERCHANTS (JSON). Two accepted shapes per retailer:

      Flat (single program):     "sephora": "12345"
      Region-aware (per country): "douglas": {
          "HU": {"mid": "111", "search": "https://www.douglas.hu/hu/search/{q}"},
          "IT": {"mid": "222", "search": "https://www.douglas.it/it/search/{q}"},
          "default": "IT"          # used when the shopper's country has no program
      }
    The region-aware form is what makes a link resolve to the shopper's own regional
    store + the matching regional AWIN program."""
    try:
        raw = json.loads(os.environ.get("AWIN_MERCHANTS", "").strip() or "{}")
        return {str(k).strip().lower(): v for k, v in raw.items()}
    except Exception:  # noqa: BLE001
        return {}


def _pick_program(retailer: str, country: str) -> tuple:
    """(awinmid, region_search_template) for a retailer given the SHOPPER's country,
    or (None, None) if the retailer isn't configured. Region-aware config picks the
    country's program, else the retailer's declared default, else the first program."""
    cfg = _awin_config().get((retailer or "").strip().lower())
    if cfg is None:
        return None, None
    if isinstance(cfg, str):                                   # flat: one program
        return cfg.strip(), _RETAILER_SEARCH.get((retailer or "").strip().lower())
    if isinstance(cfg, dict) and ("mid" in cfg or "search" in cfg):
        # single global program: {"mid": "...", "search": "https://store/..{q}.."}
        return str(cfg.get("mid", "")).strip() or None, cfg.get("search")
    entry = (cfg.get((country or "").upper())                  # shopper's region
             or cfg.get(str(cfg.get("default", "")).upper())   # declared default
             or next((v for v in cfg.values() if isinstance(v, dict)), None))  # any
    if not isinstance(entry, dict):
        return None, None
    return str(entry.get("mid", "")).strip() or None, entry.get("search")


class AwinAffiliateNetwork:
    """AWIN deep links via cread.php, geo-aware. Using the SHOPPER's country (from the
    click), we pick that retailer's regional program (advertiser id + regional store
    URL), wrap the destination with awinaffid + awinmid + a clickref for per-sale
    attribution. Retailers/regions we're not approved for fall back to a plain
    destination (link still works, earns nothing)."""
    def __init__(self) -> None:
        self.affid = os.environ.get("AWIN_PUBLISHER_ID", "").strip()

    def resolve_link(self, brand: str, name: str, retailer: str,
                     clickref: str = "", country: str = "") -> dict:
        mid, search = _pick_program(retailer, country)
        if search:
            dest = search.format(q=quote_plus(f"{brand} {name}".strip()))
        else:
            dest = _destination(brand, name, retailer)
        if self.affid and mid:
            url = (f"https://www.awin1.com/cread.php?awinmid={mid}&awinaffid={self.affid}"
                   f"&clickref={quote(clickref, safe='')}&ued={quote(dest, safe='')}")
            return {"url": url, "rate": 8, "retailer": retailer, "network": "awin"}
        return {"url": dest, "rate": 0, "retailer": retailer, "network": "none"}


class PayoutProvider(Protocol):
    """Connected accounts + payouts. Phase 4 (Stripe Connect swaps in here)."""
    name: str
    def onboarding_url(self, handle: str) -> str: ...
    def is_connected(self, handle: str) -> bool: ...
    def create_payout(self, handle: str, amount: float) -> dict: ...


class MockPayoutProvider:
    """No real transfers. Onboarding is auto-completed; payouts return a fake ref."""
    name = "mock"

    def onboarding_url(self, handle: str) -> str:
        return f"https://connect.stripe.com/setup/mock/{handle}"

    def is_connected(self, handle: str) -> bool:
        return True   # demo: treat every creator as payout-ready

    def create_payout(self, handle: str, amount: float) -> dict:
        return {"ref": f"po_mock_{handle}", "status": "paid"}


class StripePayoutProvider:
    """Stripe Connect Express. Creators onboard via Stripe-hosted KYC; the platform
    holds each creator's commission balance and transfers it to their connected
    account on withdrawal. The Stripe account id is stored on the Creator row.

    Requires STRIPE_SECRET_KEY. USE A TEST KEY FIRST: create_payout moves REAL money
    in live mode, so only set a live key once earnings are real (AWIN conversions
    imported + reconciled) — until then the 'ready' balance is estimated."""
    name = "stripe"

    def __init__(self) -> None:
        import stripe
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"].strip()
        self._stripe = stripe
        self._base = os.environ.get("PUBLIC_BASE_URL", "https://reelie.io").rstrip("/")

    def _account_id(self, handle: str, create: bool = False) -> str | None:
        from sqlmodel import Session
        from app.db import engine
        from app.models import Creator
        with Session(engine) as s:
            c = s.get(Creator, handle)
            if not c:
                return None
            if c.stripe_account_id:
                return c.stripe_account_id
            if not create:
                return None
            acct = self._stripe.Account.create(
                type="express", business_type="individual",
                capabilities={"transfers": {"requested": True}},
                metadata={"handle": handle})
            c.stripe_account_id = acct.id
            s.add(c); s.commit()
            return acct.id

    def onboarding_url(self, handle: str) -> str:
        aid = self._account_id(handle, create=True)
        link = self._stripe.AccountLink.create(
            account=aid, type="account_onboarding",
            refresh_url=f"{self._base}/studio?payout=refresh",
            return_url=f"{self._base}/studio?payout=done")
        return link.url

    def is_connected(self, handle: str) -> bool:
        aid = self._account_id(handle)
        if not aid:
            return False
        try:
            return bool(self._stripe.Account.retrieve(aid).payouts_enabled)
        except Exception:  # noqa: BLE001
            return False

    def create_payout(self, handle: str, amount: float) -> dict:
        aid = self._account_id(handle)
        if not aid:
            return {"ref": None, "status": "failed"}
        tr = self._stripe.Transfer.create(
            amount=int(round(amount * 100)), currency="usd",
            destination=aid, metadata={"handle": handle})
        return {"ref": tr.id, "status": "paid"}


def _make_payouts() -> PayoutProvider:
    if os.environ.get("STRIPE_SECRET_KEY", "").strip():
        try:
            return StripePayoutProvider()
        except Exception as e:  # noqa: BLE001 — never brick the app on a bad key
            print(f"[payouts] Stripe init failed, using mock: {e}", flush=True)
    return MockPayoutProvider()


affiliate: AffiliateNetwork = (AwinAffiliateNetwork()
                               if os.environ.get("AWIN_PUBLISHER_ID", "").strip()
                               else MockAffiliateNetwork())
payouts: PayoutProvider = _make_payouts()
