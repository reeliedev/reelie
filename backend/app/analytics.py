"""
Page-view analytics with an eye on GEO/AEO: we log every public page load and
classify it as a human, a named AI answer-engine crawler (GPTBot, PerplexityBot,
ClaudeBot, …), or a generic bot. The AI crawls are the signal that a creator's
page is being ingested by answer engines. Unique human views are de-duped by a
cookieless per-day hash of ip+ua.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from sqlmodel import Session, func, select

from app import config
from app.db import engine
from app.models import Click, PageView, Sale

# AI crawler user-agent token → friendly answer-engine name (what creators see).
_AI_ENGINE = {
    "GPTBot": "ChatGPT", "OAI-SearchBot": "ChatGPT", "ChatGPT-User": "ChatGPT",
    "ClaudeBot": "Claude", "Claude-Web": "Claude", "anthropic-ai": "Claude",
    "PerplexityBot": "Perplexity", "Perplexity-User": "Perplexity",
    "Google-Extended": "Google AI", "Applebot-Extended": "Apple",
    "Amazonbot": "Amazon", "Bytespider": "TikTok", "Meta-ExternalAgent": "Meta",
    "CCBot": "Common Crawl",
}
_GENERIC_BOT_HINTS = ("bot", "crawl", "spider", "slurp", "curl", "wget",
                      "python-requests", "httpx", "headless", "uptime", "monitor",
                      "facebookexternalhit", "embedly", "preview", "scan")


def engine_name(agent: str) -> str:
    return _AI_ENGINE.get(agent, agent or "AI")


def classify(user_agent: str) -> tuple[str, str]:
    """(kind, agent). kind ∈ {'ai','bot','human'}; agent is the AI crawler token
    (e.g. 'GPTBot') for kind='ai', else ''."""
    ua = user_agent or ""
    low = ua.lower()
    for token in config.AI_CRAWLERS:                 # named answer-engine crawlers first
        if token.lower() in low:
            return "ai", token
    if not ua.strip() or any(h in low for h in _GENERIC_BOT_HINTS):
        return "bot", ""
    return "human", ""


def _session_hash(ip: str, ua: str) -> str:
    raw = f"{ip}|{ua}|{date.today().isoformat()}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def log_view(handle: str, slug: str, ip: str, user_agent: str, referer: str) -> None:
    """Record one page load (own session — safe from a BackgroundTask)."""
    kind, agent = classify(user_agent)
    try:
        with Session(engine) as s:
            s.add(PageView(handle=handle, page_slug=slug, kind=kind, agent=agent,
                           session=_session_hash(ip, user_agent),
                           referer=(referer or "")[:300]))
            s.commit()
    except Exception as e:  # noqa: BLE001  (analytics must never break a page load)
        print(f"[analytics] log_view failed: {type(e).__name__}: {e}", flush=True)


def _count(session: Session, model, **where) -> int:
    q = select(func.count()).select_from(model)
    for k, v in where.items():
        q = q.where(getattr(model, k) == v)
    return session.exec(q).one()


def page_stats_lite(session: Session, handle: str, slug: str) -> dict:
    """Fast counts for the pages list (no row scan)."""
    return {
        "humanViews": _count(session, PageView, handle=handle, page_slug=slug, kind="human"),
        "aiCrawls": _count(session, PageView, handle=handle, page_slug=slug, kind="ai"),
        "clicks": _count(session, Click, handle=handle, page_slug=slug),
    }


def page_stats(session: Session, handle: str, slug: str) -> dict:
    """Funnel + GEO/AEO breakdown for one page."""
    views = session.exec(select(PageView).where(
        PageView.handle == handle, PageView.page_slug == slug)).all()
    human = [v for v in views if v.kind == "human"]
    ai = [v for v in views if v.kind == "ai"]
    by_engine: dict[str, int] = {}
    for v in ai:
        name = engine_name(v.agent)
        by_engine[name] = by_engine.get(name, 0) + 1
    clicks = _count(session, Click, handle=handle, page_slug=slug)
    sale_rows = session.exec(select(Sale).where(
        Sale.handle == handle, Sale.page_slug == slug)).all()
    return {
        "humanViews": len(human),
        "uniqueViews": len({v.session for v in human if v.session}),
        "aiCrawls": len(ai),
        "aiByEngine": [{"engine": k, "count": v}
                       for k, v in sorted(by_engine.items(), key=lambda kv: -kv[1])],
        "clicks": clicks,
        "sales": len(sale_rows),
        "earnings": round(sum(r.value for r in sale_rows), 2),
    }
