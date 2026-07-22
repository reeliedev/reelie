"""
Dynamic public site (served at reelie.io). Renders the crawlable creator pages
+ SEO files straight from the database, so a page is live and AI-discoverable the
moment it's generated — no static build, no file sync.

  page_html(page, products, creator)  -> the shoppable "shop + guide" page, with
                                         embedded Schema.org JSON-LD (Product+Offer
                                         per item) so assistants can cite it.
  directory_html(rows)                -> browsable index of every page.
  creator_html(creator, rows)         -> a creator's page index.
  robots_txt / llms_txt / sitemap_xml -> the SEO files, at the domain root.
  page_graph / site_graph             -> the JSON-LD documents.

Mirrors the offline page-generator's output shape (render/schema.py, web.py,
site_files.py) but sources everything from SQLModel rows.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from app import config
from app.models import Creator, Page, Product

BASE = config.PUBLIC_BASE_URL
_TEMPLATE = (Path(__file__).parent / "templates" / "public_page.html").read_text()


def _esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


def page_url(handle: str, slug: str) -> str:
    return f"{BASE}/{handle}/{slug}"


def shop_url(handle: str, slug: str, position: int) -> str:
    # Route through the /r redirect so clicks are logged before the retailer.
    return f"{BASE}/r/{handle}/{slug}/{position}"


def _money(amount: float | None, currency: str) -> str:
    if amount is None:
        return ""
    sym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(currency, "")
    if abs(amount - round(amount)) < 0.005:
        return f"{sym}{int(round(amount))}"
    return f"{sym}{amount:,.2f}"


# --------------------------------------------------------------------------
# JSON-LD
# --------------------------------------------------------------------------
def _pname(p: Product) -> str:
    return (f"{p.brand} {p.name}".strip() if p.brand else p.name)


def _offer(page: Page, p: Product) -> dict | None:
    if p.price_amount is None:
        return None
    offer = {"@type": "Offer", "price": f"{p.price_amount:.2f}",
             "priceCurrency": p.currency, "availability": "https://schema.org/InStock",
             "url": shop_url(page.handle, page.slug, p.position)}
    if p.retailer:
        offer["seller"] = {"@type": "Organization", "name": p.retailer}
    return offer


def _product_node(page: Page, creator: Creator, p: Product) -> dict:
    url = page_url(page.handle, page.slug)
    node: dict = {
        "@type": "Product", "@id": f"{url}#product-{p.position}",
        "name": _pname(p), "position": p.position,
    }
    if p.brand:
        node["brand"] = {"@type": "Brand", "name": p.brand}
    if p.variant:
        node["description"] = f"Variant: {p.variant}"
    if p.clip_poster:
        node["image"] = p.clip_poster
    if p.note:
        node["review"] = {"@type": "Review",
                          "author": {"@type": "Person", "name": creator.display_name},
                          "reviewBody": p.note}
    offer = _offer(page, p)
    if offer:
        node["offers"] = offer
    return node


def _aggregate_offer(page: Page, products: list[Product]) -> dict | None:
    """The whole-routine price, as a first-class Offer AI can quote directly."""
    priced = [p for p in products if p.price_amount is not None]
    if not priced:
        return None
    amounts = [p.price_amount for p in priced]
    return {
        "@type": "AggregateOffer", "@id": f"{page_url(page.handle, page.slug)}#offer",
        "priceCurrency": priced[0].currency,
        "lowPrice": f"{min(amounts):.2f}", "highPrice": f"{max(amounts):.2f}",
        "price": f"{sum(amounts):.2f}",          # full-routine total
        "offerCount": len(priced),
        "availability": "https://schema.org/InStock",
    }


def _howto_node(page: Page, creator: Creator, products: list[Product], has_video: bool) -> dict:
    """The routine as a HowTo — steps + supplies matched to AI 'how do I…' queries."""
    url = page_url(page.handle, page.slug)
    priced = [p for p in products if p.price_amount is not None]
    node: dict = {
        "@type": "HowTo", "@id": f"{url}#howto", "name": page.title,
        "description": page.summary or page.meta or page.title,
        "supply": [{"@type": "HowToSupply", "name": _pname(p)} for p in products],
        "step": [
            {"@type": "HowToStep", "position": i, "name": _pname(p),
             "text": p.guide or p.note or f"Use {_pname(p)}.",
             "url": f"{url}#product-{p.position}"}
            for i, p in enumerate(products, 1)
        ],
    }
    if priced:
        node["estimatedCost"] = {"@type": "MonetaryAmount", "currency": priced[0].currency,
                                 "value": f"{sum(p.price_amount for p in priced):.2f}"}
    if has_video:
        node["video"] = {"@id": f"{url}#video"}
    return node


def _video_node(page: Page, creator: Creator, products: list[Product]) -> dict | None:
    if not page.video_id:
        return None
    url = page_url(page.handle, page.slug)
    node = {"@type": "VideoObject", "@id": f"{url}#video",
            "name": page.title, "description": page.summary or page.meta or page.title,
            "uploadDate": page.created_at.date().isoformat()}
    thumb = next((p.clip_poster for p in products if p.clip_poster), "")
    if thumb:
        node["thumbnailUrl"] = thumb
    return node


def faqs(page: Page, creator: Creator, products: list[Product]) -> list[tuple[str, str]]:
    """Q&A generated from the page's own data — the format AI answer engines cite.
    Answers are derivable from the visible page, so the FAQPage schema stays honest."""
    name = creator.display_name or f"@{page.handle}"
    title = page.title
    t = _totals(products)
    priced = [p for p in products if p.price_amount is not None]
    out: list[tuple[str, str]] = []
    names = [_pname(p) for p in products]
    if names:
        out.append((f"What products does {name} use in “{title}”?",
                    f"{name} uses {len(products)} products in {title}: "
                    f"{', '.join(names)} — each found from the video and linked to buy."))
    if priced:
        out.append((f"How much does {name}’s {title} cost?",
                    f"The whole routine is about {t['total_display']} — {len(priced)} products, "
                    f"ranging {t['range_display']}. Prices are approximate."))
    if t["retailers"]:
        out.append((f"Where can I buy the products in {title}?",
                    f"They're available at {', '.join(t['retailers'])}."))
    for p in priced[:4]:
        disp = p.price_display or _money(p.price_amount, p.currency)
        at = f" at {p.retailer}" if p.retailer else ""
        out.append((f"How much is the {_pname(p)}?", f"The {_pname(p)} is {disp}{at}."))
    result = [(q, a, False) for q, a in out]        # generated (read-only)
    try:
        custom = json.loads(page.custom_faqs) if page.custom_faqs else []
    except Exception:
        custom = []
    result += [((c.get("q") or "").strip(), (c.get("a") or "").strip(), True)
               for c in custom if (c.get("q") or "").strip()]
    return result


def _faq_node(page: Page, creator: Creator, products: list[Product]) -> dict | None:
    qa = faqs(page, creator, products)
    if not qa:
        return None
    return {
        "@type": "FAQPage", "@id": f"{page_url(page.handle, page.slug)}#faq",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a, _ in qa
        ],
    }


def page_graph(page: Page, creator: Creator, products: list[Product]) -> dict:
    """AI-optimized graph: Article › HowTo + Product/Offers + AggregateOffer +
    VideoObject + FAQPage, plus Person / Organization / Breadcrumb."""
    url = page_url(page.handle, page.slug)
    summary = page.summary or page.meta or page.title
    video = _video_node(page, creator, products)

    article = {
        "@type": "Article", "@id": f"{url}#article", "headline": page.title,
        "description": summary, "url": url,
        "datePublished": page.created_at.date().isoformat(),
        "author": {"@id": f"{BASE}/{page.handle}#person"},
        "publisher": {"@id": f"{BASE}#org"},
        "mainEntityOfPage": url,
        "about": {"@id": f"{url}#howto"},
    }
    item_list = {
        "@type": "ItemList", "@id": f"{url}#products", "name": page.title,
        "numberOfItems": len(products),
        "itemListOrder": "https://schema.org/ItemListOrderAscending",
        "itemListElement": [
            {"@type": "ListItem", "position": p.position, "item": _product_node(page, creator, p)}
            for p in products
        ],
    }
    person = {
        "@type": "Person", "@id": f"{BASE}/{page.handle}#person",
        "name": creator.display_name, "alternateName": f"@{page.handle}",
        "url": f"{BASE}/{page.handle}",
    }
    org = {"@type": "Organization", "@id": f"{BASE}#org", "name": config.BRAND, "url": BASE}
    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": config.BRAND, "item": BASE},
            {"@type": "ListItem", "position": 2, "name": creator.display_name, "item": f"{BASE}/{page.handle}"},
            {"@type": "ListItem", "position": 3, "name": page.title, "item": url},
        ],
    }
    graph = [article, _howto_node(page, creator, products, bool(video)),
             item_list, person, org, breadcrumb]
    agg = _aggregate_offer(page, products)
    if agg:
        graph.append(agg)
    if video:
        graph.append(video)
    faq = _faq_node(page, creator, products)
    if faq:
        graph.append(faq)
    return {"@context": "https://schema.org", "@graph": graph}


def site_graph(rows: list[dict]) -> dict:
    org = {"@type": "Organization", "@id": f"{BASE}#org", "name": config.BRAND,
           "url": BASE, "description": config.TAGLINE, "email": config.SUPPORT_EMAIL}
    website = {"@type": "WebSite", "@id": f"{BASE}#website", "url": BASE,
               "name": config.BRAND, "publisher": {"@id": f"{BASE}#org"}}
    collection = {
        "@type": "CollectionPage", "@id": f"{BASE}#creator-pages",
        "name": f"{config.BRAND} creator pages", "isPartOf": {"@id": f"{BASE}#website"},
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(rows),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": r["url"],
                 "name": f"{r['title']} — {r['creator_name']}"}
                for i, r in enumerate(rows)
            ],
        },
    }
    return {"@context": "https://schema.org", "@graph": [org, website, collection]}


# --------------------------------------------------------------------------
# SEO text files
# --------------------------------------------------------------------------
def robots_txt() -> str:
    lines = ["# Reelie — we WANT AI assistants to read and cite our creator pages.",
             "User-agent: *", "Allow: /", ""]
    for bot in config.AI_CRAWLERS:
        lines += [f"User-agent: {bot}", "Allow: /", ""]
    lines += [f"Sitemap: {BASE}/sitemap.xml", f"# LLM guide: {BASE}/llms.txt", ""]
    return "\n".join(lines)


def _product_line(p: dict) -> str:
    """'Brand Name ($price, Retailer)' — the shape an LLM can quote directly."""
    name = f"{p['brand']} {p['name']}".strip() if p.get("brand") else p["name"]
    bits = []
    if p.get("price_amount") is not None:
        bits.append(p.get("price_display") or _money(p["price_amount"], p.get("currency", "USD")))
    if p.get("retailer"):
        bits.append(p["retailer"])
    return f"{name} ({', '.join(bits)})" if bits else name


def _row_total(r: dict) -> str:
    amounts = [p["price_amount"] for p in r.get("products", []) if p.get("price_amount") is not None]
    if not amounts:
        return ""
    cur = next((p.get("currency", "USD") for p in r["products"] if p.get("price_amount") is not None), "USD")
    return _money(sum(amounts), cur)


def llms_txt(rows: list[dict]) -> str:
    """llmstxt.org map with the substance inline — an LLM can answer 'what's in X
    routine and how much?' from this file alone, without fetching each page."""
    out = [f"# {config.BRAND}", "", f"> {config.TAGLINE}", "",
           f"{config.BRAND} auto-generates shoppable routine pages from creators' videos. "
           "Each page below lists the real products the creator used, in order, with an "
           "approximate current price and a buy link. Details are inlined here so they can "
           "be cited directly.", "", "## Creator pages", ""]
    for r in rows:
        total = _row_total(r)
        head = f"- [{r['title']} — {r['creator_name']}]({r['url']}): {r['num_products']} products"
        head += f", ~{total} total." if total else "."
        out.append(head)
        for p in r.get("products", []):
            out.append(f"    - {_product_line(p)}")
        out.append("")
    out += ["## About", "", f"- [{config.BRAND}]({BASE}): {config.TAGLINE}", ""]
    return "\n".join(out)


