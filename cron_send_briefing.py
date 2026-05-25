#!/usr/bin/env python3
"""Send one scheduled market briefing from Render Cron Job environment variables."""

from __future__ import annotations

import os

from market_morning_briefing import BriefingSettings, EmailSettings, build_briefing, send_email


def env_value(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def main() -> int:
    recipient = env_value("BRIEFING_RECIPIENT_EMAIL")
    symbols = [
        symbol.strip().upper()
        for symbol in env_value(
            "BRIEFING_SYMBOLS",
            "^GSPC,^IXIC,^DJI,^VIX,ES=F,NQ=F,CL=F,GC=F,EURUSD=X,BTC-USD",
        ).split(",")
        if symbol.strip()
    ]
    if not recipient:
        raise ValueError("Set BRIEFING_RECIPIENT_EMAIL in the Render Cron Job environment.")
    if not env_value("RESEND_API_KEY"):
        raise ValueError("Set RESEND_API_KEY in the Render Cron Job environment.")
    if not env_value("RESEND_FROM_EMAIL"):
        raise ValueError("Set RESEND_FROM_EMAIL in the Render Cron Job environment.")

    email_settings = EmailSettings(
        smtp_host="",
        smtp_port=587,
        username="",
        password="",
        sender=env_value("RESEND_FROM_EMAIL"),
        recipient=recipient,
        use_tls=True,
    )
    briefing_settings = BriefingSettings(
        send_time="",
        timezone_label=env_value("BRIEFING_TIMEZONE_LABEL", "America/New_York"),
        symbols=symbols,
        headline_count=int(env_value("BRIEFING_HEADLINE_COUNT", "8")),
        subject_prefix=env_value("BRIEFING_SUBJECT_PREFIX", "Market Morning Briefing"),
    )

    subject, body_text, body_html = build_briefing(briefing_settings)
    send_email(email_settings, subject, body_text, body_html)
    print(f"Sent {subject} to {recipient}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
