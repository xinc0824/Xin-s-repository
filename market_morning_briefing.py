#!/usr/bin/env python3
"""Send a scheduled market morning briefing email.

The tool uses only Python's standard library. It pulls delayed market quotes
from Yahoo Finance's public endpoints and top finance headlines from Yahoo RSS,
then sends the briefing through an SMTP account you configure.
"""

from __future__ import annotations

import argparse
import configparser
import datetime as dt
import email.message
import html
import json
import smtplib
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_CONFIG = Path(__file__).with_name("market_briefing.ini")
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
YAHOO_NEWS_RSS = "https://finance.yahoo.com/news/rssindex"


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    sender: str
    recipient: str
    use_tls: bool


@dataclass(frozen=True)
class BriefingSettings:
    send_time: str
    timezone_label: str
    symbols: list[str]
    headline_count: int
    subject_prefix: str


def read_config(path: Path) -> tuple[EmailSettings, BriefingSettings]:
    parser = configparser.ConfigParser()
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            "Create one from market_briefing.example.ini first."
        )

    parser.read(path, encoding="utf-8")
    email_cfg = parser["email"]
    briefing_cfg = parser["briefing"]

    email_settings = EmailSettings(
        smtp_host=email_cfg.get("smtp_host", "").strip(),
        smtp_port=email_cfg.getint("smtp_port", fallback=587),
        username=email_cfg.get("username", "").strip(),
        password=email_cfg.get("password", "").strip(),
        sender=email_cfg.get("sender", "").strip(),
        recipient=email_cfg.get("recipient", "").strip(),
        use_tls=email_cfg.getboolean("use_tls", fallback=True),
    )
    symbols = [
        symbol.strip().upper()
        for symbol in briefing_cfg.get("symbols", "").split(",")
        if symbol.strip()
    ]
    briefing_settings = BriefingSettings(
        send_time=briefing_cfg.get("send_time", "08:00").strip(),
        timezone_label=briefing_cfg.get("timezone_label", "local time").strip(),
        symbols=symbols,
        headline_count=briefing_cfg.getint("headline_count", fallback=8),
        subject_prefix=briefing_cfg.get("subject_prefix", "Market Morning Briefing").strip(),
    )

    missing = [
        name
        for name, value in {
            "smtp_host": email_settings.smtp_host,
            "username": email_settings.username,
            "password": email_settings.password,
            "sender": email_settings.sender,
            "recipient": email_settings.recipient,
            "symbols": ",".join(briefing_settings.symbols),
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required config value(s): {', '.join(missing)}")

    parse_send_time(briefing_settings.send_time)
    return email_settings, briefing_settings


def parse_send_time(value: str) -> dt.time:
    try:
        hour_text, minute_text = value.split(":", 1)
        return dt.time(hour=int(hour_text), minute=int(minute_text))
    except ValueError as exc:
        raise ValueError("send_time must use 24-hour HH:MM format, such as 08:00") from exc


def next_run_at(send_time: str, now: dt.datetime | None = None) -> dt.datetime:
    current = now or dt.datetime.now()
    target_time = parse_send_time(send_time)
    target = current.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += dt.timedelta(days=1)
    return target


def fetch_json(url: str, params: dict[str, str], timeout: int = 20) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "market-morning-briefing/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_quotes(symbols: Iterable[str]) -> list[dict]:
    data = fetch_json(YAHOO_QUOTE_URL, {"symbols": ",".join(symbols)})
    return data.get("quoteResponse", {}).get("result", [])


def fetch_headlines(limit: int) -> list[dict[str, str]]:
    request = urllib.request.Request(
        YAHOO_NEWS_RSS,
        headers={"User-Agent": "market-morning-briefing/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    items: list[dict[str, str]] = []
    for item in root.findall("./channel/item")[:limit]:
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        published = item.findtext("pubDate", default="").strip()
        if title:
            items.append({"title": title, "link": link, "published": published})
    return items


def format_number(value: object, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def write_config(path: Path, email_settings: EmailSettings, briefing_settings: BriefingSettings) -> None:
    parser = configparser.ConfigParser()
    parser["email"] = {
        "smtp_host": email_settings.smtp_host,
        "smtp_port": str(email_settings.smtp_port),
        "use_tls": str(email_settings.use_tls).lower(),
        "username": email_settings.username,
        "password": email_settings.password,
        "sender": email_settings.sender,
        "recipient": email_settings.recipient,
    }
    parser["briefing"] = {
        "send_time": briefing_settings.send_time,
        "timezone_label": briefing_settings.timezone_label,
        "subject_prefix": briefing_settings.subject_prefix,
        "symbols": ", ".join(briefing_settings.symbols),
        "headline_count": str(briefing_settings.headline_count),
    }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)


def build_briefing(settings: BriefingSettings) -> tuple[str, str, str]:
    today = dt.datetime.now().strftime("%A, %B %d, %Y")
    quotes = fetch_quotes(settings.symbols)
    headlines = fetch_headlines(settings.headline_count)

    subject = f"{settings.subject_prefix} - {today}"
    text_lines = [
        settings.subject_prefix,
        today,
        "",
        "Market Snapshot",
    ]
    html_rows = []

    for quote in quotes:
        symbol = quote.get("symbol", "")
        name = quote.get("shortName") or quote.get("longName") or symbol
        price = format_number(quote.get("regularMarketPrice"))
        change = format_number(quote.get("regularMarketChange"))
        pct = format_number(quote.get("regularMarketChangePercent"), "%")
        market_time = quote.get("regularMarketTime")
        time_text = ""
        if market_time:
            time_text = dt.datetime.fromtimestamp(int(market_time)).strftime("%I:%M %p")

        text_lines.append(f"- {symbol} ({name}): {price}, {change} ({pct}) {time_text}")
        html_rows.append(
            "<tr>"
            f"<td>{html.escape(symbol)}</td>"
            f"<td>{html.escape(name)}</td>"
            f"<td>{html.escape(price)}</td>"
            f"<td>{html.escape(change)}</td>"
            f"<td>{html.escape(pct)}</td>"
            f"<td>{html.escape(time_text)}</td>"
            "</tr>"
        )

    text_lines.extend(["", "Top Headlines"])
    html_headlines = []
    for headline in headlines:
        title = headline["title"]
        link = headline["link"]
        published = headline["published"]
        text_lines.append(f"- {title} ({published}) {link}")
        html_headlines.append(
            "<li>"
            f"<a href=\"{html.escape(link)}\">{html.escape(title)}</a>"
            f"<br><small>{html.escape(published)}</small>"
            "</li>"
        )

    text_lines.extend(
        [
            "",
            "Data is delayed and for informational use only. This is not investment advice.",
        ]
    )

    body_html = f"""\
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #1f2937;">
    <h2>{html.escape(settings.subject_prefix)}</h2>
    <p>{html.escape(today)}</p>
    <h3>Market Snapshot</h3>
    <table cellpadding="8" cellspacing="0" border="1" style="border-collapse: collapse;">
      <thead>
        <tr>
          <th align="left">Symbol</th>
          <th align="left">Name</th>
          <th align="right">Price</th>
          <th align="right">Change</th>
          <th align="right">Change %</th>
          <th align="left">Time</th>
        </tr>
      </thead>
      <tbody>
        {''.join(html_rows)}
      </tbody>
    </table>
    <h3>Top Headlines</h3>
    <ol>
      {''.join(html_headlines)}
    </ol>
    <p><small>Data is delayed and for informational use only. This is not investment advice.</small></p>
  </body>
</html>
"""
    return subject, "\n".join(text_lines), body_html


def send_email(settings: EmailSettings, subject: str, body_text: str, body_html: str) -> None:
    message = email.message.EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message.set_content(body_text)
    message.add_alternative(body_html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.use_tls:
            server.starttls(context=context)
        server.login(settings.username, settings.password)
        server.send_message(message)


def run_once(config_path: Path, dry_run: bool) -> None:
    email_settings, briefing_settings = read_config(config_path)
    subject, body_text, body_html = build_briefing(briefing_settings)
    if dry_run:
        print(f"Subject: {subject}")
        print()
        print(body_text)
        return
    send_email(email_settings, subject, body_text, body_html)
    print(f"Sent briefing to {email_settings.recipient}: {subject}")


def run_scheduler(config_path: Path, dry_run: bool) -> None:
    _, briefing_settings = read_config(config_path)
    print(
        "Scheduler started. "
        f"Briefing will send daily at {briefing_settings.send_time} "
        f"({briefing_settings.timezone_label})."
    )
    while True:
        target = next_run_at(briefing_settings.send_time)
        sleep_seconds = max(1, int((target - dt.datetime.now()).total_seconds()))
        print(f"Next run: {target.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(sleep_seconds)
        try:
            run_once(config_path, dry_run=dry_run)
        except Exception as exc:
            print(f"Briefing failed: {exc}", file=sys.stderr)
        _, briefing_settings = read_config(config_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Email a scheduled market morning briefing.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config file. Defaults to {DEFAULT_CONFIG.name}.",
    )
    parser.add_argument("--once", action="store_true", help="Send one briefing immediately.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the briefing without sending an email.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.once or args.dry_run:
            run_once(args.config, dry_run=args.dry_run)
        else:
            run_scheduler(args.config, dry_run=False)
    except KeyboardInterrupt:
        print("Stopped.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
