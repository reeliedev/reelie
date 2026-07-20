# Authentication — Supabase Auth (Apple + Google + email magic-link)

Creators sign in; consumers stay guests (likes/saves are local, no account).
The login UI is **ours** (Reelie design) — Supabase is headless underneath and
brokers all three methods. Nothing about auth is hard-coded: with no Supabase
env vars the Studio falls back to the local dev email login.

## How it's wired (already built)
- Backend verifies Supabase's JWT via its **JWKS** using the existing
  `OIDCAuthProvider` ([app/auth.py](backend/app/auth.py)). Setting `SUPABASE_URL`
  auto-derives `OIDC_JWKS_URL/ISSUER/AUDIENCE` and flips `AUTH_PROVIDER=oidc`
  ([app/config.py](backend/app/config.py)). First login **auto-provisions** a
  Reelie account (keyed by the Supabase user id).
- `/auth/config` tells the Studio which login to render.
- The Studio ([app/studio.py](backend/app/studio.py)) loads `supabase-js`, shows
  **Sign in with Apple / Continue with Google / email magic-link**, and uses the
  returned access token as the `Bearer` for all API calls.

## Activation (when going public — needs a Supabase project)
1. Create a free project at **supabase.com** → Project Settings → API. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public key** → `SUPABASE_ANON_KEY` (public; safe in the browser)
2. **Authentication → Providers** → enable:
   - **Email** (magic link — on by default)
   - **Google** → paste a Google OAuth client id/secret (Google Cloud console)
   - **Apple** → paste the Apple service id + key (Apple Developer)
3. **Authentication → URL Configuration** → set **Site URL** = `https://reelie.shop`
   and add redirect URLs: `https://reelie.shop/studio`, `https://reelie.shop/*`.
4. Ensure asymmetric JWTs: **Auth → Signing keys** → use the ES256/RS256 key
   (exposes the JWKS endpoint our backend reads). Legacy HS256-only projects
   won't verify via JWKS.
5. Set in Render (`reelie-api` → Environment):
   - `SUPABASE_URL = https://<project>.supabase.co`
   - `SUPABASE_ANON_KEY = <anon key>`
   Redeploy. The Studio login instantly switches to Apple/Google/magic-link.

## iOS (later)
Use the Supabase Swift SDK (or Sign in with Apple via `AuthenticationServices`) →
send the access token as `Bearer` to the same API. Backend needs no change.

## Note
`AUTH_PROVIDER=dev` (email dev-login, no password) is for **local only** — never
deploy with it. Setting `SUPABASE_URL` in prod switches everything to real auth.
