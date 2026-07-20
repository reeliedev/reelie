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
    # rebrand (the static file predates the Reelie rename)
    s = s.replace("Retrieva", config.BRAND).replace("retrieva.com", "reelie.shop")
    # nav → live pages
    s = s.replace('<a class="nav-try" href="/">Browse creators</a>',
                  '<a class="nav-try" href="/discover">Discover creators</a>')
    s = s.replace('<a class="nav-try" href="/try">Try it out!</a>',
                  '<a class="nav-try" href="/studio">Creator studio</a>')
    s = s.replace('href="/try"', 'href="/studio"')
    return s
