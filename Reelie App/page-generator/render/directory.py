"""
Public directory / discovery page: out/public/index.html — a browsable catalogue
of every creator and routine, with client-side search over an embedded JSON index
(no backend). Built from the registry (out/pages.json).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import config
from render import recommend


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _grad(g):
    g0 = g[0] if g else "#E8E4DA"
    g1 = g[1] if g and len(g) > 1 else "#D8D2C4"
    return f"linear-gradient(135deg,{g0},{g1})"


def render_directory(pages: list[dict]) -> str:
    idx = recommend.creator_index(pages)
    creators = sorted(idx.values(), key=lambda c: c["name"])

    creator_cards = "".join(
        f'<a class="ccard" href="{config.BASE_URL}/{_esc(c["handle"])}" data-name="{_esc(c["name"].lower())} {_esc(c["handle"].lower())}">'
        f'<span class="cav" style="background:{_grad(c["avatar_gradient"])}"></span>'
        f'<span class="cname">{_esc(c["name"])}</span>'
        f'<span class="cmeta">@{_esc(c["handle"])} · {len(c["pages"])} routines</span></a>'
        for c in creators
    )

    routine_cards = "".join(
        f'<a class="rcard" href="{_esc(p["url"])}" '
        f'data-search="{_esc((p["title"] + " " + p.get("creator_name","") + " " + " ".join(p.get("brands",[]))).lower())}">'
        f'<span class="rthumb">{p.get("emoji","🎬")}</span>'
        f'<span class="rt">{_esc(p["title"])}</span>'
        f'<span class="rm">{_esc(p.get("creator_name",""))} · {p.get("num_products",0)} products</span></a>'
        for p in sorted(pages, key=lambda x: (x["handle"], x["slug"]))
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Browse creators & routines | {config.BRAND}</title>
<meta name="description" content="Browse every creator's shoppable routine on {config.BRAND}.">
<link rel="canonical" href="{config.BASE_URL}/">
<meta name="robots" content="index, follow">
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
  .hero{{background:var(--cream);border-bottom:1px solid var(--line)}}
  .hero .wrap{{padding:52px 24px 40px;text-align:center}}
  h1{{font-family:'Fraunces',serif;font-style:italic;font-weight:700;font-size:clamp(34px,5vw,54px);letter-spacing:-1px;margin-bottom:20px}}
  .search{{max-width:520px;margin:0 auto;display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:13px 16px}}
  .search input{{border:none;outline:none;font:inherit;font-size:15px;width:100%;background:transparent}}
  .sec{{padding:44px 0 8px}}
  .crow{{display:flex;gap:18px;overflow-x:auto;padding-bottom:8px}}
  .ccard{{flex:0 0 120px;display:flex;flex-direction:column;align-items:center;gap:7px;text-align:center;text-decoration:none}}
  .cav{{width:64px;height:64px;border-radius:50%;box-shadow:0 0 0 2px var(--sun)}}
  .cname{{font-weight:700;font-size:13px}}
  .cmeta{{font-size:11px;color:var(--grey)}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;padding-bottom:40px}}
  .rcard{{display:flex;flex-direction:column;gap:2px;text-decoration:none;border:1px solid var(--line);border-radius:18px;padding:18px;transition:transform .1s,box-shadow .1s}}
  .rcard:hover{{transform:translateY(-2px);box-shadow:0 24px 44px -30px rgba(20,20,20,.4)}}
  .rthumb{{font-size:30px;margin-bottom:8px}}
  .rt{{font-weight:700;font-size:16px}}
  .rm{{font-size:12.5px;color:var(--grey)}}
  .empty{{color:var(--grey);padding:30px 0}}
</style>
</head>
<body>
  <header class="topbar"><div class="wrap">
    <a class="brandmark" href="{config.BASE_URL}">{config.BRAND}<span class="dot">.</span></a>
    <a class="brandmark" href="{config.BASE_URL}" style="font-size:13px;font-weight:600;font-style:normal;border-bottom:2px solid var(--sun);text-decoration:none">Home</a>
  </div></header>

  <section class="hero"><div class="wrap">
    <h1>Shop your favorite<br>creators' routines</h1>
    <div class="search">
      <span>🔍</span>
      <input id="q" type="search" placeholder="Search creators, routines, or products" autocomplete="off">
    </div>
  </div></section>

  <section class="sec"><div class="wrap">
    <div class="eyebrow">Creators</div>
    <div class="crow" id="creators" style="margin-top:16px">{creator_cards}</div>
  </div></section>

  <section class="sec"><div class="wrap">
    <div class="eyebrow">All routines</div>
    <div class="grid" id="routines" style="margin-top:16px">{routine_cards}</div>
    <div class="empty" id="noresults" style="display:none">No matches.</div>
  </div></section>

  <script>
    var q = document.getElementById('q');
    var routines = Array.prototype.slice.call(document.querySelectorAll('.rcard'));
    var creators = Array.prototype.slice.call(document.querySelectorAll('.ccard'));
    q.addEventListener('input', function(){{
      var term = q.value.trim().toLowerCase();
      var shown = 0;
      routines.forEach(function(el){{
        var ok = !term || el.getAttribute('data-search').indexOf(term) !== -1;
        el.style.display = ok ? '' : 'none'; if(ok) shown++;
      }});
      creators.forEach(function(el){{
        el.style.display = (!term || el.getAttribute('data-name').indexOf(term) !== -1) ? '' : 'none';
      }});
      document.getElementById('noresults').style.display = shown ? 'none' : 'block';
    }});
  </script>
</body>
</html>
"""


def write_directory(pages: list[dict], out_root: Path) -> Path:
    dest = out_root / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_directory(pages))
    return dest
