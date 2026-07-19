"""
Content-based recommendations over the page registry (out/pages.json). No ML,
no backend — pure joins on shared brands and shared products.

  similar_creators(handle)      -> creators ranked by shared-brand overlap
  creators_using(product_key)   -> creators whose routines include that product

Requires a multi-creator corpus (seed several handles) to return signal.
"""

from __future__ import annotations

import json

import config
from render.site_files import normalize_product

_DEFAULT_GRADIENT = ["#E8E4DA", "#D8D2C4"]


def load_registry() -> list[dict]:
    idx = config.PAGES_INDEX
    return json.loads(idx.read_text()) if idx.exists() else []


def creator_index(pages: list[dict]) -> dict[str, dict]:
    """Aggregate registry entries into one record per creator handle."""
    by: dict[str, dict] = {}
    for p in pages:
        h = p["handle"]
        c = by.setdefault(h, {
            "handle": h,
            "name": p.get("creator_name", h),
            "avatar_gradient": p.get("avatar_gradient", _DEFAULT_GRADIENT),
            "platforms": p.get("platforms", []),
            "pages": [],
            "brands": set(),
            "product_keys": set(),
        })
        c["pages"].append(p)
        c["brands"].update(p.get("brands", []))
        c["product_keys"].update(pk["key"] for pk in p.get("products", []))
    return by


def similar_creators(handle: str, pages: list[dict] | None = None, limit: int = 6) -> list[dict]:
    pages = pages if pages is not None else load_registry()
    idx = creator_index(pages)
    me = idx.get(handle)
    if not me or not me["brands"]:
        return []
    out = []
    for h, c in idx.items():
        if h == handle:
            continue
        shared = me["brands"] & c["brands"]
        if not shared:
            continue
        score = len(shared) / len(me["brands"] | c["brands"])
        out.append({
            "handle": h, "name": c["name"], "avatar_gradient": c["avatar_gradient"],
            "reason": "Also uses " + ", ".join(sorted(shared)[:2]), "score": score,
        })
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def creators_using(product_key: str, pages: list[dict] | None = None,
                   exclude_handle: str | None = None, limit: int = 6) -> list[dict]:
    pages = pages if pages is not None else load_registry()
    idx = creator_index(pages)
    out = []
    for h, c in idx.items():
        if h == exclude_handle:
            continue
        if product_key in c["product_keys"]:
            out.append({"handle": h, "name": c["name"], "avatar_gradient": c["avatar_gradient"]})
    return out[:limit]


def product_key(brand: str, name: str) -> str:
    return normalize_product(brand, name)


def write_reco_json(pages: list[dict] | None = None) -> dict:
    """Dump a flat reco file (handy for debugging / the iOS/web clients)."""
    pages = pages if pages is not None else load_registry()
    idx = creator_index(pages)
    data = {
        "similar": {h: similar_creators(h, pages) for h in idx},
        "creators_using": {},
    }
    for p in pages:
        for prod in p.get("products", []):
            k = prod["key"]
            if k not in data["creators_using"]:
                data["creators_using"][k] = [
                    c["handle"] for c in creators_using(k, pages)
                ]
    out = config.OUT_DIR / "reco.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