def sitemap_xml(rows: list[dict]) -> str:
    urls = [BASE] + [f"{BASE}/{r['handle']}" for r in {r['handle']: r for r in rows}.values()] \
           + [r["url"] for r in rows]
    body = "\n".join(f"  <url><loc>{_esc(u)}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n")


# --------------------------------------------------------------------------
# HTML — the designed "shop + guide" page (bundled template, filled from the DB)
# --------------------------------------------------------------------------
_EVIDENCE = {"both": "Shown &amp; mentioned", "shown": "Shown in the video",
             "spoken": "Mentioned in the video", "description": "From the description"}


def _approx(estimated: bool) -> str:
    return ' <span class="approx">approx.</span>' if estimated else ""


def _totals(products: list[Product]) -> dict:
    priced = [p for p in products if p.price_amount is not None]
    amounts = [p.price_amount for p in priced]
    currency = priced[0].currency if priced else "USD"
    retailers: list[str] = []
    for p in products:
        if p.retailer and p.retailer not in retailers:
            retailers.append(p.retailer)
    return {
        "count": len(products),
        "total_display": _money(sum(amounts), currency) if amounts else "",
        "range_display": (f"{_money(min(amounts), currency)}–{_money(max(amounts), currency)}"
                          if amounts else "—"),
        "any_estimated": any(p.price_estimated for p in priced),
        "retailers": retailers,
    }


