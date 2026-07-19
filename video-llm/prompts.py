"""
Extraction prompt + JSON schema for the beauty/skincare product extractor.

Keep all prompt engineering in THIS file so you can iterate on wording and the
schema without touching pipeline code. `build_extraction_messages()` and
`EXTRACTION_SCHEMA` are the only things pipeline.py imports.

Model: claude-sonnet-4-6 (multimodal). The schema is enforced via the Messages
API `output_config.format` (structured outputs), so the model is *constrained*
to emit conforming JSON rather than merely asked to.
"""

# ---------------------------------------------------------------------------
# JSON schema — enforced by the API (structured outputs).
#
# Notes on structured-output limitations (validated client-side instead):
#   - `confidence` is 0..1 but numeric min/max isn't enforceable in the schema;
#     we clamp/validate in pipeline.py.
#   - Every object needs additionalProperties:false and a `required` list.
#   - Nullable fields are expressed as {"type": ["string", "null"]}.
# ---------------------------------------------------------------------------
EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The specific product name as used/shown. "
                        "Exclude the brand from this field when the brand is "
                        "separable (e.g. product_name='Soft Pinch Liquid Blush', "
                        "brand='Rare Beauty'). Keep product line/qualifier words "
                        "that are part of the product's name.",
                    },
                    "brand": {
                        "type": ["string", "null"],
                        "description": "Brand/manufacturer. MUST be null unless the "
                        "brand is explicitly spoken, written on-screen, or clearly "
                        "legible on the packaging in a frame. Never infer or guess "
                        "a brand from the product type or your own knowledge.",
                    },
                    "variant_or_shade": {
                        "type": ["string", "null"],
                        "description": "Shade name/number, size, formulation, or "
                        "variant (e.g. 'Shade 2N', 'Happy', 'SPF 50', '50ml'). "
                        "Null if not stated or shown.",
                    },
                    "evidence_type": {
                        "type": "string",
                        "enum": ["spoken", "shown", "both", "on-screen-text", "description"],
                        "description": "How the product was evidenced: 'spoken' "
                        "(said in the transcript), 'shown' (visible product/"
                        "packaging in a frame), 'both' (spoken AND shown), or "
                        "'on-screen-text' (appears only as burned-in text/caption/"
                        "graphic, not spoken and not physical packaging).",
                    },
                    "timestamp_s": {
                        "type": "number",
                        "description": "Best single timestamp in SECONDS where the "
                        "product is first clearly evidenced. Use the transcript "
                        "word timestamp when spoken; use the keyframe's labeled "
                        "time when only shown.",
                    },
                    "transcript_quote": {
                        "type": ["string", "null"],
                        "description": "Short verbatim quote from the transcript that "
                        "mentions the product. Null when the product is only shown "
                        "or only appears as on-screen text.",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "0.0-1.0 confidence that this is a real, "
                        "correctly-identified product the creator actually uses or "
                        "recommends. Lower it when the brand/name is uncertain, the "
                        "frame is blurry, or the mention is ambiguous.",
                    },
                },
                "required": [
                    "product_name",
                    "brand",
                    "variant_or_shade",
                    "evidence_type",
                    "timestamp_s",
                    "transcript_quote",
                    "confidence",
                ],
            },
        }
    },
    "required": ["products"],
}


# ---------------------------------------------------------------------------
# System prompt — the rules that shape extraction behavior.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an expert product-extraction analyst for beauty and skincare creator \
videos. You are given (1) a time-stamped transcript of a single video and (2) a \
set of keyframes sampled from that same video, each labeled with its timestamp \
in seconds. Your job is to identify the beauty/skincare products the CREATOR \
actually uses, applies, or genuinely recommends in the video.

