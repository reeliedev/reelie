"""
External-integration seams — defined now, wired later. Nothing here calls a paid
service; these are the swap points for Phase 3 (affiliate) and Phase 4 (payouts).
Mirrors how the generator's PriceResolver already isolates a real feed.
"""

from __future__ import annotations

from typing import Protocol


from urllib.parse import quote_plus

# Retailer → search-URL template. A real affiliate network returns a tracked deep
# link; until then we send shoppers to the retailer's search for the product so
# the redirect actually lands somewhere believable.
_RETAILER_SEARCH = {
    "sephora": "https://www.sephora.com/search?keyword={q}",
    "ulta": "https://www.ulta.com/search?q={q}",
    "amazon": "https://www.amazon.com/s?k={q}",
    "walmart": "https://www.walmart.com/search?q={q}",
    "yesstyle": "https://www.yesstyle.com/en/search?q={q}",
    "olive young": "https://global.oliveyoung.com/display/search?query={q}",
    "target": "https://www.target.com/s?searchTerm={q}",
}


class AffiliateNetwork(Protocol):
    """Resolve a product to a best-rate buy link + commission. Phase 3."""
    def resolve_link(self, brand: str, name: str, retailer: str) -> dict: ...


class MockAffiliateNetwork:
    """No real network yet — routes to the retailer's product search."""
    def resolve_link(self, brand: str, name: str, retailer: str) -> dict:
        q = quote_plus(f"{brand} {name}".strip())
        tmpl = _RETAILER_SEARCH.get((retailer or "").lower())
        url = tmpl.format(q=q) if tmpl else f"https://www.google.com/search?q={q}"
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