def _avatar(gradient: list) -> str:
    g0 = gradient[0] if gradient else "#E8E4DA"
    g1 = gradient[1] if len(gradient) > 1 else "#D8D2C4"
    return f'<span class="who-av" style="background:linear-gradient(135deg,{g0},{g1})"></span>'


def _also_used(others: list[dict]) -> str:
    """Small 'also used by' strip of other creators using this exact product."""
    if not others:
        return ""
    chips = "".join(
        f'<a class="who" href="{BASE}/{_esc(c["handle"])}" title="{_esc(c["name"])}">'
        f'{_avatar(c["avatar_gradient"])}</a>' for c in others)
    return f'<div class="s-also"><span class="s-also-label">Also used by</span>{chips}</div>'


def _product_block(page: Page, p: Product, also: list[dict] | None = None) -> str:
    # data-edit / data-pos hooks let the studio editor make the real page editable
    # inline (harmless attributes on the public page).
    brand = f'<div class="s-brand" data-edit="brand">{_esc(p.brand)}</div>' if p.brand else ""
    variant = f' <span class="s-variant">{_esc(p.variant)}</span>' if p.variant else ""
    narration = p.guide or (f'"{p.note}"' if p.note else None)
    note = f'<p class="s-note" data-edit="note">{_esc(narration)}</p>' if narration else ""
    evidence = _EVIDENCE.get(p.evidence, "")
    ev_tag = f'<div class="s-tags"><span class="tag">{evidence}</span></div>' if evidence else ""
    price_html = ""
    if p.price_amount is not None:
        disp = p.price_display or _money(p.price_amount, p.currency)
        price_html = f'<div class="s-price">{_esc(disp)}{_approx(p.price_estimated)}</div>'
    retailer = _esc(p.retailer) if p.retailer else "Shop"
    return f"""          <div class="s-product" data-pos="{p.position}">
            {brand}
            <h3 class="s-name"><span data-edit="name">{_esc(p.name)}</span>{variant}</h3>
            {ev_tag}
            {note}
            <div class="s-buy">
              {price_html}
              <a class="shop" href="{_esc(shop_url(page.handle, page.slug, p.position))}" rel="sponsored nofollow" target="_blank">Shop at {retailer} <span aria-hidden="true">→</span></a>
            </div>
            {_also_used(also or [])}
          </div>"""


def _similar_module(similar: list[dict]) -> str:
    if not similar:
        return ""
    cards = "".join(
        f'<a class="sim-card" href="{BASE}/{_esc(c["handle"])}">{_avatar(c["avatar_gradient"])}'
        f'<span class="sim-name">{_esc(c["name"])}</span>'
        f'<span class="sim-reason">{_esc(c["reason"])}</span></a>' for c in similar)
    return (f'<section class="similar"><div class="wrap">'
            f'<div class="eyebrow">You might also like</div>'
            f'<h2>Creators with a similar shelf</h2>'
            f'<div class="sim-row">{cards}</div></div></section>')


def _group_by_clip(products: list[Product]) -> list[list[Product]]:
    """Group products that share the same clip into one moment (so a shared clip
    is never repeated), preserving routine order. Products with no clip each form
    their own group."""
    groups: list[list[Product]] = []
    index: dict[str, int] = {}
    for p in products:
        key = p.clip_url or f"solo-{p.id}"
        if key in index:
            groups[index[key]].append(p)
        else:
            index[key] = len(groups)
            groups.append([p])
    return groups


def _steps_html(page: Page, products: list[Product], also: dict[int, list] | None = None) -> str:
    """One editorial step per video moment (clip), listing every product in that
    moment. When a product has a clip URL the big video renders (with tap-to-
    unmute, driven by the template's JS); otherwise the emoji fallback shows."""
    also = also or {}
    rows = []
    for gi, group in enumerate(_group_by_clip(products), 1):
        lead = group[0]
        if lead.clip_url:
            poster = f' poster="{_esc(lead.clip_poster)}"' if lead.clip_poster else ""
            media = (f'<div class="s-clipwrap">'
                     f'<video class="s-clip" src="{_esc(lead.clip_url)}"{poster} '
                     f'muted loop playsinline preload="metadata"></video>'
                     f'<button class="s-sound" type="button" aria-label="Unmute clip">'
                     f'<span class="ic ic-muted">🔇</span>'
                     f'<span class="ic ic-on">🔊</span></button>'
                     f'</div>')
        else:
            media = f'<div class="s-emoji">{lead.emoji or "🛍️"}</div>'
        side = "media-left" if gi % 2 else "media-right"
        when = f' · {_esc(lead.timestamp)}' if lead.timestamp and lead.timestamp != "0:00" else ""
        multi = " has-multi" if len(group) > 1 else ""
        products_html = "\n".join(_product_block(page, p, also.get(p.position)) for p in group)
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


def _faq_html(page: Page, creator: Creator, products: list[Product]) -> str:
    qa = faqs(page, creator, products)
    if not qa:
        return ""
    items = "".join(
        (f'<details class="faq-item" data-custom="1"><summary data-cq>{_esc(q)}</summary>'
         f'<div class="faq-a" data-ca>{_esc(a)}</div></details>') if custom else
        (f'<details class="faq-item"><summary>{_esc(q)}</summary>'
         f'<div class="faq-a">{_esc(a)}</div></details>')
        for q, a, custom in qa)
    return (f'<section class="faq" id="faq"><div class="wrap">'
            f'<div class="eyebrow">Good to know</div>'
            f'<h2>Questions &amp; answers</h2>'
            f'<div class="faq-list">{items}</div></div></section>')


