import os
import re
import smtplib
import requests
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG ──────────────────────────────────────────────────────────────────
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
# ─────────────────────────────────────────────────────────────────────────────

CINEMA_CODE  = "CSWO"
EVENT_CODE   = "ET00451760"
SHOW_DATE    = "20260326"
MOVIE_NAME   = "Project Hail Mary"
CINEMA_NAME  = "Cinepolis Nexus Seawoods, Navi Mumbai"
FORMAT       = "4DX"

ALL_VENUES_API = (
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
    f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
    f"&eventCode={EVENT_CODE}&regionCode=MUMBAI"
    f"&subRegion=MUMBAI&format=json&date={SHOW_DATE}"
)

MOVIE_PAGE_URL = f"https://in.bookmyshow.com/movies/mumbai/project-hail-mary/{EVENT_CODE}"


def fetch_via_scraperapi(url: str) -> str:
    api_key = os.environ.get("SCRAPERAPI_KEY", "")
    if not api_key:
        raise Exception("No SCRAPERAPI_KEY set")
    resp = requests.get(
        "http://api.scraperapi.com/",
        params={"api_key": api_key, "url": url, "country_code": "in"},
        timeout=30,
    )
    print(f"   HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def fetch_page(url: str) -> str:
    for attempt in range(3):
        try:
            html = fetch_via_scraperapi(url)
            if html and len(html) > 200:
                return html
        except Exception as e:
            print(f"   ❌ Attempt {attempt+1} failed: {e}")
            time.sleep(3)
    raise Exception("All fetch attempts failed")


def check_shows() -> tuple:
    # ── Method 1: All-venues API, filter by CSWO ─────────────────────────────
    print(f"📡 Method 1: All-venues API (filtering for {CINEMA_CODE})...")
    try:
        data_str = fetch_page(ALL_VENUES_API)
        cswo_block = re.search(
            rf'"VenueCode"\s*:\s*"{CINEMA_CODE}".{{0,5000}}?(?="VenueCode"|\Z)',
            data_str, re.DOTALL
        )
        if cswo_block:
            block = cswo_block.group(0)
            times = re.findall(r'"ShowTime"\s*:\s*"(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)"', block)
            screens = re.findall(r'"ScreenName"\s*:\s*"([^"]+)"', block)
            formats = re.findall(r'"ScreenFormat"\s*:\s*"([^"]+)"', block)
            print(f"   {CINEMA_CODE} found! Screens: {list(set(screens))[:5]}")
            print(f"   Formats: {list(set(formats))[:5]}")
            print(f"   Show times: {times[:8]}")
            # Filter for 4DX specifically
            is_4dx = any("4dx" in s.lower() or "4dx" in f.lower()
                        for s in screens for f in formats)
            if times and is_4dx:
                print(f"   ✅ Method 1: {FORMAT} shows found at {CINEMA_NAME}!")
                return True, times
            elif times:
                print(f"   ⚠️  Shows found but not {FORMAT} format")
            else:
                print(f"   🔴 Method 1: Venue found but no shows yet")
        else:
            print(f"   🔴 Method 1: {CINEMA_CODE} not in API yet")
            venues = re.findall(r'"VenueCode"\s*:\s*"([^"]+)"', data_str)
            names  = re.findall(r'"VenueName"\s*:\s*"([^"]+)"', data_str)
            print(f"   Venues available: {list(zip(venues[:5], names[:5]))}")
    except Exception as e:
        print(f"   ⚠️  Method 1 error: {e}")

    # ── Method 2: Movie page, look for CSWO + 4DX in JSON ────────────────────
    print("🌐 Method 2: Movie page JSON check...")
    try:
        html = fetch_page(MOVIE_PAGE_URL)
        # Find CSWO venue block in page JSON
        cswo_in_page = re.search(
            rf'"VenueCode"\s*:\s*"{CINEMA_CODE}".{{0,3000}}?(?="VenueCode"|\Z)',
            html, re.DOTALL
        )
        if cswo_in_page:
            block = cswo_in_page.group(0)
            times = re.findall(
                r'"(?:showTime|ShowTime|startTime)"\s*:\s*"(\d{{1,2}}:\d{{2}}(?:\s*[AaPp][Mm])?)"',
                block
            )
            has_4dx = "4dx" in block.lower()
            print(f"   {CINEMA_CODE} in page: True | 4DX: {has_4dx} | Times: {times[:5]}")
            if times and has_4dx:
                print(f"   ✅ Method 2: {FORMAT} shows confirmed!")
                return True, times
        else:
            print(f"   🔴 Method 2: {CINEMA_CODE} not found in movie page yet")
    except Exception as e:
        print(f"   ⚠️  Method 2 error: {e}")

    return False, []


def send_email(show_times: list):
    formatted = sorted(set(show_times))
    times_html = (
        "<ul>" + "".join(f"<li><b>{t}</b></li>" for t in formatted) + "</ul>"
        if formatted else "<p>Check BookMyShow for show timings.</p>"
    )
    subject = f"🎬 {FORMAT} Shows OPEN — {MOVIE_NAME} at {CINEMA_NAME}!"
    body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <h2 style="color:#e63946;">🎬 {FORMAT} Tickets Are Live!</h2>
  <p><b>{FORMAT}</b> shows for <b>{MOVIE_NAME}</b> are now bookable at <b>{CINEMA_NAME}</b>!</p>
  <h3>🕐 Show Timings on 26 Mar 2026:</h3>
  {times_html}
  <br>
  <a href="https://in.bookmyshow.com/movies/mumbai/project-hail-mary/{EVENT_CODE}"
     style="background:#e63946;color:white;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:bold;font-size:16px;">
    👉 Book {FORMAT} Tickets Now
  </a>
  <br><br>
  <p style="color:#888;font-size:12px;">⚡ {FORMAT} seats sell out fast — book now!</p>
  <p style="color:#ccc;font-size:11px;">Sent by BookMyShow Tracker · GitHub Actions</p>
</body></html>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
    print(f"✅ Email sent to {NOTIFY_EMAIL}")


def main():
    print(f"🎬 {MOVIE_NAME} @ {CINEMA_NAME}")
    print(f"📅 Date: 26 Mar 2026 | Format: {FORMAT}")
    print(f"🎟️  Event: {EVENT_CODE} | Venue: {CINEMA_CODE}\n")

    found, show_times = check_shows()

    print()
    if found:
        print(f"🟢 {FORMAT} SHOWS BOOKABLE! Times: {show_times}")
        send_email(show_times)
    else:
        print(f"🔴 No {FORMAT} shows for {MOVIE_NAME} at {CINEMA_NAME} yet.")
        print("   Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
