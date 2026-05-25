# Market Morning Briefing Email Tool

This tool sends a daily finance market briefing email at a configured local time.
It uses delayed Yahoo Finance quote data and Yahoo Finance RSS headlines.

## Website

Run the local website:

```powershell
python .\market_briefing_web.py
```

Then open:

```text
http://127.0.0.1:8080
```

The website lets you edit settings, preview the briefing, send a test email,
and start or stop the in-process daily scheduler.

The dashboard uses Resend for email delivery, so users only need a recipient
email, send time, symbols, and headline count.

## Resend Email Sending

For the simplest public setup, use Resend instead of asking every user to enter
SMTP settings.

Set these environment variables on Render:

```text
RESEND_API_KEY=re_your_api_key
RESEND_FROM_EMAIL=Market Briefing <briefing@yourdomain.com>
```

With those set, users only need to enter their recipient email, send time, and
symbols.

For email setup instructions, open:

```text
http://127.0.0.1:8080/instructions
```

## Setup

1. Copy `market_briefing.example.ini` to `market_briefing.ini`.
2. Fill in your SMTP email settings.
3. Set the recipient, send time, and symbols you want to track.

For Gmail, use an app password rather than your normal account password.

## Test Without Sending

```powershell
python .\market_morning_briefing.py --dry-run
```

## Send One Email Now

```powershell
python .\market_morning_briefing.py --once
```

## Run Daily

Leave this running:

```powershell
python .\market_morning_briefing.py
```

For a more reliable daily schedule on Windows, create a Task Scheduler task that
runs this command at your desired time:

```powershell
python C:\Users\gigif\OneDrive\文档\New project\market_morning_briefing.py --once
```

Set the task's "Start in" folder to:

```text
C:\Users\gigif\OneDrive\文档\New project
```

## Notes

- Quotes are delayed and are for informational use only.
- The generated briefing is not investment advice.
- Keep `market_briefing.ini` private because it contains email credentials.