WHAT COUNTS (include):
- Products the creator physically uses or applies on camera.
- Products the creator explicitly recommends, praises, or names as part of their \
routine/favorites.
- A product evidenced by clearly legible packaging in a frame, even if not spoken.
- ALL categories, not just color makeup. Include skincare and base-prep steps: \
moisturizer, toner, essence, serum, face oil, sunscreen/SPF, setting/face mist, \
hydrosol, and primer.
- Makeup application TOOLS the creator uses ARE products: brushes, sponges, \
beauty blenders/puffs, eyelash curlers, and applicators.
- Colored/cosmetic contact lenses count.

WHAT DOES NOT COUNT (exclude):
- Sponsor bumpers / ad reads for products the creator does not actually use in \
the video, and generic "this video is sponsored by" mentions.
- The creator's own channel merch, Patreon, discount codes, or storefront plugs.
- Products only mentioned to dismiss, compare against, or say they DON'T use.
- Non-beauty equipment: phones, cameras, ring lights, tripods, mirrors.
- Background clutter you can't actually identify.

CORE RULES:
1. BRAND HONESTY: Only fill `brand` when the brand is explicitly spoken, written \
on screen, or clearly legible on packaging in a frame. If you are not sure of the \
brand, set `brand` to null. NEVER guess a brand from the product category or from \
prior knowledge of what product this "looks like".
2. DEDUPE vs DISTINCT: If the SAME product is mentioned or shown multiple times, \
output it ONCE — merge the evidence: pick the earliest clear `timestamp_s`, set \
`evidence_type` to "both" if it is both spoken and shown, and keep the most \
informative `variant_or_shade` and `transcript_quote`. BUT do NOT collapse \
DIFFERENT products just because they share a brand: two different items from the \
same brand (e.g. two separate brow products, or a primer and a highlighter from \
one brand) are SEPARATE entries. Different shades used from the SAME single \
product stay one entry with the shade(s) noted.
3. EVIDENCE FIDELITY: `transcript_quote` must be verbatim from the transcript (or \
null). Do not paraphrase. Set it to null when the product is only shown or only \
appears as on-screen text.
4. VARIANT/SHADE: Capture the shade, number, size, or formulation only if it is \
actually stated or visible. Otherwise null.
5. CONFIDENCE: Calibrate honestly. High (>0.85) when name and brand are both \
clearly evidenced. Medium when the product is clear but the brand is uncertain or \
inferred-from-context. Low (<0.5) when you are guessing at identity or reading a \
blurry label. It is better to return a product with brand=null and lower \
confidence than to fabricate a brand.
6. If NO qualifying products appear, return {"products": []}.

Return ONLY the structured JSON conforming to the provided schema. No commentary.\
"""


# ---------------------------------------------------------------------------
# Per-request user message builder.
# ---------------------------------------------------------------------------
def build_extraction_messages(transcript_text, frames, chunk_note=None):
    """
    Build the `messages` list for one API call.

    Args:
        transcript_text: str, the (possibly chunked) time-stamped transcript.
        frames: list of {"timestamp_s": float, "media_type": str, "data": b64str}
                for the keyframes to include in THIS call.
        chunk_note: optional str describing the time window when a long video is
                    split across multiple calls (helps the model with timestamps).

    Returns a single-element list with one user message containing interleaved
    text + image blocks.
    """
    content = []

    header = (
        "Extract the beauty/skincare products the creator uses or recommends in "
        "this video, following the rules in the system prompt.\n"
    )
    if chunk_note:
        header += f"\nNOTE: {chunk_note}\n"
    content.append({"type": "text", "text": header})

    # Transcript block.
    content.append(
        {
            "type": "text",
            "text": "=== TIME-STAMPED TRANSCRIPT ===\n" + transcript_text,
        }
    )

    # Keyframes, each preceded by a label so the model can attribute timestamps.
    content.append(
        {
            "type": "text",
            "text": "=== KEYFRAMES (each labeled with its timestamp in seconds) ===",
        }
    )
    for fr in frames:
        content.append(
            {"type": "text", "text": f"[frame @ {fr['timestamp_s']:.1f}s]"}
        )
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": fr["media_type"],
                    "data": fr["data"],
                },
            }
        )

    return [{"role": "user", "content": content}]


# ---------------------------------------------------------------------------
# Reconciliation pass — a final cheap text-only call that cleans up the merged
# product list (collapses ASR-variant duplicates that fuzzy matching misses,
# fixes clearly-misheard brands, drops noise). Reuses EXTRACTION_SCHEMA.
# ---------------------------------------------------------------------------
RECONCILE_SYSTEM_PROMPT = """\
You are cleaning up a raw list of beauty/skincare products that were extracted \
from a single creator video across several passes. Because of chunking and \
speech-to-text errors, the list contains duplicates and mis-transcribed names. \
Return a corrected, de-duplicated list conforming to the schema.