def page_html(page: Page, creator: Creator, products: list[Product],
              similar: list[dict] | None = None, also: dict[int, list] | None = None) -> str:
    url = page_url(page.handle, page.slug)
    grad = creator.avatar_gradient or config.DEFAULT_AVATAR_GRADIENT
    grad0, grad1 = grad[0], grad[1] if len(grad) > 1 else grad[0]
    first = creator.display_name.split()[0] if creator.display_name else config.BRAND
    t = _totals(products)
    summary = page.summary or page.meta or f"{t['count']} products from {creator.display_name}."

    tokens = {
        "TITLE": _esc(page.title), "BRAND": config.BRAND, "BASE_URL": BASE,
        "SUMMARY": _esc(summary), "URL": _esc(url),
        "CREATOR": _esc(creator.display_name), "CREATOR_FIRST": _esc(first),
        "HANDLE": _esc(page.handle),
        "PLATFORMS": _esc(" & ".join(creator.platforms)) if creator.platforms else "",
        "META": _esc(page.meta), "INTRO": _esc(page.intro), "DISCLOSURE": _esc(page.disclosure),
        "GRAD0": grad0, "GRAD1": grad1,
        "JSONLD": json.dumps(page_graph(page, creator, products), indent=2, ensure_ascii=False),
        "STEPS": _steps_html(page, products, also),
        "FAQ": _faq_html(page, creator, products),
        "SIMILAR_MODULE": _similar_module(similar or []),
        "SAVE_KEY": _esc(f"{page.handle}/{page.slug}"),
        "PRODUCT_COUNT": str(t["count"]), "TOTAL_DISPLAY": t["total_display"] or "—",
        "TOTAL_APPROX": _approx(t["any_estimated"]), "RANGE_DISPLAY": t["range_display"],
        "RETAILER_COUNT": str(len(t["retailers"])),
        "RETAILER_CHIPS": "".join(f'<span class="chip">{_esc(r)}</span>' for r in t["retailers"]),
        "SHOP_ALL_URL": _esc(url),
    }
    out = _TEMPLATE
    for k, v in tokens.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


# --- directory + creator index (same brand system, lighter layout) --------
_LIST_CSS = """
:root{--bg:#FFE566;--sun:#FFD84D;--ink:#201B0A;--grey:#7A6F4A;--line:rgba(32,27,10,.14);--soft:#FBF7E6;--surface:#fff;--accent:#6F5DF0;--accent-deep:#5A47E0;--accent-soft:#ECE8FE}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Instrument Sans',-apple-system,BlinkMacSystemFont,sans-serif;color:var(--ink);line-height:1.55;-webkit-font-smoothing:antialiased;background:radial-gradient(circle at 18% 10%,#FFF3A8 0%,transparent 46%),radial-gradient(circle at 85% 92%,#FFD23E 0%,transparent 52%),var(--bg)}
a{color:inherit;text-decoration:none}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
.eyebrow{font-family:'Space Grotesk',sans-serif;font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--grey)}
.topbar{background:rgba(255,255,255,.6);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}.topbar .wrap{display:flex;align-items:center;justify-content:space-between;height:64px}
.brandmark{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:22px;letter-spacing:-.5px}.brandmark .dot{color:var(--accent)}
.hero .wrap{padding:60px 24px 40px}
.creator{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.cavatar{width:52px;height:52px;border-radius:50%;border:2px solid var(--accent)}
h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:clamp(34px,5vw,52px);line-height:1.05;letter-spacing:-1.5px;margin:8px 0 14px}
.lede{font-size:18px;color:var(--grey);max-width:42ch}
.search{margin-top:26px;width:100%;max-width:520px;padding:15px 18px;font:inherit;font-size:16px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink);outline:none;box-shadow:0 6px 16px rgba(32,27,10,.08)}
.search:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(111,93,240,.18)}
.noresults{padding:20px 0 72px;color:var(--grey)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;padding:8px 0 72px}
.card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:22px 22px;box-shadow:0 6px 16px rgba(32,27,10,.06);transition:transform .15s cubic-bezier(.16,1,.3,1),box-shadow .15s}
.card:hover{transform:translateY(-3px);box-shadow:0 16px 34px rgba(90,71,224,.18)}
.card .ci{width:44px;height:44px;border-radius:12px;background:var(--accent-soft);display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:14px}
.card h3{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:21px;line-height:1.15;margin-bottom:5px}
.card .m{color:var(--grey);font-size:13.5px}
.footer{border-top:1px solid var(--line)}.footer .wrap{padding:34px 24px 48px;color:var(--grey);font-size:12.5px}
/* discover: featured creators + their posts */
.cblock{padding:30px 0;border-top:1px solid var(--line)}
.cblock:first-of-type{border-top:none}
.cb-head{display:flex;align-items:center;gap:14px;margin-bottom:18px}
.cb-av{width:56px;height:56px;border-radius:50%;border:2px solid var(--accent);flex-shrink:0}
.cb-name{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:20px;line-height:1.1}
.cb-meta{color:var(--grey);font-size:13px}
.cb-view{margin-left:auto;font-weight:600;font-size:13.5px;color:var(--accent-deep);border-bottom:2px solid var(--accent);white-space:nowrap}
.cb-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
"""

_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
          '<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">')


def _list_shell(title: str, desc: str, canonical: str, hero: str, cards: str,
                jsonld: dict | None = None, script: str = "") -> str:
    ld = (f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
          if jsonld else "")
    grid = f'<section class="wrap"><div class="grid" id="grid">{cards}</div>' \
           f'<p class="noresults" id="noresults" hidden>No matches.</p></section>' if cards else \
           '<section class="wrap"><p style="padding:44px 0;color:#8A8A8A">No pages yet.</p></section>'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}">
