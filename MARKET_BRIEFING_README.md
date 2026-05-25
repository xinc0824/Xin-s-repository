# Market Morning Briefing Email Tool

This tool sends a daily finance market briefing email at a configured local time.
It uses delayed Yahoo Finance quote data and Yahoo Finance RSS headlines.

## Recommended Setup: Render Web Service + UptimeRobot

Use the Python web service when you want users to type only the recipient email
in the form.

```text
Build Command: pip install -r requirements.txt
Start Command: python market_briefing_web.py --host 0.0.0.0 --port $PORT
```

Set these environment variables on Render:

```text
RESEND_API_KEY=re_your_api_key
RESEND_FROM_EMAIL=Market Briefing <onboarding@resend.dev>
```

Then use UptimeRobot to ping your Render URL every 5 minutes so the free web
service stays awake more reliably.

## UptimeRobot Setup

1. Create a free account at `https://uptimerobot.com`.
2. Click `New Monitor`.
3. Choose `HTTP(s)`.
4. Friendly Name: `Market Morning Briefing`.
5. URL: your Render web service URL.
6. Monitoring Interval: `5 minutes`.
7. Click `Create Monitor`.

## Resend Email Sending

The web service sends email through Resend instead of asking users to enter SMTP
settings.

```text
RESEND_API_KEY=re_your_api_key
RESEND_FROM_EMAIL=Market Briefing <briefing@yourdomain.com>
```

For testing without a custom domain, use `Market Briefing <onboarding@resend.dev>`
and send only to the email verified in your Resend account.

The public form only shows recipient email. These optional Render environment
variables control the fixed briefing defaults:

```text
BRIEFING_SEND_TIME=08:00
BRIEFING_SYMBOLS=^GSPC,^IXIC,^DJI,^VIX,ES=F,NQ=F,CL=F,GC=F,EURUSD=X,BTC-USD
BRIEFING_HEADLINE_COUNT=8
BRIEFING_TIMEZONE_LABEL=America/New_York
BRIEFING_SUBJECT_PREFIX=Market Morning Briefing
```

## Static Site Alternative

The `public/` folder contains a static setup page, but the static-only option
cannot save form recipients for scheduling without adding a database/API.

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
