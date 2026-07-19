"""
Price resolution. `PriceResolver` is the swap point for a real commerce/affiliate
feed later; today we ship an LLM estimator (default) and a deterministic stub
(`--mock`, no API key) so the whole pipeline runs offline.
"""

from __future__ import annotations

import datetime as _dt
import json
from abc import ABC, abstractmethod

import config
from models import Price
from prompts import PRICE_SCHEMA, PRICE_SYSTEM_PROMPT, build_price_messages


def _valid_until(days: int = config.PRICE_VALID_DAYS) -> str:
    # Fixed epoch base kept out of the hot path; date math only.
    today = _dt.date.today()
    return (today + _dt.timedelta(days=days)).isoformat()


class PriceResolver(ABC):
    """Given the raw extracted products (list of dicts), return a list of Price
    (or None) aligned by index."""

    @abstractmethod
    def resolve(self, products: list[dict]) -> list[Price | None]:
        ...


class StubPriceResolver(PriceResolver):
    """Deterministic, offline. Prices from a small category heuristic so `--mock`
    runs produce stable, realistic-looking numbers without any API call."""

    # rough typical USD full-size prices by category keyword
    CATEGORY_PRICE = [
        (("cleansing balm", "cleanser", "cleansing"), 22.0, "YesStyle"),
        (("toner", "essence"), 19.0, "Olive Young"),
        (("serum", "ampoule", "mucin"), 25.0, "YesStyle"),
        (("eye",), 24.0, "Sephora"),
        (("sunscreen", "spf", "sun"), 18.0, "Olive Young"),
        (("moisturiser", "moisturizer", "cream", "mask"), 28.0, "Sephora"),
        (("foundation", "skin tint", "tint"), 42.0, "Sephora"),
        (("concealer",), 30.0, "Sephora"),
        (("powder",), 34.0, "Ulta"),
        (("blush", "bronzer", "highlighter"), 23.0, "Sephora"),
        (("lip", "lipstick", "gloss", "balm"), 20.0, "Sephora"),
        (("brush", "sponge", "blender", "tool"), 16.0, "Amazon"),
    ]
    DEFAULT = (24.0, "Amazon")

    def _guess(self, p: dict) -> tuple[float, str]:
        hay = f"{p.get('product_name','')} {p.get('variant_or_shade') or ''}".lower()
        for keys, price, retailer in self.CATEGORY_PRICE:
            if any(k in hay for k in keys):
                return price, retailer
        return self.DEFAULT

    def resolve(self, products: list[dict]) -> list[Price | None]:
        vu = _valid_until()
        out = []
        for p in products:
            amount, _retailer = self._guess(p)
            out.append(Price(amount=amount, currency=config.DEFAULT_CURRENCY,
                             valid_until=vu, estimated=True))
        return out

    def retailer_for(self, p: dict) -> str:
        return self._guess(p)[1]


class LLMPriceResolver(PriceResolver):
    """Estimates typical retail price with Claude (structured output). Falls back
    to the stub for any product the model skips."""

    def __init__(self, client, model: str = config.MODEL):
        self.client = client
        self.model = model
        self._stub = StubPriceResolver()
        self._last_retailers: dict[int, str] = {}

    def resolve(self, products: list[dict]) -> list[Price | None]:
        if not products:
            return []
        vu = _valid_until()
        resp = self.client.messages.create(
            model=self.model, max_tokens=2048,
            system=PRICE_SYSTEM_PROMPT,
            messages=build_price_messages(products),
            output_config={"format": {"type": "json_schema", "schema": PRICE_SCHEMA}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        by_index = {int(e["index"]): e for e in json.loads(text).get("prices", [])}

        out: list[Price | None] = []
        for i, p in enumerate(products):
            e = by_index.get(i)
            if e and e.get("amount_usd"):
                out.append(Price(amount=round(float(e["amount_usd"]), 2),
                                 currency=config.DEFAULT_CURRENCY,
                                 valid_until=vu, estimated=True))
                self._last_retailers[i] = e.get("retailer") or self._stub.retailer_for(p)
            else:
                out.append(self._stub.resolve([p])[0])
                self._last_retailers[i] = self._stub.retailer_for(p)
        return out

    def retailer_for_index(self, i: int, p: dict) -> str:
        return self._last_retailers.get(i) or self._stub.retailer_for(p)