<link rel="canonical" href="{_esc(canonical)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:title" content="{_esc(title)}"><meta property="og:description" content="{_esc(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{_esc(canonical)}">
{_FONTS}{ld}<style>{_LIST_CSS}</style></head><body>
<header class="topbar"><div class="wrap"><a class="brandmark" href="{BASE}">{config.BRAND}<span class="dot">.</span></a>
<a class="eyebrow" href="{BASE}">Browse all →</a></div></header>
<section class="hero"><div class="wrap">{hero}</div></section>
{grid}
<footer class="footer"><div class="wrap">{config.BRAND} — {_esc(config.TAGLINE)}</div></footer>
{script}</body></html>"""


def _search_text(r: dict) -> str:
    """Everything a shopper might type: title, creator, brands, product names."""
    parts = [r["title"], r["creator_name"], f"@{r['handle']}"]
    for p in r.get("products", []):
        parts += [p.get("brand", ""), p.get("name", ""), p.get("retailer", "")]
    return _esc(" ".join(parts).lower())


def _card(r: dict, show_creator: bool = True) -> str:
    sub = f'{_esc(r["creator_name"])} · {r["num_products"]} products' if show_creator \
          else f'{r["num_products"]} products'
    return (f'<a class="card" href="{_esc(r["url"])}" data-search="{_search_text(r)}">'
            f'<div class="ci">🛍️</div>'
            f'<h3>{_esc(r["title"])}</h3><div class="m">{sub}</div></a>')


def creator_html(creator: Creator, rows: list[dict]) -> str:
    url = f"{BASE}/{creator.handle}"
    grad = creator.avatar_gradient or config.DEFAULT_AVATAR_GRADIENT
    g0, g1 = grad[0], grad[1] if len(grad) > 1 else grad[0]
    hero = (f'<div class="creator"><span class="cavatar" style="background:linear-gradient(135deg,{g0},{g1})"></span>'
            f'<div><div class="eyebrow">Creator</div></div></div>'
            f'<h1>{_esc(creator.display_name)}</h1>'
            f'<p class="lede">@{_esc(creator.handle)}'
            f'{" · " + _esc(creator.bio) if creator.bio else ""}</p>')
    cards = "".join(_card(r, show_creator=False) for r in rows)
    return _list_shell(f"{creator.display_name} (@{creator.handle}) · {config.BRAND}",
                       f"{creator.display_name}'s shoppable routine pages on {config.BRAND}.",
                       url, hero, cards)


# --- legal pages (privacy / terms) ----------------------------------------
_LEGAL_CSS = """
:root{--bg:#FFE566;--ink:#201B0A;--grey:#7A6F4A;--line:rgba(32,27,10,.14);--surface:#fff;--accent:#6F5DF0;--accent-deep:#5A47E0}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Instrument Sans',-apple-system,BlinkMacSystemFont,sans-serif;color:var(--ink);line-height:1.65;background:radial-gradient(circle at 18% 10%,#FFF3A8 0%,transparent 46%),radial-gradient(circle at 85% 92%,#FFD23E 0%,transparent 52%),var(--bg)}
a{color:inherit}
.wrap{max-width:760px;margin:0 auto;padding:0 24px}
.topbar{background:rgba(255,255,255,.6);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);position:sticky;top:0}.topbar .wrap{display:flex;align-items:center;justify-content:space-between;height:64px;max-width:1080px}
.brandmark{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:22px;letter-spacing:-.5px;text-decoration:none}.brandmark .dot{color:var(--accent)}
.legal{margin:32px auto;max-width:800px;padding:0 20px}
.legal>div{background:var(--surface);border:1px solid var(--line);border-radius:24px;padding:48px 44px;box-shadow:0 10px 30px rgba(32,27,10,.08)}
.legal h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:42px;letter-spacing:-1.5px;margin-bottom:10px}
.updated{color:var(--grey);font-size:13.5px;margin-bottom:36px}
.legal h2{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:22px;margin:34px 0 12px}
.legal p{margin:0 0 14px}
.legal ul{margin:0 0 14px 22px}.legal li{margin-bottom:7px}
.legal a{font-weight:600;color:var(--accent-deep);border-bottom:2px solid var(--accent);text-decoration:none}
.footer{margin-top:8px}.footer .wrap{padding:26px 24px 46px;color:var(--grey);font-size:12.5px;max-width:1080px}
.footer a{color:var(--accent-deep);font-weight:600}
"""

# NOTE: starting template — review with counsel and edit before relying on it.
LEGAL_UPDATED = "20 July 2026"


def _legal_html(title: str, blocks: list[tuple[str, str]], canonical: str) -> str:
    body = "".join(f"<h2>{_esc(h)}</h2>{c}" for h, c in blocks)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)} · {config.BRAND}</title>
<meta name="description" content="{_esc(title)} for {config.BRAND}.">
<link rel="canonical" href="{_esc(canonical)}">
<meta name="robots" content="index, follow">
{_FONTS}<style>{_LEGAL_CSS}</style></head><body>
<header class="topbar"><div class="wrap"><a class="brandmark" href="{BASE}">{config.BRAND}<span class="dot">.</span></a>
<a href="{BASE}" style="color:var(--grey);font-size:13.5px;font-weight:600;text-decoration:none">Browse creators →</a></div></header>
<main class="legal"><div class="wrap"><h1>{_esc(title)}</h1>
<div class="updated">Last updated: {LEGAL_UPDATED}</div>
{body}</div></main>
<footer class="footer"><div class="wrap"><a href="{BASE}/privacy">Privacy</a> · <a href="{BASE}/terms">Terms</a> · {config.BRAND} — {_esc(config.TAGLINE)}</div></footer>
</body></html>"""


