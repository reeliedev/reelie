"""
Prompts + JSON schemas for the two LLM steps in page generation:
  1. page assembly  — products (+ transcript) -> title, emoji, slug, ordered steps
  2. price estimate — brand/name/variant     -> typical retail price + retailer

Schemas are enforced via the Messages API `output_config.format` (structured
outputs), the same style used in ../../video-llm/prompts.py.
"""

from __future__ import annotations

import json

# ==========================================================================
# 1. PAGE ASSEMBLY
# ==========================================================================
PAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {
            "type": "string",
            "description": "Short, warm, human page title in the creator's voice — "
            "how they'd caption the routine (e.g. 'My K-beauty night routine', "
            "'Everyday no-makeup makeup'). No brand names, no 'Reelie'. Max ~48 chars.",
        },
        "emoji": {
            "type": "string",
            "description": "A single emoji that captures the routine's vibe.",
        },
        "slug": {
            "type": "string",
            "description": "URL slug: lowercase, words separated by hyphens, no "
            "punctuation, 2-5 words (e.g. 'k-beauty-night-routine').",
        },
        "summary": {
            "type": "string",
            "description": "One factual sentence describing the page for search "
            "engines and AI assistants: what the routine is and roughly how many "
            "products. No marketing fluff.",
        },
        "intro": {
            "type": "string",
            "description": "A warm 2-3 sentence guide introduction in the creator's "
            "first-person voice, as if walking a friend through this routine. Set up "
            "what the routine is for and the overall approach. Ground every claim in "
            "the transcript/frames — never invent results, skin types, or occasions "
            "not evidenced. No brand names here, no 'Reelie'.",
        },
        "steps": {
            "type": "array",
            "description": "The products, ordered as a routine the way the creator "
            "would actually do them (cleanse -> treat -> moisturise -> protect for "
            "skincare; base -> eyes -> lips for makeup). Include EVERY input product "
            "exactly once, matched by name.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "match_name": {
                        "type": "string",
                        "description": "The product_name from the input list this step "
                        "refers to, copied verbatim so it can be matched back.",
                    },
                    "emoji": {
                        "type": "string",
                        "description": "One emoji for this product (a cleanser 🧼, "
                        "toner 🧴, serum 💧, sunscreen 🌞, lipstick 💄, etc.).",
                    },
                    "note": {
                        "type": ["string", "null"],
                        "description": "A very short (<=8 word) usage note in the "
                        "creator's voice, ideally drawn from their transcript quote "
                        "(e.g. 'melts everything off', 'three layers on dry days'). "
                        "Null if nothing natural to say.",
                    },
                    "guide": {
                        "type": ["string", "null"],
                        "description": "1-3 sentences of GUIDE narration for this step, "
                        "in the creator's first-person voice: what this product is for "
                        "in the routine, how/where she applies it, and any technique or "
                        "tip she actually gives. Base it strictly on the transcript and "
                        "the video frames — describe only what is said or shown. Do not "
                        "invent benefits, ingredients, or claims. Null if there is truly "
                        "nothing grounded to say.",
                    },
                },
                "required": ["match_name", "emoji", "note", "guide"],
            },
        },
    },
    "required": ["title", "emoji", "slug", "summary", "intro", "steps"],
}

PAGE_SYSTEM_PROMPT = """\
You are a beauty editor turning ONE creator video into a clean, shoppable "routine \
guide" — a page a reader can both FOLLOW as a how-to and shop from. You are given \
the products (with any transcript quotes), the video's title and transcript, and \
often keyframes from the video itself.

Your job:
- Write a short, warm page TITLE in the creator's own voice — the caption they'd \
give this routine. Never include brand names or the word "Reelie".
- Write an INTRO: 2-3 sentences, first person, that set up the routine like the \
creator is walking a friend through it.
- Pick ONE emoji for the page and ONE for each product.
- Order the products into the sequence the creator would actually use them \
(skincare: cleanse -> tone -> treat/serum -> eye -> moisturise -> SPF; makeup: \
prep/base -> concealer -> powder -> eyes -> cheeks -> lips). Use the transcript \
order as a hint but prefer the natural routine order.
- For each product write GUIDE narration: 1-3 sentences on what it's for at this \
step, how/where she applies it, and any technique she gives. Also give the short \
NOTE (<=8 words) for compact views.

GROUNDING (critical): Narrate only what is actually said in the transcript or \
visible in the frames. Never invent benefits, ingredients, skin types, results, \
shades, or steps that aren't evidenced. If the video is terse and there's little to \
say about a product, keep its guide short or set it null rather than padding. You \
are describing THIS video, not beauty knowledge in general.

- Include EVERY product from the input exactly once. Match each step back to an \
input product via `match_name` copied verbatim.

Return ONLY the structured JSON.\
"""


