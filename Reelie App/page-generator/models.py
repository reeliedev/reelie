"""
Canonical data model for a generated page. This is the single source of truth —
the app JSON, the public HTML, and all schema.org / robots / llms outputs are
rendered FROM these objects, never the other way around.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Price:
    amount: float
    currency: str = "USD"
    display: str = ""            # "$18"
    valid_until: str = ""        # ISO date; when an estimate should be refreshed
    estimated: bool = True       # True = LLM/heuristic guess, not a live quote

    def __post_init__(self):
        if not self.display and self.amount:
            self.display = _money(self.amount, self.currency)


@dataclass
class Link:
    kind: str = "reelie"         # "reelie" (we route to best rate) | "own" (creator's link)
    rate: int | None = None      # commission % for reelie links
    label: str | None = None     # e.g. "LTK" for own links
    url: str = ""


@dataclass
class Creator:
    display_name: str
    handle: str
    platforms: list[str] = field(default_factory=list)
    avatar_gradient: list[str] = field(default_factory=lambda: ["#E8E4DA", "#D8D2C4"])


@dataclass
class SourceVideo:
    platform: str = ""           # "youtube" | "instagram" | "tiktok"
    url: str = ""
    title: str = ""
    duration_s: float = 0.0
    thumbnail_url: str = ""


@dataclass
class ProductItem:
    name: str
    brand: str = ""
    emoji: str = "🛍️"
    variant: str | None = None
    evidence: str = "shown"      # spoken | shown | both | on-screen-text | description
    timestamp: str = "0:00"      # "0:12" display
    timestamp_s: float = 0.0
    note: str | None = None      # short quote / usage note (compact contexts)
    guide: str | None = None     # 1-3 sentence narration for the web guide
    clip: str | None = None      # per-step video clip (relative to the public page)
    clip_poster: str | None = None  # poster frame for the clip
    retailer: str = ""
    price: Price | None = None
    link: Link = field(default_factory=Link)
    confidence: float = 0.0
    position: int = 0
    id: str = field(default_factory=_uuid)


@dataclass
class Page:
    handle: str
    title: str
    slug: str
    creator: Creator
    emoji: str = "🎬"
    custom_slug: str | None = None      # creator-named link; overrides slug when set
    meta: str = ""
    summary: str = ""                   # one-liner for llms.txt + meta description
    intro: str = ""                     # guide overview paragraph, creator's voice
    disclosure: str = ""
    source_video: SourceVideo = field(default_factory=SourceVideo)
    products: list[ProductItem] = field(default_factory=list)
    video_id: str = ""
    schema_version: int = 1
    id: str = field(default_factory=_uuid)

    # ---- derived ----
    @property
    def path_slug(self) -> str:
        """The slug actually used in URLs (creator's custom link wins)."""
        return self.custom_slug or self.slug

    @property
    def url(self) -> str:
        from config import BASE_URL
        return f"{BASE_URL}/{self.handle}/{self.path_slug}"

    # ---- (de)serialization ----
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def from_dict(cls, d: dict) -> "Page":
        d = dict(d)
        d["creator"] = Creator(**d["creator"])
        d["source_video"] = SourceVideo(**d.get("source_video", {}))
        prods = []
        for p in d.get("products", []):
            p = dict(p)
            p["price"] = Price(**p["price"]) if p.get("price") else None
            p["link"] = Link(**p["link"]) if p.get("link") else Link()
            prods.append(ProductItem(**p))
        d["products"] = prods
        return cls(**d)

    @classmethod
    def load(cls, path: Path) -> "Page":
        return cls.from_dict(json.loads(Path(path).read_text()))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
_SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "$", "AUD": "$"}


def _money(amount: float, currency: str = "USD") -> str:
    sym = _SYMBOL.get(currency, "")
    # whole dollars look cleaner without .00
    if abs(amount - round(amount)) < 0.005:
        return f"{sym}{int(round(amount))}"
    return f"{sym}{amount:.2f}"


def fmt_timestamp(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"
