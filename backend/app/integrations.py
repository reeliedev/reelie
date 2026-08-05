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
    conversion so the sale can be attributed to the right creator/page."""
    def resolve_link(self, brand: str, name: str, retailer: str, clickref: str = "") -> dict: ...


class MockAffiliateNetwork:
    """No real network. Prefer a trusted retailer's search when we're confident it
    carries the item; otherwise Google Shopping so the link always works. No tracking."""
    def resolve_link(self, brand: str, name: str, retailer: str, clickref: str = "") -> dict:
        return {"url": _destination(brand, name, retailer), "rate": 8,
                "retailer": retailer, "network": "mock"}


def _awin_merchants() -> dict:
    """retailer name (lowercased) -> AWIN advertiser id (awinmid). Configured via the
    AWIN_MERCHANTS env var as JSON, e.g. {"sephora": "12345", "target": "67890"} —
    one entry per merchant you're approved with in AWIN."""
    try:
        raw = json.loads(os.environ.get("AWIN_MERCHANTS", "").strip() or "{}")
        return {str(k).strip().lower(): str(v).strip() for k, v in raw.items()}
    except Exception:  # noqa: BLE001
        return {}


class AwinAffiliateNetwork:
    """AWIN deep links via cread.php. The destination retailer search URL is wrapped
    with the publisher id (awinaffid) + the merchant's advertiser id (awinmid) + a
    clickref for per-sale attribution. If the product's retailer isn't an approved
    AWIN merchant, we return the plain destination (link still works, earns nothing)."""
    def __init__(self) -> None:
        self.affid = os.environ.get("AWIN_PUBLISHER_ID", "").strip()

    def resolve_link(self, brand: str, name: str, retailer: str, clickref: str = "") -> dict:
        dest = _destination(brand, name, retailer)
        mid = _awin_merchants().get((retailer or "").strip().lower())
        if self.affid and mid:
            url = (f"https://www.awin1.com/cread.php?awinmid={mid}&awinaffid={self.affid}"
                   f"&clickref={quote(clickref, safe='')}&ued={quote(dest, safe='')}")
            return {"url": url, "rate": 8, "retailer": retailer, "network": "awin"}
        return {"url": dest, "rate": 0, "retailer": retailer, "network": "none"}


class PayoutProvider(Protocol):
    """Connected accounts + payouts. Phase 4 (Stripe Connect swaps in here)."""
    def onboarding_url(self, handle: str) -> str: ...
    def is_connected(self, handle: str) -> bool: ...
    def create_payout(self, handle: str, amount: float) -> dict: ...


class MockPayoutProvider:
    """No real transfers. Onboarding is auto-completed; payouts return a fake ref."""
    def onboarding_url(self, handle: str) -> str:
        return f"https://connect.stripe.com/setup/mock/{handle}"

    def is_connected(self, handle: str) -> bool:
        return True   # demo: treat every creator as payout-ready

    def create_payout(self, handle: str, amount: float) -> dict:
        return {"ref": f"po_mock_{handle}", "status": "paid"}


affiliate: AffiliateNetwork = (AwinAffiliateNetwork()
                               if os.environ.get("AWIN_PUBLISHER_ID", "").strip()
                               else MockAffiliateNetwork())
payouts: PayoutProvider = MockPayoutProvider()
