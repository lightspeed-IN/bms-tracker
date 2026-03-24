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

# Target: Miraj Cinemas IMAX Wadala — Project Hail Mary — 26 Mar 2026
CINEMA_CODE  = "MCIW"
EVENT_CODE   = "ET00451760"
SHOW_DATE    = "20260326"
MOVIE_NAME   = "Project Hail Mary"
CINEMA_NAME  = "Miraj Cinemas IMAX Wadala"
BOOKING_URL  = "https://in.bookmyshow.com/cinemas/mumbai/miraj-cinemas-imax-wadala/buytickets/MCIW/20260326"

# BMS API — returns all shows for a specific cinema + date
CINEMA_API_URL = (
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
    f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
    f"&eventCode={EVENT_CODE}&regionCode=MUMBAI"
    f"&subRegion=MUMBAI&format=json&venueCode={CINEMA_CODE}&date={SHOW_DATE}"
)

# BMS venue page API — alternative endpoint
VENUE_API_URL = (
    f"https://in.bookmyshow.com/api/movies-data/venue-wise-showtimes"
    f"?venueCode={CINEMA_CODE}&eventCode={EVENT_CODE}"
    f"&regionCode=MUMBAI&date={SHOW_DATE}&format=json"
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
    print(f"   HTTP {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'})")
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


def check_imax_at_cinema() -> tuple:
    """
    Check if IMAX shows are available at Miraj IMAX Wadala for Project Hail Mary.
    Uses 3 methods — returns (found: bool, show_times: list)
    """
    show_times = []

    # ── Method 1: Cinema-specific showtime API ────────────────────────────────
    print("📡 Method 1: Cinema showtime API...")
    try:
        data_str = fetch_page(CINEMA_API_URL)
        data_lower = data_str.lower()

        if "imax" in data_lower or "show" in data_lower:
            # Extract show times
            times = re.findall(r'"ShowTime"\s*:\s*"([^"]+)"', data_str)
            screens = re.findall(r'"ScreenName"\s*:\s*"([^"]+)"', data_str)
            formats = re.findall(r'"ScreenFormat"\s*:\s*"([^"]+)"', data_str)

            print(f"   Screens: {list(set(screens))[:5]}")
            print(f"   Formats: {list(set(formats))[:5]}")
            print(f"   Show times found: {times[:5]}")

            if times:
                show_times = times
                print(f"   ✅ Method 1: Shows found at {CINEMA_NAME}!")
                return True, show_times
        else:
            print("   🔴 Method 1: No shows found yet")

    except Exception as e:
        print(f"   ⚠️  Method 1 failed: {e}")

    # ── Method 2: Venue page API ──────────────────────────────────────────────
    print("📡 Method 2: Venue page API...")
    try:
        data_str = fetch_page(VENUE_API_URL)
        times = re.findall(r'"ShowTime"\s*:\s*"([^"]+)"', data_str)
        if times:
            show_times = times
            print(f"   ✅ Method 2: Shows found! Times: {times[:5]}")
            return True, show_times
        else:
            print("   🔴 Method 2: No shows found yet")
    except Exception as e:
        print(f"   ⚠️  Method 2 failed: {e}")

    # ── Method 3: Scrape the actual booking page ──────────────────────────────
    print("🌐 Method 3: Scraping booking page directly...")
    try:
        html = fetch_page(BOOKING_URL)
        html_lower = html.lower()

        # Look for show times or seat layout (means booking is open)
        time_matches = re.findall(
            r'\b([01]?\d|2[0-3]):[0-5]\d\s*(?:AM|PM|am|pm)\b', html
        )
        has_seats    = "seattype" in html_lower or "seat-" in html_lower
        has_shows    = "showtime" in html_lower or "show-time" in html_lower
        has_imax     = "imax" in html_lower

        print(f"   Times found: {time_matches[:5]}")
        print(f"   Has seat layout: {has_seats}")
        print(f"   Has showtime data: {has_shows}")
        print(f"   IMAX mentioned: {has_imax}")

        if time_matches or has_seats:
            show_times = time_matches[:5] if time_matches else ["Check BMS app"]
            print(f"   ✅ Method 3: Booking page has show data!")
            return True, show_times
        else:
            print("   🔴 Method 3: No show data on booking page yet")

    except Exception as e:
        print(f"   ⚠️  Method 3 failed: {e}")

    return False, []


def send_email(show_times: list):
    times_html = (
        "<ul>" + "".join(f"<li><b>{t}</b></li>" for t in show_times) + "</ul>"
        if show_times
        else "<p>Shows are now available — check BookMyShow for timings.</p>"
    )

    subject = f"🎬 IMAX Shows Open at {CINEMA_NAME} — Book Now!"
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

    found, show_times = check_imax_at_cinema()

    print()
    if found:
        print(f"🟢 SHOWS ARE BOOKABLE! Times: {show_times}")
        send_email(show_times)
    else:
        print("🔴 No shows available yet at Miraj IMAX Wadala.")
        print("   Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
