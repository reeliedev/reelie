"""
Transactional email via Resend's HTTP API (stdlib only — no new dependency).
Every send is best-effort and non-fatal: when RESEND_API_KEY is unset it logs
and returns, so dev never sends and a mail outage never breaks a request.
Call these from a BackgroundTask so the response isn't blocked.
"""

from __future__ import annotations

import html
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
    # quote=True also escapes " and ' so values are safe inside HTML attributes.
    return html.escape(s or "", quote=True)


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


def content_reported(kind: str, ref: str, reason: str, detail: str, reporter: str) -> None:
    """Alert the team that a viewer reported content (UGC moderation)."""
    link = f"{config.PUBLIC_BASE_URL}/{ref}" if kind == "page" else f"{config.PUBLIC_BASE_URL}/{ref}"
    rows = "".join(
        f'<tr><td style="padding:4px 14px 4px 0;color:#7A6F4A">{k}</td>'
        f'<td style="padding:4px 0"><b>{v}</b></td></tr>'
        for k, v in [("Type", _esc(kind)), ("Target", _esc(ref)),
                     ("Reason", _esc(reason)), ("Reported by", _esc(reporter))])
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,sans-serif;color:#201B0A;max-width:520px">'
        f'<h2 style="margin:0 0 4px">Content reported 🚩</h2>'
        f'<p style="color:#7A6F4A;margin:0 0 16px">Review and action if needed.</p>'
        f'<table style="border-collapse:collapse;font-size:15px">{rows}</table>'
        + (f'<p style="margin:14px 0 0"><b>Detail:</b> {_esc(detail)}</p>' if detail else "")
        + f'<p style="margin:22px 0 0"><a href="{_esc(link)}" '
        f'style="background:#6F5DF0;color:#fff;text-decoration:none;padding:10px 18px;'
        f'border-radius:999px;font-weight:600">View the content →</a></p></div>')
    send_email(config.ADMIN_EMAIL, f"Reported: {kind} {ref}", html)


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


def _p(text: str) -> str:
    """A body paragraph in the branded card's muted style."""
    return f'<p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#7A6F4A">{text}</p>'


def _brand_email(kicker: str, heading: str, body_html: str,
                 cta: tuple[str, str] | None = None) -> str:
    """Wrap content in Reelie's branded email card — yellow ground, white card,
    wordmark, optional purple pill CTA (label, url), and footer. Table-based +
    inline CSS so it renders across Gmail / Apple Mail / Outlook."""
    button = ""
    if cta:
        label, url = cta
        button = (
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 4px">'
            '<tr><td align="center" bgcolor="#6F5DF0" style="border-radius:999px">'
            f'<a href="{url}" target="_blank" style="display:inline-block;padding:15px 34px;'
            'font-size:15px;font-weight:600;color:#FFFFFF;text-decoration:none;border-radius:999px;'
            f'background:#6F5DF0">{label}</a></td></tr></table>')
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#FFE566;margin:0;padding:0">'
        '<tr><td align="center" style="padding:32px 16px 40px;font-family:\'Instrument Sans\',-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="440" style="width:440px;max-width:100%">'
        '<tr><td style="padding:4px 8px 20px;font-size:22px;font-weight:700;letter-spacing:-0.02em;color:#201B0A">Reelie</td></tr></table>'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="440" style="width:440px;max-width:100%;background:#FFFFFF;border-radius:20px;box-shadow:0 8px 30px rgba(32,27,10,0.12)">'
        '<tr><td style="padding:40px 36px 36px">'
        f'<div style="font-family:\'Space Grotesk\',monospace;font-size:11px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#6F5DF0;margin:0 0 14px">{kicker}</div>'
        f'<h1 style="margin:0 0 16px;font-size:26px;line-height:1.2;font-weight:700;letter-spacing:-0.02em;color:#201B0A">{heading}</h1>'
        f'{body_html}{button}'
        '</td></tr></table>'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="440" style="width:440px;max-width:100%">'
        '<tr><td style="padding:22px 8px 0;font-size:12px;line-height:1.6;color:#7A6F4A">'
        '<a href="https://reelie.io" style="color:#7A6F4A;text-decoration:none;font-weight:600">Reelie</a>&nbsp;·&nbsp; Turn your videos into shoppable pages<br>'
        'Sent by Reelie · <a href="mailto:hello@reelie.io" style="color:#7A6F4A">hello@reelie.io</a>'
        '</td></tr></table></td></tr></table>')


def creator_approved(email: str, display_name: str, handle: str) -> None:
    """Tell the creator they're approved and can start publishing."""
    if not email:
        return
    name = _esc(display_name.split()[0]) if display_name else "there"
    ink = 'color:#201B0A'
    body = (
        _p(f'Hi {name}, your creator account <b style="{ink}">@{_esc(handle)}</b> is approved. '
           f'<b style="{ink}">Start posting, start earning</b> — turn any of your videos into a '
           f'shoppable routine page in minutes.')
        + _p('Sign in with the same email and you’ll land straight in. Paste a video link, '
             'review the products we find, and publish.')
        + _p('Questions? Just reply to this email — we’re here to help.'))
    html = _brand_email("You’re approved", "Congratulations — you’re approved! 🎉", body,
                        cta=("Start creating →", f"{config.PUBLIC_BASE_URL}/studio"))
    send_email(email, "Congratulations — you’re approved! Start posting, start earning 🎉",
               html, reply_to=config.SUPPORT_EMAIL)


def creator_confirmation(email: str, display_name: str, handle: str) -> None:
    """Confirm we got their socials and tell them to watch their Instagram DMs."""
    if not email:
        return
    name = _esc(display_name.split()[0]) if display_name else "there"
    ink = 'color:#201B0A'
    body = (
        _p(f'Hi {name}, we’ve got your details for <b style="{ink}">@{_esc(handle)}</b> — '
           f'you’re on your way to being approved.')
        + _p(f'<b style="{ink}">One important step:</b> please check your '
             f'<b style="{ink}">Instagram DMs — including your DM Requests</b>. Our team will '
             f'message you there to confirm your identity, and replying is how we verify you '
             f'and finish your approval.')
        + _p('Once you’re verified and approved, you’ll be able to turn any of your videos '
             'into a shoppable routine page in minutes.'))
    html = _brand_email("You’re on your way", "Great — you’re on your way! 🚀", body)
    send_email(email, "You’re on your way — check your Instagram DMs 📩", html,
               reply_to=config.SUPPORT_EMAIL)
