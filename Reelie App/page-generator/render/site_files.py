"""
Site-wide artifacts that must stay in sync with EVERY generated page:
robots.txt, llms.txt, sitemap.xml, an authoritative schema-graph.json, and the
managed Schema.org block injected into the main webpage.

A small registry (out/pages.json) is the list of all pages ever generated; these
files are regenerated from it on every run so the site always reflects the full
catalogue.
"""

from __future__ import annotations

import json
from pathlib import Path

import config
from models import Page
from render.schema import site_graph


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------
def normalize_product(brand: str, name: str) -> str:
    """Stable cross-page product key: 'brand|name', lowercased, punctuation stripped."""
    def norm(s: str) -> str:
        return "".join(c for c in (s or "").lower() if c.isalnum() or c == " ").strip()
    return f"{norm(brand)}|{norm(name)}"


def register_page(page: Page) -> list[dict]:
    """Upsert this page into out/pages.json (keyed by URL). Returns the full list.
    The entry now indexes products/brands/retailers so recommendations can be
    computed without re-scanning every per-page file."""
    idx = config.PAGES_INDEX
    pages = json.loads(idx.read_text()) if idx.exists() else []
    products = [
        {"key": normalize_product(p.brand, p.name), "brand": p.brand,
         "name": p.name, "retailer": p.retailer, "emoji": p.emoji}
        for p in page.products
    ]
    entry = {
        "url": page.url,
        "handle": page.handle,
        "slug": page.path_slug,
        "title": page.title,
        "emoji": page.emoji,
        "summary": page.summary or page.meta,
        "creator_name": page.creator.display_name,
        "platforms": page.creator.platforms,
        "avatar_gradient": page.creator.avatar_gradient,
        "num_products": len(page.products),
        "products": products,
        "brands": sorted({p.brand for p in page.products if p.brand}),
        "retailers": sorted({p.retailer for p in page.products if p.retailer}),
    }
    pages = [p for p in pages if p["url"] != entry["url"]]
    pages.append(entry)
    pages.sort(key=lambda p: (p["handle"], p["slug"]))
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(json.dumps(pages, indent=2, ensure_ascii=False))
    return pages


# --------------------------------------------------------------------------
# robots.txt — invite AI crawlers explicitly
# --------------------------------------------------------------------------
def robots_txt() -> str:
    lines = [
        "# Reelie — we WANT AI assistants to read and cite our creator pages.",
        "User-agent: *",
        "Allow: /",
        "",
    ]
    for bot in config.AI_CRAWLERS:
        lines += [f"User-agent: {bot}", "Allow: /", ""]
    lines += [f"Sitemap: {config.BASE_URL}/sitemap.xml",
              f"# LLM guide: {config.BASE_URL}/llms.txt", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# llms.txt — a plain-text map for language models (llmstxt.org convention)
# --------------------------------------------------------------------------
def llms_txt(pages: list[dict]) -> str:
    out = [
        f"# {config.BRAND}",
        "",
        f"> {config.TAGLINE}",
        "",
        f"{config.BRAND} auto-generates shoppable routine pages from creators' "
        "videos. Every product below is a real item the creator used, with an "
        "approximate current price and a link to buy it.",
        "",
        "## Creator pages",
        "",
    ]
    for p in pages:
        out.append(f"- [{p['title']} — {p['creator_name']}]({p['url']}): "
                   f"{p['summary']} ({p['num_products']} products)")
    out += ["", "## About", "",
            f"- [{config.BRAND}]({config.BASE_URL}): {config.TAGLINE}", ""]
    return "\n".join(out)


# --------------------------------------------------------------------------
# sitemap.xml
# --------------------------------------------------------------------------
def sitemap_xml(pages: list[dict]) -> str:
    urls = [config.BASE_URL] + [p["url"] for p in pages]
    body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n")


# --------------------------------------------------------------------------
# main-site Schema.org injection (idempotent, between markers)
# --------------------------------------------------------------------------
def inject_main_site_schema(pages: list[dict], target: Path | None = None) -> bool:
    """Replace (or insert) the managed <script id="reelie-schema"> block in the
    main webpage with a graph referencing all pages. Returns True if written."""
    target = target or config.MAIN_SITE_HTML
    if not target.exists():
        return False

    graph = site_graph(pages)
    block = (
        f"{config.SCHEMA_MARKER_START}\n"
        '<script id="reelie-schema" type="application/ld+json">\n'
        f"{json.dumps(graph, indent=2, ensure_ascii=False)}\n"
        "</script>\n"
        f"{config.SCHEMA_MARKER_END}"
    )

    src = target.read_text()
    start, end = config.SCHEMA_MARKER_START, config.SCHEMA_MARKER_END
    if start in src and end in src:
        pre = src[: src.index(start)]
        post = src[src.index(end) + len(end):]
        new = pre + block + post
    else:
        # insert just before </head>
        needle = "</head>"
        i = src.lower().find(needle)
        if i == -1:
            return False
        new = src[:i] + "  " + block + "\n" + src[i:]
    if new != src:
        target.write_text(new)
    return True


# --------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------
def write_all(pages: list[dict]) -> dict:
    site = config.OUT_SITE
    site.mkdir(parents=True, exist_ok=True)
    (site / "robots.txt").write_text(robots_txt())
    (site / "llms.txt").write_text(llms_txt(pages))
    (site / "sitemap.xml").write_text(sitemap_xml(pages))
    (site / "schema-graph.json").write_text(
        json.dumps(site_graph(pages), indent=2, ensure_ascii=False))
    injected = inject_main_site_schema(pages)
    return {
        "robots": site / "robots.txt",
        "llms": site / "llms.txt",
        "sitemap": site / "sitemap.xml",
        "schema": site / "schema-graph.json",
        "main_site_injected": injected,
    }
