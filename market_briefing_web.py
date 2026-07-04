#!/usr/bin/env python3
"""Local website for configuring and sending market morning briefings."""

from __future__ import annotations

import argparse
import configparser
import datetime as dt
import html
import os
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from market_morning_briefing import (
    DEFAULT_CONFIG,
    BriefingSettings,
    EmailSettings,
    build_briefing,
    next_run_at,
    read_config,
    send_email,
    write_config,
)


EXAMPLE_CONFIG = Path(__file__).with_name("market_briefing.example.ini")
SERVER_STATE = {
    "scheduler_running": False,
    "next_run": "",
    "last_result": "No briefing sent yet.",
    "last_error": "",
}
SCHEDULER_STOP = threading.Event()
SCHEDULER_THREAD: threading.Thread | None = None
DEFAULT_SYMBOLS = [
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^VIX",
    "ES=F",
    "NQ=F",
    "CL=F",
    "GC=F",
    "EURUSD=X",
    "BTC-USD",
]


def fixed_briefing_settings() -> BriefingSettings:
    symbols = [
        symbol.strip().upper()
        for symbol in os.environ.get("BRIEFING_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",")
        if symbol.strip()
    ]
    return BriefingSettings(
        send_time=os.environ.get("BRIEFING_SEND_TIME", "08:00").strip(),
        timezone_label=os.environ.get("BRIEFING_TIMEZONE_LABEL", "America/New_York").strip(),
        symbols=symbols,
        headline_count=int(os.environ.get("BRIEFING_HEADLINE_COUNT", "8")),
        subject_prefix=os.environ.get("BRIEFING_SUBJECT_PREFIX", "Market Morning Briefing").strip(),
    )


def saved_recipient() -> str:
    parser = configparser.ConfigParser()
    if not DEFAULT_CONFIG.exists():
        return ""
    parser.read(DEFAULT_CONFIG, encoding="utf-8")
    return parser.get("email", "recipient", fallback="").strip()


def resend_ready() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip() and os.environ.get("RESEND_FROM_EMAIL", "").strip())


def default_settings() -> tuple[EmailSettings, BriefingSettings]:
    return (
        EmailSettings(
            smtp_host="",
            smtp_port=587,
            username="",
            password="",
            sender=os.environ.get("RESEND_FROM_EMAIL", "").strip(),
            recipient=saved_recipient(),
            use_tls=True,
        ),
        fixed_briefing_settings(),
    )


def settings_from_form(form: dict[str, list[str]]) -> tuple[EmailSettings, BriefingSettings]:
    def field(name: str, fallback: str = "") -> str:
        return form.get(name, [fallback])[0].strip()

    sender = os.environ.get("RESEND_FROM_EMAIL", "").strip()
    email_settings = EmailSettings(
        smtp_host="",
        smtp_port=587,
        username="",
        password="",
        sender=sender,
        recipient=field("recipient"),
        use_tls=True,
    )
    return email_settings, fixed_briefing_settings()


def save_form(form: dict[str, list[str]]) -> tuple[EmailSettings, BriefingSettings]:
    email_settings, briefing_settings = settings_from_form(form)
    write_config(DEFAULT_CONFIG, email_settings, briefing_settings)
    return email_settings, briefing_settings


def scheduler_loop() -> None:
    while not SCHEDULER_STOP.is_set():
        try:
            email_settings, briefing_settings = read_config(DEFAULT_CONFIG)
            target = next_run_at(briefing_settings.send_time)
            SERVER_STATE["next_run"] = target.strftime("%Y-%m-%d %H:%M:%S")
            SERVER_STATE["last_error"] = ""
            wait_seconds = max(1, int((target - dt.datetime.now()).total_seconds()))
            if SCHEDULER_STOP.wait(wait_seconds):
                break

            subject, body_text, body_html = build_briefing(briefing_settings)
            send_email(email_settings, subject, body_text, body_html)
            SERVER_STATE["last_result"] = f"Sent {subject} to {email_settings.recipient}"
            SERVER_STATE["last_error"] = ""
        except Exception as exc:
            SERVER_STATE["last_error"] = str(exc)
            SERVER_STATE["last_result"] = "The last scheduled send failed."
            SCHEDULER_STOP.wait(60)

    SERVER_STATE["scheduler_running"] = False
    SERVER_STATE["next_run"] = ""


def start_scheduler() -> None:
    global SCHEDULER_THREAD
    if SCHEDULER_THREAD and SCHEDULER_THREAD.is_alive():
        SERVER_STATE["scheduler_running"] = True
        return
    SCHEDULER_STOP.clear()
    SCHEDULER_THREAD = threading.Thread(target=scheduler_loop, daemon=True)
    SCHEDULER_THREAD.start()
    SERVER_STATE["scheduler_running"] = True


