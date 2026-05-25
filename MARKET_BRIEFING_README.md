# Market Morning Briefing Email Tool

This tool sends a daily finance market briefing email at a configured local time.
It uses delayed Yahoo Finance quote data and Yahoo Finance RSS headlines.

## Static Website

The public website can be hosted as a Render Static Site so it does not spin
down. Use:

```text
Publish directory: public
Build command: leave blank
```

The static website is for setup and configuration guidance. It does not send
email directly because a static site cannot safely store the Resend API key.

## Scheduled Email

Use a Render Cron Job for scheduled sending. Cron jobs do not depend on the
static website staying awake.

```text
Command: python cron_send_briefing.py
```

## Resend Email Sending

For the simplest public setup, use Resend instead of asking every user to enter
SMTP settings.

Set these environment variables on Render:

```text
RESEND_API_KEY=re_your_api_key
RESEND_FROM_EMAIL=Market Briefing <briefing@yourdomain.com>
```

Also set:

```text
BRIEFING_RECIPIENT_EMAIL=xin.chen.29@gmail.com
BRIEFING_SYMBOLS=^GSPC,^IXIC,^DJI,^VIX,ES=F,NQ=F,CL=F,GC=F,EURUSD=X,BTC-USD
BRIEFING_HEADLINE_COUNT=8
BRIEFING_TIMEZONE_LABEL=America/New_York
BRIEFING_SUBJECT_PREFIX=Market Morning Briefing
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
