"""
Serve the marketing Landing Page as the site home (/). The static page lives in
app/landing/ (bundled into the image); we rebrand it to the current name and
point its nav at the live routes:

  "Discover creators" -> /discover     "Creator studio" -> /studio
"""

from __future__ import annotations

from app import config


def home_html() -> str:
    s = (config.LANDING_DIR / "index.html").read_text()
    # rebrand (the static file predates the Reelie rename); nav + CTAs already
    # point at /discover and /studio in the source.
    s = s.replace("Retrieva", config.BRAND).replace("retrieva.com", "reelie.io")
    s = s.replace('href="/try"', 'href="/studio"')   # safety net for any stray link
    return s
