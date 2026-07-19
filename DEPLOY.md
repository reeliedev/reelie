# Deploying Reelie to reelie.shop

This deploys **one service** that serves both the API *and* the public
AI-discoverable site (they share known route prefixes; the site owns `/`,
`/{handle}`, `/{handle}/{slug}` and the SEO files). Postgres is provisioned
alongside. ~15 min of clicking; ~$0–14/mo to start.

## What this deploy includes (Phase 1)
- ✅ Accounts (email sign-up), OAuth connect endpoints, all API routes
- ✅ Public crawlable pages + Schema.org + `llms.txt`/`robots.txt`/`sitemap.xml`
- ✅ Seed content (10 demo pages) so the site is non-empty on day one
- ⛔️ **Not** included: real video→page generation (needs the extraction worker —
  Phase 2) and real OAuth (needs Google/Meta keys — see `OAUTH_SETUP.md`).
  Generation jobs fail cleanly if triggered; everything else works.

## Prerequisites
- A **GitHub** account, a **Render** account (render.com), and access to the
  **DNS** for reelie.shop (wherever you registered it).

## 1 — Push the repo to GitHub
The repo is already committed locally on `main`. Create an empty GitHub repo, then:
```bash
cd "/Volumes/LaCie/Retrieva_Creator"
git remote add origin https://github.com/<you>/reelie.git
git push -u origin main
```

## 2 — Deploy the blueprint on Render
1. Render dashboard → **New → Blueprint**.
2. Connect the GitHub repo. Render auto-detects [`backend/render.yaml`](backend/render.yaml).
3. It provisions **`reelie-api`** (Docker web service) + **`reelie-db`** (Postgres).
   `JWT_SECRET` is auto-generated; `DATABASE_URL` is wired from the DB.
4. Click **Apply**. First build runs `alembic upgrade head` then starts gunicorn.
5. When live you get a URL like `https://reelie-api.onrender.com` — check
   `…/health` returns `{"ok": true}`.

## 3 — Set the remaining env vars
In the `reelie-api` service → **Environment**:
- `ALLOWED_ORIGINS = https://reelie.shop,https://www.reelie.shop`

(`PUBLIC_BASE_URL`, `REELIE_SELF_URL`, `OAUTH_REDIRECT_BASE` are already set to
`https://reelie.shop` in render.yaml. Google/Meta keys come later — `OAUTH_SETUP.md`.)

## 4 — Point reelie.shop at Render
1. `reelie-api` → **Settings → Custom Domains** → add `reelie.shop` and
   `www.reelie.shop`. Render shows a DNS target.
2. In your **DNS provider**:
   - `reelie.shop` → the `ALIAS`/`A` target Render gives (apex).
   - `www` → `CNAME` to the Render target.
3. Wait for DNS + Render's automatic **TLS** (Let's Encrypt) to go green.

## 5 — Verify it's live + AI-discoverable
```bash
curl https://reelie.shop/health
curl https://reelie.shop/robots.txt          # invites GPTBot/ClaudeBot/PerplexityBot…
curl https://reelie.shop/llms.txt            # products + prices inline
curl https://reelie.shop/glowbyjess/everyday-routine   # a rendered page
```
- Paste a page URL into Google's **Rich Results Test** / **Schema Markup Validator**
  to confirm the Article/HowTo/Product/FAQPage graph parses.
- The iOS release build already targets `https://reelie.shop`
  ([AppConfig](Reelie%20App/ReelieApp/ReelieApp/Models/APIClient.swift)).

## Notes / gotchas
- **Free tier sleeps.** Render's free web service spins down when idle — bad for a
  crawlable site (bots hit a cold start). Use the **Starter** ($7/mo) instance to
  keep it warm. Free Postgres expires after 90 days; upgrade before then.
- **Clips are ephemeral in Phase 1.** Per-step videos are served from the
  container's local `/media`, which is wiped on redeploy. Fine for the demo; for
  durable clips move them to object storage (Cloudflare R2 / S3) — that's bundled
  into the Phase-2 worker.
- **Seed data.** The 10 demo pages seed on first boot. To launch empty, clear the
  `page`/`product`/`creator` tables (or gate `seed_if_empty` behind an env flag).
