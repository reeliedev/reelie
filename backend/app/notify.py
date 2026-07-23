"""
Transactional email via Resend's HTTP API (stdlib only — no new dependency).
Every send is best-effort and non-fatal: when RESEND_API_KEY is unset it logs
and returns, so dev never sends and a mail outage never breaks a request.
Call these from a BackgroundTask so the response isn't blocked.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

from app import config

_ENDPOINT = "https://api.resend.com/emails"

# Verify TLS against certifi's CA bundle so a slim container (or a macOS Python
# without system certs) can still reach api.resend.com. Falls back to default.
try:
    import certifi
    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL_CTX = None


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
                 "Content-Type": "application/json",
                 # Cloudflare (fronting Resend) 403s the default Python-urllib UA.
                 "User-Agent": "Reelie/1.0 (+https://reelie.io)"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
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


def creator_approved(email: str, display_name: str, handle: str) -> None:
    """Tell the creator they're approved and can start publishing."""
    if not email:
        return
    name = _esc(display_name.split()[0]) if display_name else "there"
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,sans-serif;color:#201B0A;max-width:520px;line-height:1.6">'
        f'<h2 style="margin:0 0 6px">Congratulations — you’re approved! 🎉</h2>'
        f'<p>Hi {name}, your creator account <b>@{_esc(handle)}</b> is approved. '
        f'<b>Start posting, start earning</b> — turn any of your videos into a shoppable '
        f'routine page in a couple of minutes.</p>'
        f'<p style="margin:22px 0"><a href="{config.PUBLIC_BASE_URL}/studio" '
        f'style="background:#6F5DF0;color:#fff;text-decoration:none;padding:12px 22px;'
        f'border-radius:999px;font-weight:600;display:inline-block">Start creating →</a></p>'
        f'<p>Sign in with the same email and you’ll land straight in. Paste a video link, '
        f'review the products we find, and publish.</p>'
        f'<p style="color:#7A6F4A;margin-top:22px">Questions? Just reply to this email — '
        f'we’re here to help.<br>— The Reelie team</p></div>')
    send_email(email, "Congratulations — you’re approved! Start posting, start earning 🎉",
               html, reply_to=config.SUPPORT_EMAIL)


def creator_confirmation(email: str, display_name: str, handle: str) -> None:
    """Confirm we got their socials and tell them to watch their Instagram DMs."""
    if not email:
        return
    name = _esc(display_name.split()[0]) if display_name else "there"
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,sans-serif;color:#201B0A;max-width:520px;line-height:1.6">'
        f'<h2 style="margin:0 0 6px">Great — you’re on your way! 🚀</h2>'
        f'<p>Hi {name}, we’ve got your details for <b>@{_esc(handle)}</b> and you’re '
        f'on your way to being approved.</p>'
        f'<p><b>One important step:</b> please check your <b>Instagram DMs — including '
        f'your DM Requests</b>. Our team will message you there to confirm your identity, '
        f'and replying is how we verify you and finish your approval.</p>'
        f'<p>Once you’re verified and approved, you’ll be able to turn any of your videos '
        f'into a shoppable routine page in a couple of minutes.</p>'
        f'<p style="color:#7A6F4A;margin-top:22px">— The Reelie team</p></div>')
    send_email(email, "You’re on your way — check your Instagram DMs 📩", html,
               reply_to=config.SUPPORT_EMAIL)
