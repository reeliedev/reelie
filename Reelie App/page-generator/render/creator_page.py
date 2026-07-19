"""
Per-creator index page: out/public/<handle>/index.html — the page the public
routine pages link to via "<Creator>'s pages →" (previously a dead route). Lists
all of a creator's routines plus a "similar creators" module. Built from the
registry (out/pages.json), so it always reflects the full catalogue.
"""

from __future__ import annotations

import html
from pathlib import Path

import config
from render import recommend

_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@1,9..144,700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{--sun:#FFD60A;--ink:#141414;--grey:#8A8A8A;--line:#EAEAEA;--soft:#F6F5F2;--cream:#FBFAF7}}
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'DM Sans',-apple-system,sans-serif;color:var(--ink);background:#fff;line-height:1.55}}
  a{{color:inherit}}
  .wrap{{max-width:1080px;margin:0 auto;padding:0 24px}}
  .eyebrow{{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--grey)}}
  .topbar{{border-bottom:1px solid var(--line)}}
  .topbar .wrap{{display:flex;align-items:center;justify-content:space-between;height:64px}}
  .brandmark{{font-family:'Fraunces',serif;font-style:italic;font-weight:700;font-size:22px;text-decoration:none}}
  .brandmark .dot{{color:var(--sun)}}
  .allpages{{font-size:13px;font-weight:600;text-decoration:none;border-bottom:2px solid var(--sun)}}
  .hero{{background:var(--cream);border-bottom:1px solid var(--line)}}
  .hero .wrap{{display:flex;flex-direction:column;align-items:center;text-align:center;padding:56px 24px}}
  .avatar{{width:88px;height:88px;border-radius:50%;box-shadow:0 0 0 3px var(--sun)}}
  h1{{font-family:'Fraunces',serif;font-style:italic;font-weight:700;font-size:clamp(34px,5vw,52px);letter-spacing:-1px;margin:18px 0 8px}}
  .handle{{font-size:14px;color:var(--grey)}}
  .sec{{padding:48px 0 8px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;padding-bottom:24px}}
  .card{{display:flex;align-items:center;gap:14px;text-decoration:none;border:1px solid var(--line);border-radius:18px;padding:16px;transition:transform .1s ease,box-shadow .1s}}
  .card:hover{{transform:translateY(-2px);box-shadow:0 24px 44px -30px rgba(20,20,20,.4)}}
  .card .thumb{{width:56px;height:56px;border-radius:14px;background:var(--soft);display:flex;align-items:center;justify-content:center;font-size:26px;flex-shrink:0}}
  .card .t{{font-weight:700;font-size:16px}}
  .card .m{{font-size:12.5px;color:var(--grey);margin-top:2px}}
  .similar{{background:var(--cream);border-top:1px solid var(--line);margin-top:32px}}
  .similar .wrap{{padding:52px 24px}}
  .similar h2{{font-family:'Fraunces',serif;font-style:italic;font-weight:700;font-size:28px;letter-spacing:-.5px;margin:8px 0 22px}}
  .sim-row{{display:flex;gap:16px;overflow-x:auto;padding-bottom:6px}}
  .sim-card{{flex:0 0 150px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:8px;text-decoration:none;background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px 14px}}
  .sim-av{{width:56px;height:56px;border-radius:50%;box-shadow:0 0 0 2px var(--sun)}}
  .sim-name{{font-weight:700;font-size:14px}}
  .sim-reason{{font-size:12px;color:var(--grey)}}
  .footer{{border-top:1px solid var(--line);margin-top:44px}}
  .footer .wrap{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;padding:32px 24px 44px;font-size:12.5px;color:var(--grey)}}
</style>
</head>
<body>
  <header class="topbar"><div class="wrap">
    <a class="brandmark" href="{base}">{brand}<span class="dot">.</span></a>
    <a class="allpages" href="{base}">Browse creators →</a>
  </div></header>
"""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _grad(g):
    g0 = g[0] if g else "#E8E4DA"
    g1 = g[1] if g and len(g) > 1 else "#D8D2C4"
    return f"linear-gradient(135deg,{g0},{g1})"


def render_creator_page(handle: str, pages: list[dict]) -> str:
    mine = [p for p in pages if p["handle"] == handle]
    if not mine:
        return ""
    first = mine[0]
    name = first.get("creator_name", handle)
    grad = _grad(first.get("avatar_gradient"))
    platforms = " · ".join(first.get("platforms", []))
    url = f"{config.BASE_URL}/{handle}"

    cards = "".join(
        f'<a class="card" href="{_esc(p["url"])}">'
        f'<div class="thumb">{p.get("emoji","🎬")}</div>'
        f'<div><div class="t">{_esc(p["title"])}</div>'
        f'<div class="m">{p.get("num_products",0)} products</div></div></a>'
        for p in sorted(mine, key=lambda x: x["slug"])
    )

    sims = recommend.similar_creators(handle, pages, limit=6)
    similar = ""
    if sims:
        sim_cards = "".join(
            f'<a class="sim-card" href="{config.BASE_URL}/{_esc(c["handle"])}">'
            f'<span class="sim-av" style="background:{_grad(c["avatar_gradient"])}"></span>'
            f'<span class="sim-name">{_esc(c["name"])}</span>'
            f'<span class="sim-reason">{_esc(c["reason"])}</span></a>'
            for c in sims
        )
        similar = (f'<section class="similar"><div class="wrap">'
                   f'<div class="eyebrow">Discover more</div>'
                   f'<h2>Creators with a similar shelf</h2>'
                   f'<div class="sim-row">{sim_cards}</div></div></section>')

    head = _HEAD.format(
        title=f"{name} — routines & products | {config.BRAND}",
        desc=f"Every product {name} uses, priced and linked.",
        url=url, base=config.BASE_URL, brand=config.BRAND,
    )
    body = f"""
  <section class="hero"><div class="wrap">
    <span class="avatar" style="background:{grad}"></span>
    <h1>{_esc(name)}</h1>
    <div class="handle">@{_esc(handle)}{' · ' + _esc(platforms) if platforms else ''}</div>
  </div></section>

  <section class="sec"><div class="wrap">
    <div class="eyebrow">Routines</div>
    <div class="grid" style="margin-top:16px">{cards}</div>
  </div></section>

  {similar}

  <footer class="footer"><div class="wrap">
    <a class="brandmark" href="{config.BASE_URL}" style="font-size:18px">{config.BRAND}<span class="dot">.</span></a>
    <div>Are you a creator? <a href="{config.BASE_URL}" style="color:var(--ink);font-weight:700;border-bottom:2px solid var(--sun);text-decoration:none">Claim your page →</a></div>
  </div></footer>
</body>
</html>
"""
    return head + body


def write_creator_pages(pages: list[dict], out_root: Path) -> list[Path]:
    """Write out/public/<handle>/index.html for every creator in the registry."""
    written = []
    for handle in sorted({p["handle"] for p in pages}):
        htmlstr = render_creator_page(handle, pages)
        if not htmlstr:
            continue
        dest = out_root / handle / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(htmlstr)
        written.append(dest)
    return written
