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

LOCATION_ID = os.getenv("LOCATION_ID", "2084")
SERVICE_ID  = os.getenv("SERVICE_ID",  "31156")
VENUE_SLUG  = os.getenv("VENUE_SLUG",  "Omnifortlauderdale")
POLL_SECS   = int(os.getenv("POLL_SECS", "30"))
DATES       = os.getenv("DATES", "2026-05-09,2026-05-10").split(",")

BOOK_URL = "https://book.onagilysys.com/onecart/spa/services/{location}/{venue}?date={date}&serviceId={service}"

API_PATTERNS = [
    "https://book.onagilysys.com/onecart/api/spa/{location}/availability?date={date}&serviceId={service}",
    "https://book.onagilysys.com/onecart/api/services/{service}/availability?locationId={location}&date={date}",
    "https://book.onagilysys.com/onecart/api/v2/locations/{location}/services/{service}/timeslots?date={date}",
    "https://book.onagilysys.com/onecart/api/v1/spa/availability?locationId={location}&serviceId={service}&date={date}",
    "https://book.onagilysys.com/onecart/api/availability?locationId={location}&serviceId={service}&date={date}",
    "https://book.onagilysys.com/onecart/api/v1/locations/{location}/services/{service}/slots?date={date}",
    "https://book.onagilysys.com/onecart/api/v1/services/{service}/slots?locationId={location}&date={date}",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://book.onagilysys.com/",
    "Origin": "https://book.onagilysys.com",
}

last_state = {d: "unknown" for d in DATES}
alerted    = {d: False for d in DATES}
api_url_found = {}

twilio = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_sms(body):
    try:
        msg = twilio.messages.create(to=ALERT_TO, from_=TWILIO_FROM, body=body)
        log.info(f"SMS sent: {msg.sid}")
    except Exception as e:
        log.error(f"SMS failed: {e}")

def try_api_endpoints(date):
    patterns = [api_url_found[date]] if date in api_url_found else API_PATTERNS
    for pattern in patterns:
        url = pattern.format(location=LOCATION_ID, service=SERVICE_ID, date=date, venue=VENUE_SLUG)
        try:
            r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=12)
            body = r.text.strip()
            if r.status_code == 200 and body and body[0] in ("{", "["):
                api_url_found[date] = pattern
                data = r.json()
                slots = []
                if isinstance(data, list):
                    slots = data
                elif isinstance(data, dict):
                    for key in ("slots", "availableSlots", "timeSlots", "data", "results", "times", "appointments"):
                        if isinstance(data.get(key), list):
                            slots = data[key]
                            break
                    if not slots:
                        avail = data.get("available") or data.get("isAvailable")
                        if avail is True: return True, "API reports available"
                        if avail is False: return False, "API reports unavailable"
                if slots:
                    times = [str(s.get("time") or s.get("startTime") or s.get("displayTime") or "") for s in slots[:5]]
                    return True, ", ".join(t for t in times if t) or f"{len(slots)} slot(s)"
                if isinstance(slots, list) and len(slots) == 0:
                    return False, "empty slots array"
        except Exception:
            continue
    return None, "no_api_match"

def check_page_html(date):
    url = BOOK_URL.format(location=LOCATION_ID, venue=VENUE_SLUG, date=date, service=SERVICE_ID)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        html = r.text.lower()
        negative = ["no availability", "no times available", "fully booked", "sold out", "no appointments available", "unavailable for this date", "no openings", "nothing available"]
        positive = ["select a time", "choose a time", "book now", "add to cart", "9:00 am", "10:00 am", "11:00 am", "1:00 pm", "2:00 pm", "3:00 pm", "select time", "available times"]
        neg_hits = [k for k in negative if k in html]
        pos_hits = [k for k in positive if k in html]
        if neg_hits: return False, f"page says: {neg_hits[0]}"
        if pos_hits: return True, f"page shows: {pos_hits[0]}"
        return None, "ambiguous — JS-rendered page"
    except Exception as e:
        return None, f"page error: {e}"

def check_date(date):
    result, detail = try_api_endpoints(date)
    if result is None:
        result, detail = check_page_html(date)
    if result is True:
        if not alerted[date]:
            alerted[date] = True
            last_state[date] = "available"
            book_link = BOOK_URL.format(location=LOCATION_ID, venue=VENUE_SLUG, date=date, service=SERVICE_ID)
            send_sms(f"Omni Spa slot open!\nDate: {date}\nDetails: {detail}\nBook: {book_link}")
            log.info(f"[{date}] AVAILABLE — {detail}")
        else:
            log.info(f"[{date}] Still available — SMS already sent")
    elif result is False:
        if last_state[date] != "unavailable":
            log.info(f"[{date}] Not available ({detail})")
        last_state[date] = "unavailable"
        alerted[date] = False
    else:
        log.warning(f"[{date}] Unknown: {detail}")

def main():
    log.info("Omni Spa Monitor v2 | Dates: " + ", ".join(DATES))
    send_sms(f"Spa monitor v2 running.\nWatching: {', '.join(DATES)}\nWill text when slot opens.")
    while True:
        for date in DATES:
            check_date(date)
        log.info(f"--- sleeping {POLL_SECS}s ---")
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()
