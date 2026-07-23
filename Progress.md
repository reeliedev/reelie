# Reelie — Progress

_Last updated: 2026-07-23_

**Reelie** turns a beauty/skincare creator's video into one **shoppable "routine
page"** and publishes it for both the iOS app and an AI-discoverable public web
page. Four sub-projects on this drive form a single pipeline:

```
video-llm  ──▶  page-generator  ──▶  ReelieApp (iOS)  +  Landing Page (web)
(extract       (assemble the         (preview/publish)   (marketing +
 products)      canonical Page)                            synced Schema.org)
```

## Sub-projects & status

| dir | what it is | status |
|---|---|---|
| `video-llm/` | Product-extraction prototype. `claude-sonnet-4-6` over transcript + keyframes (incl. "held-product" freeze-frame detection); scored vs. hand labels. Product-level F1 ≈ 0.73. | **Working.** See `report.md`, `calibration.md`. Env was broken — see below. |
| `Reelie App/page-generator/` | Video-llm extraction → one canonical `Page` JSON → (a) app JSON, (b) AI-discoverable public web page, (c) idempotent Schema.org sync into the Landing Page. **Most recent work.** | **Complete & runs green.** |
| `Reelie App/ReelieApp/` | SwiftUI iOS prototype (converted from `reelie-screens` HTML mockups), in-memory sample data, no backend. | Generated, **not compiled here** (needs Xcode 16+). |
| `Reelie App/reelie-screens/` | Original static HTML mockups (screens 01–14). | Reference only. |
| `Landing Page/` | Marketing page; receives the synced Schema.org block. | Schema block injected at `index.html` lines 26–77. |

## Creators can now link their OWN video (2026-07-19)

The "real thing": a creator pastes a video link (or picks a past video) and the
server extracts products and builds the page — no longer limited to pre-extracted
demo videos.

- `video-llm/extract_one.py` — single URL/file → download (yt-dlp) → full pipeline
  → `output/<id>.json`. Bundles ffmpeg via **static-ffmpeg** (no Homebrew) and adds
  **Deno** (`~/.deno/bin`) to PATH for yt-dlp's YouTube JS runtime.
- Backend `POST /me/generate` accepts `{url}` → runs `extract_one` (stage
  "Fetching your video" → "Found your products"), then builds + publishes the page.
  Verified via API: `Fetching your video → Published` under a creator account.
- iOS `PickVideoView` now leads with a **"Paste a video link"** field → the same
  generate flow with live stages. Build: **BUILD SUCCEEDED**.
- Extraction cost ≈ **$0.045/video** (live LLM); still `--mock` ($0) by default,
  set `GENERATE_LIVE=1` for real pricing/products.
- Caveat: this runs on **localhost only**. Public use needs the backend + extraction
  worker deployed (extraction is CPU/ffmpeg-heavy — a worker/queue, not the web dyno).

## Where we left off

- The **page-generator + main-site Schema.org sync** was the last feature built and
  is finished. Offline smoke test passes:
  ```bash
  cd "Reelie App/page-generator"
  python3 generate.py --from-output YmA9l0eHFrk --handle glowbyjess --name "Jess Tan" --mock
  ```
  → emits canonical page, app JSON, public HTML, `robots/llms/sitemap/schema`,
  and `main site: updated` (writes between the `<!-- reelie:schema:start/end -->`
  markers in `Landing Page/index.html`).
- No feature was mid-flight; this file was created to record state.

## Verification (2026-07-18)

- **Localhost demo (`video-llm/webapp`)** — ✅ working. Installed `fastapi`/
  `uvicorn`/`python-multipart` into the rebuilt venv; server runs at
  `http://localhost:8000`. Exercised the full cached-demo flow (POST a pre-cached
  YouTube id → SSE progress → `done`): products come back with confidence buckets
  (confirmed/review/hidden) and Spoken/Shown/Both evidence badges; YouTube
  thumbnail resolves. Start it with `./webapp/run.sh` from `video-llm/`.
