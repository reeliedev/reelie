# Reelie — Security

_Last audit: 2026-07-24 (adversarial review of the FastAPI backend + SwiftUI app)._

This records the security review, what was fixed, and what remains. Severities
reflect real exploitability.

## Scope reviewed
- **Auth & access control** — JWT/JWKS verification, dev-login, admin/ingest
  tokens, IDOR across all `/me/*` and `/admin/*` routes, OAuth-callback state.
- **Injection** — SQL (SQLModel/SQLAlchemy) and XSS in the server-rendered HTML
  (public routine pages, studio, admin console) + emails.
- **SSRF / redirect / upload / config / DoS** — the server-fetched generate URL,
  the `/r` affiliate redirect, presigned uploads, secrets/CORS/headers, rate
  limiting, and the iOS client (token storage, ATS, deep links).

## Verified safe (no issue found)
- No SQL injection — every query is parameterized via the SQLModel expression API.
- JWT signature always verified; OIDC pins **asymmetric** algs (RS256/ES256) →
  no `alg:none` / RS256↔HS256 confusion; `exp`/`aud`/`iss` enforced.
- IDOR blocked on pages/jobs/favorites/connections/payouts (`_owned`, `user_id`/
  `handle` scoping). Handle is a primary key; can't be shared.
- OAuth-callback `state` is a `JWT_SECRET`-signed, TTL-bound token — unforgeable.
- iOS: auth token in the **Keychain**; `ASWebAuthenticationSession` callback
  carries no token (only `?ok=1`); only `NSAllowsLocalNetworking` (no arbitrary
  loads). No secrets committed to the repo.

## Fixed (2026-07-24)

### Critical
- **Stored XSS via JSON-LD** (`public_site.py`) — creator fields could break out
  of the `<script type="application/ld+json">` block. Now escape `<>&` → `<…`.
- **Stored XSS → admin takeover** (`me.py`, `admin_page.py`) — a crafted `handle`
  injected into the admin console and stole the `ADMIN_TOKEN`. Now: strict handle
  charset `^[a-z0-9][a-z0-9_-]{2,29}$`, social-handle sanitization, and the admin
  `esc()` escapes single quotes.

### High
- **Revenue leak** — `GET /creators/{handle}/earnings` was unauthenticated. Now
  requires auth and returns only the caller's own financials (iOS sends the token).
- **dev-login bypass** — hard-404 in prod; the app refuses to boot if prod runs
  the password-less `dev` auth provider.
- **OIDC account takeover** — auto-link by email only when `email_verified` AND
  the account has no bound identity; never overwrite a different `external_id`.
- **Cost-DoS** — per-creator generation quota (25/day, 3 in-flight) on
  `/me/generate` + a baseline per-IP rate limit (slowapi, 300/min).
- **SSRF** — the generate URL is validated (http/https only; private/loopback/
  link-local/reserved/metadata IPs rejected).

### Medium / hardening
- Constant-time token comparison (`hmac.compare_digest`) for admin + ingest.
- `JWT_SECRET`/`ADMIN_TOKEN`/`INGEST_TOKEN` stripped (Render trailing-newline).
- Email escaper uses `html.escape(quote=True)` (attribute-safe).
- Security headers: `nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`,
  HSTS (prod).
- Presigned upload restricted to `video/mp4|quicktime`.
- Affiliate URLs validated to http(s) on write (open-redirect scheme guard).

## Remaining (tracked)
- 🟡 **`/r/postback`** can fabricate commissions with the shared ingest secret —
  replace with the affiliate network's signed-postback verification before real
  money moves; interim: a separate secret + `hmac.compare_digest`.
- 🟡 **Rate limiting is in-memory per worker** — add a Redis `storage_uri` for
  cross-worker accuracy at scale.
- 🟡 **SSRF residual** — DNS-rebinding TOCTOU (resolve-then-fetch). Pin the
  resolved IP through to yt-dlp for full protection.
- 🟢 **CSP** — not set (server pages use inline styles → needs nonces).
- 🟢 OAuth access/refresh tokens stored plaintext at rest — encrypt (KMS/Fernet).
- 🟢 Pipeline `job.error` leaks internal stderr tails to clients — return generic.
- 🟢 `/health` discloses auth mode + admin email — trim for anonymous callers.
- 🟢 `avatar_gradient` is interpolated into CSS unescaped (not self-serve
  reachable today) — validate `^#[0-9a-fA-F]{3,8}$` before it becomes editable.
- 🟢 Guest like/view/click writes are unauthenticated (metrics integrity, not
  compromise) — covered partly by the per-IP limit; make idempotent if likes
  ever influence ranking/payouts.
