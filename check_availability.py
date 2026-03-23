import os
import re
import smtplib
import requests
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG (set these as GitHub Secrets) ────────────────────────────────────
BMS_URL      = os.environ.get("BMS_URL", "https://in.bookmyshow.com/movies/mumbai/project-hail-mary/ET00451760")
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
# ─────────────────────────────────────────────────────────────────────────────

EVENT_CODE = BMS_URL.rstrip("/").split("/")[-1]   # ET00451760
CITY_CODE  = "MUMBAI"


def fetch_via_scraperapi(url: str) -> str:
    api_key = os.environ.get("SCRAPERAPI_KEY", "")
    if not api_key:
        raise Exception("No SCRAPERAPI_KEY set")
    resp = requests.get(
        "http://api.scraperapi.com/",
        params={"api_key": api_key, "url": url, "country_code": "in"},
        timeout=30,
    )
    print(f"   ScraperAPI HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def fetch_via_allorigins(url: str) -> str:
    proxy = f"https://api.allorigins.win/get?url={urllib.parse.quote(url)}"
    resp  = requests.get(proxy, timeout=20)
    print(f"   AllOrigins HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.json().get("contents", "")


def fetch_page(url: str) -> str:
    methods = []
    if os.environ.get("SCRAPERAPI_KEY"):
        methods.append(("ScraperAPI", lambda: fetch_via_scraperapi(url)))
    methods.append(("AllOrigins", lambda: fetch_via_allorigins(url)))

    last_error = None
    for name, fn in methods:
        try:
            print(f"   Trying {name}...")
            html = fn()
            if html and len(html) > 500:
                print(f"   ✅ {name} succeeded ({len(html)} chars)")
                return html
        except Exception as e:
            print(f"   ❌ {name} failed: {e}")
            last_error = e
            time.sleep(2)

    raise Exception(f"All fetch methods failed. Last error: {last_error}")


def check_imax_via_buytickets_api(event_code: str) -> tuple:
    """
    Hit the BMS venue/showtime listing API — this only returns formats
    that are ACTUALLY bookable right now, not just listed on the movie page.
    """
    # This endpoint returns the actual venue+format list shown in the booking popup
    api_url = (
        f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
        f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
        f"&eventCode={event_code}&regionCode={CITY_CODE}"
        f"&subRegion={CITY_CODE}&format=json"
    )
    proxied = f"http://api.scraperapi.com/?api_key={os.environ.get('SCRAPERAPI_KEY','')}&url={urllib.parse.quote(api_url)}&country_code=in"

    try:
        resp = requests.get(proxied, timeout=30)
        print(f"   Showtime API HTTP {resp.status_code}")
        if resp.status_code != 200:
            return False, []
        data = resp.json()

        imax_venues = []
        venues = (
            data.get("ShowDetails") or
            data.get("BookMyShow", {}).get("ShowDetails") or []
        )
        for venue in venues:
            venue_name = venue.get("VenueName", "")
            for show in (venue.get("ShowDetails") or []):
                screen = show.get("ScreenName", "").lower()
                fmt    = show.get("ScreenFormat", "").lower()
                if "imax" in screen or "imax" in fmt:
                    imax_venues.append(
                        f"{venue_name} — {show.get('ScreenName','IMAX')}"
                    )

        return len(imax_venues) > 0, imax_venues

    except Exception as e:
        print(f"   ⚠️  Showtime API failed: {e}")
        return False, []


def check_imax_via_html(html: str) -> tuple:
    """
    Look for IMAX inside the booking/showtime section of the HTML only.
    Specifically target the JSON blobs that BMS embeds for actual showtimes,
    NOT the movie metadata tags at the top of the page.
    """
    # BMS embeds showtime data as JSON in the page — look for IMAX there
    # Pattern: find JSON chunks that contain both "imax" and a date/show structure
    imax_found = False
    imax_details = []

    # Strategy: find __NEXT_DATA__ or similar JSON blob
    json_match = re.search(r'__NEXT_DATA__\s*=\s*(\{.+?\})\s*;?\s*</script>', html, re.DOTALL)
    if json_match:
        import json
        try:
            data = json.loads(json_match.group(1))
            data_str = json.dumps(data).lower()

            # Check if IMAX appears in showtime-related keys
            # Look for imax near "shows", "screentype", "format" etc.
            imax_in_shows = bool(re.search(
                r'"(?:screentype|screenformat|format|screenname)"\s*:\s*"[^"]*imax[^"]*"',
                data_str
            ))
            if imax_in_shows:
                imax_found = True
                imax_details = ["IMAX (from showtime data)"]
                print("   Found IMAX in __NEXT_DATA__ showtime JSON")
        except Exception as e:
            print(f"   ⚠️  JSON parse failed: {e}")

    # Fallback: look for IMAX inside a <select> or booking widget section
    # BMS often has a section like: <div class="format-selector">...IMAX...</div>
    if not imax_found:
        # Find content between booking-related divs
        booking_section = re.search(
            r'(?:format-selector|screen-type|show-format|cinemaFilters|filterFormat)'
            r'.{0,5000}?imax',
            html, re.IGNORECASE | re.DOTALL
        )
        if booking_section:
            imax_found = True
            imax_details = ["IMAX (from booking filter section)"]
            print("   Found IMAX in booking filter section")

    return imax_found, imax_details


def extract_movie_name(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip().split("|")[0].strip()
        # Clean up common BMS title prefixes
        for prefix in ["Watch ", " Movie Online", " - BookMyShow"]:
            title = title.replace(prefix, "")
        if title.strip():
            return title.strip()
    return "Project Hail Mary"


def send_email(movie_name: str, url: str, imax_details: list):
    venues_html = (
        "<ul>" + "".join(f"<li>{v}</li>" for v in imax_details) + "</ul>"
        if imax_details
        else "<p>IMAX screens detected — check BookMyShow for full venue list.</p>"
    )

    subject = f"🎬 IMAX Booking OPEN — {movie_name} | Book Now!"
    body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <h2 style="color:#e63946;">🎬 IMAX Tickets Are Live!</h2>
  <p><b>IMAX</b> bookings for <b>{movie_name}</b> are now open on BookMyShow.</p>
  <h3>🏟️ IMAX Screens Available:</h3>
  {venues_html}
  <br>
  <a href="{url}"
     style="background:#e63946;color:white;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:bold;font-size:16px;">
    👉 Book IMAX Tickets Now
  </a>
  <br><br>
  <p style="color:#888;font-size:12px;">⚡ Act fast — IMAX seats sell out in minutes!</p>
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

    print(f"✅ IMAX alert email sent to {NOTIFY_EMAIL}")


def main():
    print(f"🔍 Checking IMAX availability for: {BMS_URL}")
    print(f"🎟️  Event Code: {EVENT_CODE}")

    imax_found  = False
    imax_venues = []

    # Method 1 — Hit the actual showtime/venue API (most accurate)
    if os.environ.get("SCRAPERAPI_KEY"):
        print("\n📡 Checking showtime API (actual bookable formats)...")
        imax_found, imax_venues = check_imax_via_buytickets_api(EVENT_CODE)
        if imax_found:
            print(f"   🟢 IMAX found in showtime API: {imax_venues}")
        else:
            print("   🔴 IMAX not in showtime API yet")

    # Method 2 — HTML scrape (looks inside showtime JSON, not movie metadata)
    if not imax_found:
        print("\n🌐 Fetching movie page for HTML check...")
        html = fetch_page(BMS_URL)
        movie_name = extract_movie_name(html)
        print(f"🎬 Movie: {movie_name}")
        imax_found, imax_venues = check_imax_via_html(html)
    else:
        html = ""
        movie_name = "Project Hail Mary"

    if imax_found:
        print(f"\n🟢 IMAX booking is OPEN! {imax_venues}")
        send_email(movie_name, BMS_URL, imax_venues)
    else:
        print("\n🔴 IMAX not available yet for booking.")
        print("   (IMAX 2D appears in movie info but is NOT bookable yet)")
        print("   No email sent. Checking again at next scheduled run.")


if __name__ == "__main__":
    main()
