"""
Google Cloud Vision grounding for product extraction.

Runs OCR (on-pack text) + logo detection (brand) + web detection (visual product
match) on the keyframes, and returns a short per-frame hint. We feed those hints
to the extraction LLM so it anchors the exact brand / product / packaging text on
real image evidence instead of guessing.

Enabled only when GOOGLE_VISION_API_KEY is set; otherwise annotate() is a no-op
and everything downstream works exactly as before. Never raises — best-effort.

  GOOGLE_VISION_API_KEY = an API key for a project with the Vision API enabled.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import urllib.error
import urllib.request

import certifi

_API = "https://vision.googleapis.com/v1/images:annotate"
_CTX = ssl.create_default_context(cafile=certifi.where())
_BATCH = 16          # Vision allows up to 16 images per request
_MAX_OCR = 220       # chars of on-pack text per frame (keep the prompt lean)


def enabled() -> bool:
    return bool(os.environ.get("GOOGLE_VISION_API_KEY", "").strip())


def _post(body: dict) -> dict:
    key = os.environ["GOOGLE_VISION_API_KEY"].strip()
    req = urllib.request.Request(
        f"{_API}?key={key}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45, context=_CTX) as r:
        return json.loads(r.read().decode())


def _hint(resp: dict) -> dict:
    ocr = ((resp.get("fullTextAnnotation") or {}).get("text") or "")
    ocr = " ".join(ocr.split())[:_MAX_OCR]
    logos = [l.get("description", "") for l in resp.get("logoAnnotations", []) if l.get("description")]
    web = resp.get("webDetection") or {}
    guesses = [g.get("label", "") for g in web.get("bestGuessLabels", []) if g.get("label")]
    entities = [e.get("description", "") for e in (web.get("webEntities") or [])
                if e.get("description") and float(e.get("score", 0)) > 0.5]
    return {"ocr": ocr, "logos": logos[:5], "guess": guesses[:3], "entities": entities[:6]}


def annotate(frame_paths: list) -> dict:
    """Return {frame_path: hint_dict}. Empty if disabled or on any error."""
    if not enabled() or not frame_paths:
        return {}
    feats = [{"type": "TEXT_DETECTION"},
             {"type": "LOGO_DETECTION"},
             {"type": "WEB_DETECTION", "maxResults": 8}]
    out: dict = {}
    for i in range(0, len(frame_paths), _BATCH):
        batch = frame_paths[i:i + _BATCH]
        try:
            reqs = []
            for p in batch:
                with open(p, "rb") as f:
                    data = base64.standard_b64encode(f.read()).decode()
                reqs.append({"image": {"content": data}, "features": feats})
            resp = _post({"requests": reqs})
            for p, r in zip(batch, resp.get("responses", [])):
                out[p] = _hint(r or {})
        except Exception as e:  # noqa: BLE001
            print(f"[vision] batch failed: {type(e).__name__}: {e}", flush=True)
    return out


def hint_text(h: dict) -> str:
    """Render one frame's hint into a compact prompt line ('' if nothing useful)."""
    if not h:
        return ""
    parts = []
    if h.get("logos"):
        parts.append("brand logo(s): " + ", ".join(h["logos"]))
    if h.get("guess"):
        parts.append("visual match: " + ", ".join(h["guess"]))
    if h.get("entities"):
        parts.append("related: " + ", ".join(h["entities"]))
    if h.get("ocr"):
        parts.append('on-pack text: "' + h["ocr"] + '"')
    return " · ".join(parts)