- **iOS↔pipeline contract** — ✅ verified by cross-checking
  `render/app_json.py` output against `GeneratedPageDTO`
  (`Models/GeneratedPage.swift`): every required key present, `evidence`/
  `linkKind` map correctly, extra JSON keys ignored by `Decodable`.
- **iOS build & run** — ✅ **verified on 2026-07-18** after Xcode was updated to
  **26.5**. `xcodebuild -scheme ReelieApp -destination 'iOS Simulator,iPhone 17 Pro'`
  → `** BUILD SUCCEEDED **`. Installed + launched on the iPhone 17 Pro simulator
  with ad-hoc signing ("Sign to Run Locally", no team); the Login screen renders
  correctly (Fraunces wordmark, tagline, Apple/Google/email buttons). No crash,
  no runtime errors in `log stream`. **If "Run" seems blocked in the Xcode GUI**,
  the cause is the run destination, not the code: pick an **iOS Simulator** (e.g.
  iPhone 17 Pro) from the destination dropdown — a physical device / "Any iOS
  Device" needs a signing Team set under Signing & Capabilities.
- **"No Run button" fix (2026-07-18)** — root cause: the project's shared scheme
  file was missing. `xcschememanagement.plist` referenced
  `ReelieApp.xcscheme_^#shared#^_`, but `ReelieApp.xcodeproj/xcshareddata/xcschemes/`
  didn't exist, so Xcode had no loadable scheme → no Run button. Created
  `xcshareddata/xcschemes/ReelieApp.xcscheme` (targets native target
  `A100000000000000000000T1`, `com.reelie.app`). `xcodebuild -list` now shows the
  scheme and it resolves the target. **Close and reopen the project in Xcode** to
  pick up the scheme.

## Public page redesign (2026-07-18)

The public web page was a fixed 640px column that read as a widened phone screen.
Rebuilt it as a wide, responsive **editorial shop + guide** (`render/web.py` +
`render/templates/public_page.html`):
- **Hero**: creator chip, big Fraunces title, lede, and a "Shop the whole
  routine" summary card — total price, product count, price range, retailer chips,
  primary CTA.
- **The guide**: numbered, step-by-step routine — each row shows brand / name /
  variant, a "Shown & mentioned / Mentioned" evidence tag, the video timestamp,
  the creator's note, price, and a "Shop at <retailer>" button.
- **Closing band**: dark "Get the whole routine — $total" bundle CTA.
- Two-column desktop hero + 4-col step rows collapse to single-column stacked
  cards ≤640px. Verified headless in Chrome at 1280px and 500px — no overflow.
- `web.py` now computes routine totals/range/retailer list, and suppresses a note
  identical to the row above it (same transcript beat). Tokens still filled by the
  same `{{TOKEN}}` replace; JSON-LD unchanged.
- Regenerate: `python3 generate.py --from-output YmA9l0eHFrk --handle glowbyjess
  --name "Jess Tan" --mock`.

## Video-narrated guide (2026-07-18)

The public page is now a real **how-to guide**, not just a product list. In live
mode the page-assembly LLM call writes:
- a first-person **intro** (2–3 sentences) that frames the whole routine, and
- **per-step narration** (1–3 sentences) describing what each product is for, how
  she applies it, and the technique — grounded in the transcript **and the actual
  video keyframes** (up to 8, sampled across the video, sent as images).