def build_page_messages(video_title: str, transcript_text: str, products: list,
                        frames: list | None = None) -> list:
    """`frames` is an optional list of (label, media_type, base64_data) tuples —
    keyframes from the video so the model can narrate from what it sees."""
    lines = []
    for p in products:
        b = p.get("brand") or "(brand unknown)"
        v = f" · {p['variant_or_shade']}" if p.get("variant_or_shade") else ""
        q = f'  — quote: "{p["transcript_quote"]}"' if p.get("transcript_quote") else ""
        lines.append(f"- {b}: {p.get('product_name','')}{v}{q}")
    prod_block = "\n".join(lines) or "(none)"

    text = ""
    if video_title:
        text += f"VIDEO TITLE: {video_title}\n\n"
    text += "PRODUCTS (match each step back by product_name):\n" + prod_block
    if transcript_text:
        text += "\n\n=== TRANSCRIPT (verbatim; your only source for what she says) ===\n" \
            + transcript_text[:6000]
    if frames:
        text += ("\n\n=== VIDEO FRAMES ===\nKeyframes from the video follow, in time "
                 "order. Narrate only what these + the transcript actually show.")

    content: list = [{"type": "text", "text": text}]
    for label, media_type, data in (frames or []):
        content.append({"type": "text", "text": f"Frame {label}:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })
    content.append({"type": "text", "text": "\nBuild the routine guide."})
    return [{"role": "user", "content": content}]


# ==========================================================================
# 2. PRICE ESTIMATE
# ==========================================================================
PRICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "prices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The 0-based index of the product in the input list.",
                    },
                    "amount_usd": {
                        "type": "number",
                        "description": "Typical current US retail price in USD for the "
                        "standard full size. Your best estimate from product knowledge.",
                    },
                    "retailer": {
                        "type": "string",
                        "description": "A common retailer that stocks it (e.g. 'Sephora', "
                        "'Ulta', 'YesStyle', 'Olive Young', 'Amazon').",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "0-1 confidence in the price estimate.",
                    },
                },
                "required": ["index", "amount_usd", "retailer", "confidence"],
            },
        }
    },
    "required": ["prices"],
}

PRICE_SYSTEM_PROMPT = """\
You are a beauty/skincare retail-pricing estimator. For each product you are given \
(brand, name, variant), estimate its TYPICAL current US retail price in USD for the \
standard full size, and name a common retailer that stocks it.

Rules:
- Use your product knowledge to give a realistic single price (not a range). If the \
brand is unknown, price it like a typical product of that category and drop your \
confidence.
- Prefer the product's usual full-size price, not travel/mini sizes.
- retailer: a real store that commonly carries this brand/category.
- confidence: honest 0-1. Lower it when brand is null or the item is generic.
These are approximate estimates, not live quotes. Return ONLY the structured JSON.\
"""


def build_price_messages(products: list) -> list:
    lines = []
    for i, p in enumerate(products):
        b = p.get("brand") or "(brand unknown)"
        v = f" · {p['variant_or_shade']}" if p.get("variant_or_shade") else ""
        lines.append(f"[{i}] {b}: {p.get('product_name','')}{v}")
    text = ("Estimate the US retail price for each product:\n\n"
            + "\n".join(lines) + "\n\nReturn one entry per product index.")
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]
