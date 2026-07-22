"""
Resolve products to direct buy links via DataForSEO's Google Shopping API.

Env-gated (DATAFORSEO_LOGIN/PASSWORD): with no creds this is a no-op and callers
keep the Google Shopping *search* fallback. Batches every product on a page into
ONE request (cheap: one API call per page), and only returns a direct URL when
the top result's title actually matches the brand — otherwise None, so the caller
keeps the safe search link instead of risking a wrong product.

stdlib only (urllib); TLS via certifi. Resolve once at generation and cache the
URL on the product — never per click.
"""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request

from app import config

_ENDPOINT = "https://api.dataforseo.com/v3/merchant/google/products/live/advanced"
_LOCATION_CODE = 2840   # United States
_LANGUAGE_CODE = "en"

try:
    import certifi
    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL_CTX = None


def enabled() -> bool:
    return config.PRODUCT_SEARCH_ENABLED


def _auth_header() -> str:
    raw = f"{config.DATAFORSEO_LOGIN}:{config.DATAFORSEO_PASSWORD}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _query(brand: str, name: str, variant: str = "") -> str:
    return " ".join(t.strip() for t in (brand, name, variant) if t and t.strip()).strip()


def _brand_ok(brand: str, title: str) -> bool:
    """Guard against wrong matches: the result title must contain the brand (or,
    when we have no brand, accept — the query was just the product name)."""
    b = (brand or "").strip().lower()
    if not b:
        return True
    t = (title or "").lower()
    # match on the brand as a whole or its most distinctive word
    if b in t:
        return True
    longest = max(b.split(), key=len, default="")
    return len(longest) >= 4 and longest in t


def _pick_url(items: list[dict], brand: str) -> tuple[str, str] | None:
    """First brand-matching product → (direct_url, title). None if none match."""
    for it in items:
        if it.get("type") not in (None, "product", "shopping"):
            continue
        title = it.get("title") or ""
        if not _brand_ok(brand, title):
            continue
        url = it.get("url") or it.get("link") or it.get("shop_url")
        if url and str(url).startswith("http"):
            return str(url), title
    return None


def resolve_batch(products: list[dict]) -> dict[str, dict]:
    """products: [{"id","brand","name","variant"}]. Returns {id: {"url","title"}}
    for confident matches only. Never raises — a failure returns {} so callers
    fall back to search links."""
    if not enabled() or not products:
        return {}
    tasks = [{"keyword": _query(p.get("brand", ""), p.get("name", ""), p.get("variant", "")),
              "location_code": _LOCATION_CODE, "language_code": _LANGUAGE_CODE,
              "tag": str(p.get("id", i))}
             for i, p in enumerate(products) if _query(p.get("brand", ""), p.get("name", ""))]
    if not tasks:
        return {}
    body = json.dumps(tasks).encode()
    req = urllib.request.Request(_ENDPOINT, data=body, headers={
        "Authorization": _auth_header(), "Content-Type": "application/json",
        "User-Agent": "Reelie/1.0 (+https://reelie.io)"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as r:
            data = json.loads(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:  # noqa: BLE001
        print(f"[product_search] request failed: {type(e).__name__}: {e}", flush=True)
        return {}

    # Map each result task back to its product via the tag we sent (= product id),
    # then apply the brand guard using that product's brand.
    inputs = {str(p.get("id", i)): p for i, p in enumerate(products)}
    out: dict[str, dict] = {}
    for task in data.get("tasks", []) or []:
        tag = str((task.get("data") or {}).get("tag") or task.get("tag") or "")
        src = inputs.get(tag)
        if not src:
            continue
        items: list[dict] = []
        for res in task.get("result") or []:
            items.extend(res.get("items") or [])
        hit = _pick_url(items, src.get("brand", ""))
        if hit:
            out[tag] = {"url": hit[0], "title": hit[1]}
    print(f"[product_search] resolved {len(out)}/{len(tasks)} products to direct links", flush=True)
    return out
