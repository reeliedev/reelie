"""
Render a canonical Page into a standalone public web page — an editorial
"shop + guide" of the creator's routine (not a widened mobile screen), with
embedded JSON-LD. Uses a simple {{TOKEN}} template so no template-engine
dependency is needed.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import config
from models import Page
from render.schema import page_graph
from render import recommend

_TEMPLATE = Path(__file__).parent / "templates" / "public_page.html"

# How the extraction's evidence flag reads to a shopper.
_EVIDENCE_LABEL = {
    "both": "Shown &amp; mentioned",
    "shown": "Shown in the video",
    "spoken": "Mentioned in the video",
    "description": "From the description",
}


def _esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


def _money(amount: float, currency: str) -> str:
    """Whole-dollar display for round amounts, else 2dp. USD/‌£/€ symbols."""
    sym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(currency, "")
    if abs(amount - round(amount)) < 0.005:
        return f"{sym}{int(round(amount))}"
    return f"{sym}{amount:,.2f}"


def _totals(page: Page) -> dict:
    priced = [p for p in page.products if p.price]
    amounts = [p.price.amount for p in priced]
    currency = priced[0].price.currency if priced else "USD"
    total = sum(amounts)
    any_estimated = any(p.price.estimated for p in priced)
    retailers = [p.retailer for p in page.products if p.retailer]
    seen: list[str] = []
    for r in retailers:
        if r not in seen:
            seen.append(r)
    return {
        "count": len(page.products),
        "priced_count": len(priced),
        "total_display": _money(total, currency) if amounts else "",
        "range_display": (
            f"{_money(min(amounts), currency)}–{_money(max(amounts), currency)}"
            if amounts else ""
        ),
        "any_estimated": any_estimated,
        "retailers": seen,
        "retailer_count": len(seen),
    }


def _approx(estimated: bool) -> str:
    return ' <span class="approx">approx.</span>' if estimated else ""


def _group_by_clip(products: list) -> list[list]:
    """Group products that share the same clip into one 'moment', preserving
    routine order (a moment appears where its first product does). Products with
    no clip each form their own group so the no-source fallback is unchanged."""
    groups: list[list] = []
    index: dict[str, int] = {}
    for p in products:
        key = p.clip or f"solo-{p.id}"
        if key in index:
            groups[index[key]].append(p)
        else:
            index[key] = len(groups)
            groups.append([p])
    return groups


def _avatar(gradient: list) -> str:
    g0 = gradient[0] if gradient else "#E8E4DA"
    g1 = gradient[1] if len(gradient) > 1 else "#D8D2C4"
    return (f'<span class="who-av" style="background:linear-gradient(135deg,{g0},{g1})"></span>')


def _also_used_by(p, page: Page, pages: list[dict]) -> str:
    """Small 'also used by' strip of other creators using this exact product."""
    key = recommend.product_key(p.brand, p.name)
    others = recommend.creators_using(key, pages, exclude_handle=page.handle, limit=4)
    if not others:
        return ""
    chips = "".join(
        f'<a class="who" href="{config.BASE_URL}/{_esc(c["handle"])}" title="{_esc(c["name"])}">'
        f'{_avatar(c["avatar_gradient"])}</a>'
        for c in others
    )
    return f'<div class="s-also"><span class="s-also-label">Also used by</span>{chips}</div>'


def _product_block(p, page: Page, pages: list[dict]) -> str:
    brand = f'<div class="s-brand">{_esc(p.brand)}</div>' if p.brand else ""
    variant = f'<span class="s-variant">{_esc(p.variant)}</span>' if p.variant else ""
    narration = p.guide or (f'"{p.note}"' if p.note else None)
    note = f'<p class="s-note">{_esc(narration)}</p>' if narration else ""
    evidence = _EVIDENCE_LABEL.get(p.evidence, "")
    ev_tag = f'<div class="s-tags"><span class="tag">{evidence}</span></div>' if evidence else ""
    price_html = ""
    if p.price:
        price_html = f'<div class="s-price">{_esc(p.price.display)}{_approx(p.price.estimated)}</div>'
    retailer = _esc(p.retailer) if p.retailer else "Shop"
    return f"""          <div class="s-product">
            {brand}
            <h3 class="s-name">{_esc(p.name)} {variant}</h3>
            {ev_tag}
            {note}
            <div class="s-buy">
              {price_html}
              <a class="shop" href="{_esc(p.link.url)}" rel="sponsored nofollow" target="_blank">Shop at {retailer} <span aria-hidden="true">→</span></a>
            </div>
            {_also_used_by(p, page, pages)}
          </div>"""


def _similar_module(page: Page, pages: list[dict]) -> str:
    sims = recommend.similar_creators(page.handle, pages, limit=6)
    if not sims:
        return ""
    cards = "".join(
        f'<a class="sim-card" href="{config.BASE_URL}/{_esc(c["handle"])}">'
        f'{_avatar(c["avatar_gradient"])}'
        f'<span class="sim-name">{_esc(c["name"])}</span>'
        f'<span class="sim-reason">{_esc(c["reason"])}</span></a>'
        for c in sims
    )
    return (f'<section class="similar"><div class="wrap">'
            f'<div class="eyebrow">You might also like</div>'
            f'<h2>Creators with a similar shelf</h2>'
            f'<div class="sim-row">{cards}</div></div></section>')


def _steps_html(page: Page, pages: list[dict]) -> str:
    """The guide: one editorial block per video moment (clip), listing every
    product used in that moment so a shared clip is never repeated."""
    rows = []
    for gi, group in enumerate(_group_by_clip(page.products), 1):
        lead = group[0]
        if lead.clip:
            poster = f' poster="{_esc(lead.clip_poster)}"' if lead.clip_poster else ""
            media = (f'<div class="s-clipwrap">'
                     f'<video class="s-clip" src="{_esc(lead.clip)}"{poster} '
                     f'muted loop playsinline preload="metadata"></video>'
                     f'<button class="s-sound" type="button" aria-label="Unmute clip">'
                     f'<span class="ic ic-muted">🔇</span>'
                     f'<span class="ic ic-on">🔊</span></button>'
                     f'</div>')
        else:
            media = f'<div class="s-emoji">{lead.emoji}</div>'

        # Alternate which side the clip sits on (odd = media left, even = media right).
        side = "media-left" if gi % 2 else "media-right"
        when = f' · {_esc(lead.timestamp)}' if lead.timestamp else ""
        products_html = "\n".join(_product_block(p, page, pages) for p in group)
        multi = " has-multi" if len(group) > 1 else ""

        rows.append(f"""      <article class="step {side}">
        <div class="s-media">{media}</div>
        <div class="s-content">
          <div class="s-step">Step {gi}{when}</div>
          <div class="s-products{multi}">
{products_html}
          </div>
        </div>
      </article>""")
    return "\n".join(rows)


def _retailer_chips(retailers: list[str]) -> str:
    return "".join(f'<span class="chip">{_esc(r)}</span>' for r in retailers)


def render_html(page: Page, pages: list[dict] | None = None) -> str:
    tpl = _TEMPLATE.read_text()
    graph = page_graph(page)
    creator_first = page.creator.display_name.split()[0] if page.creator.display_name else config.BRAND
    t = _totals(page)
    pages = pages if pages is not None else recommend.load_registry()

    tokens = {
        "TITLE": _esc(page.title),
        "BRAND": config.BRAND,
        "BASE_URL": config.BASE_URL,
        "SUMMARY": _esc(page.summary or page.meta),
        "URL": _esc(page.url),
        "CREATOR": _esc(page.creator.display_name),
        "CREATOR_FIRST": _esc(creator_first),
        "HANDLE": _esc(page.handle),
        "PLATFORMS": _esc(" & ".join(page.creator.platforms)),
        "META": _esc(page.meta),
        "INTRO": _esc(page.intro),
        "DISCLOSURE": _esc(page.disclosure),
        "GRAD0": page.creator.avatar_gradient[0],
        "GRAD1": page.creator.avatar_gradient[1],
        "JSONLD": json.dumps(graph, indent=2, ensure_ascii=False),
        "STEPS": _steps_html(page, pages),
        "SIMILAR_MODULE": _similar_module(page, pages),
        "SAVE_KEY": _esc(f"{page.handle}/{page.path_slug}"),
        # Editorial "shop + guide" summary bits
        "PRODUCT_COUNT": str(t["count"]),
        "TOTAL_DISPLAY": t["total_display"],
        "TOTAL_APPROX": _approx(t["any_estimated"]),
        "RANGE_DISPLAY": t["range_display"],
        "RETAILER_COUNT": str(t["retailer_count"]),
        "RETAILER_CHIPS": _retailer_chips(t["retailers"]),
        "SHOP_ALL_URL": _esc(page.url),
    }
    out = tpl
    for k, v in tokens.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def write_public_page(page: Page, out_root: Path, pages: list[dict] | None = None) -> Path:
    dest = out_root / page.handle / page.path_slug / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_html(page, pages))
    return dest
