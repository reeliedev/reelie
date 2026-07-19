"""
Assemble a canonical `Page` from an `Extraction` + resolved prices.

The page-level fields (title, emoji, slug, ordering, per-product notes/emoji) come
from one Claude call in live mode, or a deterministic heuristic in --mock mode.
"""

from __future__ import annotations

import base64
import json
import re

import config
from extractor import Extraction
from models import Page, ProductItem, Creator, SourceVideo, Link, Price, fmt_timestamp
from prompts import PAGE_SCHEMA, PAGE_SYSTEM_PROMPT, build_page_messages

# How many video keyframes to show the model when narrating the guide.
_MAX_GUIDE_FRAMES = 8

# Rotating reelie commission rates so a page looks realistic (mirrors the app's 6-8%).
_RATES = [8, 7, 6]

# --mock emoji heuristic (LLM assigns these in live mode).
_EMOJI_RULES = [
    (("cleansing balm", "cleanser", "cleansing", "clean it"), "🧼"),
    (("toner", "essence"), "🧴"),
    (("serum", "ampoule", "mucin", "oil"), "💧"),
    (("eye",), "🌙"),
    (("sunscreen", "spf", "sun"), "🌞"),
    (("mask", "sleeping"), "💤"),
    (("moisturiser", "moisturizer", "cream"), "🧴"),
    (("foundation", "skin tint", "tint", "concealer"), "🪞"),
    (("powder",), "✨"),
    (("blush", "cheek"), "🌸"),
    (("bronzer", "contour"), "🤎"),
    (("highlighter", "glow"), "🌟"),
    (("lip", "lipstick", "gloss"), "💄"),
    (("brush", "sponge", "blender", "tool"), "🖌️"),
    (("brow",), "🖊️"),
    (("mascara", "lash"), "👁️"),
]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s) or "routine"


def _guess_emoji(name: str, variant: str | None) -> str:
    hay = f"{name} {variant or ''}".lower()
    for keys, emoji in _EMOJI_RULES:
        if any(k in hay for k in keys):
            return emoji
    return "🛍️"


def _short_note(quote: str | None) -> str | None:
    if not quote:
        return None
    q = quote.strip().strip('"')
    words = q.split()
    if len(words) > 9:
        q = " ".join(words[:9]) + "…"
    return q


def _brand_of(p: dict) -> str:
    return (p.get("brand") or "").strip()


def _display_name_from_handle(handle: str) -> str:
    return handle.replace("_", " ").replace(".", " ").title()


def _load_frames(video_id: str, limit: int = _MAX_GUIDE_FRAMES) -> list[tuple]:
    """Grab up to `limit` cached keyframes (skipping the mirror-flip copies), in
    time order, as (label, media_type, base64) tuples for the guide LLM call.
    Returns [] if no frames are cached — narration then falls back to transcript."""
    base = config.VIDEO_LLM_CACHE / video_id
    if not base.exists():
        return []
    frame_dirs = sorted(base.glob("frames_*"))
    if not frame_dirs:
        return []
    files = sorted(
        f for f in frame_dirs[0].glob("frame_*.jpg") if "_flip" not in f.name
    )
    if len(files) > limit:  # even sample across the video, keep first + last
        step = len(files) / limit
        files = [files[int(i * step)] for i in range(limit)]
    out = []
    for f in files:
        # label from filename: frame_002_5.8s_hold.jpg -> "5.8s"
        m = re.search(r"_(\d+\.?\d*)s", f.name)
        label = m.group(1) + "s" if m else f.stem
        out.append((label, "image/jpeg", base64.b64encode(f.read_bytes()).decode()))
    return out