Do the following:
1. MERGE DUPLICATES — combine entries that refer to the SAME real product, \
INCLUDING when the brand or name was mis-transcribed as a phonetic variant \
(e.g. "Cleo"/"CLIO", "Fui"/"fwee", "Desique"/"Jasique"/"dasique", \
"Judy Doll"/"Judydoll", "Fraudage"/"Frottage"). Also merge a spoken-only entry \
with the shown/packaging entry for the same product. When merging: keep the \
EARLIEST `timestamp_s`; set `evidence_type` to "both" if the merged entries \
include both a spoken and a shown (or on-screen-text) version; keep the most \
complete `product_name`, `variant_or_shade`, and `transcript_quote`; use the \
HIGHEST `confidence`.
2. FIX MISHEARD BRANDS — when a duplicate entry or the product name makes the \
real brand clear, use the correct canonical spelling. Prefer a brand that came \
from clearly-shown packaging over a spoken-only mishearing. But NEVER invent a \
brand: if you cannot confidently identify it, set `brand` to null rather than guess.
3. KEEP DISTINCT PRODUCTS SEPARATE — do NOT merge two genuinely different \
products just because they share a brand or category. Two different brow products \
from one brand remain two entries.
4. DROP noise — entries that are not real beauty/skincare products.

Do NOT add any product that is not represented in the input list. Do NOT raise a \
confidence you are unsure about. Return ONLY the schema JSON.\
"""


def build_reconcile_messages(products):
    import json
    blob = json.dumps({"products": products}, indent=2, ensure_ascii=False)
    return [{
        "role": "user",
        "content": [{
            "type": "text",
            "text": "Here is the raw extracted product list to reconcile "
                    "(merge duplicates, fix misheard brands, drop noise):\n\n" + blob,
        }],
    }]


# ---------------------------------------------------------------------------
# Description parsing — turn the creator's video description into products.
# ---------------------------------------------------------------------------
DESCRIPTION_PARSE_SYSTEM_PROMPT = """\
You are parsing a beauty creator's video DESCRIPTION into a structured product \
list. Creators often list the products they used, in varied formats — e.g. \
"{Brand} Product #shade", "@brandhandle product name shade", or \
"- Brand Product (shade) https://affiliate-link". Extract each product.

