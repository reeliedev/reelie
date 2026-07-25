"""
Response builders — camelCase dicts that decode 1:1 into the iOS models
(GeneratedPageDTO / Creator) so the app's existing decoders work unchanged.
"""

from __future__ import annotations

from app import public_site
from app.integrations import effective_retailer, money
from app.models import Creator, Page, Product, User

# Appended to a routine's disclosure so every client shows the price disclaimer the
# web page always shows (templates/public_page.html keeps the matching copy).
PRICE_DISCLAIMER = "Prices are approximate and refreshed regularly."


def _full_disclosure(page: Page) -> str:
    return " ".join(x for x in [(page.disclosure or "").strip(), PRICE_DISCLAIMER] if x)


def user_dict(u: User, session=None) -> dict:
    # Closed beta: expose the creator's review status so the UI can gate posting.
    status = None
    if u.handle and session is not None:
        c = session.get(Creator, u.handle)
        status = c.status if c else None
    return {
        "id": u.id,
        "email": u.email,
        "displayName": u.display_name,
        "handle": u.handle,
        "avatarGradient": u.avatar_gradient or [],
        "role": u.role,
        "isCreator": u.role in ("creator", "both"),
        "creatorStatus": status,          # pending | approved | rejected | null
        "approved": status == "approved",
    }


def normalize_product(brand: str, name: str) -> str:
    def norm(s: str) -> str:
        return "".join(c for c in (s or "").lower() if c.isalnum() or c == " ").strip()
    return f"{norm(brand)}|{norm(name)}"


def creator_dict(c: Creator) -> dict:
    return {
        "handle": c.handle,
        "displayName": c.display_name,
        "avatarGradient": c.avatar_gradient or [],
        "platforms": c.platforms or [],
        "bio": c.bio,
    }


def product_app(p: Product) -> dict:
    return {
        "id": p.id,
        "position": p.position,
        "brand": p.brand,
        "name": p.name,
        "emoji": p.emoji,
        "variant": p.variant,
        "evidence": p.evidence,
        "timestamp": p.timestamp,
        "note": p.note,
        "guide": p.guide,
        # Honest retailer: matches where the link actually resolves (same helper the
        # web page uses), so a client can't show "Ulta" while the link goes to Amazon.
        "retailer": effective_retailer(p),
        # Fall back to formatting the numeric price so a client (iOS) that only
        # reads priceDisplay still shows a price — matches the web + feed.
        "priceDisplay": p.price_display or money(p.price_amount, p.currency),
        "priceAmount": p.price_amount,
        "currency": p.currency,
        "priceEstimated": p.price_estimated,
        "linkKind": p.link_kind,
        "rate": p.rate,
        "ownLabel": p.own_label,
        "url": p.url,
    }


def page_app(page: Page, products: list[Product], creator: Creator) -> dict:
    """GeneratedPageDTO-compatible payload for a routine."""
    ordered = sorted(products, key=lambda x: x.position)
    t = public_site._totals(ordered)
    # Auto-generated + custom FAQs (the same Q&A the web page shows), and the
    # "shop the whole routine" kit totals — so the app can show both like the web.
    faqs = ([{"q": q, "a": a} for q, a, _custom in public_site.faqs(page, creator, ordered)]
            if creator else [])
    return {
        "id": page.id,
        "title": page.title,
        "emoji": page.emoji,
        "slug": page.slug,
        "customSlug": None,
        "meta": page.meta,
        "intro": page.intro,
        "handle": page.handle,
        "creatorName": creator.display_name if creator else page.handle,
        "platforms": creator.platforms if creator else [],
        "disclosure": _full_disclosure(page),
        "publicURL": f"reelie.io/{page.handle}/{page.slug}",
        "products": [product_app(p) for p in ordered],
        "faqs": faqs,
        "totals": {"count": t["count"], "totalDisplay": t["total_display"],
                   "rangeDisplay": t["range_display"], "anyEstimated": t["any_estimated"],
                   "retailers": t["retailers"]},
    }