def privacy_html() -> str:
    email = config.SUPPORT_EMAIL
    blocks = [
        ("Who we are",
         f"<p>{config.BRAND} turns beauty and skincare creators' videos into shoppable "
         f"“routine” pages. This policy explains what we collect and why. Questions: "
         f'<a href="mailto:{email}">{email}</a>.</p>'),
        ("Information we collect",
         "<ul>"
         "<li><b>Account details</b> — your email address, and (for creators) your handle "
         "and display name.</li>"
         "<li><b>Connected accounts</b> — if you connect YouTube or Instagram, we store an "
         "access token and read <b>only</b> your public video list and video content. We "
         "<b>never</b> post, message, or change anything on your accounts.</li>"
         "<li><b>Content you generate</b> — the routine pages, products, and prices produced "
         "from your videos.</li>"
         "<li><b>Usage data</b> — basic analytics such as clicks on product links, used to "
         "measure interest and (where applicable) attribute affiliate activity.</li>"
         "<li><b>Guest favorites</b> — if you're not signed in, favorites are stored on your "
         "device (local storage), not on our servers.</li></ul>"),
        ("How we use it",
         "<ul><li>To create and display your shoppable pages.</li>"
         "<li>To operate, secure, and improve the service.</li>"
         "<li>To measure link performance and, where applicable, affiliate commissions.</li></ul>"
         "<p>We do <b>not</b> sell your personal information.</p>"),
        ("AI processing",
         "<p>To identify products, we process your video's transcript and selected frames "
         "using third-party AI services. This is used solely to generate your page.</p>"),
        ("Third parties we share with",
         "<ul>"
         "<li><b>Google / YouTube</b> and <b>Meta / Instagram</b> — only to authenticate the "
         "connection you initiate.</li>"
         "<li><b>Hosting and infrastructure</b> providers that run the service.</li>"
         "<li><b>Retailers / affiliate networks</b> — when you click a product link, standard "
         "referral parameters may be passed.</li></ul>"),
        ("Affiliate disclosure",
         "<p>Some product links may be affiliate links. If you buy through them, we may earn "
         "a commission at no extra cost to you. Prices shown are approximate and may change.</p>"),
        ("Your choices",
         "<ul><li><b>Disconnect</b> a social account at any time from your profile.</li>"
         "<li><b>Delete your account</b> and associated data from the app; you can also email "
         f'us at <a href="mailto:{email}">{email}</a>.</li></ul>'),
        ("Data retention",
         "<p>We keep your information while your account is active and delete it on request, "
         "except where we must retain records to meet legal obligations.</p>"),
        ("Children",
         "<p>The service is not directed to children under 13 (or the minimum age in your "
         "country), and we don't knowingly collect their data.</p>"),
        ("Changes",
         "<p>We may update this policy; we'll revise the date above and, for material changes, "
         "provide notice in the app.</p>"),
        ("Contact",
         f'<p>Questions or requests: <a href="mailto:{email}">{email}</a>.</p>'),
    ]
    return _legal_html("Privacy Policy", blocks, f"{BASE}/privacy")


def terms_html() -> str:
    email = config.SUPPORT_EMAIL
    blocks = [
        ("Agreement",
         f"<p>By using {config.BRAND} you agree to these terms. If you don't agree, please "
         f"don't use the service.</p>"),
        ("Accounts",
         "<p>You're responsible for activity under your account and for keeping your login "
         "secure. You must provide accurate information and meet the minimum age in your country.</p>"),
        ("Creator content and rights",
         "<p>If you connect an account or generate pages, you represent that you have the "
         f"rights to the videos and content involved, and you grant {config.BRAND} a license to "
         "process and display that content to operate the service. You can remove your pages "
         "or delete your account at any time.</p>"),
        ("Acceptable use",
         "<p>Don't use the service to break the law, infringe others' rights, or attempt to "
         "disrupt or reverse-engineer it.</p>"),
        ("Products, prices, and affiliate links",
         "<p>Product names and prices are generated automatically and are approximate — they "
         "may be inaccurate or out of date. Purchases happen on third-party retailer sites "
         f"under their terms. Some links may be affiliate links from which {config.BRAND} may "
         "earn a commission.</p>"),
        ("Third-party platforms",
         "<p>Connecting YouTube or Instagram is also governed by those platforms' terms. We "
         "access only what you authorize and never post on your behalf.</p>"),
        ("Disclaimer",
         "<p>The service is provided “as is,” without warranties of any kind. We don't "
         "guarantee accuracy of extracted products, prices, or availability.</p>"),
        ("Limitation of liability",
         f"<p>To the extent permitted by law, {config.BRAND} is not liable for indirect or "
         "consequential damages arising from your use of the service.</p>"),
        ("Changes and termination",
         "<p>We may update these terms or suspend the service; continued use after changes "
         "means you accept them.</p>"),
        ("Contact",
         f'<p>Questions: <a href="mailto:{email}">{email}</a>.</p>'),
    ]
    return _legal_html("Terms of Service", blocks, f"{BASE}/terms")


_SEARCH_JS = """<script>
(function(){
  var q=document.getElementById('q'), cards=[].slice.call(document.querySelectorAll('#grid .card')),
      none=document.getElementById('noresults');
  if(!q) return;
  function apply(){
    var t=q.value.trim().toLowerCase(), shown=0;
    cards.forEach(function(c){
      var hit=!t||c.getAttribute('data-search').indexOf(t)!==-1;
      c.style.display=hit?'':'none'; if(hit) shown++;
    });
    if(none) none.hidden=shown>0;
  }
  q.addEventListener('input', apply);
})();
</script>"""


def directory_html(rows: list[dict]) -> str:
    hero = (f'<div class="eyebrow">Every product, every routine</div>'
            f'<h1>Shop your favourite<br>creators\' videos</h1>'
            f'<p class="lede">{_esc(config.TAGLINE)}</p>'
            f'<input id="q" class="search" type="search" autocomplete="off" '
            f'placeholder="Search creators, routines, or products…" aria-label="Search">')
    cards = "".join(_card(r) for r in rows)
    return _list_shell(f"{config.BRAND} — {config.TAGLINE}", config.TAGLINE, BASE, hero, cards,
                       site_graph(rows), script=_SEARCH_JS)


_DISCOVER_JS = """<script>
(function(){
  var q=document.getElementById('q');
  if(!q) return;
  var blocks=[].slice.call(document.querySelectorAll('.cblock'));
  function apply(){
    var t=q.value.trim().toLowerCase(), any=false;
    blocks.forEach(function(b){
      var cards=[].slice.call(b.querySelectorAll('.card')), shown=0;
      cards.forEach(function(c){
        var hit=!t||c.getAttribute('data-search').indexOf(t)!==-1;
        c.style.display=hit?'':'none'; if(hit) shown++;
      });
      // also match on creator name/handle in the header
      var head=(b.getAttribute('data-creator')||'');
      var headHit=!t||head.indexOf(t)!==-1;
      if(headHit) cards.forEach(function(c){c.style.display='';});
      var visible=headHit||shown>0;
      b.style.display=visible?'':'none'; if(visible) any=true;
    });
    var none=document.getElementById('noresults'); if(none) none.hidden=any;
  }
  q.addEventListener('input', apply);
})();
</script>"""


