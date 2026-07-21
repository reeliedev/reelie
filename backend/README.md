# Reelie backend — foundation (accounts + catalog API)

The real source of truth behind the iOS app and the web pages. **Local runs cost
nothing**: SQLite (a local file) + a dev-auth stub + stubbed affiliate/payout
integrations. Postgres and a managed auth provider swap in later via env vars.

## Run it ($0, no external services)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run.sh                      # http://127.0.0.1:8000  (interactive docs at /docs)
```

On first boot it creates `reelie.db` (SQLite) and seeds the same 5-creator mock
corpus the app/web have been demoing.

## What's here

| area | file |
|---|---|
| config (SQLite default, JWT secret, provider) | `app/config.py` |
| DB engine/session | `app/db.py` |
| tables: User, Creator, Page, Product, Favorite, Sale | `app/models.py` |
| dev auth (JWT) + provider interface | `app/auth.py` |
| recommendations (shared-brand / shared-product) | `app/recommend.py` |
| **stub swap-points**: AffiliateNetwork, PayoutProvider | `app/integrations.py` |
| seed importer | `app/seed.py` |
| routes | `app/routers/{auth,me,catalog,recommend}.py` |

## Endpoints

- `POST /auth/dev-login` `{email}` → `{token, user}` (dev only; issues our own JWT)
- `GET /me` · `POST /me/become-creator` `{handle}` (viewer → creator)
- `GET/POST/DELETE /me/favorites` `{kind: page|creator, ref}`
- `GET /creators` · `/creators/{handle}` · `/creators/{handle}/routines`
- `GET /routines` · `/routines/{handle}/{slug}`  (GeneratedPageDTO-shaped)
- `GET /recommendations/similar/{handle}` · `/recommendations/using?brand=&name=`
- `GET /health`

Auth: send `Authorization: Bearer <token>` from `/auth/dev-login`.

## What costs money (all OFF here, behind interfaces)

- Deploying to the cloud (hosting + managed Postgres) — free tiers exist.
- Managed auth provider past its free tier (`AUTH_PROVIDER=clerk|auth0`, not wired).
- Stripe payout fees — only on real sales (`app/integrations.py` PayoutProvider).
- Affiliate networks — free to join; they pay us (`AffiliateNetwork`).

## Deploy (production)

The API is containerized and reads everything from env. Nothing is hardcoded.

**Env (prod):**
- `REELIE_ENV=prod` — tightens CORS, requires a real `JWT_SECRET`.
- `DATABASE_URL` — a Postgres URL (`postgres://…` or `postgresql://…` is auto-normalized to psycopg3).
- `JWT_SECRET` — a strong secret.
- `ALLOWED_ORIGINS` — comma-separated web origins (e.g. `https://reelie.io`).
- `WEB_CONCURRENCY` — uvicorn workers (default 2).

**Local prod-like run** (Postgres + prod config), needs Docker:
```bash
docker compose up --build          # API on :8000, Postgres on :5432
```

**One-click host (Render):** push the repo, then New → Blueprint → `backend/render.yaml`.
It provisions the web service **and** a managed Postgres, generates `JWT_SECRET`, and
wires `DATABASE_URL`. Set `ALLOWED_ORIGINS` to your site. Any host (Fly/Railway/…)
works the same way — build `backend/Dockerfile`, set the env vars, attach Postgres.

**Migrations:** dev/first-deploy uses `create_all` on boot. Add Alembic before you
have real data to migrate.

## Static site + SEO files

The public creator pages, directory, and `robots.txt` / `sitemap.xml` / `llms.txt`
are **static** (generated into `Reelie App/page-generator/out/`). Host them on a CDN
(Cloudflare Pages / Netlify / S3+CloudFront) at `reelie.io`, with the SEO files at
the domain **root**. Point the generator's `BASE_URL` (in `page-generator/config.py`)
at the live domain, and set `REELIE_API_URL` when generating so pages sync to the API.

## Self-serve generation in production

`/me/generate` shells out to the video pipeline (`page-generator` + `video-llm`),
which needs `ffmpeg` and the extraction deps — **not** in the API image. In prod, run
generation as a **separate worker** (same repo, with ffmpeg) consuming a job queue;
the API just records jobs. Locally it runs inline in `--mock` mode. If the pipeline
isn't reachable, generation jobs fail cleanly (the API stays up).

## Managed auth (flip on with credentials)

The backend already verifies real provider tokens — it's a **config switch**, no
code change. Set:

```
AUTH_PROVIDER=oidc
OIDC_JWKS_URL=<provider JWKS>      # Clerk: https://<app>.clerk.accounts.dev/.well-known/jwks.json
OIDC_ISSUER=<provider issuer>     # Apple: https://appleid.apple.com
OIDC_AUDIENCE=<your client/app id>
```

The client authenticates with the provider, gets its JWT, and sends it as the
Bearer token; `OIDCAuthProvider` verifies it (RS256 via JWKS), then finds-or-creates
a `User` by the provider `sub` (`external_id`). `dev-login` is disabled in this mode.
Verified locally with a self-signed JWKS (verify + provisioning + tamper-reject).
Works for **Clerk / Auth0 / Sign in with Apple** — same adapter, different env.

**Still needs YOU:** a provider account (Clerk/Auth0) *or*, for Sign in with Apple,
an Apple Developer account to add the "Sign in with Apple" capability to the iOS
target and register your Services ID (that's the `OIDC_AUDIENCE`).
