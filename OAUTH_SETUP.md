# Turning on real YouTube + Instagram connect

The backend already implements the full OAuth flow ([app/oauth.py](backend/app/oauth.py),
[app/routers/connections.py](backend/app/routers/connections.py)). With **no keys**
set it runs a **mock** provider (the connect button works, returns a fake account)
so the app is demoable. The moment you set a platform's real credentials as env
vars, that platform flips to **real consent** automatically — no code change.

> Do the deploy first (`DEPLOY.md`). Both providers require an **HTTPS redirect
> URL** and a **privacy-policy URL** on your live domain.

Set the resulting keys in Render → `reelie-api` → **Environment**.

---

## YouTube (Google) — achievable now

1. **Google Cloud Console** → create a project (e.g. "Reelie").
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **OAuth consent screen** → User type **External**.
   - App name, support email, your logo.
   - **Scopes:** add `.../auth/youtube.readonly` (a *sensitive* scope).
   - **Test users:** add the Google accounts you'll demo with (up to 100 work
     immediately, before Google verification).
   - Add your **Privacy Policy** + **Terms** URLs (e.g. `https://reelie.io/privacy`).
4. **Credentials → Create Credentials → OAuth client ID** → type **Web application**.
   - **Authorized redirect URI:**
     `https://reelie.io/connect/youtube/callback`
   - Copy the **Client ID** and **Client secret**.
5. In Render set:
   - `GOOGLE_CLIENT_ID = <client id>`
   - `GOOGLE_CLIENT_SECRET = <client secret>`
6. Redeploy. "Connect YouTube" now shows the real Google consent screen and lists
   the creator's uploads. **For public (non-test) users** you'll later submit the
   app for Google's OAuth verification (needed for the sensitive scope).

---

## Instagram (Meta) — works for testers now, App Review for public

Instagram Basic Display was shut down (Dec 2024); this uses the **Instagram API
with Instagram Login**. In development mode, only accounts with a **role on the
app** (tester/developer) that are **Professional** (Business/Creator) IG accounts
can connect — roughly the old ~25-tester ceiling. Full public use needs **Meta App
Review**.

1. **developers.facebook.com** → My Apps → **Create App** → use case
   **"Other" → Business** (or the flow that exposes Instagram).
2. Add the **Instagram** product → **API setup with Instagram login**.
3. **Business login settings:**
   - **Valid OAuth Redirect URIs:**
     `https://reelie.io/connect/instagram/callback`
   - Note the app's **Instagram app ID** and **Instagram app secret**.
4. **App roles → Roles** → add yourself / demo users as **Instagram testers**;
   each must accept the invite from their IG account (must be Professional).
5. Add a **Privacy Policy URL** in App Settings → Basic (Meta requires it even in
   dev mode).
6. In Render set:
   - `INSTAGRAM_APP_ID = <instagram app id>`
   - `INSTAGRAM_APP_SECRET = <instagram app secret>`
7. Redeploy. Testers can now connect Instagram for real. For the general public,
   submit for **App Review** (needs business verification + a screencast).

---

## Verify
- `https://reelie.io/me/connect/youtube` (with a creator bearer token) returns an
  `authorizeUrl` pointing at `accounts.google.com` (not the mock callback), and
  `"mock": false`.
- In the app: Profile → Become a creator → Connect → real consent → row flips to
  "Connected" with the fetched handle.

## Force mock (for local UI testing even with keys present)
Set `OAUTH_FORCE_MOCK=1`.