Rules:
- brand: the real brand name. Convert @handles / lowercase handles to the proper \
brand when obvious (e.g. @hudabeauty -> "Huda Beauty", @yslbeauty -> "YSL", \
@makeupbymario -> "Makeup by Mario", @tower28beauty -> "Tower 28"). If you truly \
can't tell, use the handle text without the @. If there's genuinely no brand, null.
- product_name: the product only — no brand, no shade.
- variant_or_shade: the shade/number/size if given, else null.
- evidence_type: always "description".
- timestamp_s: 0.  transcript_quote: null.
- confidence: 0.9 (the creator's own list is reliable); lower only if an entry is \
genuinely ambiguous.
- ONE entry per distinct product. If a single line lists several products (e.g. \
"bronzer Light Medium, blush veil Perfect Pink, and setting powder Fair Pink" \
from one brand), split into separate entries that share that brand.
- IGNORE non-products: discount/promo codes, bare social handles, affiliate \
boilerplate, camera/editing/music gear, and hair-styling tools.
Return ONLY the schema JSON.\
"""


def build_description_parse_messages(description_text):
    return [{
        "role": "user",
        "content": [{
            "type": "text",
            "text": "Parse the products from this video description:\n\n"
                    + description_text,
        }],
    }]


# ---------------------------------------------------------------------------
# Merge — combine video-extracted products with description products into one
# comprehensive, de-duplicated list (the union).
# ---------------------------------------------------------------------------
MERGE_SYSTEM_PROMPT = """\
You are producing ONE comprehensive, de-duplicated beauty/skincare product list \
for a single video by combining two sources:
  (A) VIDEO — products extracted from what was seen/heard on screen. Accurate \
about what was actually used and shown, but OFTEN MISSING BRANDS (the creator \
didn't hold up packaging or say the name), so many entries are generic like \
"Bronzer" with brand null.
  (B) DESCRIPTION — products the creator listed in their own description. An \
authoritative brand/shade list, but may include items not clearly shown, and \
may omit something the creator used but forgot to list.

Produce the UNION — the most comprehensive list:
1. Include every DISTINCT product from either source.
2. MERGE entries that refer to the SAME product across the two sources. A generic \
video entry ("Bronzer", brand null) should merge with the matching description \
entry ("Makeup by Mario Bronzer, Light Medium") — same product, seen in the video \
and named in the description. Use product TYPE + context to align them.
3. When merging, PREFER the DESCRIPTION's brand and shade (the creator's own \
naming is authoritative). Preserve the VIDEO's evidence: if a product was in the \
video at all, set evidence_type to its video evidence ("spoken"/"shown"/"both"/\
"on-screen-text") and keep its timestamp_s and transcript_quote. For a product \
ONLY in the description, evidence_type = "description". For a product ONLY in the \
video, keep its video evidence_type.
4. KEEP video-only products the description omits.
5. Do NOT invent products present in neither source. Keep genuinely different \
products separate (don't over-merge two different items that share a brand).
Set confidence to the higher of the two sources when merged. Return ONLY the \
schema JSON.\
"""


def build_merge_messages(video_products, description_products):
    import json
    v = json.dumps({"products": video_products}, indent=2, ensure_ascii=False)
    d = json.dumps({"products": description_products}, indent=2, ensure_ascii=False)
    return [{
        "role": "user",
        "content": [{
            "type": "text",
            "text": "SOURCE A — extracted from the VIDEO:\n" + v
                    + "\n\nSOURCE B — from the creator's DESCRIPTION:\n" + d
                    + "\n\nProduce the merged comprehensive list.",
        }],
    }]


# ---------------------------------------------------------------------------
# Mirror detection — is the video horizontally flipped (selfie camera)? If so,
# packaging text reads backwards and must be un-mirrored before extraction.
# ---------------------------------------------------------------------------
MIRROR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "mirrored": {
            "type": "boolean",
            "description": "True only if text on physical objects reads reversed.",
        },
        "reason": {
            "type": "string",
            "description": "What object-text you judged and why.",
        },
    },
    "required": ["mirrored", "reason"],
}

MIRROR_DETECT_SYSTEM_PROMPT = """\
You are shown a few still frames from a phone-camera beauty video. Some videos \
are horizontally MIRRORED — filmed with a selfie/front camera and never flipped \
back. In a mirrored video, text on PHYSICAL OBJECTS (product packaging and \
labels, brand names, clothing logos, background signage) appears REVERSED / \
backwards.

CRITICAL: subtitle/caption text that was burned in during EDITING reads NORMALLY \
even in a mirrored video. IGNORE all subtitles and caption overlays — judge ONLY \
text that is on physical objects in the scene.

Decide whether the video is horizontally mirrored:
- mirrored = true ONLY if you can see text on a physical object that is clearly \
reversed/backwards.
- mirrored = false if physical-object text reads normally, OR if there isn't \
enough legible physical-object text to tell (when unsure, say false).
Return {"mirrored": bool, "reason": "..."}.\
"""


def build_mirror_detect_messages(frames):
    content = [{"type": "text",
                "text": "Frames from the video (ignore subtitles/captions; judge "
                        "only text on physical objects):"}]
    for fr in frames:
        content.append({"type": "text", "text": f"[frame @ {fr['timestamp_s']:.1f}s]"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": fr["media_type"], "data": fr["data"]}})
    return [{"role": "user", "content": content}]


# ---------------------------------------------------------------------------
# Brand recovery — last-resort: for a product seen in the video but returned
# with no brand, ask Claude to identify the SPECIFIC product from its packaging
# using its own product knowledge. Strict anti-guessing.
# ---------------------------------------------------------------------------
RECOVER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "identified": {"type": "boolean",
                       "description": "True only if you recognize the specific product."},
        "brand": {"type": ["string", "null"]},
        "product_name": {"type": ["string", "null"]},
        "variant_or_shade": {"type": ["string", "null"]},
        "confidence": {"type": "number",
                       "description": "0-1 confidence it is exactly this product."},
        "reason": {"type": "string",
                   "description": "What in the packaging made it identifiable (or not)."},
    },
    "required": ["identified", "brand", "product_name", "variant_or_shade",
                 "confidence", "reason"],
}

RECOVER_SYSTEM_PROMPT = """\
You are a beauty-product identification expert. You are shown a few frames from a \
video in which the creator is using or holding a specific product that an earlier \
pass could only describe GENERICALLY (e.g. "Bronzer", "Concealer") with NO brand. \
Using your knowledge of real beauty/skincare products, identify the SPECIFIC \
product — but ONLY if you can genuinely recognize it.

STRICT RULES:
- Identify ONLY from what is visible in these frames. You may recognize a product \
by distinctive packaging (shape, color, cap, logo, embossing) even when the text \
isn't fully legible — but you must be genuinely confident it is that exact product.
- NEVER guess a brand from the product category, from what's trendy, or from the \
creator's general style. If you cannot confidently recognize the SPECIFIC product, \
set identified=false and brand=null.
- Saying "not identified" is the correct, expected answer when you're unsure. \
Fabricating a brand is a serious error.
- confidence: your honest probability that this is the exact product. Only above \
0.7 when the packaging is distinctive and clearly matches a product you know well.
Return ONLY the schema JSON.\
"""


MATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pred_index": {"type": "integer"},
                    "gt_index": {"type": "integer"},
                    "variant_match": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["pred_index", "gt_index", "variant_match", "reason"],
            },
        }
    },
    "required": ["matches"],
}

MATCH_SYSTEM_PROMPT = """\
You are grading a beauty-product extraction against a ground-truth answer key for \
ONE video. You are given two indexed lists: PREDICTED products (what a tool \
extracted) and GROUND-TRUTH products (the correct answer). Match them.

A predicted product matches a ground-truth product ONLY if they refer to the SAME \
real product. BE TOLERANT of superficial differences:
- spelling / British-vs-American (multicolour = multicolor), spacing (lip liner = \
lipliner = lip-liner);
- speech-to-text mishearings of brand or product names when it's clearly the same \
item (e.g. "Miro" for "Byroe", "Hyalun Ice" for "Hyssop Rice");
- generic-vs-specific naming when it's clearly the same item — a brand-null \
generic matches the named product when context makes it the same thing (e.g. \
"eye patches" matches "Summer Fridays Jet Lag Eye Patches"; "Tatcha moisturizer" \
matches "Tatcha The Dewy Skin Cream").

But DO NOT match two genuinely DIFFERENT products, even from the same brand:
- "Medicube PORE 99 toner pads" is NOT "Medicube PDRN Pink Collagen Toner Pad";
- "Arencia Blue/Hyssop cleanser" is NOT "Arencia Green cleanser";
- a bronzer is not a blush; a foundation is not a concealer.

Rules:
- ONE-TO-ONE: each predicted product matches at most one ground-truth product and \
vice versa. Choose the single best match.
- For each match, set variant_match = true if the shade/variant/size also agrees \
OR both sides omit it; false if they specify conflicting shades.
- Omit non-matches entirely (unmatched predictions and unmatched labels).
Return ONLY the schema JSON.\
"""


JUDGE_PAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "match": {"type": "boolean",
                  "description": "True if both refer to the same real product."},
        "variant_match": {"type": "boolean",
                          "description": "True if shade/variant agrees or both omit it."},
        "reasoning": {"type": "string",
                      "description": "ONE short line explaining the verdict."},
    },
    "required": ["match", "variant_match", "reasoning"],
}

JUDGE_PAIR_SYSTEM_PROMPT = """\
You are grading ONE predicted beauty product against ONE ground-truth product from \
an answer key. Decide whether they refer to the SAME real product.

BE TOLERANT of superficial differences:
- spelling / British-vs-American (multicolour = multicolor), spacing (lip liner = \
lipliner);
- speech-to-text mishearings of brand or product names when clearly the same item \
("Miro" for "Byroe", "Hyalun Ice" for "Hyssop Rice");
- generic-vs-specific naming for the same item (brand-null "eye patches" = "Summer \
Fridays Jet Lag Eye Patches"; "Tatcha moisturizer" = "Tatcha The Dewy Skin Cream").

But DO NOT match two genuinely DIFFERENT products, even from the same brand:
- "Medicube PORE 99 toner pads" is NOT "Medicube PDRN Pink Collagen Toner Pad";
- "Arencia Blue/Hyssop cleanser" is NOT "Arencia Green cleanser";
- a bronzer is not a blush; a foundation is not a concealer.

Also set variant_match: true if the shade/variant/size agrees OR both omit it; \
false if they specify conflicting shades.

You MUST include a one-line `reasoning` string with every verdict. Return ONLY a \
single JSON object with exactly these keys: "match" (boolean), "variant_match" \
(boolean), "reasoning" (a one-line string). No markdown fences, no other text.\
"""


def build_judge_pair_messages(pred, gt):
    def fmt(p):
        return (f"brand={p.get('brand') or '—'} | name={p.get('product_name','')}"
                + (f" | shade={p.get('variant_or_shade')}" if p.get('variant_or_shade') else ""))
    text = ("PREDICTED product:\n  " + fmt(pred)
            + "\n\nGROUND-TRUTH product:\n  " + fmt(gt)
            + "\n\nDo they refer to the same real product?")
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


def build_match_messages(preds, gts):
    def fmt(items):
        out = []
        for i, p in enumerate(items):
            b = p.get("brand") or "—"
            v = p.get("variant_or_shade") or ""
            out.append(f"  [{i}] brand={b} | name={p.get('product_name','')}"
                       + (f" | shade={v}" if v else ""))
        return "\n".join(out) or "  (none)"
    text = ("PREDICTED products:\n" + fmt(preds)
            + "\n\nGROUND-TRUTH products:\n" + fmt(gts)
            + "\n\nReturn the one-to-one matches.")
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


def build_recover_messages(product, frames):
    pname = product.get("product_name") or "(unnamed)"
    ev = product.get("evidence_type", "")
    ts = product.get("timestamp_s", 0)
    content = [{
        "type": "text",
        "text": (f"An earlier pass extracted this product generically, with no brand:\n"
                 f"  product_name: {pname}\n  brand: null\n"
                 f"  evidence: {ev} around {ts:.0f}s\n\n"
                 f"Here are the frames from around that moment. Identify the specific "
                 f"product ONLY if you truly recognize it from its packaging:"),
    }]
    for fr in frames:
        content.append({"type": "text", "text": f"[frame @ {fr['timestamp_s']:.1f}s]"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": fr["media_type"], "data": fr["data"]}})
    return [{"role": "user", "content": content}]