# --------------------------------------------------------------------------
# page-level assembly (LLM or mock)
# --------------------------------------------------------------------------
def _assemble_llm(ext: Extraction, client) -> dict:
    frames = _load_frames(ext.video_id)
    resp = client.messages.create(
        model=config.MODEL, max_tokens=4096,
        system=PAGE_SYSTEM_PROMPT,
        messages=build_page_messages(ext.title, ext.transcript_text, ext.products, frames),
        output_config={"format": {"type": "json_schema", "schema": PAGE_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


def _mock_guide(quote: str | None) -> str | None:
    """Offline stand-in for LLM narration: the creator's own line, lightly framed.
    Live mode replaces this with real transcript+frame-grounded narration."""
    if not quote:
        return None
    q = quote.strip().strip('"')
    if not q:
        return None
    return q[0].upper() + q[1:] + ("." if q[-1] not in ".!?…" else "")


def _assemble_mock(ext: Extraction) -> dict:
    title = ext.title.strip() or "My everyday routine"
    # Keep it caption-like: strip trailing " | channel", emoji etc. left as-is.
    title = re.split(r"\s*[|–-]\s*", title)[0][:48].strip() or "My everyday routine"
    steps = [{
        "match_name": p.get("product_name", ""),
        "emoji": _guess_emoji(p.get("product_name", ""), p.get("variant_or_shade")),
        "note": _short_note(p.get("transcript_quote")),
        "guide": _mock_guide(p.get("transcript_quote")),
    } for p in ext.products]
    n = len(ext.products)
    return {
        "title": title,
        "emoji": "🎬",
        "slug": slugify(title),
        "summary": f"{title} — {n} products, each found and linked automatically.",
        "intro": (f"{title} — {n} products, in the order I actually use them, "
                  f"straight from the video."),
        "steps": steps,
    }


def _order_products(products: list[dict], steps: list[dict]) -> list[tuple[dict, dict]]:
    """Pair each input product with its step (by fuzzy-ish name match), in the
    step order the model returned; append any unmatched products at the end."""
    remaining = list(products)
    paired: list[tuple[dict, dict]] = []
    for st in steps:
        want = (st.get("match_name") or "").strip().lower()
        hit = None
        for p in remaining:
            if (p.get("product_name") or "").strip().lower() == want:
                hit = p
                break
        if hit is None:  # loose contains-match fallback
            for p in remaining:
                pn = (p.get("product_name") or "").strip().lower()
                if want and (want in pn or pn in want):
                    hit = p
                    break
        if hit is not None:
            remaining.remove(hit)
            paired.append((hit, st))
    for p in remaining:  # anything the model dropped, keep it
        paired.append((p, {"emoji": _guess_emoji(p.get("product_name", ""),
                                                  p.get("variant_or_shade")),
                            "note": _short_note(p.get("transcript_quote")),
                            "guide": _mock_guide(p.get("transcript_quote"))}))
    return paired


# --------------------------------------------------------------------------
# public entry
# --------------------------------------------------------------------------
def build_page(ext: Extraction, handle: str, prices: list[Price | None],
               retailers: list[str], client=None, mock: bool = False,
               display_name: str | None = None,
               platforms: list[str] | None = None,
               video_url: str = "") -> Page:
    assembled = _assemble_mock(ext) if mock else _assemble_llm(ext, client)

    creator = Creator(
        display_name=display_name or _display_name_from_handle(handle),
        handle=handle,
        platforms=platforms or ["YouTube", "Instagram"],
    )
    slug = slugify(assembled.get("slug") or assembled.get("title") or "routine")

    # price/retailer are index-aligned to ext.products; keep that mapping while we
    # reorder into routine order.
    price_by_id = {id(p): prices[i] if i < len(prices) else None
                   for i, p in enumerate(ext.products)}
    retailer_by_id = {id(p): retailers[i] if i < len(retailers) else ""
                      for i, p in enumerate(ext.products)}

    items: list[ProductItem] = []
    for pos, (p, st) in enumerate(_order_products(ext.products, assembled.get("steps", [])), 1):
        pid_short = f"{pos:02d}"
        rate = _RATES[(pos - 1) % len(_RATES)]
        item = ProductItem(
            name=p.get("product_name", ""),
            brand=_brand_of(p),
            emoji=st.get("emoji") or _guess_emoji(p.get("product_name", ""),
                                                   p.get("variant_or_shade")),
            variant=p.get("variant_or_shade"),
            evidence=p.get("evidence_type", "shown"),
            timestamp=fmt_timestamp(p.get("timestamp_s", 0.0)),
            timestamp_s=float(p.get("timestamp_s", 0.0)),
            note=st.get("note") or _short_note(p.get("transcript_quote")),
            guide=st.get("guide"),
            retailer=retailer_by_id.get(id(p), ""),
            price=price_by_id.get(id(p)),
            link=Link(kind="reelie", rate=rate,
                      url=f"{config.REELIE_LINK_BASE}/{handle}/{slug}/{pid_short}"),
            confidence=float(p.get("confidence", 0.0)),
            position=pos,
        )
        items.append(item)

    n = len(items)
    creator_first = creator.display_name.split()[0] if creator.display_name else "the creator"
    return Page(
        handle=handle,
        title=assembled.get("title", "My routine"),
        slug=slug,
        creator=creator,
        emoji=assembled.get("emoji", "🎬"),
        meta=f"{n} product{'s' if n != 1 else ''}, in the order {creator_first} uses them",
        summary=assembled.get("summary", ""),
        intro=assembled.get("intro", ""),
        disclosure=f"Some links earn {creator_first} a commission — it never changes what you pay.",
        source_video=SourceVideo(
            platform="youtube" if video_url and "you" in video_url else "",
            url=video_url, title=ext.title, duration_s=ext.duration_s,
        ),
        products=items,
        video_id=ext.video_id,
    )
