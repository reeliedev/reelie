"""
Seed the DB with the same mock corpus the app + web have been demoing (5
creators, overlapping brands so recommendations have signal). Idempotent: only
runs when the DB is empty. Mirrors the iOS Catalog.swift / generator registry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import Click, Creator, Page, Product, Sale
from app.serialize import normalize_product

_CREATORS = [
    ("glowbyjess", "Jess Tan", ["#E8E4DA", "#D8D2C4"], ["YouTube", "Instagram"]),
    ("mariskincare", "Maria Lopez", ["#DCE4E8", "#C4D2D8"], ["Instagram", "TikTok"]),
    ("thefacefiles", "Priya Shah", ["#E8E0DC", "#D8CFC4"], ["YouTube"]),
    ("kbeautykay", "Kay Kim", ["#E4E8DC", "#D2D8C4"], ["TikTok"]),
    ("everydayamira", "Amira Hassan", ["#E8DCE4", "#D8C4D2"], ["Instagram", "YouTube"]),
]

# (handle, title, emoji, slug, [ (brand, name, emoji, price, retailer, rate) ])
_ROUTINES = [
    ("glowbyjess", "My everyday routine", "💄", "everyday-routine", [
        ("Rare Beauty", "Soft Pinch Liquid Blush", "🌸", "$23", "Sephora", 7),
        ("Armani Beauty", "Luminous Silk Concealer", "🪞", "$34", "Sephora", 8),
        ("Laneige", "Lip Sleeping Mask", "💤", "$24", "Sephora", 6),
        ("Charlotte Tilbury", "Flawless Filter", "✨", "$49", "Sephora", 8)]),
    ("glowbyjess", "Summer glow", "🌞", "summer-glow", [
        ("Beauty of Joseon", "Relief Sun SPF 50+", "🌞", "$18", "Amazon", 8),
        ("Iconic London", "Illuminator Drops", "🌟", "$36", "Sephora", 7),
        ("Johnson's", "Baby Oil", "💧", "$7", "Walmart", 6)]),
    ("mariskincare", "My 8-step night routine", "🌙", "night-routine", [
        ("Banila Co", "Clean It Zero Balm", "🧼", "$20", "Amazon", 7),
        ("COSRX", "Snail 96 Mucin Essence", "💧", "$25", "Amazon", 8),
        ("Beauty of Joseon", "Glow Deep Serum", "🌙", "$17", "YesStyle", 8),
        ("Laneige", "Water Sleeping Mask", "💤", "$29", "Sephora", 6),
        ("Anua", "Heartleaf 77% Toner", "🧴", "$22", "Amazon", 8)]),
    ("mariskincare", "Barrier repair basics", "🧴", "barrier-repair", [
        ("CeraVe", "Moisturizing Cream", "🧴", "$16", "Ulta", 6),
        ("COSRX", "Snail 96 Mucin Essence", "💧", "$25", "Amazon", 8),
        ("Beauty of Joseon", "Relief Sun SPF 50+", "🌞", "$18", "Amazon", 8)]),
    ("thefacefiles", "Soft glam in 10 minutes", "✨", "soft-glam", [
        ("Rare Beauty", "Soft Pinch Liquid Blush", "🌸", "$23", "Sephora", 7),
        ("Armani Beauty", "Luminous Silk Concealer", "🪞", "$34", "Sephora", 8),
        ("Charlotte Tilbury", "Flawless Filter", "✨", "$49", "Sephora", 8),
        ("Laneige", "Lip Sleeping Mask", "💤", "$24", "Sephora", 6)]),
    ("kbeautykay", "K-beauty glass skin", "🧴", "glass-skin", [
        ("COSRX", "Snail 96 Mucin Essence", "💧", "$25", "Amazon", 8),
        ("Anua", "Heartleaf 77% Toner", "🧴", "$22", "Amazon", 8),
        ("Beauty of Joseon", "Glow Deep Serum", "🌙", "$17", "YesStyle", 8),
        ("Banila Co", "Clean It Zero Balm", "🧼", "$20", "Amazon", 7)]),
    ("kbeautykay", "My cleansing routine", "🧼", "cleansing", [
        ("Banila Co", "Clean It Zero Balm", "🧼", "$20", "Amazon", 7),
        ("CeraVe", "Foaming Facial Cleanser", "🧼", "$14", "Ulta", 6),
        ("Anua", "Heartleaf 77% Toner", "🧴", "$22", "Amazon", 8)]),
    ("everydayamira", "No-makeup makeup", "💄", "no-makeup", [
        ("The Ordinary", "Niacinamide 10% + Zinc", "💧", "$6", "Ulta", 6),
        ("CeraVe", "Moisturizing Cream", "🧴", "$16", "Ulta", 6),
        ("Maybelline", "Fit Me Foundation", "🪞", "$9", "Walmart", 6),
        ("Beauty of Joseon", "Relief Sun SPF 50+", "🌞", "$18", "Amazon", 8)]),
    ("everydayamira", "Drugstore heroes", "🛍️", "drugstore-heroes", [
        ("CeraVe", "Foaming Facial Cleanser", "🧼", "$14", "Ulta", 6),
        ("The Ordinary", "Niacinamide 10% + Zinc", "💧", "$6", "Ulta", 6),
        ("Maybelline", "Fit Me Foundation", "🪞", "$9", "Walmart", 6)]),
]


def _amount(display: str) -> float:
    return float(display.replace("$", "").replace(",", "") or 0)


def seed_if_empty() -> bool:
    with Session(engine) as s:
        if s.exec(select(Creator)).first():
            return False  # already seeded

        for handle, name, grad, platforms in _CREATORS:
            s.add(Creator(handle=handle, display_name=name, avatar_gradient=grad, platforms=platforms))

        for handle, title, emoji, slug, products in _ROUTINES:
            page = Page(handle=handle, slug=slug, title=title, emoji=emoji,
                        meta=f"{len(products)} products",
                        summary=f"{title} — {len(products)} products, each found and linked automatically.",
                        intro=f"{title} — {len(products)} products, in the order I actually use them.")
            s.add(page)
            s.flush()  # get page.id
            for i, (brand, pname, pemoji, price, retailer, rate) in enumerate(products, 1):
                s.add(Product(
                    page_id=page.id, position=i, brand=brand, name=pname, emoji=pemoji,
                    evidence="both", timestamp="0:00", retailer=retailer,
                    price_display=price, price_amount=_amount(price), currency="USD",
                    price_estimated=True, link_kind="reelie", rate=rate,
                    url=f"https://reelie.shop/r/{handle}/{slug}/{i:02d}",
                    product_key=normalize_product(brand, pname)))

        # Dated sales for glowbyjess so the dashboard has real rollups (incl. paid).
        now = datetime.now(timezone.utc)
        for days, val, amt, slug, nm, em, ret, st in [
            (1, 3.20, 46.0, "everyday-routine", "Rare Beauty Blush", "🌸", "Sephora", "pending"),
            (5, 4.90, 49.0, "everyday-routine", "Charlotte Tilbury Filter", "✨", "Sephora", "ready"),
            (12, 2.40, 18.0, "summer-glow", "Beauty of Joseon Sun", "🌞", "Amazon", "ready"),
            (26, 5.20, 34.0, "everyday-routine", "Armani Concealer", "🪞", "Sephora", "paid"),
            (40, 3.60, 29.0, "summer-glow", "Iconic Illuminator", "🌟", "Sephora", "paid"),
        ]:
            s.add(Sale(handle="glowbyjess", page_slug=slug, name=nm, emoji=em,
                       value=val, order_amount=amt, retailer=ret, state=st,
                       date=now - timedelta(days=days)))

        # A baseline of clicks for glowbyjess so click-through shows on the dashboard.
        for i in range(60):
            slug = "everyday-routine" if i % 2 else "summer-glow"
            s.add(Click(handle="glowbyjess", page_slug=slug, position=(i % 4) + 1,
                        user_agent="seed", ts=now - timedelta(days=i % 30)))

        s.commit()
        return True
