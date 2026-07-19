# Reelie — Launch Checklist (real users on the website)

Account model for launch: **creators = real self-serve accounts; consumers = guests**
(guest favorites, no login). Auth only ever appears on the creator path.

Legend: 🔴 blocker · 🟡 soon-after · ✅ done · 🚧 in progress

---

## 1. Creator accounts (real, self-serve)
- [x] ✅ **1.1 Wire creator auth end-to-end (dev provider)** — guest-first entry (no
      login wall; consumers browse as guests); "Become a creator" → `/auth/dev-login`
      → token persisted (UserDefaults) → `/me/become-creator` → server role unlocks the
      studio; session restored on relaunch via `/me`; sign-out returns to guest.
      Verified: app hit dev-login + become-creator (200s), creator created in DB,
      relaunch restored via /me, fresh install = guest with 3 tabs.
- [~] 🔴 1.2 **Managed auth** — **code-complete**: backend `OIDCAuthProvider` verifies
      real RS256 tokens via JWKS + provisions users by `sub` (`external_id`) — a config
      switch (`AUTH_PROVIDER=oidc` + `OIDC_*`), works for Clerk/Auth0/**Sign in with
      Apple** (self-tested: verify + provision + tamper-reject). iOS token now in the
      **Keychain** (not UserDefaults). **Needs YOU:** a provider account (Clerk/Auth0)
      or Apple Developer acct for the Sign-in-with-Apple capability + client UI +
      Services ID; then set the env. `dev-login` auto-disables in `oidc` mode.
- [x] ✅ 1.3 **Self-serve generation service** — creator picks a video in the app →
      `POST /me/generate` runs the pipeline **server-side** (subprocess of `generate.py`,
      publishes via `/ingest`) → page saved to their account & browsable. Backend:
      `GenerationJob`, `/me/videos`, `/me/generate`, `/me/generate/{id}`. iOS:
      `PickVideoView` self-serve flow + "+ New" studio entry. Verified from the app:
      sign-up → generate → "My everyday routine · 18 products" published & shown in
      Discover. **Remaining for prod:** video **upload/URL → extraction** step needs
      ffmpeg + a worker/queue (today generates from already-extracted videos); run
      `GENERATE_LIVE=1` for real LLM titles/prices.
- [x] ✅ 1.4 **Account-scoped dashboard/publish** — studio reads the creator's real
      pages (`/me/pages`, incl. archived); Earnings API-backed; **edit/archive/delete
      are now server-side** (`PATCH /me/pages/{slug}`, `/archive`, `/unarchive`,
      `DELETE`). **iOS wired**: studio reads `/me/pages` (active + archived), editor
      PATCHes, manage menu archives/deletes (verified app calls `GET /me/pages`).
- [x] ✅ 1.5 **Account deletion** — `DELETE /me` purges the user + owned data
      (verified: 401/404 after). **iOS wired**: Profile → "Delete account" → confirm.
      *Data export still to add.*

## 2. Consumers (guests) — keep as-is
- [x] ✅ Guest favorites on web (localStorage) and iOS (FavoritesStore).
- [ ] 🟡 2.1 Guest→creator continuity (saved items survive becoming a creator).

## 3. Shop links & monetization
- [ ] 🔴 3.1 **`/r` redirect live** in production (currently local API only).
- [ ] 🔴 3.2 **One affiliate program approved** (Amazon Associates / Rakuten / Impact)
      + real tracked deep links replacing the search-URL stub.
- [ ] 🔴 3.3 Decide prices: keep LLM **estimates ("approx.")** or wire a real feed.
- [~] 🟡 3.4 **Payouts** — endpoints done behind the stub (`GET /me/payouts`,
      `/connect`, `/withdraw`; `Payout` model; ready→paid on withdraw). **iOS wired**:
      Earnings shows Cash-out + payout history (verified app calls `GET /me/payouts`).
      **Remaining**: swap `MockPayoutProvider` for real **Stripe Connect** (your account).

## 4. Infra / deployment
- [~] 🔴 4.1 Own **reelie.shop**; deploy static site + API over **HTTPS** behind a CDN.
      **Artifacts ready** (`backend/Dockerfile`, `render.yaml`, README deploy steps);
      **remaining**: buy domain + click-deploy (Render Blueprint) + point DNS/CDN.
- [x] ✅ 4.2 **Managed Postgres + migrations** — config supports it (`DATABASE_URL`,
      psycopg3, URL normalized); `render.yaml` provisions it; `docker-compose.yml` runs
      API+Postgres locally; **Alembic** baseline covers all 9 tables (`alembic upgrade
      head` runs at deploy via the Dockerfile; dev keeps `create_all`).
- [~] 🔴 4.3 Serve `robots.txt` / `sitemap.xml` / `llms.txt` at domain root — generated
      into `page-generator/out/`; **remaining**: host them at the CDN root (documented).
- [x] ✅ 4.4 **Dev scaffolding gated** — `REELIE_START` presets + `REELIE_DEMO_*` hooks
      now `#if DEBUG` (compiled out of Release; Release build verified). Prod API URL via
      `AppConfig.productionAPIBaseURL`. *Trivial leftovers: `[Reelie]` prints,
      `NSAllowsLocalNetworking` (benign, dev-http only).*
- [ ] 🟡 4.5 CDN/object storage for video clips & images.
- [ ] 🟡 4.6 Secrets server-side only (ANTHROPIC/DB/affiliate keys); no leaks.
- [ ] 🟡 4.7 Analytics, error monitoring (Sentry), uptime, rate limiting, LLM cost caps.

## 5. Legal / compliance
- [ ] 🔴 5.1 **Privacy Policy + Terms of Service** (real, linked in footer/app).
- [ ] 🔴 5.2 **FTC affiliate disclosure** clear & conspicuous on every page with links.
- [ ] 🔴 5.3 **Pick one brand** — site still says "Retrieva"; everything else "Reelie".
- [ ] 🟡 5.4 Cookie/consent + GDPR/CCPA basics (data rights, opt-out).
- [ ] 🟡 5.5 Email compliance (CAN-SPAM: unsubscribe + physical address).
- [ ] 🟡 5.6 Creator agreement (rights to video/likeness, commission & payout terms).

## 6. Content & polish
- [ ] 🟡 6.1 Real content beyond the 5-creator mock corpus; all cross-page links resolve.
- [ ] 🟡 6.2 Loading / empty / error / offline states (graceful when API is down).
- [ ] 🟡 6.3 Real fonts (Fraunces/DM Sans), app icon, launch screen.
- [ ] 🟡 6.4 Mobile-web perf/accessibility (lazy/poster-first clips).
- [ ] 🟡 6.5 Content moderation / reporting if creators self-publish.

---

### Working order
Backend + iOS feature-complete on mock/$0 infra. Remaining blockers need YOUR
accounts/decisions: **deploy (4.1/4.3) → legal + brand (5) → real affiliate (3.2) +
Stripe (3.4) + managed auth (1.2)**, then polish (6).
