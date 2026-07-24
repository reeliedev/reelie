"""Auth routes. Dev login issues a JWT for an email — the managed provider
(Clerk/Auth0) would replace this with an OAuth callback later."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app import config
from app.auth import provider
from app.db import get_session
from app.models import User
from app.serialize import user_dict

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config():
    """What the login UI should render. 'supabase' → Apple/Google/magic-link via
    the public anon key; 'dev' → the local email login (no real auth)."""
    if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
        return {"provider": "supabase", "supabaseUrl": config.SUPABASE_URL,
                "supabaseAnonKey": config.SUPABASE_ANON_KEY}
    return {"provider": "dev"}


class DebugToken(BaseModel):
    token: str


@router.post("/debug-token")
def debug_token(body: DebugToken):
    """TEMP diagnostic — reports whether a provider token verifies and, if not, the
    exact reason, plus the issuer/audience/JWKS the backend expects. No secrets."""
    payload = provider.verify(body.token) if hasattr(provider, "verify") else None
    return {
        "provider": config.AUTH_PROVIDER,
        "ok": payload is not None,
        "reason": "" if payload else getattr(type(provider), "last_error", ""),
        "sub": (payload or {}).get("sub"),
        "expectedIssuer": getattr(config, "OIDC_ISSUER", None),
        "expectedAudience": getattr(config, "OIDC_AUDIENCE", None),
        "jwksUrl": getattr(config, "OIDC_JWKS_URL", None),
    }


@router.get("/debug-jwks")
def debug_jwks():
    """TEMP diagnostic — what signing keys the backend can actually fetch from the
    configured JWKS (confirms reachability + the ES256 key is visible). Remove after."""
    import jwt as _jwt
    from app.auth import _SSL_CTX
    try:
        s = _jwt.PyJWKClient(config.OIDC_JWKS_URL, ssl_context=_SSL_CTX).get_jwk_set()
        return {"jwksUrl": config.OIDC_JWKS_URL,
                "keys": [{"kid": k.key_id,
                          "kty": k._jwk_data.get("kty"),
                          "alg": k._jwk_data.get("alg")} for k in s.keys]}
    except Exception as e:  # noqa: BLE001
        return {"jwksUrl": config.OIDC_JWKS_URL, "error": f"{type(e).__name__}: {e}"}


class DevLogin(BaseModel):
    email: str
    displayName: str | None = None


@router.post("/dev-login")
def dev_login(body: DevLogin, session: Session = Depends(get_session)):
    """Create or fetch a viewer account for this email, return a bearer token.
    Dev provider only — with a managed provider (AUTH_PROVIDER=oidc) the client
    sends the provider's token directly and the server verifies it via JWKS."""
    # dev-login is a password-less token mint. Disabled unless the dev provider is
    # active, and in prod only when explicitly acknowledged (ALLOW_DEV_AUTH=1).
    if config.AUTH_PROVIDER != "dev" or (config.IS_PROD and not config.ALLOW_DEV_AUTH):
        raise HTTPException(404, "dev-login is disabled; use the configured auth provider.")
    user = session.exec(select(User).where(User.email == body.email.lower())).first()
    if not user:
        user = User(
            email=body.email.lower(),
            display_name=body.displayName or body.email.split("@")[0].title(),
            avatar_gradient=config.DEFAULT_AVATAR_GRADIENT,
            role="viewer",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    token = provider.issue_token(user.id)
    return {"token": token, "user": user_dict(user, session)}
