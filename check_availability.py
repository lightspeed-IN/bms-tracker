import os
import re
import smtplib
import requests
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG (set these as GitHub Secrets) ────────────────────────────────────
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
# ─────────────────────────────────────────────────────────────────────────────

CINEMA_CODE  = "MCIW"
EVENT_CODE   = "ET00451760"
SHOW_DATE    = "20260326"
MOVIE_NAME   = "Project Hail Mary"
CINEMA_NAME  = "Miraj Cinemas IMAX Wadala"
BOOKING_URL  = "https://in.bookmyshow.com/cinemas/mumbai/miraj-cinemas-imax-wadala/buytickets/MCIW/20260326"

CINEMA_API_URL = (
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
    f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
    f"&eventCode={EVENT_CODE}&regionCode=MUMBAI"
    f"&subRegion=MUMBAI&format=json&venueCode={CINEMA_CODE}&date={SHOW_DATE}"
)


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
    show_times = []

    # ── Method 1: Cinema-specific showtime API ────────────────────────────────
    print("📡 Method 1: Cinema showtime API...")
    try:
        data_str = fetch_page(CINEMA_API_URL)

        # Look for ShowTime keys in JSON — these are actual show start times
        # Format in BMS API: "ShowTime":"09:30:00" or "ShowTime":"21:30"
        api_times = re.findall(r'"ShowTime"\s*:\s*"(\d{1,2}:\d{2}(?::\d{2})?)"', data_str)
        api_screens = re.findall(r'"ScreenName"\s*:\s*"([^"]+)"', data_str)
        api_formats = re.findall(r'"ScreenFormat"\s*:\s*"([^"]+)"', data_str)

        print(f"   Screens found: {list(set(api_screens))[:5]}")
        print(f"   Formats found: {list(set(api_formats))[:5]}")
        print(f"   Show times found: {api_times[:8]}")

        if api_times:
            show_times = api_times
            print(f"   ✅ Method 1: {len(api_times)} shows found!")
            return True, show_times
        else:
            print("   🔴 Method 1: No shows in API yet")

    except Exception as e:
        print(f"   ⚠️  Method 1 error: {e}")

    # ── Method 2: Scrape the booking page ────────────────────────────────────
    print("🌐 Method 2: Scraping booking page...")
    try:
        html = fetch_page(BOOKING_URL)

        # Look for proper time format: "09:30 AM", "9:30 AM", "21:30" in JSON/HTML
        # BMS embeds show data as JSON strings like "showTime":"09:30 AM"
        json_times = re.findall(
            r'"(?:showTime|ShowTime|time|startTime)"\s*:\s*"(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)"',
            html
        )

        # Also look for time patterns inside __NEXT_DATA__ JSON blob
        next_data = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.+?)</script>',
            html, re.DOTALL
        )
        next_times = []
        if next_data:
            blob = next_data.group(1)
            next_times = re.findall(
                r'"(?:showTime|ShowTime|time|startTime|showtime)"\s*:\s*"(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)"',
                blob
            )
            print(f"   NEXT_DATA times: {next_times[:5]}")

        all_times = list(set(json_times + next_times))
        print(f"   JSON show times: {all_times[:8]}")

        if all_times:
            show_times = all_times
            print(f"   ✅ Method 2: Shows found on booking page!")
            return True, show_times

        # Last resort — check if "No shows" or "coming soon" message is absent
        # and a specific session/show element exists
        has_no_shows = any(phrase in html.lower() for phrase in [
            "no shows", "no shows available", "shows not available",
            "coming soon", "currently not available"
        ])
        has_show_element = any(phrase in html.lower() for phrase in [
            '"sessionid"', '"session_id"', '"showid"', '"show_id"',
            'class="show-time"', 'class="showtime"', '"ShowId"'
        ])

        print(f"   'No shows' message present: {has_no_shows}")
        print(f"   Show session element present: {has_show_element}")

        if has_show_element and not has_no_shows:
            print("   ✅ Method 2: Show sessions detected on page!")
            return True, ["Check BMS app for timings"]

        print("   🔴 Method 2: No confirmed shows on booking page")

    except Exception as e:
        print(f"   ⚠️  Method 2 error: {e}")

    return False, []


def send_email(show_times: list):
    times_html = (
        "<ul>" + "".join(f"<li><b>{t}</b></li>" for t in show_times) + "</ul>"
        if show_times
        else "<p>Shows are now available — check BookMyShow for timings.</p>"
    )

    subject = f"🎬 IMAX Shows OPEN at {CINEMA_NAME} — Book Now!"
    body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <h2 style="color:#e63946;">🎬 IMAX Tickets Are Live!</h2>
  <p>Shows for <b>{MOVIE_NAME}</b> are now bookable at <b>{CINEMA_NAME}</b>!</p>
  <h3>🕐 Show Timings on 26 Mar 2026:</h3>
  {times_html}
  <br>
  <a href="{BOOKING_URL}"
     style="background:#e63946;color:white;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:bold;font-size:16px;">
    👉 Book IMAX Tickets Now
  </a>
  <br><br>
  <p style="color:#888;font-size:12px;">⚡ IMAX seats sell out in minutes — book fast!</p>
  <p style="color:#ccc;font-size:11px;">Sent by BookMyShow IMAX Tracker · GitHub Actions</p>
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
    print(f"📅 Date: 26 Mar 2026")
    print(f"🎟️  Event: {EVENT_CODE} | Venue: {CINEMA_CODE}\n")

    found, show_times = check_shows()

    print()
    if found:
        print(f"🟢 SHOWS ARE BOOKABLE! Times: {show_times}")
        send_email(show_times)
    else:
        print("🔴 No shows available yet at Miraj IMAX Wadala.")
        print("   Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
