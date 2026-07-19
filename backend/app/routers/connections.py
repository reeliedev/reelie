"""
Social connections (Pillar 2). A creator links their YouTube / Instagram via
OAuth so we can list their videos:

  GET    /me/connect/{platform}        -> { authorizeUrl }   (open in a web-auth session)
  GET    /connect/{platform}/callback  -> provider redirect; upserts the connection,
                                          then 302s to the app's custom scheme
  GET    /me/connections               -> connected platforms for the current user
  DELETE /me/connections/{platform}    -> disconnect
  GET    /me/connections/{platform}/videos -> that account's videos (feeds PickVideo)

The callback isn't Bearer-authed (the provider calls it); instead a short-lived
signed `state` carries the user id, so we know who is connecting.
"""

from __future__ import annotations

import time
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app import config, oauth
from app.auth import current_user
from app.db import get_session
from app.models import SocialConnection, User, _now

router = APIRouter(tags=["connections"])

_STATE_TTL = 600  # seconds


def _require_creator(user: User) -> None:
    if user.role not in ("creator", "both") or not user.handle:
        raise HTTPException(403, "Become a creator first.")


def _sign_state(user_id: str, platform: str) -> str:
    now = int(time.time())
    return jwt.encode({"uid": user_id, "platform": platform, "purpose": "oauth_state",
                       "iat": now, "exp": now + _STATE_TTL},
                      config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _read_state(state: str, platform: str) -> str:
    try:
        p = jwt.decode(state, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(400, "Invalid or expired connect request.")
    if p.get("purpose") != "oauth_state" or p.get("platform") != platform:
        raise HTTPException(400, "Bad connect state.")
    return p["uid"]


def _conn_dict(c: SocialConnection) -> dict:
    return {"platform": c.platform, "username": c.username,
            "connectedAt": c.connected_at.isoformat(), "mock": oauth.is_mock(c.platform)}


# --- start ----------------------------------------------------------------
@router.get("/me/connect/{platform}")
def start_connect(platform: str, user: User = Depends(current_user)):
    _require_creator(user)
    if platform not in oauth.SUPPORTED:
        raise HTTPException(404, "Unsupported platform.")
    prov = oauth.provider_for(platform)
    url = prov.authorize_url(_sign_state(user.id, platform), oauth.redirect_uri_for(platform))
    return {"authorizeUrl": url, "mock": oauth.is_mock(platform),
            "callbackScheme": config.APP_CALLBACK_SCHEME}


# --- callback (provider → us → app) ---------------------------------------
@router.get("/connect/{platform}/callback")
def oauth_callback(platform: str, state: str = "", code: str = "", error: str = "",
                   session: Session = Depends(get_session)):
    scheme = config.APP_CALLBACK_SCHEME
    if error or not code:
        return RedirectResponse(f"{scheme}://connected/{platform}?ok=0", status_code=302)
    if platform not in oauth.SUPPORTED:
        raise HTTPException(404, "Unsupported platform.")
    user_id = _read_state(state, platform)
    prov = oauth.provider_for(platform)
    try:
        tok = prov.exchange_code(code, oauth.redirect_uri_for(platform))
        ident = prov.fetch_identity(tok.access_token)
    except Exception as e:  # noqa: BLE001
        return RedirectResponse(f"{scheme}://connected/{platform}?ok=0", status_code=302)

    existing = session.exec(select(SocialConnection).where(
        SocialConnection.user_id == user_id,
        SocialConnection.platform == platform)).first()
    conn = existing or SocialConnection(user_id=user_id, platform=platform)
    conn.external_id = ident.external_id
    conn.username = ident.username
    conn.access_token = tok.access_token
    conn.refresh_token = tok.refresh_token or conn.refresh_token
    conn.scopes = tok.scopes
    conn.token_expires_at = (_now() + timedelta(seconds=tok.expires_in)) if tok.expires_in else None
    conn.connected_at = _now()
    session.add(conn)
    session.commit()
    return RedirectResponse(f"{scheme}://connected/{platform}?ok=1", status_code=302)


# --- list / disconnect -----------------------------------------------------
@router.get("/me/connections")
def list_connections(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(SocialConnection).where(SocialConnection.user_id == user.id)).all()
    return [_conn_dict(c) for c in rows]


@router.delete("/me/connections/{platform}")
def disconnect(platform: str, user: User = Depends(current_user),
               session: Session = Depends(get_session)):
    row = session.exec(select(SocialConnection).where(
        SocialConnection.user_id == user.id,
        SocialConnection.platform == platform)).first()
    if row:
        session.delete(row)
        session.commit()
    return {"ok": True}


# --- videos from a connected account --------------------------------------
@router.get("/me/connections/{platform}/videos")
def connection_videos(platform: str, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    _require_creator(user)
    row = session.exec(select(SocialConnection).where(
        SocialConnection.user_id == user.id,
        SocialConnection.platform == platform)).first()
    if not row:
        raise HTTPException(404, f"No {platform} account connected.")
    prov = oauth.provider_for(platform)
    try:
        vids = prov.list_videos(row.access_token, row.external_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Couldn't load your {platform} videos: {e}")
    return [v.as_dict() for v in vids]
