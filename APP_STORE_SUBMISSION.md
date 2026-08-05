# Reelie — App Store Submission Pack

Copy-paste-ready listing text, App Privacy answers, and review notes.
Fields note Apple's character limits. Bundle ID: `com.reelie.app`.

---

## 1. Listing copy

**App Name** (30 chars max)
```
Reelie
```

**Subtitle** (30 chars max)
```
Your routines, shoppable
```
Alternates: `Turn videos into shop pages` · `Shoppable creator routines`

**Promotional Text** (170 chars — editable anytime without review)
```
Post like you always do. Reelie finds every product in your video and builds a shoppable page automatically — one tap to review, then publish.
```

**Description** (4000 chars max)
```
Reelie turns your videos into shoppable routine pages — automatically.

Post like you always do. Paste a link (YouTube, TikTok, Instagram) or upload a video, and Reelie watches it, finds every product you show or mention, and builds a clean, shoppable page for your routine. Review it, tweak anything, and publish — your followers get one page with every product, and you earn commission when they shop.

FOR CREATORS
• Auto-detect products — Reelie reads your video and pulls out the brands and products, step by step.
• Review before you publish — check each product, edit names or links, add anything we missed.
• Your own shoppable page — a clean routine page with clips, prices, and shop links.
• Earnings & insights — see views, clicks, and what's performing.
• Connect your accounts — pull videos straight from YouTube or Instagram.

FOR SHOPPERS
• Browse creators' real routines in a full-screen video feed.
• Tap any product to shop it.
• Save the routines and creators you love.

Reelie is free to start. Some product links may be affiliate links — if you buy through them, the creator may earn a commission at no extra cost to you.
```

**Keywords** (100 chars max, comma-separated, no spaces after commas)
```
shoppable,creator,routine,affiliate,makeup,skincare,beauty,link in bio,storefront,products,video,shop
```

**Support URL**: `https://reelie.io`  (ideally a `/support` or `/help` page)
**Marketing URL**: `https://reelie.io`
**Privacy Policy URL** (required): `https://reelie.io/privacy`

**Category**: Primary **Shopping** · Secondary **Lifestyle**

---

## 2. App Privacy ("nutrition label")

Answer the App Store Connect questionnaire to match what the app ACTUALLY does.
Based on the current code, the app collects the following. Confirm against your
backend before submitting — Apple holds you to this.

**Data collected & linked to the user (App Functionality):**
- **Contact Info → Email Address** — sign-in / account (Apple/Google/email).
- **Identifiers → User ID** — the creator account identity.
- **User Content → Photos or Videos** — videos creators upload/link for processing.
- **User Content → Other User Content** — page text/products the creator edits.

**Data collected, used for Analytics/App Functionality:**
- **Identifiers → Device ID** — a device-generated id for guest likes/saves/reports (not the IDFA).
- **Usage Data → Product Interaction** — shop-link clicks (for creator earnings attribution + insights).

**Not collected:** Location, Contacts, Health, Financial/Payment info (no in-app
purchases; payouts are handled by a third party later), Browsing history,
Search history tied to identity, Sensitive info.

**Tracking (the ATT question):** **No** — the app does not link user data with
third-party data for advertising and includes no ad/tracking SDKs or IDFA. So you
should NOT need the App Tracking Transparency prompt. (Double-check no analytics
SDK is added later.)

> If you add analytics (e.g. Sentry/Firebase) before launch, update this label.

---

## 3. App Review notes (paste into "Notes" for the reviewer)

```
Reelie has a guest experience (browse videos, search, save) that needs no login,
and a creator experience behind sign-in.

DEMO CREATOR ACCOUNT (please use to review the creator flow):
  Sign in: "Continue with email"
  Email: <REVIEW_EMAIL@reelie.io>
  Code / password: <PROVIDE — a working OTP or dev login for this account>

To review the core feature:
1. Open the app — you land in the browsable video feed as a guest (no login).
2. To test creation: Profile tab → "Become a creator" (or sign in with the demo
   account above) → Pages tab → "New" → paste this test video:
   https://www.youtube.com/shorts/gyDRYoz9yAw
3. Wait ~1–2 min while it builds (this runs on our servers; you can leave and it
   lands in Drafts).
4. Open the draft → review the detected products → "Publish page".

Notes:
- Product links open external retailer pages (some are affiliate links; disclosed
  on every page and in the Privacy Policy).
- Sign in with Apple and Google are both supported.
```

> You MUST supply a real working demo account + a way for the reviewer to log in.
> If email OTP requires a code you can't share, create a dedicated review account
> with a fixed password or keep dev-login enabled for that one account.

---

## 4. Pre-submission blockers (do these or it fails review)

- [ ] **Backend live at `reelie.io`** (or point the app at the Render URL) — reviewers
      open the app and hit the API. If it's not reachable, they see mock/guest data
      or errors → rejection.
- [ ] **Sign in with Apple actually works** — Supabase configured (`AUTH_PROVIDER=supabase`
      + Apple/Google OAuth + Apple Services ID). Reviewers WILL test login.
- [ ] **Working demo account** in the review notes above.
- [ ] **Screenshots** uploaded — at least 6.9"/6.7" iPhone (1290×2796 or 1284×2778).
      Suggested shots: the video feed, a routine/product page, the "analyzing"
      screen, the pages/studio list, the earnings screen.
- [ ] **Privacy Policy** reachable at `https://reelie.io/privacy`.
- [ ] **Age rating** questionnaire completed (likely 4+ / 12+; no objectionable content).
- [ ] **Earnings honesty** — payouts are still a mock provider; make sure nothing
      promises real, withdrawable money until real affiliate + Stripe are wired
      (or frame earnings as beta).

## 5. Then, to publish
1. In App Store Connect → your app → Distribution: attach the build, fill all
   metadata, set price to **Free**.
2. **Add for Review → Submit**.
3. On approval, choose **Manually release** (so you control the go-live moment) or
   **Automatically release**.
