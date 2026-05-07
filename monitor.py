import os
import time
import requests
import logging
from datetime import datetime
from twilio.rest import Client

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Config (from environment variables) ───────────────────────────
TWILIO_SID        = os.environ["TWILIO_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM       = os.environ["TWILIO_FROM"]   # e.g. +15005550006
ALERT_TO          = os.environ["ALERT_TO"]      # your cell, e.g. +13051234567

LOCATION_ID = os.getenv("LOCATION_ID", "2084")
SERVICE_ID  = os.getenv("SERVICE_ID",  "31156")
VENUE_SLUG  = os.getenv("VENUE_SLUG",  "Omnifortlauderdale")
POLL_SECS   = int(os.getenv("POLL_SECS", "30"))

DATES = os.getenv("DATES", "2026-05-09,2026-05-10").split(",")

BOOK_URL = (
    f"https://book.onagilysys.com/onecart/spa/services/"
    f"{LOCATION_ID}/{VENUE_SLUG}?date={{date}}&serviceId={SERVICE_ID}"
)

API_URL = (
    f"https://book.onagilysys.com/onecart/api/v1/locations/"
    f"{LOCATION_ID}/services/{SERVICE_ID}/slots?date={{date}}"
)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; SpaMonitor/1.0)",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"https://book.onagilysys.com/onecart/spa/services/{LOCATION_ID}/{VENUE_SLUG}",
}

# ── State ──────────────────────────────────────────────────────────
# Tracks last known slot count per date so we only alert on changes
last_counts: dict[str, int] = {d: -1 for d in DATES}
alerted:     dict[str, bool] = {d: False for d in DATES}

twilio = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)


def send_sms(body: str):
    try:
        msg = twilio.messages.create(to=ALERT_TO, from_=TWILIO_FROM, body=body)
        log.info(f"SMS sent: {msg.sid}")
    except Exception as e:
        log.error(f"SMS failed: {e}")


def parse_slots(data) -> list:
    """Extract available slots from various Agilysys response shapes."""
    candidates = []
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        for key in ("slots", "availableSlots", "timeSlots", "data", "results"):
            if isinstance(data.get(key), list):
                candidates = data[key]
                break

    available = []
    for s in candidates:
        status = s.get("status") or s.get("available") or s.get("isAvailable") or "available"
        if isinstance(status, bool):
            if status:
                available.append(s)
        elif str(status).lower() not in ("unavailable", "booked", "closed", "blocked"):
            available.append(s)
    return available


def check_date(date: str):
    url = API_URL.format(date=date)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"[{date}] Request error: {e}")
        return

    slots = parse_slots(data)
    count = len(slots)

    if count > 0:
        if not alerted[date] or last_counts[date] != count:
            alerted[date] = True
            last_counts[date] = count
            times = []
            for s in slots[:5]:
                t = s.get("time") or s.get("startTime") or s.get("displayTime") or s.get("slot", "")
                if t:
                    times.append(str(t))
            time_str = ", ".join(times) if times else "check app"
            book_link = BOOK_URL.format(date=date)
            msg = (
                f"🎉 Omni Spa slot open!\n"
                f"Date: {date}\n"
                f"Times: {time_str}\n"
                f"Book: {book_link}"
            )
            log.info(f"[{date}] AVAILABLE — {count} slot(s): {time_str}")
            send_sms(msg)
        else:
            log.info(f"[{date}] Still available ({count} slots) — SMS already sent")
    else:
        if last_counts[date] != 0:
            log.info(f"[{date}] No slots available")
        last_counts[date] = 0
        alerted[date] = False  # reset so we re-alert if slots open again later


def main():
    log.info("=" * 50)
    log.info("Omni Fort Lauderdale Spa Monitor starting")
    log.info(f"Monitoring dates: {', '.join(DATES)}")
    log.info(f"Poll interval: {POLL_SECS}s")
    log.info(f"Alerts → {ALERT_TO}")
    log.info("=" * 50)

    send_sms(f"✅ Spa monitor started.\nWatching: {', '.join(DATES)}\nI'll text you the moment a slot opens.")

    while True:
        for date in DATES:
            check_date(date)
        time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()
