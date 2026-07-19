"""
Social OAuth providers (Pillar 2) — the seam that lets a creator connect their
YouTube / Instagram so we can list their videos.

Same pattern as the affiliate seam: a Protocol with swappable implementations.
`provider_for(platform)` returns the real provider when its credentials are set,
otherwise a MockProvider so the entire connect flow (authorize → callback →
"Connected" → list videos) is demoable locally with no Google/Meta app.

Each provider does four things:
  authorize_url(state, redirect_uri) -> str      # where we send the creator to consent
  exchange_code(code, redirect_uri) -> Token     # code → access/refresh tokens
  fetch_identity(token) -> Identity              # who they are (channel/user id + handle)
  list_videos(token, external_id) -> list[Video] # their uploads, newest first
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlencode

from app import config


def _request(url: str, *, data: dict | None = None, headers: dict | None = None) -> dict:
    """Minimal JSON HTTP (stdlib) — GET, or POST when `data` is given (form-encoded)."""
    body = urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or {},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise RuntimeError(f"{url} → {e.code}: {detail}") from e


@dataclass
class Token:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None          # seconds
    scopes: str = ""


@dataclass
class Identity:
    external_id: str
    username: str


@dataclass
class Video:
    id: str
    title: str
    url: str                                # canonical link we can hand to extract_one
    thumb: str = ""
    published: str = ""
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "url": self.url,
                "thumb": self.thumb, "published": self.published}


class OAuthProvider(Protocol):
    platform: str
    def authorize_url(self, state: str, redirect_uri: str) -> str: ...
    def exchange_code(self, code: str, redirect_uri: str) -> Token: ...
    def fetch_identity(self, token: str) -> Identity: ...
    def list_videos(self, token: str, external_id: str) -> list[Video]: ...


# --------------------------------------------------------------------------
# Mock — no external app needed. authorize_url points straight back at our own
# callback so ASWebAuthenticationSession completes instantly; identity + videos
# are believable fakes so the UI has something real to render.
# --------------------------------------------------------------------------
class MockProvider:
    def __init__(self, platform: str) -> None:
        self.platform = platform

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        # Bounce right back to the callback with a fake code.
        return f"{redirect_uri}?{urlencode({'code': 'mock-code', 'state': state})}"

    def exchange_code(self, code: str, redirect_uri: str) -> Token:
        return Token(access_token=f"mock-{self.platform}-token", scopes="mock.readonly")

    def fetch_identity(self, token: str) -> Identity:
        handle = "yourchannel" if self.platform == "youtube" else "yourhandle"
        return Identity(external_id=f"mock-{self.platform}-id", username=handle)

    def list_videos(self, token: str, external_id: str) -> list[Video]:
        # A couple of real, publicly-downloadable clips so "generate" actually runs.
        base = "https://www.youtube.com/watch?v="
        return [
            Video(id="demo1", title="My everyday skincare routine",
                  url=base + "dQw4w9WgXcQ", published="2026-06-01"),
            Video(id="demo2", title="GRWM — spring edition",
                  url=base + "dQw4w9WgXcQ", published="2026-05-12"),
        ]


# --------------------------------------------------------------------------
# YouTube — Google OAuth 2.0 + YouTube Data API v3.
# Scope youtube.readonly is "sensitive": public use needs Google verification,
# but up to 100 test users work immediately.
# --------------------------------------------------------------------------
_G_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_G_TOKEN = "https://oauth2.googleapis.com/token"
_G_API = "https://www.googleapis.com/youtube/v3"
_G_SCOPES = "https://www.googleapis.com/auth/youtube.readonly"


class YouTubeProvider:
    platform = "youtube"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        q = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _G_SCOPES,
            "access_type": "offline",       # get a refresh token
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{_G_AUTH}?{urlencode(q)}"

    def exchange_code(self, code: str, redirect_uri: str) -> Token:
        d = _request(_G_TOKEN, data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        return Token(access_token=d["access_token"], refresh_token=d.get("refresh_token"),
                     expires_in=d.get("expires_in"), scopes=d.get("scope", _G_SCOPES))

    def fetch_identity(self, token: str) -> Identity:
        h = {"Authorization": f"Bearer {token}"}
        items = _request(f"{_G_API}/channels?{urlencode({'part': 'snippet', 'mine': 'true'})}",
                         headers=h).get("items", [])
        if not items:
            raise RuntimeError("No YouTube channel on this account.")
        ch = items[0]
        return Identity(external_id=ch["id"], username=ch["snippet"]["title"])

    def list_videos(self, token: str, external_id: str) -> list[Video]:
        h = {"Authorization": f"Bearer {token}"}
        # channel → uploads playlist → items
        ch = _request(f"{_G_API}/channels?{urlencode({'part': 'contentDetails', 'id': external_id})}",
                      headers=h)
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = _request(f"{_G_API}/playlistItems?"
                      f"{urlencode({'part': 'snippet', 'playlistId': uploads, 'maxResults': 30})}",
                      headers=h)
        out: list[Video] = []
        for it in pl.get("items", []):
            sn = it["snippet"]
            vid = sn["resourceId"]["videoId"]
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            out.append(Video(id=vid, title=sn.get("title", "Untitled"),
                             url=f"https://www.youtube.com/watch?v={vid}",
                             thumb=thumb, published=sn.get("publishedAt", "")[:10]))
        return out


# --------------------------------------------------------------------------
# Instagram — Meta app (Instagram API with Instagram Login). In dev/standard
# mode a limited set of tester accounts (each a Professional IG account that has
# accepted the tester invite) can use it without full App Review.
# --------------------------------------------------------------------------
_IG_AUTH = "https://www.instagram.com/oauth/authorize"
_IG_TOKEN = "https://api.instagram.com/oauth/access_token"
_IG_GRAPH = "https://graph.instagram.com"
_IG_SCOPES = "instagram_business_basic"


class InstagramProvider:
    platform = "instagram"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        q = {
            "client_id": config.INSTAGRAM_APP_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _IG_SCOPES,
            "state": state,
        }
        return f"{_IG_AUTH}?{urlencode(q)}"

    def exchange_code(self, code: str, redirect_uri: str) -> Token:
        d = _request(_IG_TOKEN, data={
            "client_id": config.INSTAGRAM_APP_ID,
            "client_secret": config.INSTAGRAM_APP_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
        })
        return Token(access_token=d["access_token"], scopes=_IG_SCOPES)

    def fetch_identity(self, token: str) -> Identity:
        d = _request(f"{_IG_GRAPH}/me?{urlencode({'fields': 'user_id,username', 'access_token': token})}")
        return Identity(external_id=str(d.get("user_id", d.get("id", ""))),
                        username=d.get("username", ""))

    def list_videos(self, token: str, external_id: str) -> list[Video]:
        d = _request(f"{_IG_GRAPH}/me/media?"
                     f"{urlencode({'fields': 'id,caption,media_type,media_url,permalink,timestamp', 'access_token': token})}")
        out: list[Video] = []
        for m in d.get("data", []):
            if m.get("media_type") not in ("VIDEO", "REEL"):
                continue
            out.append(Video(
                id=m["id"], title=(m.get("caption") or "Instagram video")[:80],
                url=m.get("media_url") or m.get("permalink", ""),
                published=(m.get("timestamp") or "")[:10]))
        return out


# --------------------------------------------------------------------------
_REAL = {
    "youtube": (YouTubeProvider, lambda: bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)),
    "instagram": (InstagramProvider, lambda: bool(config.INSTAGRAM_APP_ID and config.INSTAGRAM_APP_SECRET)),
}
SUPPORTED = tuple(_REAL.keys())


def provider_for(platform: str) -> OAuthProvider:
    if platform not in _REAL:
        raise ValueError(f"Unsupported platform: {platform}")
    cls, has_creds = _REAL[platform]
    if config.OAUTH_FORCE_MOCK or not has_creds():
        return MockProvider(platform)
    return cls()


def is_mock(platform: str) -> bool:
    _, has_creds = _REAL[platform]
    return config.OAUTH_FORCE_MOCK or not has_creds()


def redirect_uri_for(platform: str) -> str:
    return f"{config.OAUTH_REDIRECT_BASE}/connect/{platform}/callback"
