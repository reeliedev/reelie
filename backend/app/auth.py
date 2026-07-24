"""
Authentication. A provider abstraction so the managed provider swaps in by config:

  AUTH_PROVIDER=dev    -> DevAuthProvider: issues/verifies our own HS256 JWTs (local $0).
  AUTH_PROVIDER=oidc   -> OIDCAuthProvider: verifies a real provider's RS256 token
                          against its JWKS. Works for Clerk / Auth0 / Sign in with
                          Apple — set OIDC_JWKS_URL / OIDC_ISSUER / OIDC_AUDIENCE.

Both resolve a Bearer token to a User. For OIDC, a first-seen token provisions a
User keyed by the provider 'sub' (external_id).
"""

from __future__ import annotations

import time
from typing import Protocol

import jwt
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from app import config
from app.db import get_session
from app.models import User


class AuthProvider(Protocol):
    def issue_token(self, user_id: str) -> str: ...
    def resolve_user(self, session: Session, token: str) -> User | None: ...


class DevAuthProvider:
    """Local, no-dependency auth: signs/verifies our own JWTs."""

    def issue_token(self, user_id: str) -> str:
        now = int(time.time())
        payload = {"sub": user_id, "iat": now, "exp": now + config.JWT_TTL_SECONDS}
        return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

    def resolve_user(self, session: Session, token: str) -> User | None:
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except jwt.PyJWTError:
            return None
        return session.get(User, payload.get("sub"))


class OIDCAuthProvider:
    """Verify a managed provider's RS256 token via JWKS; provision by `sub`."""

    def __init__(self) -> None:
        if not config.OIDC_JWKS_URL:
            raise RuntimeError("OIDC_JWKS_URL must be set when AUTH_PROVIDER=oidc")
        # Lazy JWKS client (caches keys, refetches on rotation).
        self._jwks = jwt.PyJWKClient(config.OIDC_JWKS_URL)

    def issue_token(self, user_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("OIDC tokens are issued by the provider, not us.")

    def verify(self, token: str) -> dict | None:
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            opts = {}
            # Accept both common asymmetric families: RS256 (Clerk/Auth0/Apple) and
            # ES256 (Supabase's default signing key).
            kwargs: dict = {"algorithms": ["RS256", "ES256"]}
            if config.OIDC_AUDIENCE:
                kwargs["audience"] = config.OIDC_AUDIENCE
            else:
                opts["verify_aud"] = False
            if config.OIDC_ISSUER:
                kwargs["issuer"] = config.OIDC_ISSUER
            return jwt.decode(token, key, options=opts, **kwargs)
        except jwt.PyJWTError:
            return None

    def resolve_user(self, session: Session, token: str) -> User | None:
        payload = self.verify(token)
        if not payload:
            return None
        sub = payload.get("sub")
        if not sub:
            return None
        user = session.exec(select(User).where(User.external_id == sub)).first()
        if user:
            return user
        # First sign-in with this provider identity → provision a viewer account.
        email = (payload.get("email") or f"{sub}@users.reelie.io").lower()
        # Only auto-link to an existing email-based account when the provider has
        # VERIFIED the email AND that account isn't already bound to another
        # identity. Otherwise an unverified-email signup could take over an account.
        email_verified = payload.get("email_verified") is True
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing and email_verified and not existing.external_id:
            existing.external_id = sub   # safe first-time link
            user = existing
        elif existing and existing.external_id and existing.external_id != sub:
            # Email already belongs to a different identity — refuse to hijack it.
            return None
        elif existing:
            user = existing
        else:
            user = User(email=email, external_id=sub,
                        display_name=payload.get("name") or email.split("@")[0].title(),
                        avatar_gradient=config.DEFAULT_AVATAR_GRADIENT, role="viewer")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _make_provider() -> AuthProvider:
    if config.AUTH_PROVIDER == "dev":
        return DevAuthProvider()
    if config.AUTH_PROVIDER == "oidc":
        return OIDCAuthProvider()
    raise RuntimeError(f"Unknown AUTH_PROVIDER: {config.AUTH_PROVIDER}")


provider: AuthProvider = _make_provider()


# --- FastAPI dependencies --------------------------------------------------
def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    token = _bearer(authorization)
    user = provider.resolve_user(session, token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def optional_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User | None:
    token = _bearer(authorization)
    return provider.resolve_user(session, token) if token else None
