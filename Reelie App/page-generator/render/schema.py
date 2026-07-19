"""
Schema.org JSON-LD builders.

  page_graph(page)   -> the @graph embedded in a public page: ProfilePage + Person
                        + ItemList of Product/Offer (with PRICE) + VideoObject +
                        BreadcrumbList. This is what makes each page "complete" for
                        AI assistants — every product carries a real Offer.

  site_graph(pages)  -> the site-wide @graph injected into the main webpage:
                        Organization + WebSite + a CollectionPage/ItemList of every
                        generated creator page, so crawlers discover them all.
"""

from __future__ import annotations

import config
from models import Page, ProductItem

SCHEMA_CTX = "https://schema.org"

_AVAILABILITY = "https://schema.org/InStock"


def _offer(product: ProductItem) -> dict | None:
    if not product.price:
        return None
    offer = {
        "@type": "Offer",
        "price": f"{product.price.amount:.2f}",
        "priceCurrency": product.price.currency,
        "availability": _AVAILABILITY,
        "url": product.link.url,
    }
    if product.price.valid_until:
        offer["priceValidUntil"] = product.price.valid_until
    if product.retailer:
        offer["seller"] = {"@type": "Organization", "name": product.retailer}
    return offer


def _product_node(page: Page, product: ProductItem) -> dict:
    node: dict = {
        "@type": "Product",
        "@id": f"{page.url}#product-{product.position}",
        "name": (f"{product.brand} {product.name}".strip() if product.brand else product.name),
        "position": product.position,
    }
    if product.brand:
        node["brand"] = {"@type": "Brand", "name": product.brand}
    if product.variant:
        node["description"] = f"Variant: {product.variant}"
    if product.note:
        node["review"] = {
            "@type": "Review",
            "author": {"@type": "Person", "name": page.creator.display_name},
            "reviewBody": product.note,
        }
    offer = _offer(product)
    if offer:
        node["offers"] = offer
    return node


def _person(page: Page) -> dict:
    return {
        "@type": "Person",
        "@id": f"{config.BASE_URL}/{page.handle}#person",
        "name": page.creator.display_name,
        "alternateName": f"@{page.handle}",
        "url": f"{config.BASE_URL}/{page.handle}",
    }


def _video(page: Page) -> dict | None:
    v = page.source_video
    if not (v.url or v.title):
        return None
    node = {
        "@type": "VideoObject",
        "name": v.title or page.title,
        "description": page.summary or page.meta,
    }
    if v.url:
        node["contentUrl"] = v.url
    if v.duration_s:
        node["duration"] = f"PT{int(v.duration_s)}S"
    if v.thumbnail_url:
        node["thumbnailUrl"] = v.thumbnail_url
    return node


def page_graph(page: Page) -> dict:
    """Full JSON-LD document (with @context) for embedding in a public page."""
    item_list = {
        "@type": "ItemList",
        "@id": f"{page.url}#products",
        "name": page.title,
        "numberOfItems": len(page.products),
        "itemListOrder": "https://schema.org/ItemListOrderAscending",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": p.position,
                "item": _product_node(page, p),
            }
            for p in page.products
        ],
    }

    profile = {
        "@type": "ProfilePage",
        "@id": f"{page.url}#page",
        "url": page.url,
        "name": page.title,
        "headline": page.title,
        "description": page.summary or page.meta,
        "isPartOf": {"@id": f"{config.BASE_URL}#website"},
        "about": {"@id": f"{config.BASE_URL}/{page.handle}#person"},
        "mainEntity": {"@id": f"{page.url}#products"},
    }

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": config.BRAND,
             "item": config.BASE_URL},
            {"@type": "ListItem", "position": 2, "name": page.creator.display_name,
             "item": f"{config.BASE_URL}/{page.handle}"},
            {"@type": "ListItem", "position": 3, "name": page.title, "item": page.url},
        ],
    }

    graph = [profile, _person(page), item_list, breadcrumb]
    video = _video(page)
    if video:
        graph.append(video)

    return {"@context": SCHEMA_CTX, "@graph": graph}


def site_graph(pages: list[dict]) -> dict:
    """Site-wide JSON-LD injected into the main webpage. `pages` is the registry
    (list of dicts from pages.json)."""
    org = {
        "@type": "Organization",
        "@id": f"{config.BASE_URL}#org",
        "name": config.BRAND,
        "url": config.BASE_URL,
        "description": config.TAGLINE,
        "email": config.SUPPORT_EMAIL,
    }
    website = {
        "@type": "WebSite",
        "@id": f"{config.BASE_URL}#website",
        "url": config.BASE_URL,
        "name": config.BRAND,
        "publisher": {"@id": f"{config.BASE_URL}#org"},
    }
    collection = {
        "@type": "CollectionPage",
        "@id": f"{config.BASE_URL}#creator-pages",
        "name": f"{config.BRAND} creator pages",
        "isPartOf": {"@id": f"{config.BASE_URL}#website"},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(pages),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": p["url"],
                    "name": f"{p['title']} — {p['creator_name']}",
                }
                for i, p in enumerate(pages)
            ],
        },
    }
    return {"@context": SCHEMA_CTX, "@graph": [org, website, collection]}