Grounding is enforced in `PAGE_SYSTEM_PROMPT`: narrate only what's said or shown,
never invent benefits/ingredients/results. Verified output references on-screen
detail ("in a triangle shape", "in the glass dish with a brush", "the dropper
applicator", "running down in the video").

Touched: `prompts.py` (schema adds `intro` + per-step `guide`; `build_page_messages`
takes frames), `page_builder.py` (`_load_frames` reads cached
`cache/<id>/frames_*`, live call bumped to 4096 max_tokens, mock synthesises a
fallback guide from the transcript quote), `models.py` (`Page.intro`,
`ProductItem.guide`), `render/web.py` + template (intro paragraph in the guide
header; per-step narration as prose, falling back to the short quote), and
`render/app_json.py` (adds `intro` + `guide`, ignored by the Swift DTO for now).

Live run needs the key: `export $(grep -v '^#' ../../video-llm/.env | xargs)` then
`../../video-llm/.venv/bin/python3 generate.py --from-output <id> --handle <h>
--name "<Name>"`. Latest live page:
`out/public/glowbyjess/makeup-hacks-colour-correct-glow/index.html`.

## Per-step video clips (2026-07-18)

Each guide step now shows a short clip of that exact moment from the source video,
matched to the narration. Rendered with **PyAV** (bundled ffmpeg libraries — no
system ffmpeg binary needed, which matters since Homebrew's ffmpeg is gone).
- `clips.py`: resolves the source (`video-llm/videos/[_processed/]<id>.mp4`), plans
  one `[start,end]` window per product from its `timestamp_s` (next-timestamp or
  `CLIP_MAX_S`, min `CLIP_MIN_S`, small lead-in), dedups identical windows to one
  file, cuts+re-encodes to a ~360px H.264 mp4 + JPEG poster. Reads
  `cache/<id>/mirror.json` and **un-flips** clips the pipeline flagged as mirrored
  so on-product text reads correctly.
- Output lands in `out/public/<handle>/<slug>/clips/NN.mp4|jpg`; sizes are tiny
  (~780 KB for 8 steps / 4 unique windows on the sample). `models.py` gains
  `ProductItem.clip` / `clip_poster`; `render/web.py` emits a
  `<video muted loop playsinline>` (falls back to the emoji tile when no clip); a
  small IntersectionObserver in the template plays each clip only while on screen.
- Wired in `generate.py` between page-build and render; opt out with `--no-clips`.
  Tunables (`CLIP_WIDTH/MIN_S/MAX_S/LEAD_S`) live in `config.py`.
- Needs the source video present (same availability as the cached frames). If it's
  missing, clips are skipped and the page uses emoji tiles — nothing else changes.
- Latest page with clips: `out/public/glowbyjess/unexpected-makeup-dupes-routine/`.

### Step layout: alternating editorial (2026-07-18)
Steps are no longer compact rows. Each step is a full-width block with a **large
portrait clip (288px, 9:16)** and, on the other side, the content — "Step N"
eyebrow, brand, name, tags, narration, and price + Shop button stacked beneath the
text. The clip side **alternates** (odd = left, even = right) via a `media-left`/
`media-right` class in `render/web.py`; on ≤760px it stacks (clip centered on top,
content below). Clip encode width bumped to `CLIP_WIDTH=480` for crispness at the
larger display size. To re-render layout tweaks WITHOUT re-calling the LLM: load
the canonical page (`Page.load`), re-run `clips.make_step_clips`, then
`web.write_public_page` — see the one-off used this session.

### Clip audio + tap-to-unmute (2026-07-18)
Clips now keep the source **audio track** (AAC), but the `<video>` stays `muted`
so muted-autoplay-on-scroll still works. `clips.py` `_write_clip` transcodes the
window's audio alongside the video (AudioResampler → aac, clip-relative pts). Each
clip has a round unmute button (`render/web.py` wraps the video in `.s-clipwrap`
with a `.s-sound` toggle); the template JS unmutes on tap, **mutes all other clips**
(one audible at a time), turns the button yellow (`.is-on`), and **re-mutes when the
clip scrolls out of view**. Default state verified: `muted=true`, no `is-on`.
Clips are still tiny (~230–330 KB with audio). If the source has no audio stream,
clips are silent as before.

### Group products by clip (2026-07-18)
Products that share a clip are now rendered as ONE "moment" block instead of
repeating the same footage per product. `render/web.py` `_group_by_clip()` groups
by `p.clip` (products with no clip stay solo, preserving the no-source fallback),
in routine order; each moment shows the clip once + a `Step N · <timestamp>` label,
and lists each product (brand, name, evidence tag, narration, price + Shop) with a
divider between them (`.s-product + .s-product`). On the sample this collapses 8
repeated-clip steps into 4 moments of 2 products each.

## Two-sided expansion — consumer + creator (2026-07-18)

Built per the approved plan (`~/.claude/plans/okay-lets-go-into-moonlit-meteor.md`):
one unified account (viewer by default, "become a creator" unlocks the studio),
on mock/local data, across iOS + web. Real backend/auth/payments still deferred.

**iOS (SwiftUI) — builds green in the simulator.**
- Identity: `User`/`Role`(viewer/creator/both) + `Creator` in `Models.swift`;
  `AppState.currentUser`, `favorites`/`favoriteCreators`, seeded multi-creator
  corpus in `Models/Catalog.swift` (5 creators, deliberately overlapping brands).
- Tabs are role-aware: `MainTab` gains `.discover/.saved`; `ReelieTabBar(showsCreator:)`
  shows Pages/Earnings only for creators. Onboarding forks at `PickRoleView`
  (browse vs create); `BecomeCreatorView` unlocks later from Profile.
- Consumer screens (`Consumer/`): `DiscoverView`, `CreatorProfileView`,
  `RoutineView` (save + per-product "also used by"), `SavedView`, `RecoRail`,
  shared `ConsumerComponents`. Favorites persist via `FavoritesStore` (UserDefaults).
- Recommendations: `AppState.similarCreators(to:)` (Jaccard on brand sets) +
  `creatorsUsing(brand:name:)` (normalized product key).
- Creator studio: `EarningsView` gains a period toggle (week/month/lifetime) +
  "earnings by page" over dated `Sale`s; `PageDetailView` gets archive/delete;
  new `PageEditorView` edits title/intro/disclosure/slug/per-product name·note·
  narration, persisted by `OverridesStore` and re-applied in `GeneratedPageStore`.
  `GeneratedPage`/DTO gained `intro` + per-product `guide`.
- Debug-only launch presets in `ReelieApp.swift` (env `REELIE_START`) for
  screenshotting — no effect unless the env var is set.

**Web (page-generator).**
- `render/site_files.py` `register_page()` now indexes products/brands/retailers
  (+ `normalize_product`) so `out/pages.json` is a cross-page reco index.
- `render/recommend.py`: `similar_creators`, `creators_using`, `write_reco_json`.
- `render/creator_page.py` → `out/public/<handle>/index.html` (fills the
  previously-dead `<handle>` route) with a "similar creators" module.
- `render/directory.py` → `out/public/index.html`: browsable catalogue with
  client-side search.
- Public routine page: `♡ Save` (localStorage guest favorites), per-product
  "Also used by" avatars, and a "similar creators" footer (`render/web.py` +
  template). Landing gains a "Browse creators" nav link.
- `generate.py` registers before rendering and re-renders ALL pages from the
  final registry each run (so a new creator refreshes earlier pages' reco).
- Verified: seeded 5 creators (`--mock --no-clips`); `out/reco.json` has real
  signal (glowbyjess↔kbeautykay/thefacefiles via Huda Beauty; nars|foundation →
  everydayamira, kbeautykay); directory + all 5 creator index pages render.

## Backend — foundation slice (2026-07-18)

New `backend/` FastAPI service = the real source of truth behind app + web.
Decisions (confirmed with user): **Python/FastAPI + Postgres** (SQLite for local
dev), **managed-auth-ready with a dev stub**, **Foundation + accounts + catalog
first**, **external integrations stubbed**. Runs **$0 locally** (SQLite file + dev
JWT auth + stubbed Stripe/affiliate — nothing external is called).

- Stack: FastAPI + SQLModel; `app/config.py` (SQLite default via `DATABASE_URL`,
  swappable to Postgres), `app/db.py`, `app/models.py`
  (User/Creator/Page/Product/Favorite/Sale).
- Auth: `app/auth.py` — `AuthProvider` protocol + `DevAuthProvider` (issues our
  own JWTs, no external dep); Clerk/Auth0 are stubbed swap-ins. Bearer-token
  `current_user` dependency.
- Routes: `/auth/dev-login`, `/me` + `/me/become-creator`, `/me/favorites`
  (GET/POST/DELETE), `/creators[/{handle}[/routines]]`, `/routines[/{h}/{slug}]`
  (GeneratedPageDTO-shaped so iOS decodes unchanged), `/recommendations/similar/{h}`
  + `/recommendations/using`, `/ingest/page`, `/health`.
- `app/recommend.py` (DB-backed similar/using), `app/integrations.py`
  (`AffiliateNetwork`/`PayoutProvider` mock stubs — the paid seams, all OFF),
  `app/seed.py` (seeds the same 5-creator mock corpus on first boot).
- Verified with curl: creators/routines/reco/login/favorites/become-creator all work.
- Run: `cd backend && python3 -m venv .venv && .venv/bin/pip install -r
  requirements.txt && ./run.sh` (uses port 8000; I demoed on 8010).

**Wire-in (thin, flagged, mock fallback kept):**
- iOS `Models/APIClient.swift` + `AppState.refreshFromAPI()` (called from
  `RootView.task`): when env `REELIE_API_URL` is set, Discover/creators/routines
  load from the API; otherwise the seeded `Catalog.swift` mock is used. Added a
  minimal `Info.plist` (at `Reelie App/ReelieApp/Info.plist`, `INFOPLIST_FILE`
  build setting) with `NSAllowsLocalNetworking` so the simulator can reach the
  local http API.
- Web generator `render/api_sync.py`: when `REELIE_API_URL` is set, `generate.py`
  POSTs each page to `/ingest/page` (stdlib urllib, never fatal). Verified: a new
  creator generated with the env set appears in `/creators`.

**Cost note:** everything above is $0. First recurring cost only on cloud deploy
(hosting + managed Postgres — free tiers exist); managed auth past its free tier;
Stripe fees only on real sales. All paid pieces sit behind interfaces (off).

## Backend Phase 3 — monetization core (2026-07-18)

Makes earnings real: the affiliate redirect + click/conversion tracking + earnings
aggregation feeding the dashboard. Affiliate network + payouts remain stubbed, so
conversions are simulated via a mock postback (natural consequence of "stub
integrations").

- `models.py`: new `Click` table (raw redirect taps); `Sale` extended
  (order_amount, retailer, network, click_id, state pending→ready→**paid**).
- `routers/redirect.py`: **`GET /r/{handle}/{slug}/{nn}`** logs a Click and 302s
  to the destination from `AffiliateNetwork` (stub → retailer search URL);
  **`POST /r/postback`** records a conversion (commission = order × rate);
  **`POST /r/simulate`** dev-fabricates clicks + conversions for the demo.
- `integrations.py`: `MockAffiliateNetwork.resolve_link` now returns believable
  retailer search URLs (Sephora/Ulta/Amazon/…); real network is still the swap point.
- `routers/earnings.py`: **`GET /creators/{handle}/earnings`** → lifetime / week /
  month, pending / ready / paid, clicks, conversions, per-page rollup, recent sales.
- `seed.py`: seeds a click baseline + a paid sale so the dashboard has movement.
- Verified via curl: `/r/...` 302s to `sephora.com/search?...` and logs a click;
  simulate/postback create conversions; `/creators/glowbyjess/earnings` reflects
  them (lifetime $37.83, 111 clicks, 14 conversions, per-page split).
- iOS: `EarningsSummary` + `APIClient.earnings(handle:)`; `AppState.loadEarnings()`
  (creator + backend only); `EarningsView` prefers the live summary (mock fallback
  kept) and shows a "N shop clicks · M sales" line.
- **Still $0** — affiliate + payouts stubbed; conversions are simulated locally.
  Next: real affiliate-network postbacks + Stripe Connect (Phase 4), both behind
  the existing interfaces.

## Launch prep — checklist + creator auth + self-serve generation (2026-07-19)

Account model for launch (user decision): **creators = real self-serve accounts;
consumers = guests**. Auth only appears on the creator path. Durable checklist:
`LAUNCH_CHECKLIST.md`.

**Item 1.1 — creator auth end-to-end (done).** iOS `APIClient` gained auth
(dev-login/me/become-creator); `AppState` stores a persisted token (UserDefaults),
`signIn`/`becomeCreatorAPI`/`restoreSession`/`signOut`. **Guest-first entry**:
`RootView` opens straight into the app (no login wall); consumers browse as guests;
"Become a creator" (`BecomeCreatorView`, rebuilt) runs email sign-in → claim handle
against the API and the **server returns the role**. Verified in the simulator:
app hit `/auth/dev-login` + `/me/become-creator` (200s), creator written to DB,
relaunch restored via `/me`, fresh install = guest with 3 tabs.

**Item 1.3 — self-serve generation (done).** Backend orchestrates the existing
`generate.py` pipeline as a subprocess that POSTs the finished page to `/ingest`,
so it publishes into the creator's account. `models.py` `GenerationJob`;
`routers/generate.py`: `GET /me/videos` (available extractions), `POST /me/generate`
(auth, creator-only, background runner), `GET /me/generate/{id}` (poll). `config.py`
adds generator paths, `PYTHON_BIN` (video-llm venv), `SELF_URL`, `GENERATE_LIVE`
(defaults to $0 `--mock`). Verified via curl: creator picked a cached video →
job running→done → **page published under their handle** in `/creators/{h}/routines`.
iOS: `PickVideoView` rebuilt as the self-serve flow (loads `/me/videos` → tap →
`/me/generate` + poll with progress → success → catalog refresh); "+ New" entry in
the studio header; `AppState.availableVideos()`/`generatePage()`.

Dev-only verification hooks in `ReelieApp.swift`: `REELIE_DEMO_SIGNIN` /
`REELIE_DEMO_GENERATE` (and the `REELIE_START` presets). Remove before store
submission (tracked in the checklist).

## Deployment prep (item 4) — 2026-07-19

Made the backend production-shaped (no cloud account here, so artifacts + config,
verified on SQLite; Postgres needs the deploy env). Docker/psql not installed
locally.
- `app/config.py`: `REELIE_ENV` (dev|prod); prod **requires `JWT_SECRET`** (raises
  otherwise), **CORS restricted** to `ALLOWED_ORIGINS`; `DATABASE_URL` normalized so
  managed `postgres://`/`postgresql://` → `postgresql+psycopg://` (psycopg3).
  Verified: prod boot fails without secret, loads with it, both URL forms normalize.
- `requirements.txt`: added `psycopg[binary]` + `gunicorn`.
- `Dockerfile` (gunicorn+uvicorn workers, `$PORT`), `.dockerignore`,
  `docker-compose.yml` (API + Postgres, prod-like), `render.yaml` (one-click:
  web service + managed Postgres + generated secret). README deploy section +
  static-hosting + self-serve-worker notes.
- iOS de-scaffold: `AppConfig.productionAPIBaseURL` (empty until deployed) — release
  builds use it; `REELIE_API_URL` env still overrides in any build. The
  `REELIE_START` presets and `REELIE_DEMO_*` hooks are now `#if DEBUG` (compiled out
  of Release). Remaining trivia: `[Reelie]` prints, `NSAllowsLocalNetworking`
  (benign, dev-http only) — noted in the checklist.

Deploy path: push repo → Render Blueprint (`backend/render.yaml`) → set
`ALLOWED_ORIGINS` → set iOS `AppConfig.productionAPIBaseURL` to the API URL. Static
site (page-generator `out/`) → a CDN at reelie.io with SEO files at root.

## Backend completion (2026-07-19) — domain bought (reelie.io)

Finished the remaining API surface so the backend is launch-complete (external
integrations still behind stubs). All verified via curl.
- **Page management** (`routers/pages.py`, owner-only): `GET /me/pages` (own pages
  incl. archived), `PATCH /me/pages/{slug}` (title/intro/disclosure/per-product
  name·note·guide), `POST …/archive` + `/unarchive`, `DELETE …`. `Page.archived`
  added; public catalog (`/routines`, `/creators/{h}/routines`) excludes archived.
- **Payouts** (`routers/payouts.py`, Phase 4 behind the stub): `Payout` model;
  `GET /me/payouts` (connected/ready/pending/paid/history), `POST /connect`
  (onboarding URL), `POST /withdraw` (ready→paid + Payout record). `PayoutProvider`
  stub = `MockPayoutProvider`; Stripe Connect swaps in.
- **Account deletion**: `DELETE /me` purges user + owned creator/pages/products/
  sales/clicks/jobs/payouts/favorites (verified 401/404 after).
- **Alembic migrations**: `backend/migrations/` wired to SQLModel metadata + config
  URL; baseline revision covers all 9 tables (`import sqlmodel` added to the mako
  template + baseline); prod boot uses `alembic upgrade head` (Dockerfile), dev
  keeps `create_all`. `db.init_db` skips create_all in prod.
- Config: prod CORS defaults to the reelie.io domains.

**Backend now launch-complete except items needing YOUR external accounts:** real
affiliate deep links (3.2, Amazon/Rakuten/Impact), real Stripe Connect transfers
(3.4), managed auth provider (1.2, Clerk/Auth0), and the URL→extraction generation
worker (needs ffmpeg). iOS still needs to call the new page-edit/delete/payout/
account-delete endpoints (backend ready).

## iOS wired to the new backend endpoints (2026-07-19)

- Studio now loads the creator's pages from **`GET /me/pages`** (incl. archived +
  flag); `HomeView` shows separate YOUR PAGES / ARCHIVED sections.
- `GeneratedPageView` gained a manage menu: **Archive/Unarchive** (`POST …/archive`)
  and **Delete** (`DELETE /me/pages/{slug}`) with a confirm dialog.
- `PageEditorView` Save now **PATCHes** `/me/pages/{slug}` (title/intro/disclosure/
  per-product name·note·guide) instead of the local override; `Product.serverId`
  carries the backend id (decoded from the DTO).
- `EarningsView` loads **`GET /me/payouts`**: a "Cash out $X" button
  (`POST /me/payouts/withdraw`) when ready>0, plus a PAYOUTS history list.
- `ProfileView` has **Delete account** (creators) → confirm → `DELETE /me` → guest.
- APIClient: added `myPages`, `editPage` (PATCH), `setArchived`, `deletePage`,
  `payouts`, `connectPayouts`, `withdraw`, `deleteAccount` + a generic `send`
  helper; `PayoutsSummary`/`Ack` DTOs; `GeneratedPage.archived`.

## Branded emails, admin delete, Retrieva cleanup, favicon (2026-07-23)

Polish pass across the creator lifecycle + marketing site. All backend changes
shipped to `main` (Render auto-deploys); Supabase-side items done in the dashboard.

**Auth emails (Supabase templates + custom SMTP) — DONE in the Supabase dashboard.**
The sign-in/magic-link email is sent by **Supabase Auth**, not this repo (Studio
just calls `signInWithOtp`, `app/studio.py`), so its HTML lives in Supabase →
Authentication → Emails. Both templates now use the Reelie branded card (yellow
ground, white rounded card, wordmark, purple pill CTA):
- **Confirm signup** — "Welcome, verify your email + provide your socials" (this is
  the template a brand-new email hits, NOT Magic Link — the classic Supabase gotcha).
- **Magic Link** — "Your Reelie sign-in link" (returning users).
- **Custom SMTP → Resend** enabled (smtp.resend.com:465, user `resend`, API key),
  sending from the verified reelie.io domain for deliverability + branded sender.

**Creator lifecycle emails (`backend/app/notify.py`) — code, deployed.** Added a
shared `_brand_email()` helper (table-based + inline CSS card, matching the Supabase
templates) and routed the two creator-facing emails through it:
- `creator_confirmation` — rewritten to the socials-submitted message: "you're on
  your way — check your Instagram DMs / DM Requests to confirm your identity."
- `creator_approved` — **new** "Congratulations — you're approved! Start posting,
  start earning" with a Start-creating CTA. Sent as a BackgroundTask from the admin
  approve endpoint (`routers/admin.py`), idempotent (only on a real transition into
  approved, never re-sent on re-approve). Verified end-to-end in-process.

**Admin per-creator delete (`routers/admin.py` + `admin_page.py`) — deployed.**
New `POST /admin/applications/{handle}/delete` removes one creator + all their data
(products/clicks/views/sales/payouts/likes/jobs/pages/connections/favorites/creator/
user) FK-safe, children first; a red **Delete** button (confirm dialog) sits next to
Approve/Reject on each `/admin` card. Verified scoped (deletes only that creator).
NB: like `/admin/wipe`, this clears Reelie's DB only — the Supabase Auth user must
still be deleted by hand (Supabase → Authentication → Users) to free the email.

**Removed all "Retrieva" from the live site (`backend/app/landing/`) — deployed.**
The served marketing page rebranded "Retrieva"→Reelie at serve time
(`landing_page.py`) but only swapped `retrieva.com`, so the app-demo "Published"
screen still showed `retrieva.me/maya/night-routine`. Fixed at the source
(index.html/styles.css/main.js → Reelie / reelie.io; demo URL now
`reelie.io/maya/night-routine`) and hardened the defensive replace to also cover
`retrieva.me`. NB: the **non-served** root `Landing Page/` copy still contains
"Retrieva" (harmless — production serves `backend/app/landing/`).

**Reelie logo as favicon (browser-tab icon) — deployed.** Logo bundled at
`backend/app/landing/favicon.png`, served from `/favicon.ico`, `/favicon.png`,
`/apple-touch-icon.png` (one handler, three paths in `routers/site.py`). Browsers
auto-request `/favicon.ico` on every page, so the whole site is covered; explicit
`<link rel="icon">` tags added to landing, studio, admin, and public creator/discover
heads. Source logo `LogoReelie.png` left at repo root (untracked; the served copy is
the one that ships).

Commits: `adf63f9` (emails + delete) → `3f9c8ae` (branded card) → `6d34fbe`
(Retrieva cleanup) → `9d56f04` (favicon).

## Environment note (fixed 2026-07-18)

- `video-llm/.venv` had died: its `python3 → python3.14` symlink pointed at
  `/opt/homebrew/opt/python@3.14/…`, and **Homebrew is no longer installed** on
  this machine. The only interpreter present is the system framework
  **Python 3.11.4** (`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`).
- Action taken: rebuilt `video-llm/.venv` on Python 3.11 and reinstalled
  `requirements.txt`. `--mock` never needed deps; live/extraction modes do.
- **Still external:** `ffmpeg`/`ffprobe` (needed for full `--video` extraction)
  came from Homebrew and are gone — reinstall ffmpeg before running raw-video
  extraction. Existing cached outputs in `video-llm/output/` are unaffected.

## Live runs need

- `ANTHROPIC_API_KEY` — present in `video-llm/.env`.
- For page-generator live pricing/titles: run without `--mock`.
- For full raw-video extraction: ffmpeg + the video-llm venv.

## Possible next steps

- Live (non-mock) page-generator run to get real titles + LLM price estimates.
- Replace `StubPriceResolver` / `LLMPriceResolver` with a live retailer/affiliate
  feed (`price.py` — the documented swap point).
- Build/verify `ReelieApp` in Xcode; wire generated-page JSON into the app.
- Reinstall ffmpeg to re-enable raw-video extraction.
