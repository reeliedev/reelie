# Reelie — iOS app

SwiftUI conversion of the `reelie-screens` HTML mockups. A functioning,
navigable prototype driven by in-memory sample data (no backend yet).

## Open & run

Requires **Xcode 16+** (the project uses file-system-synchronized groups).

```
open ReelieApp/ReelieApp.xcodeproj
```

Pick an iOS 17+ simulator (e.g. iPhone 15) and press ⌘R.

> This machine only had the Command Line Tools installed, so the project was
> generated but not compiled here. Open it in Xcode to build.

## Flow (mirrors the mockups)

Onboarding: **Login → Connect socials → Claim page → Notifications** → main app.

Main app is three tabs (custom bottom bar):

- **Pages** (`HomeView`) — empty state (05) when there are no pages, otherwise the
  sectioned list (10: Needs your OK / Working on it / Live).
  - *Review* → **Approve page** (07) with expandable link editors + "needs a look"
    thumbs, "+ Add a product" opens the **Add a product** sheet (08).
  - *Approve page* → **Page is live** (09); *Done* pops back to the list.
  - Tapping a live page → **Page detail** (11).
  - *Make a page from a past video* → **Pick a video** (06).
- **Earnings** (12)
- **Profile** (13) — *Sign out* returns to onboarding.

Screen 14 (public web page) is intentionally excluded — it's viewer-facing, not
part of the iOS app.

## Project layout

```
ReelieApp/
  ReelieApp.swift          app entry + RootView (onboarding vs main)
  DesignSystem/
    Theme.swift            Palette (Sun/Ink/Grey/Line/Soft), fonts
    Components.swift        BigButton, PillButton, tab bar, chips, thumbs…
  Models/
    Models.swift           Product, Page, Sale, SourceVideo, SocialAccount…
    AppState.swift         @Observable state + sample data
  Onboarding/              screens 01–04
  Main/                    screens 05–13
```

## Fonts

The mockups use **Fraunces** (italic display) and **DM Sans** (UI). Those aren't
system fonts, so `Theme.swift` falls back to the system serif italic and system
sans. To use the real faces:

1. Drop `Fraunces-Italic.ttf` and `DMSans-Regular.ttf` into the `ReelieApp`
   folder (they'll be picked up automatically by the synchronized group).
2. Add them under **Info → Fonts provided by application** in the target.

`ReelieFont` already looks up `"Fraunces-Italic"` / `"DMSans-Regular"` by name.

## Notes

- Colors: Sun `#FFD60A`, Ink `#141414`, Grey `#9A9A9A`, Line `#EDEDED`,
  Soft `#F7F7F7`.
- Bundle id `com.reelie.app`; set your team under Signing & Capabilities to run
  on a device.
- All data is sample data in `SampleData` — swap for real API calls later.
