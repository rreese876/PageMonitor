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

SESSION_URL = f"https://book.onagilysys.com/onecart/api/v1/session?tenantId={TENANT_ID}&propertyId={PROPERTY_ID}&appName=spa"
SLOT_URL    = "https://book.onagilysys.com/wbe-spa-service/spa/tenants/{tenant}/propertyId/{property}/v2/serviceId/{service}/date/{date}/therapistSlotDetails?appName=spa&serviceCode={code}"
BOOK_URL    = "https://book.onagilysys.com/onecart/spa/services/{tenant}/{property}?date={date}&serviceId={service}"

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://book.onagilysys.com",
    "Referer": "https://book.onagilysys.com/onecart/spa/services/2084/Omnifortlauderdale?date=2026-05-09&serviceId=31156",
    "Propertydttm": "2026-05-07T00:00:00",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Timezone": "America/New_York",
}

last_state   = {d: "unknown" for d in DATES}
alerted      = {d: False for d in DATES}
auth_token   = None
session_id   = None
token_expiry = 0

twilio = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_sms(body):
    try:
        msg = twilio.messages.create(to=ALERT_TO, from_=TWILIO_FROM, body=body)
        log.info(f"SMS sent: {msg.sid}")
    except Exception as e:
        log.error(f"SMS failed: {e}")

def refresh_token():
    global auth_token, session_id, token_expiry
    try:
        r = requests.get(SESSION_URL, headers=BASE_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        token = data.get("token") or data.get("accessToken") or data.get("bearerToken") or data.get("access_token") or (data.get("data") or {}).get("token")
        sid   = data.get("sessionId") or data.get("wbeSessionId") or data.get("session_id") or (data.get("data") or {}).get("sessionId")
        if token:
            auth_token   = token
            session_id   = sid
            token_expiry = time.time() + 3300
            log.info(f"Token refreshed. Session: {sid}")
            return True
        log.warning(f"No token in session response. Keys: {list(data.keys())} | Body: {str(data)[:300]}")
        return False
    except Exception as e:
        log.error(f"Token refresh failed: {e}")
        return False

def get_headers():
    h = dict(BASE_HEADERS)
    if auth_token: h["Authorization"] = f"Bearer {auth_token}"
    if session_id: h["Wbesessionid"]  = session_id
    return h

def check_date(date):
    global auth_token, token_expiry
    if not auth_token or time.time() > token_expiry:
        if not refresh_token():
            log.warning(f"[{date}] Skipping — no valid token")
            return
    url = SLOT_URL.format(tenant=TENANT_ID, property=PROPERTY_ID, service=SERVICE_ID, date=date, code=SERVICE_CODE)
    try:
        r = requests.get(url, headers=get_headers(), timeout=15)
        if r.status_code == 401:
            log.info(f"[{date}] 401 — refreshing token and retrying")
            auth_token = None
            if refresh_token():
                r = requests.get(url, headers=get_headers(), timeout=15)
            else:
                return
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"[{date}] Request error: {e}")
        return

    therapists = data.get("therapist", [])
    if therapists:
        times = []
        for t in therapists:
            name  = t.get("therapistName", "")
            slots = t.get("slots") or t.get("timeSlots") or t.get("availableSlots") or []
            for s in slots[:3]:
                st = s.get("startTime") or s.get("time") or s.get("slot", "")
                if st: times.append(f"{name} @ {st}" if name else str(st))
        detail = ", ".join(times[:5]) if times else f"{len(therapists)} therapist(s) available"
        if not alerted[date]:
            alerted[date]      = True
            last_state[date]   = "available"
            book_link = BOOK_URL.format(tenant=TENANT_ID, property=PROPERTY_ID, date=date, service=SERVICE_ID)
            send_sms(f"Omni Spa slot open!\nDate: {date}\n{detail}\nBook: {book_link}")
            log.info(f"[{date}] AVAILABLE — {detail}")
        else:
            log.info(f"[{date}] Still available — SMS already sent")
    else:
        if last_state[date] != "unavailable":
            log.info(f"[{date}] No slots available")
        last_state[date] = "unavailable"
        alerted[date]    = False

def main():
    log.info(f"Omni Spa Monitor v4 | Dates: {', '.join(DATES)} | Interval: {POLL_SECS}s")
    send_sms(f"Spa monitor v4 running.\nWatching: {', '.join(DATES)}\nWill text when slot opens.")
    while True:
        for date in DATES: check_date(date)
        log.info(f"--- sleeping {POLL_SECS}s ---")
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()
