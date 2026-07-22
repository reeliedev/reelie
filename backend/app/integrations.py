"""
External-integration seams — defined now, wired later. Nothing here calls a paid
service; these are the swap points for Phase 3 (affiliate) and Phase 4 (payouts).
Mirrors how the generator's PriceResolver already isolates a real feed.
"""

from __future__ import annotations

from typing import Protocol


from urllib.parse import quote_plus

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


def _shopping_search(brand: str, name: str, retailer: str = "") -> str:
    """Google Shopping search for the product — finds it across all retailers, so
    it always resolves to something buyable even when the retailer guess is off."""
    q = quote_plus(" ".join(t for t in (brand, name) if t).strip() or retailer or "product")
    return f"https://www.google.com/search?tbm=shop&q={q}"


class AffiliateNetwork(Protocol):
    """Resolve a product to a best-rate buy link + commission. Phase 3."""
    def resolve_link(self, brand: str, name: str, retailer: str) -> dict: ...


class MockAffiliateNetwork:
    """No real network yet. Prefer a trusted retailer's search when we're confident
    it carries the item; otherwise Google Shopping so the link always works."""
    def resolve_link(self, brand: str, name: str, retailer: str) -> dict:
        tmpl = _RETAILER_SEARCH.get((retailer or "").strip().lower())
        if tmpl:
            url = tmpl.format(q=quote_plus(f"{brand} {name}".strip()))
        else:
            url = _shopping_search(brand, name, retailer)
        return {"url": url, "rate": 8, "retailer": retailer, "network": "mock"}


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


affiliate: AffiliateNetwork = MockAffiliateNetwork()
payouts: PayoutProvider = MockPayoutProvider()