_FEED_CSS = """
:root{--bg:#FFE566;--sun:#FFD84D;--ink:#201B0A;--grey:#7A6F4A;--line:rgba(32,27,10,.14);--soft:#FBF7E6;--accent:#6F5DF0;--accent-deep:#5A47E0;--accent-soft:#ECE8FE}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;color:var(--ink);font-family:'Instrument Sans',-apple-system,sans-serif;-webkit-font-smoothing:antialiased;
  background:radial-gradient(circle at 18% 10%,#FFF3A8 0%,transparent 46%),radial-gradient(circle at 85% 92%,#FFD23E 0%,transparent 52%),var(--bg)}
a{color:inherit;text-decoration:none}
.topnav{position:fixed;top:0;left:0;right:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:16px 26px;
  background:rgba(255,255,255,.55);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.topnav .bm{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:21px}.topnav .bm .d{color:var(--accent)}
.topnav .hm{font-size:13px;font-weight:600;color:var(--accent-deep)}
.feed{height:100dvh;overflow-y:scroll;scroll-snap-type:y mandatory;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.feed::-webkit-scrollbar{display:none}
.reel{min-height:100dvh;scroll-snap-align:center;display:flex;align-items:center;justify-content:center;gap:40px;padding:88px 32px 40px}
/* the phone-shaped video, centered like the landing mockup */
.stage{position:relative;height:min(78vh,720px);aspect-ratio:9/16;flex-shrink:0;background:#0c0c0c;border-radius:34px;overflow:hidden;
  box-shadow:0 40px 90px -30px rgba(32,27,10,.5),0 0 0 6px #fff,0 0 0 8px var(--line)}
.stage video,.stage .poster{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.stage .poster{display:flex;align-items:center;justify-content:center;font-size:120px;background:linear-gradient(135deg,#2a2a2a,#111)}
.tapsound{position:absolute;inset:0;z-index:4;cursor:pointer}
.snd{position:absolute;top:14px;right:14px;z-index:6;width:38px;height:38px;border:none;border-radius:50%;background:rgba(0,0,0,.4);color:#fff;font-size:15px;cursor:pointer;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
.snd .on{display:none}.stage.is-on .snd .on{display:inline}.stage.is-on .snd .off{display:none}
/* like action rail */
.rail{position:absolute;right:12px;bottom:20px;z-index:6;display:flex;flex-direction:column;align-items:center;gap:5px}
.likebtn{width:50px;height:50px;border:none;border-radius:50%;background:rgba(0,0,0,.35);color:#fff;font-size:24px;line-height:1;cursor:pointer;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);transition:transform .12s ease,background .12s ease}
.likebtn:hover{transform:scale(1.08)}
.likebtn:active{transform:scale(.9)}
.likebtn .heart{opacity:.92;transition:color .12s ease}
.likebtn.liked{background:rgba(255,255,255,.16)}
.likebtn.liked .heart{color:#FF3B6B}
.likebtn.pop{animation:pop .3s ease}
@keyframes pop{0%{transform:scale(1)}45%{transform:scale(1.35)}100%{transform:scale(1)}}
.likect{color:#fff;font-size:13px;font-weight:700;text-shadow:0 1px 6px rgba(0,0,0,.5)}
/* the side panel to shop + open the page */
.panel{width:min(400px,42vw);max-height:min(78vh,720px);display:flex;flex-direction:column;background:#fff;border:1px solid var(--line);border-radius:26px;box-shadow:0 24px 60px -34px rgba(32,27,10,.4);overflow:hidden}
.p-head{padding:22px 22px 16px;border-bottom:1px solid var(--line)}
.who{display:flex;align-items:center;gap:11px;margin-bottom:14px}
.who .av{width:44px;height:44px;border-radius:50%;border:2px solid var(--accent);flex-shrink:0}
.who .nm{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:16px;line-height:1.1}
.who .hd{font-size:12.5px;color:var(--grey)}
.who .vp{margin-left:auto;font-size:12px;font-weight:700;color:var(--accent-deep);border:1px solid var(--line);padding:7px 13px;border-radius:999px}
.p-title{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:22px;line-height:1.15;letter-spacing:-.4px}
.p-sub{color:var(--grey);font-size:13px;margin-top:5px}
.p-list{flex:1;overflow-y:auto;padding:8px 22px}
.p-item{display:flex;align-items:center;gap:12px;padding:13px 0;border-top:1px solid var(--line)}
.p-item:first-child{border-top:none}
.p-item .pi{width:44px;height:44px;border-radius:11px;background:var(--accent-soft);display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
.p-item .pd{flex:1;min-width:0}
.p-item .pb{font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;color:var(--grey)}
.p-item .pn{font-weight:600;font-size:14px;line-height:1.25}
.p-item .pp{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:14px;margin-top:1px}
.p-item .shop{background:var(--ink);color:#fff;font-weight:600;font-size:12.5px;padding:9px 14px;border-radius:999px;white-space:nowrap}
.p-foot{padding:16px 22px 20px;border-top:1px solid var(--line)}
.p-cta{display:block;text-align:center;background:var(--accent);color:#fff;font-weight:700;font-size:15px;padding:14px;border-radius:999px;box-shadow:0 8px 20px rgba(90,71,224,.35)}
.hint{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:10;color:var(--grey);font-size:12.5px;font-weight:600;animation:bob 1.8s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateX(-50%) translateY(0)}50%{transform:translateX(-50%) translateY(-5px)}}
.empty{padding:120px 40px;text-align:center;color:var(--grey)}
@media(max-width:820px){
  .reel{flex-direction:column;gap:18px;padding:80px 16px 30px}
  .stage{height:min(62vh,520px)}
  .panel{width:min(440px,94vw);max-height:none}
  .p-list{max-height:34vh}
}
"""


