"""
SQLModel tables. Fields mirror the canonical Page/Product/Creator used by the
page-generator and the iOS app so the API is a drop-in source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    email: str = Field(index=True, unique=True)
    external_id: str | None = Field(default=None, index=True)   # provider 'sub' (OIDC)
    display_name: str = ""
    handle: str | None = Field(default=None, index=True)   # set when they become a creator
    avatar_gradient: list = Field(default_factory=list, sa_column=Column(JSON))
    role: str = "viewer"                                    # viewer | creator | both
    created_at: datetime = Field(default_factory=_now)


class Creator(SQLModel, table=True):
    handle: str = Field(primary_key=True)
    display_name: str
    avatar_gradient: list = Field(default_factory=list, sa_column=Column(JSON))
    platforms: list = Field(default_factory=list, sa_column=Column(JSON))
    bio: str = ""


class Page(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("handle", "slug", name="uq_page_handle_slug"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    handle: str = Field(index=True, foreign_key="creator.handle")
    slug: str = Field(index=True)
    title: str = ""
    emoji: str = "🎬"
    meta: str = ""
    intro: str = ""
    summary: str = ""
    disclosure: str = ""
    video_id: str = ""
    archived: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_now)

    @property
    def key(self) -> str:
        return f"{self.handle}/{self.slug}"


class Product(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    page_id: str = Field(index=True, foreign_key="page.id")
    position: int = 0
    brand: str = ""
    name: str = ""
    emoji: str = "🛍️"
    variant: str | None = None
    evidence: str = "shown"
    timestamp: str = "0:00"
    note: str | None = None
    guide: str | None = None
    retailer: str = ""
    price_display: str | None = None
    price_amount: float | None = None
    currency: str = "USD"
    price_estimated: bool = True
    link_kind: str = "reelie"
    rate: int | None = None
    own_label: str | None = None
    url: str = ""
    clip_url: str = ""                                     # per-step video clip (absolute URL)
    clip_poster: str = ""                                  # poster frame for the clip
    product_key: str = Field(default="", index=True)       # normalized brand|name for reco


class Favorite(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "kind", "ref", name="uq_fav"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(index=True, foreign_key="user.id")
    kind: str                                              # "page" | "creator"
    ref: str                                               # page key "handle/slug" or creator handle
    created_at: datetime = Field(default_factory=_now)


class Click(SQLModel, table=True):
    """One tap on a /r redirect link — the raw event earnings are built from."""
    id: str = Field(default_factory=_uuid, primary_key=True)
    handle: str = Field(index=True)
    page_slug: str = Field(default="", index=True)
    position: int = 0
    product_id: str | None = None
    user_id: str | None = None
    session: str | None = None
    user_agent: str = ""
    referer: str = ""
    ts: datetime = Field(default_factory=_now)


class GenerationJob(SQLModel, table=True):
    """A self-serve page-generation job: creator picks a video → pipeline runs →
    page published to their account. `status`: queued → running → done | error."""
    id: str = Field(default_factory=_uuid, primary_key=True)
    handle: str = Field(index=True)
    video_id: str = ""
    status: str = "queued"
    stage: str = "Queued"                                  # human-readable progress label
    page_slug: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)


class Payout(SQLModel, table=True):
    """A withdrawal of ready earnings to the creator's bank. In prod this is a
    Stripe Connect transfer; here the amount is recorded and the covered sales are
    marked paid. `status`: pending → paid | failed."""
    id: str = Field(default_factory=_uuid, primary_key=True)
    handle: str = Field(index=True)
    amount: float = 0.0
    status: str = "pending"
    provider: str = "mock"
    provider_ref: str | None = None
    created_at: datetime = Field(default_factory=_now)


class PageLike(SQLModel, table=True):
    """A guest 'like' on a routine, from the Discover feed. Deduped per browser
    via a client-generated id kept in localStorage — no account needed."""
    __table_args__ = (UniqueConstraint("handle", "slug", "client_id", name="uq_like"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    handle: str = Field(index=True)
    slug: str = Field(index=True)
    client_id: str = ""
    created_at: datetime = Field(default_factory=_now)


class SocialConnection(SQLModel, table=True):
    """A creator's linked platform account (YouTube / Instagram), established via
    OAuth. Stores the tokens we use to list their videos. One row per (user,
    platform); re-connecting upserts. Tokens are provider-issued; in prod encrypt
    at rest — for now the DB is the trust boundary (same as any session store)."""
    __table_args__ = (UniqueConstraint("user_id", "platform", name="uq_conn_user_platform"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(index=True)
    platform: str = ""                                     # youtube | instagram
    external_id: str = ""                                  # channel id / IG user id
    username: str = ""                                     # @handle / channel title
    access_token: str = ""
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scopes: str = ""
    connected_at: datetime = Field(default_factory=_now)


class Sale(SQLModel, table=True):
    """A conversion (commission). In prod, created by an affiliate-network
    postback; here also simulated. `state`: pending → ready → paid."""
    id: str = Field(default_factory=_uuid, primary_key=True)
    handle: str = Field(index=True)                        # creator the sale belongs to
    page_slug: str = ""
    position: int = 0
    name: str = ""
    emoji: str = "🛍️"
    value: float = 0.0                                     # commission earned
    order_amount: float = 0.0                              # order total the % is taken from
    retailer: str = ""
    network: str = "mock"
    click_id: str | None = None
    state: str = "pending"                                 # pending | ready | paid
    date: datetime = Field(default_factory=_now)
