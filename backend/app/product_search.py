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
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app import config

# Google organic SERP: for a specific product query the top organic result is
# almost always the direct product page (brand's own store or a retailer). The
# shopping/"popular_products" carousel has price/seller but no direct URL, so we
# resolve from organic.
_ENDPOINT = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
_LOCATION_CODE = 2840   # United States
_LANGUAGE_CODE = "en"

# Not a place to buy — never resolve a product link to these.
_SKIP_DOMAINS = ("youtube.", "reddit.", "tiktok.", "instagram.", "pinterest.",
                 "facebook.", "twitter.", "x.com", "quora.", "wikipedia.",
                 "threads.net", "medium.com")

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


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


_TRACKING = ("srsltid", "gclid", "gclsrc", "dclid", "fbclid", "_branch_match_id")


def _clean_url(url: str) -> str:
    """Drop Google/ads tracking query params for a clean direct link."""
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
        s = urlsplit(url)
        kept = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
                if k.lower() not in _TRACKING and not k.lower().startswith("utm_")]
        return urlunsplit((s.scheme, s.netloc, s.path, urlencode(kept), s.fragment))
    except Exception:
        return url


def _brand_ok(brand: str, title: str, url: str) -> bool:
    """Guard against wrong products: the brand must show up in the result title,
    the domain (brand's own store), or the URL path (retailer/<brand>). No brand
    → accept (the query was just the product name)."""
    b = _norm(brand)
    if not b:
        return True
    if b in _norm(title) or b in _norm(_domain(url)) or b in _norm(url):
        return True
    # distinctive brand word (≥4 chars) as a looser fallback
    words = [w for w in re.sub(r"[^a-z0-9 ]", "", (brand or "").lower()).split() if len(w) >= 4]
    hay = _norm(title) + _norm(_domain(url))
    return any(w in hay for w in words)


def _pick_url(items: list[dict], brand: str) -> tuple[str, str] | None:
    """Highest-ranked organic result that's a real buy page + brand-matches →
    (url, title). None if nothing qualifies (caller keeps the search link)."""
    for it in items:
        if it.get("type") != "organic":
            continue
        url = str(it.get("url") or "")
        if not url.startswith("http"):
            continue
        if any(sd in _domain(url) for sd in _SKIP_DOMAINS):
            continue
        if _brand_ok(brand, it.get("title") or "", url):
            return _clean_url(url), (it.get("title") or "")
    return None


def _resolve_one(product: dict) -> tuple[str, str] | None:
    """One live SERP request for one product (the live endpoint takes a single
    task per request). Returns (url, title) for a confident match, else None."""
    q = _query(product.get("brand", ""), product.get("name", ""), product.get("variant", ""))
    if not q:
        return None
    body = json.dumps([{"keyword": q, "location_code": _LOCATION_CODE,
                        "language_code": _LANGUAGE_CODE}]).encode()
    req = urllib.request.Request(_ENDPOINT, data=body, headers={
        "Authorization": _auth_header(), "Content-Type": "application/json",
        "User-Agent": "Reelie/1.0 (+https://reelie.io)"})
    try:
        with urllib.request.urlopen(req, timeout=45, context=_SSL_CTX) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"[product_search] request failed for {q!r}: {type(e).__name__}: {e}", flush=True)
        return None
    task = (data.get("tasks") or [{}])[0]
    items: list[dict] = []
    for res in task.get("result") or []:
        items.extend(res.get("items") or [])
    return _pick_url(items, product.get("brand", ""))


def resolve_batch(products: list[dict]) -> dict[str, dict]:
    """Resolve each product to a direct buy link (concurrent single-task requests).
    Returns {id: {"url","title"}} for confident matches only; never raises."""
    if not enabled() or not products:
        return {}
    from concurrent.futures import ThreadPoolExecutor
    # Require a brand — brand-null products are guesses; keep them as search links.
    todo = [p for p in products
            if (p.get("brand") or "").strip() and _query(p.get("brand", ""), p.get("name", ""))]
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(todo) or 1)) as ex:
        for p, hit in zip(todo, ex.map(_resolve_one, todo)):
            if hit:
                out[str(p.get("id"))] = {"url": hit[0], "title": hit[1]}
    print(f"[product_search] resolved {len(out)}/{len(todo)} products to direct links", flush=True)
    return out