def _reel(item: dict, first: bool) -> str:
    c = item["creator"]
    poster = f' poster="{_esc(item["clip_poster"])}"' if item.get("clip_poster") else ""
    if item.get("clip_url"):
        media = (f'<video src="{_esc(item["clip_url"])}"{poster} muted loop playsinline '
                 f'preload="{"auto" if first else "none"}"></video>')
    else:
        media = f'<div class="poster">{item.get("emoji", "🛍️")}</div>'
    rows = []
    for p in item["products"]:
        price = f'<div class="pp">{_esc(p["price_display"])}</div>' if p.get("price_display") else ""
        rows.append(
            f'<div class="p-item"><div class="pi">{p.get("emoji") or "🛍️"}</div>'
            f'<div class="pd"><div class="pb">{_esc(p.get("brand") or "Featured")}</div>'
            f'<div class="pn">{_esc(p["name"])}</div>{price}</div>'
            f'<a class="shop" href="{_esc(p["shop_url"])}" rel="sponsored nofollow" target="_blank">Shop</a></div>')
    plats = " · ".join(c.get("platforms") or []) or "Creator"
    like_key = f"{item['handle']}/{item['slug']}"
    return f"""<section class="reel"><div class="stage">
{media}<div class="tapsound"></div>
<button class="snd" type="button" aria-label="Sound"><span class="off">🔇</span><span class="on">🔊</span></button>
<div class="rail">
  <button class="likebtn" type="button" data-key="{_esc(like_key)}"
          data-handle="{_esc(item['handle'])}" data-slug="{_esc(item['slug'])}" aria-label="Like">
    <span class="heart">♥</span></button>
  <span class="likect" data-key="{_esc(like_key)}">{item.get('likes', 0)}</span>
</div>
</div>
<aside class="panel">
  <div class="p-head">
    <div class="who"><span class="av" style="background:linear-gradient(135deg,{c['g0']},{c['g1']})"></span>
      <div><div class="nm">{_esc(c['name'])}</div><div class="hd">@{_esc(c['handle'])} · {_esc(plats)}</div></div>
      <a class="vp" href="{BASE}/{_esc(c['handle'])}">Profile</a></div>
    <div class="p-title">{_esc(item['page_title'])}</div>
    <div class="p-sub">{len(item['products'])} products{(' · ' + item['total_display']) if item.get('total_display') else ''}</div>
  </div>
  <div class="p-list">{''.join(rows)}</div>
  <div class="p-foot"><a class="p-cta" href="{_esc(item['page_url'])}">See the full routine →</a></div>
</aside></section>"""


def discover_feed_html(items: list[dict]) -> str:
    reels = "".join(_reel(it, i == 0) for i, it in enumerate(items)) or \
            '<section class="reel"><div class="empty">No clips yet — check back soon.</div></section>'
    hint = '<div class="hint" id="hint">scroll for more ↓</div>' if len(items) > 1 else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Discover · {config.BRAND}</title>
<meta name="description" content="Scroll creators' videos and shop every product.">
<meta name="theme-color" content="#FFE566">
{_FONTS}<style>{_FEED_CSS}</style></head><body>
<div class="topnav"><a class="bm" href="{BASE}">{config.BRAND}<span class="d">.</span></a>
<a class="hm" href="{BASE}">← Home</a></div>
<div class="feed" id="feed">{reels}{hint}</div>
<script>
(function(){{
  var vids=[].slice.call(document.querySelectorAll('.reel video'));
  function stageOf(v){{return v.closest('.stage');}}
  function mute(v){{v.muted=true;var s=stageOf(v);if(s)s.classList.remove('is-on');}}
  function unmute(v){{vids.forEach(function(o){{if(o!==v)mute(o);}});v.muted=false;v.play().catch(function(){{}});var s=stageOf(v);if(s)s.classList.add('is-on');}}
  document.querySelectorAll('.tapsound, .snd').forEach(function(el){{
    el.addEventListener('click', function(e){{
      e.preventDefault();
      var v=el.closest('.stage').querySelector('video'); if(!v)return;
      if(v.muted)unmute(v); else mute(v);
    }});
  }});
  var hint=document.getElementById('hint');
  if('IntersectionObserver' in window){{
    var io=new IntersectionObserver(function(es){{
      es.forEach(function(e){{
        var v=e.target.querySelector('video'); if(!v)return;
        if(e.isIntersecting){{v.play().catch(function(){{}});}} else {{v.pause();mute(v);}}
      }});
    }},{{threshold:0.5}});
    document.querySelectorAll('.reel').forEach(function(r){{io.observe(r);}});
  }} else {{ if(vids[0])vids[0].play().catch(function(){{}}); }}
  var feed=document.getElementById('feed');
  feed.addEventListener('scroll', function(){{ if(hint)hint.style.display='none'; }}, {{once:true}});

  // --- guest likes (no account) ---
  function cid(){{
    var k='reelie.cid', v=localStorage.getItem(k);
    if(!v){{ v=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():('c'+Date.now()+Math.round(Math.random()*1e6)); localStorage.setItem(k,v); }}
    return v;
  }}
  function likedSet(){{ try{{return JSON.parse(localStorage.getItem('reelie.likes')||'[]');}}catch(e){{return [];}} }}
  function saveLikes(a){{ localStorage.setItem('reelie.likes', JSON.stringify(a)); }}
  var liked=likedSet();
  // reflect stored liked-state on load
  document.querySelectorAll('.likebtn').forEach(function(b){{
    if(liked.indexOf(b.getAttribute('data-key'))!==-1) b.classList.add('liked');
  }});
  document.querySelectorAll('.likebtn').forEach(function(b){{
    b.addEventListener('click', function(e){{
      e.preventDefault();
      var key=b.getAttribute('data-key'), now=!b.classList.contains('liked');
      b.classList.toggle('liked', now); b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop');
      liked=likedSet(); var i=liked.indexOf(key);
      if(now && i===-1) liked.push(key); else if(!now && i!==-1) liked.splice(i,1);
      saveLikes(liked);
      var ctEl=document.querySelector('.likect[data-key="'+key.replace(/"/g,'')+'"]');
      if(ctEl) ctEl.textContent=Math.max(0,(parseInt(ctEl.textContent,10)||0)+(now?1:-1)); // optimistic
      fetch('/likes/toggle',{{method:'POST',headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{handle:b.getAttribute('data-handle'),slug:b.getAttribute('data-slug'),clientId:cid(),liked:now}})}})
        .then(function(r){{return r.json();}}).then(function(d){{ if(ctEl&&typeof d.count==='number') ctEl.textContent=d.count; }})
        .catch(function(){{}});
    }});
  }});
}})();
</script>
</body></html>"""


def _list_shell_custom(title: str, desc: str, canonical: str, hero: str, body: str, script: str) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}">
<link rel="canonical" href="{_esc(canonical)}">
<meta name="robots" content="index, follow, max-image-preview:large">
{_FONTS}<style>{_LIST_CSS}</style></head><body>
<header class="topbar"><div class="wrap"><a class="brandmark" href="{BASE}">{config.BRAND}<span class="dot">.</span></a>
<a class="eyebrow" href="{BASE}">← Home</a></div></header>
<section class="hero"><div class="wrap">{hero}</div></section>
<section class="wrap"><p class="noresults" id="noresults" hidden>No matches.</p>{body}</section>
<footer class="footer"><div class="wrap">{config.BRAND} — {_esc(config.TAGLINE)}</div></footer>
{script}</body></html>"""
