import os
import time
import requests
import logging
from twilio.rest import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)

TWILIO_SID        = os.environ["TWILIO_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM       = os.environ["TWILIO_FROM"]
ALERT_TO          = os.environ["ALERT_TO"]

TENANT_ID    = os.getenv("TENANT_ID",    "2084")
PROPERTY_ID  = os.getenv("PROPERTY_ID",  "Omnifortlauderdale")
SERVICE_ID   = os.getenv("SERVICE_ID",   "31156")
SERVICE_CODE = os.getenv("SERVICE_CODE", "MASCUS50")
POLL_SECS    = int(os.getenv("POLL_SECS", "30"))
DATES        = os.getenv("DATES", "2026-05-09,2026-05-10").split(",")

SLOT_URL = (
    "https://book.onagilysys.com/wbe-spa-service/spa/tenants/{tenant}"
    "/propertyId/{property}/v2/serviceId/{service}/date/{date}"
    "/therapistSlotDetails?appName=spa&serviceCode={code}"
)

BOOK_URL = (
    "https://book.onagilysys.com/onecart/spa/services/{tenant}"
    "/{property}?date={date}&serviceId={service}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://book.onagilysys.com/onecart/spa/services/2084/Omnifortlauderdale",
    "Origin": "https://book.onagilysys.com",
}

last_state = {d: "unknown" for d in DATES}
alerted    = {d: False for d in DATES}

twilio = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_sms(body):
    try:
        msg = twilio.messages.create(to=ALERT_TO, from_=TWILIO_FROM, body=body)
        log.info(f"SMS sent: {msg.sid}")
    except Exception as e:
        log.error(f"SMS failed: {e}")

def check_date(date):
    url = SLOT_URL.format(tenant=TENANT_ID, property=PROPERTY_ID, service=SERVICE_ID, date=date, code=SERVICE_CODE)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"[{date}] Request error: {e}")
        return

    therapists = data.get("therapist", [])

    if therapists:
        times = []
        for t in therapists:
            name = t.get("therapistName", "")
            slots = t.get("slots", t.get("timeSlots", t.get("availableSlots", [])))
            for s in slots[:3]:
                st = s.get("startTime") or s.get("time") or s.get("slot", "")
                if st:
                    times.append(f"{name} @ {st}" if name else str(st))
        detail = ", ".join(times[:5]) if times else f"{len(therapists)} therapist(s) available"

        if not alerted[date]:
            alerted[date] = True
            last_state[date] = "available"
            book_link = BOOK_URL.format(tenant=TENANT_ID, property=PROPERTY_ID, date=date, service=SERVICE_ID)
            send_sms(f"Omni Spa slot open!\nDate: {date}\n{detail}\nBook: {book_link}")
            log.info(f"[{date}] AVAILABLE — {detail}")
        else:
            log.info(f"[{date}] Still available — SMS already sent")
    else:
        if last_state[date] != "unavailable":
            log.info(f"[{date}] No slots available")
        last_state[date] = "unavailable"
        alerted[date] = False

def main():
    log.info(f"Omni Spa Monitor v3 | Dates: {', '.join(DATES)} | Interval: {POLL_SECS}s")
    send_sms(f"Spa monitor v3 running.\nWatching: {', '.join(DATES)}\nWill text when slot opens.")
    while True:
        for date in DATES:
            check_date(date)
        log.info(f"--- sleeping {POLL_SECS}s ---")
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()
