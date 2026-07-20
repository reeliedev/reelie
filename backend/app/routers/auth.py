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


class DevLogin(BaseModel):
    email: str
    displayName: str | None = None


@router.post("/dev-login")
def dev_login(body: DevLogin, session: Session = Depends(get_session)):
    """Create or fetch a viewer account for this email, return a bearer token.
    Dev provider only — with a managed provider (AUTH_PROVIDER=oidc) the client
    sends the provider's token directly and the server verifies it via JWKS."""
    if config.AUTH_PROVIDER != "dev":
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
