"""Alert delivery: in-app always; Telegram / webhook / SMTP email when configured."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from eyohe.core.config import get_settings
from eyohe.core.logging import get_logger

log = get_logger("notify")


async def deliver(alert: dict[str, Any], channels: dict[str, Any] | None = None) -> dict[str, Any]:
    s = get_settings()
    channels = channels or {}
    out: dict[str, Any] = {"in_app": True}
    text = f"[Eyohe OSINT] {alert['alert_type']}: {alert['title']}\n{alert.get('message', '')}\nCase: {alert.get('case_display_id', '')}"
    if channels.get("telegram") and s.telegram_bot_token and s.telegram_chat_id:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                    json={"chat_id": s.telegram_chat_id, "text": text[:4000]},
                )
            out["telegram"] = r.status_code == 200
        except Exception as exc:
            out["telegram"] = f"failed: {type(exc).__name__}"
    elif channels.get("telegram"):
        out["telegram"] = "not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"
    if channels.get("webhook") and s.alert_webhook_url:
        try:
            from eyohe.core.netsafety import validate_url

            await validate_url(s.alert_webhook_url)
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(s.alert_webhook_url, json=alert)
            out["webhook"] = r.status_code < 300
        except Exception as exc:
            out["webhook"] = f"failed: {type(exc).__name__}"
    elif channels.get("webhook"):
        out["webhook"] = "not configured (ALERT_WEBHOOK_URL)"
    if channels.get("email") and s.smtp_host and s.smtp_from and channels.get("email_to"):
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[Eyohe OSINT] {alert['alert_type']}: {alert['title']}"[:200]
            msg["From"] = s.smtp_from
            msg["To"] = str(channels["email_to"])
            msg.set_content(text)
            import asyncio

            def _send() -> None:
                with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                    smtp.starttls()
                    if s.smtp_user:
                        smtp.login(s.smtp_user, s.smtp_password)
                    smtp.send_message(msg)

            await asyncio.to_thread(_send)
            out["email"] = True
        except Exception as exc:
            out["email"] = f"failed: {type(exc).__name__}"
    elif channels.get("email"):
        out["email"] = "not configured (SMTP_* / email_to)"
    return out
