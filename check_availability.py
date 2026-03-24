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
EVENT_CODE   = "ET00451760"   # Project Hail Mary
SHOW_DATE    = "20260326"
MOVIE_NAME   = "Project Hail Mary"
CINEMA_NAME  = "Miraj Cinemas IMAX Wadala"

# This URL is specific to Project Hail Mary at this cinema
MOVIE_BOOKING_URL = (
    f"https://in.bookmyshow.com/buytickets/{EVENT_CODE}/cinema/{CINEMA_CODE}/{SHOW_DATE}"
)

# Alternative URL format
MOVIE_BOOKING_URL_2 = (
    f"https://in.bookmyshow.com/mumbai/movies/project-hail-mary/{EVENT_CODE}"
    f"?date={SHOW_DATE}&venueCode={CINEMA_CODE}"
)

# API — movie + cinema specific
CINEMA_API_URL = (
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
    f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
    f"&eventCode={EVENT_CODE}&regionCode=MUMBAI"
    f"&subRegion=MUMBAI&format=json&venueCode={CINEMA_CODE}&date={SHOW_DATE}"
)

# This is the key API — fetches all venues for the movie, we filter by MCIW
ALL_VENUES_API = (
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
    f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
    f"&eventCode={EVENT_CODE}&regionCode=MUMBAI"
    f"&subRegion=MUMBAI&format=json&date={SHOW_DATE}"
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

    # ── Method 1: All-venues API, filter by cinema code MCIW ─────────────────
    print("📡 Method 1: All-venues API (filtering for MCIW)...")
    try:
        data_str = fetch_page(ALL_VENUES_API)

        # Find the section of JSON that belongs to MCIW venue
        # Look for MCIW venue block and extract show times from it only
        mciw_block = re.search(
            r'"VenueCode"\s*:\s*"MCIW".{0,5000}?(?="VenueCode"|\Z)',
            data_str, re.DOTALL
        )

        if mciw_block:
            block = mciw_block.group(0)
            times = re.findall(r'"ShowTime"\s*:\s*"(\d{1,2}:\d{2}(?::\d{2})?)"', block)
            screens = re.findall(r'"ScreenName"\s*:\s*"([^"]+)"', block)
            print(f"   MCIW block found! Screens: {list(set(screens))[:5]}")
            print(f"   Show times: {times[:8]}")
            if times:
                show_times = times
                print(f"   ✅ Method 1: {len(times)} shows at MCIW!")
                return True, show_times
            else:
                print("   🔴 Method 1: MCIW venue found but no shows yet")
        else:
            print("   🔴 Method 1: MCIW venue not in API response yet")
            # Show what venues ARE in the response for debugging
            venues = re.findall(r'"VenueCode"\s*:\s*"([^"]+)"', data_str)
            venue_names = re.findall(r'"VenueName"\s*:\s*"([^"]+)"', data_str)
            print(f"   Venues currently available: {list(zip(venues[:5], venue_names[:5]))}")

    except Exception as e:
        print(f"   ⚠️  Method 1 error: {e}")

    # ── Method 2: Movie-specific booking page at this cinema ──────────────────
    print("🌐 Method 2: Movie+cinema specific page...")
    for url in [MOVIE_BOOKING_URL, MOVIE_BOOKING_URL_2]:
        try:
            html = fetch_page(url)
            # Look for show times in JSON data — but ONLY if page is for correct movie
            # Verify it's the right movie first
            is_correct_movie = (
                EVENT_CODE.lower() in html.lower() or
                "project hail mary" in html.lower() or
                "hail mary" in html.lower()
            )
            print(f"   Correct movie page: {is_correct_movie}")

            if not is_correct_movie:
                print("   ⚠️  Page doesn't seem to be for Project Hail Mary, skipping")
                continue

            # Extract show times from JSON keys only
            times = re.findall(
                r'"(?:showTime|ShowTime|time|startTime|showtime)"\s*:\s*"(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)"',
                html
            )
            print(f"   Show times: {times[:8]}")

            if times:
                show_times = times
                print(f"   ✅ Method 2: Shows found for Project Hail Mary!")
                return True, show_times
            else:
                print("   🔴 Method 2: No shows for this movie yet")

        except Exception as e:
            print(f"   ⚠️  Method 2 ({url[:50]}...) error: {e}")

    return False, []


def send_email(show_times: list):
    # Format times nicely
    formatted = sorted(set(show_times))
    times_html = (
        "<ul>" + "".join(f"<li><b>{t}</b></li>" for t in formatted) + "</ul>"
        if formatted
        else "<p>Shows are now available — check BookMyShow for timings.</p>"
    )

    subject = f"🎬 {MOVIE_NAME} IMAX Shows OPEN at {CINEMA_NAME}!"
    body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <h2 style="color:#e63946;">🎬 Tickets Are Live!</h2>
  <p>Shows for <b>{MOVIE_NAME}</b> are now bookable at <b>{CINEMA_NAME}</b>!</p>
  <h3>🕐 Show Timings on 26 Mar 2026:</h3>
  {times_html}
  <br>
  <a href="https://in.bookmyshow.com/movies/mumbai/project-hail-mary/{EVENT_CODE}"
     style="background:#e63946;color:white;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:bold;font-size:16px;">
    👉 Book Tickets Now
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
        print("🔴 No shows for Project Hail Mary at Miraj IMAX Wadala yet.")
        print("   Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