def stop_scheduler() -> None:
    SCHEDULER_STOP.set()
    SERVER_STATE["scheduler_running"] = False
    SERVER_STATE["next_run"] = ""


def page_html(
    email_settings: EmailSettings,
    briefing_settings: BriefingSettings,
    notice: str = "",
    preview: str = "",
) -> str:
    notice_html = f'<div class="notice">{html.escape(notice)}</div>' if notice else ""
    preview_html = f'<section class="preview">{preview}</section>' if preview else ""
    running = SERVER_STATE["scheduler_running"]
    scheduler_text = "Running" if running else "Stopped"
    email_status = "Ready" if resend_ready() else "Needs Render env vars"
    schedule_summary = (
        f"{briefing_settings.send_time} {briefing_settings.timezone_label}, "
        f"{len(briefing_settings.symbols)} default symbols"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Morning Briefing</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18202f;
      --muted: #657184;
      --line: #d7dde6;
      --panel: #ffffff;
      --page: #f4f7fb;
      --navy: #16324f;
      --teal: #0f766e;
      --gold: #a16207;
      --red: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--page);
    }}
    header {{
      background: var(--navy);
      color: #fff;
      padding: 22px 32px;
    }}
    header h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    header p {{
      margin: 6px 0 0;
      color: #dbe7f3;
      font-size: 14px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: center;
    }}
    nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    nav a {{
      color: #fff;
      border: 1px solid rgba(255,255,255,.35);
      border-radius: 6px;
      padding: 8px 10px;
      text-decoration: none;
      font-size: 14px;
      font-weight: 700;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(280px, 380px) 1fr;
      min-height: calc(100vh - 84px);
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: #edf2f7;
      padding: 24px;
    }}
    .status {{
      display: grid;
      gap: 12px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .06em;
    }}
    .metric strong {{
      display: block;
      margin-top: 6px;
      font-size: 16px;
      overflow-wrap: anywhere;
    }}
    .workspace {{
      padding: 24px 32px 40px;
    }}
    form {{
      display: grid;
      gap: 22px;
      max-width: 1040px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
    }}
    section h2 {{
      margin: 0 0 16px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    label {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    input, textarea {{
      width: 100%;
      border: 1px solid #c8d1dd;
      border-radius: 6px;
      padding: 10px 11px;
      color: var(--ink);
      background: #fff;
      font: inherit;
      font-weight: 400;
    }}
    textarea {{
      min-height: 86px;
      resize: vertical;
    }}
    .check {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      color: var(--ink);
      font-weight: 700;
    }}
    .check input {{
      width: 18px;
      height: 18px;
    }}
    .provider {{
      margin: 0 0 14px;
      color: #334155;
      line-height: 1.45;
    }}
    .toast {{
      position: fixed;
      right: 22px;
      bottom: 22px;
      z-index: 10;
      min-width: 220px;
      max-width: min(420px, calc(100vw - 44px));
      border: 1px solid #99f6e4;
      border-radius: 8px;
      background: #134e4a;
      color: #fff;
      padding: 12px 14px;
      box-shadow: 0 12px 28px rgba(15, 23, 42, .2);
      opacity: 0;
      pointer-events: none;
      transform: translateY(10px);
      transition: opacity .18s ease, transform .18s ease;
    }}
    .toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
    .actions {{
      position: sticky;
      bottom: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 16px 0 0;
      background: linear-gradient(180deg, transparent, var(--page) 24%);
    }}
    button {{
      min-height: 42px;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 0 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .primary {{ background: var(--teal); color: #fff; }}
    .secondary {{ background: #fff; color: var(--navy); border-color: var(--line); }}
    .warning {{ background: var(--gold); color: #fff; }}
    .danger {{ background: var(--red); color: #fff; }}
    .notice {{
      max-width: 1040px;
      margin: 0 0 16px;
      border-left: 4px solid var(--teal);
      background: #ecfdf5;
      padding: 12px 14px;
      color: #134e4a;
      border-radius: 6px;
    }}
    .preview {{
      max-width: 1040px;
      margin-top: 22px;
      overflow-x: auto;
    }}
    .preview table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .preview th, .preview td {{
      border: 1px solid var(--line);
      padding: 8px;
    }}
    .preview a {{ color: var(--teal); }}
    @media (max-width: 820px) {{
      main {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .grid {{ grid-template-columns: 1fr; }}
      .workspace {{ padding: 20px; }}
      header {{ padding: 20px; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>Market Morning Briefing</h1>
        <p>Configure the daily trading briefing, preview it, and send test emails from one local page.</p>
      </div>
      <nav aria-label="Primary">
        <a href="/">Dashboard</a>
        <a href="/instructions">Email setup</a>
      </nav>
    </div>
  </header>
  <main>
    <aside>
      <div class="status">
        <div class="metric"><span>Scheduler</span><strong>{scheduler_text}</strong></div>
        <div class="metric"><span>Email Provider</span><strong>{email_status}</strong></div>
        <div class="metric"><span>Daily Briefing</span><strong>{html.escape(schedule_summary)}</strong></div>
        <div class="metric"><span>Next Run</span><strong>{html.escape(SERVER_STATE["next_run"] or "Not scheduled")}</strong></div>
        <div class="metric"><span>Last Result</span><strong>{html.escape(SERVER_STATE["last_result"])}</strong></div>
        <div class="metric"><span>Last Error</span><strong>{html.escape(SERVER_STATE["last_error"] or "None")}</strong></div>
      </div>
    </aside>
    <div class="workspace">
      {notice_html}
      <form method="post">
        <section>
          <h2>Email Delivery</h2>
          <p class="provider">Email is sent with Resend. The sender, send time, market symbols, and briefing format are fixed by the server.</p>
          <div class="grid">
            <label>Recipient email
              <input name="recipient" type="email" value="{html.escape(email_settings.recipient)}" required>
            </label>
          </div>
        </section>
        <div class="actions">
          <button class="primary" formaction="/save" type="submit">Save Settings</button>
          <button class="secondary" formaction="/preview" type="submit">Preview Briefing</button>
          <button class="warning" formaction="/send" type="submit">Send Test Email</button>
          <button class="secondary" formaction="/start" type="submit">Start Scheduler</button>
          <button class="danger" formaction="/stop" type="submit">Stop Scheduler</button>
        </div>
      </form>
      {preview_html}
    </div>
  </main>
  <div id="toast" class="toast" role="status" aria-live="polite"></div>
  <script>
    const toast = document.getElementById('toast');
    const form = document.querySelector('form');
    const messages = {{
      '/save': 'Saving settings...',
      '/preview': 'Building preview...',
      '/send': 'Sending test email...',
      '/start': 'Starting scheduler...',
      '/stop': 'Stopping scheduler...'
    }};
    function showToast(message) {{
      toast.textContent = message;
      toast.classList.add('show');
    }}
    if ({'true' if notice else 'false'}) {{
      showToast({notice!r});
      setTimeout(() => toast.classList.remove('show'), 4200);
    }}
    form.addEventListener('submit', (event) => {{
      const action = event.submitter ? event.submitter.getAttribute('formaction') : '/save';
      showToast(messages[action] || 'Working...');
    }});
  </script>
</body>
</html>"""


def instructions_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Email Setup - Market Morning Briefing</title>
  <style>
    :root {
      --ink: #18202f;
      --line: #d7dde6;
      --panel: #ffffff;
      --page: #f4f7fb;
      --navy: #16324f;
      --teal: #0f766e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--page);
    }
    header {
      background: var(--navy);
      color: #fff;
      padding: 22px 32px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: center;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }
    header p {
      margin: 6px 0 0;
      color: #dbe7f3;
      font-size: 14px;
    }
    nav {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    nav a {
      color: #fff;
      border: 1px solid rgba(255,255,255,.35);
      border-radius: 6px;
      padding: 8px 10px;
      text-decoration: none;
      font-size: 14px;
      font-weight: 700;
    }
    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 26px 24px 42px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      margin-bottom: 18px;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }
    p, li {
      color: #334155;
      line-height: 1.55;
    }
    code {
      background: #eef2f7;
      border: 1px solid #d7dde6;
      border-radius: 5px;
      padding: 2px 5px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }
    th { background: #edf2f7; }
    .callout {
      border-left: 4px solid var(--teal);
      background: #ecfdf5;
      padding: 12px 14px;
      border-radius: 6px;
      color: #134e4a;
    }
    @media (max-width: 720px) {
      header { padding: 20px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      main { padding: 20px; }
      table { display: block; overflow-x: auto; }
    }
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>Email Setup</h1>
        <p>Connect the briefing website to Resend so users only enter a recipient email.</p>
      </div>
      <nav aria-label="Primary">
        <a href="/">Dashboard</a>
        <a href="/instructions">Email setup</a>
      </nav>
    </div>
  </header>
  <main>
    <section>
      <h2>What The Website Needs</h2>
      <p>The website sends email through Resend. The API key, sender address, send time, symbols, and briefing format stay private on Render, so users do not need Gmail app passwords or SMTP settings.</p>
      <table>
        <thead>
          <tr><th>Setting</th><th>Where it goes</th></tr>
        </thead>
        <tbody>
          <tr><td><code>RESEND_API_KEY</code></td><td>Render environment variable. This is your private Resend API key.</td></tr>
          <tr><td><code>RESEND_FROM_EMAIL</code></td><td>Render environment variable. For testing, use <code>Market Briefing &lt;onboarding@resend.dev&gt;</code>.</td></tr>
          <tr><td>Recipient email</td><td>Website form. This is the only user-editable field.</td></tr>
          <tr><td><code>BRIEFING_SEND_TIME</code></td><td>Optional Render environment variable. Defaults to <code>08:00</code>.</td></tr>
          <tr><td><code>BRIEFING_SYMBOLS</code></td><td>Optional Render environment variable. Defaults to major indices, futures, EUR/USD, and BTC.</td></tr>
        </tbody>
      </table>
    </section>
    <section>
      <h2>Render Setup</h2>
      <ol>
        <li>Create a Resend API key.</li>
        <li>Open your Render service.</li>
        <li>Go to Environment.</li>
        <li>Add <code>RESEND_API_KEY</code>.</li>
        <li>Add <code>RESEND_FROM_EMAIL</code>.</li>
        <li>Redeploy the latest commit.</li>
        <li>Open the website and press Send Test Email.</li>
      </ol>
      <p class="callout">For Resend testing, send to the email address connected to your Resend account. Sending to the public usually requires verifying a real domain in Resend.</p>
    </section>
    <section>
      <h2>How Sending Works</h2>
      <p>When you press Send Test Email, or when the scheduler reaches the fixed server-side send time, the app builds the briefing, creates an HTML email, calls the Resend email API with your private server-side API key, and sends the message to the recipient address.</p>
      <p>The market data comes from Yahoo Finance quote and RSS endpoints. The email itself is sent from the Resend sender configured in <code>RESEND_FROM_EMAIL</code>.</p>
    </section>
    <section>
      <h2>Daily Delivery</h2>
      <p>Press Start Scheduler on the dashboard to keep the website process waiting in the background. At the fixed send time, it sends one briefing email to the saved recipient. Use UptimeRobot to help keep the Render web service awake.</p>
    </section>
  </main>
</body>
</html>"""


class BriefingHandler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        if self.path in ("/", "/index.html", "/health", "/instructions"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        if self.path == "/health":
            body = b"OK"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/instructions":
            body = instructions_html().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.render()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        notice = ""
        preview = ""

        try:
            if self.path in ("/save", "/preview", "/send", "/start"):
                email_settings, briefing_settings = save_form(form)
                notice = "Settings saved."
            else:
                email_settings, briefing_settings = default_settings()

            if self.path == "/preview":
                subject, _, body_html = build_briefing(briefing_settings)
                preview = f"<h2>{html.escape(subject)}</h2>{body_html}"
                notice = "Preview generated from the latest settings."
            elif self.path == "/send":
                if not resend_ready():
                    raise ValueError("Resend is not configured. Add RESEND_API_KEY and RESEND_FROM_EMAIL in Render.")
                subject, body_text, body_html = build_briefing(briefing_settings)
                send_email(email_settings, subject, body_text, body_html)
                SERVER_STATE["last_result"] = f"Sent {subject} to {email_settings.recipient}"
                SERVER_STATE["last_error"] = ""
                notice = "Test email sent."
            elif self.path == "/start":
                if not resend_ready():
                    raise ValueError("Resend is not configured. Add RESEND_API_KEY and RESEND_FROM_EMAIL in Render.")
                start_scheduler()
                notice = "Scheduler started."
            elif self.path == "/stop":
                stop_scheduler()
                notice = "Scheduler stopped."
        except Exception as exc:
            email_settings, briefing_settings = default_settings()
            SERVER_STATE["last_error"] = str(exc)
            notice = f"Action failed: {exc}"

        self.render(email_settings, briefing_settings, notice, preview)

    def render(
        self,
        email_settings: EmailSettings | None = None,
        briefing_settings: BriefingSettings | None = None,
        notice: str = "",
        preview: str = "",
    ) -> None:
        if email_settings is None or briefing_settings is None:
            email_settings, briefing_settings = default_settings()
        body = page_html(email_settings, briefing_settings, notice, preview).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the market briefing website.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), BriefingHandler)
    print(f"Market briefing website running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_scheduler()
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
