# Omni Fort Lauderdale Spa Monitor
Polls the Agilysys booking API every 30 seconds and texts you the moment
an appointment opens on May 9 or May 10, 2026.

---

## Step 1 — Get a free Twilio account (5 min)

1. Go to https://www.twilio.com/try-twilio and sign up (free, no credit card)
2. Verify your phone number during signup — this becomes your ALERT_TO number
3. From the Twilio Console dashboard, copy:
   - **Account SID** → this is your `TWILIO_SID`
   - **Auth Token** → this is your `TWILIO_AUTH_TOKEN`
4. Click "Get a free phone number" → copy it → this is your `TWILIO_FROM`
   (format: +15005550006)

---

## Step 2 — Deploy to Railway (5 min)

1. Go to https://railway.app and sign up with GitHub (free hobby tier)
2. Click **New Project → Deploy from GitHub repo**
3. Push this folder to a GitHub repo first (see Step 2a below), then select it
4. Once deployed, click your service → **Variables** tab → add these:

| Variable          | Value                        |
|-------------------|------------------------------|
| TWILIO_SID        | ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| TWILIO_AUTH_TOKEN | your auth token              |
| TWILIO_FROM       | +1XXXXXXXXXX (Twilio number) |
| ALERT_TO          | +1XXXXXXXXXX (your cell)     |
| DATES             | 2026-05-09,2026-05-10        |
| POLL_SECS         | 30                           |

5. Railway will automatically restart the service with the new variables.

---

## Step 2a — Push to GitHub

If you don't have git installed, download GitHub Desktop from https://desktop.github.com

```bash
cd spa-monitor
git init
git add .
git commit -m "Spa monitor"
# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/spa-monitor.git
git push -u origin main
```

---

## How it works

- Hits `book.onagilysys.com` API directly every 30 seconds
- When slots are found → sends you an SMS with available times + direct booking link
- Resets alert state if slots disappear, so you'll be re-notified if new ones open
- Sends a confirmation text when the monitor first starts up
- Railway keeps it running 24/7 even when your computer is off

---

## Customizing dates

Change the `DATES` environment variable in Railway to any comma-separated dates:
```
2026-05-09,2026-05-10,2026-05-11,2026-05-15
```

No code changes needed — just update the variable and Railway redeploys automatically.

---

## Costs

- **Twilio free trial**: ~$15 credit, each SMS costs ~$0.0079 — covers thousands of texts
- **Railway hobby tier**: Free ($5/mo credit included with GitHub account)
- Total cost to run: **$0**
