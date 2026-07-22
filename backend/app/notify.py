"""
Transactional email via Resend's HTTP API (stdlib only — no new dependency).
Every send is best-effort and non-fatal: when RESEND_API_KEY is unset it logs
and returns, so dev never sends and a mail outage never breaks a request.
Call these from a BackgroundTask so the response isn't blocked.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app import config

_ENDPOINT = "https://api.resend.com/emails"


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_email(to: str | list[str], subject: str, html: str, reply_to: str | None = None) -> bool:
    recipients = [to] if isinstance(to, str) else list(to)
    if not config.RESEND_API_KEY:
        print(f"[notify] email disabled (no RESEND_API_KEY) — would send to "
              f"{recipients}: {subject!r}", flush=True)
        return False
    payload = {"from": config.EMAIL_FROM, "to": recipients, "subject": subject, "html": html}
    if reply_to:
        payload["reply_to"] = reply_to
    req = urllib.request.Request(
        _ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {config.RESEND_API_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        print(f"[notify] sent {subject!r} → {recipients}", flush=True)
        return True
    except urllib.error.HTTPError as e:
        print(f"[notify] send failed HTTP {e.code}: {e.read()[:300]!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[notify] send failed: {type(e).__name__}: {e}", flush=True)
    return False


def creator_applied(handle: str, display_name: str, email: str,
                    instagram: str, youtube: str) -> None:
    """Tell the team a creator applied to the closed beta and awaits approval."""
    ig = (f'<a href="https://instagram.com/{_esc(instagram)}">@{_esc(instagram)}</a>'
          if instagram else "—")
    yt = (f'<a href="https://youtube.com/@{_esc(youtube)}">@{_esc(youtube)}</a>'
          if youtube else "—")
    rows = "".join(
        f'<tr><td style="padding:4px 14px 4px 0;color:#7A6F4A">{k}</td>'
        f'<td style="padding:4px 0"><b>{v}</b></td></tr>'
        for k, v in [("Name", _esc(display_name) or "—"), ("Handle", f"@{_esc(handle)}"),
                     ("Email", _esc(email) or "—"), ("Instagram", ig), ("YouTube", yt)])
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,sans-serif;color:#201B0A;max-width:520px">'
        f'<h2 style="margin:0 0 4px">New creator application 🎬</h2>'
        f'<p style="color:#7A6F4A;margin:0 0 16px">Awaiting approval in the admin console.</p>'
        f'<table style="border-collapse:collapse;font-size:15px">{rows}</table>'
        f'<p style="margin:22px 0 0"><a href="{config.PUBLIC_BASE_URL}/admin" '
        f'style="background:#6F5DF0;color:#fff;text-decoration:none;padding:10px 18px;'
        f'border-radius:999px;font-weight:600">Review in admin →</a></p></div>')
    send_email(config.ADMIN_EMAIL, f"New creator application: @{handle}", html,
               reply_to=email or None)
