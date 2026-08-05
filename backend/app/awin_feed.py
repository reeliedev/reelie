"""
AWIN product-feed ingestion + matching (link-resolution Step 1).

Downloads the gzip CSV at AWIN_FEED_URL (a Create-a-Feed URL covering our approved
merchants), replaces the MerchantProduct table, and matches a video-detected product
(brand + name, and EAN when available) to the best in-stock catalogue product — whose
`aw_deep_link` is an already-tracked AWIN link we can hand a shopper directly.

Only enabled when AWIN_FEED_URL is set; otherwise every entry point is a no-op and
link resolution falls through to the existing search fallbacks.
"""

from __future__ import annotations

import csv
import gzip
import io
import os
import re
import urllib.request

from sqlalchemy import insert as sa_insert
from sqlmodel import Session, delete, select

from app.db import engine
from app.models import MerchantProduct, _now, _uuid

_WORD = re.compile(r"[a-z0-9]+")
# Low-signal tokens: sizes, units, filler. Dropped so matching keys off the words that
# actually identify a product (brand + descriptive name), not "50ml"/"set"/"the".
_STOP = {
    "ml", "g", "kg", "l", "oz", "fl", "pcs", "pc", "pack", "set", "x", "the", "and",
    "of", "for", "with", "in", "new", "pro", "size", "ea", "count", "ct", "value",
}
_MATCH_THRESHOLD = 0.6   # fraction of the video product's tokens that must appear in a
                         # catalogue product for it to count as the same item. Tunable.


def enabled() -> bool:
    return bool(os.environ.get("AWIN_FEED_URL", "").strip())


def _norm(*parts: str | None) -> str:
    """Lowercased alphanumeric tokens joined by spaces — the searchable form."""
    return " ".join(_WORD.findall(" ".join(p for p in parts if p).lower()))


def _tokens(s: str | None) -> set[str]:
    """Significant tokens of a string (len>1, not a stop word)."""
    return {t for t in _WORD.findall((s or "").lower()) if len(t) > 1 and t not in _STOP}


def _f(v: str | None) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _truthy_stock(in_stock: str | None, stock_status: str | None) -> bool:
    if str(in_stock or "").strip().lower() in ("1", "true", "yes", "y", "in stock"):
        return True
    return "in stock" in (stock_status or "").lower()


_BATCH = 1000   # rows per INSERT — small enough that memory stays flat on a 512MB dyno


def _row_dict(r: dict, ts) -> dict | None:
    """One feed CSV row → a plain dict for a Core bulk insert, or None if unusable.
    Plain dicts (not ORM objects) keep memory tiny; id/updated_at are set here because
    a Core insert doesn't run the model's Python-side defaults."""
    name = (r.get("product_name") or "").strip()
    deep = (r.get("aw_deep_link") or "").strip()
    if not name or not deep:            # unusable without a name to match or a link to send
        return None
    brand = (r.get("brand_name") or "").strip()
    # brand_name is unreliable in some feeds (blank, or an EAN stuffed in) — if it
    # doesn't look like a brand (all digits), ignore it and rely on the product_name.
    if brand.isdigit():
        brand = ""
    return {
        "id": _uuid(),
        "merchant_id": str(r.get("merchant_id") or "").strip(),
        "merchant_name": (r.get("merchant_name") or "").strip(),
        "brand": brand,
        "name": name,
        "name_norm": _norm(brand, name),
        "ean": (r.get("ean") or "").strip(),
        "upc": (r.get("upc") or "").strip(),
        "deep_link": deep,
        "product_url": (r.get("merchant_deep_link") or "").strip(),
        "image": (r.get("merchant_image_url") or r.get("aw_image_url") or "").strip(),
        "price": _f(r.get("search_price") or r.get("store_price")),
        "currency": (r.get("currency") or "").strip(),
        "in_stock": _truthy_stock(r.get("in_stock"), r.get("stock_status")),
        "updated_at": ts,
    }


def ingest() -> dict:
    """Download AWIN_FEED_URL, parse the gzip CSV, and replace the MerchantProduct
    table — STREAMING, so memory stays flat regardless of feed size (the feed is tens
    of MB and 200k+ rows; loading it all at once OOMs a 512MB service). Decompress and
    parse row-by-row off the HTTP stream, insert in small batches. One transaction, so
    the swap is atomic (no empty/partial catalogue window) — the count jumps from the
    old value to the new only when it finishes. Safe to call repeatedly."""
    url = os.environ.get("AWIN_FEED_URL", "").strip()
    if not url:
        return {"ok": False, "error": "AWIN_FEED_URL not set"}
    table = MerchantProduct.__table__
    ts = _now()
    total = 0
    skipped = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "reelie-feed/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 — fixed config URL
            gz = gzip.GzipFile(fileobj=resp)                    # streaming decompress
            text = io.TextIOWrapper(gz, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text)
            with engine.begin() as conn:                        # atomic full refresh
                conn.execute(delete(MerchantProduct))
                batch: list[dict] = []
                for r in reader:
                    row = _row_dict(r, ts)
                    if row is None:
                        skipped += 1
                        continue
                    batch.append(row)
                    if len(batch) >= _BATCH:
                        conn.execute(sa_insert(table), batch)
                        total += len(batch)
                        batch = []
                if batch:
                    conn.execute(sa_insert(table), batch)
                    total += len(batch)
    except Exception as e:  # noqa: BLE001 — never brick on a bad feed/url
        print(f"[awin] feed download/parse failed: {e}", flush=True)
        return {"ok": False, "error": str(e)}
    print(f"[awin] ingested {total} products ({skipped} skipped)", flush=True)
    return {"ok": True, "products": total, "skipped": skipped}


def match(brand: str, name: str, ean: str = "", upc: str = "") -> MerchantProduct | None:
    """Best in-stock catalogue product for a video-detected product, or None.

    EAN/UPC exact match wins outright; otherwise we narrow by the most distinctive
    token (so we don't scan the whole table) and score candidates by how much of the
    video product's wording they contain, requiring >= _MATCH_THRESHOLD."""
    if not enabled():
        return None
    with Session(engine) as s:
        for code, col in ((ean, MerchantProduct.ean), (upc, MerchantProduct.upc)):
            code = (code or "").strip()
            if code:
                hit = s.exec(select(MerchantProduct).where(col == code)).first()
                if hit:
                    return hit

        want = _tokens(f"{brand} {name}")
        if len(want) < 2:                   # too little signal to match confidently
            return None
        pivot = max(want, key=len)          # narrow the scan to rows containing this token
        cands = s.exec(
            select(MerchantProduct).where(MerchantProduct.name_norm.contains(pivot)).limit(400)
        ).all()

        best: MerchantProduct | None = None
        best_score = 0.0
        for c in cands:
            have = _tokens(c.name_norm)
            if not have:
                continue
            score = len(want & have) / len(want)   # fraction of the video product covered
            if c.in_stock:
                score += 0.05                       # tie-break toward buyable stock
            if score > best_score:
                best, best_score = c, score
        return best if best_score >= _MATCH_THRESHOLD else None
