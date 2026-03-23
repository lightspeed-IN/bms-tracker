import os
import re
import smtplib
import requests
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

IMAX_KEYWORDS = ["imax", "imax 3d", "imax 2d", "imax laser"]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language":           "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
    "Sec-Fetch-User":            "?1",
    "Cache-Control":             "max-age=0",
}


def make_session() -> requests.Session:
    """Create a session that mimics a real browser, with cookies from homepage."""
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    try:
        # Visit homepage first so BMS sets cookies — avoids 403
        s.get("https://in.bookmyshow.com/", timeout=15)
        print("🍪 Session cookies acquired from BMS homepage")
    except Exception as e:
        print(f"⚠️  Could not fetch homepage for cookies: {e}")
    return s


def fetch_page(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=15)
    print(f"   HTTP {resp.status_code} for {url}")
    if resp.status_code == 403:
        raise Exception(
            "403 Forbidden — BookMyShow is blocking the request. "
            "This can happen on cloud IPs. Try re-running in a few minutes."
        )
    resp.raise_for_status()
    return resp.text


def extract_movie_name(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip().split("|")[0].strip()
        if title:
            return title
    return "Project Hail Mary"


def check_imax_in_html(html: str) -> tuple:
    html_lower = html.lower()
    found_formats = []

    for kw in IMAX_KEYWORDS:
        if kw in html_lower:
            found_formats.append(kw.upper())

    if not found_formats:
        return False, []

    booking_patterns = [
        r"book\s*tickets", r"buy\s*tickets",
        r"book\s*now", r"booknow", r"select\s*cinema"
    ]
    booking_open = any(re.search(p, html_lower) for p in booking_patterns)

    imax_positions    = [m.start() for m in re.finditer(r"imax", html_lower)]
    booking_positions = [m.start() for m in re.finditer(
        r"book(?:now|tickets|\s*tickets|\s*now)", html_lower)]

    imax_near_booking = any(
        abs(ip - bp) < 3000
        for ip in imax_positions
        for bp in booking_positions
    )

    return (booking_open and imax_near_booking), found_formats


def check_imax_via_api(session: requests.Session, event_code: str) -> tuple:
    api_url = (
        f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
        f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
        f"&eventCode={event_code}&regionCode={CITY_CODE}"
        f"&subRegion={CITY_CODE}&format=json&date="
    )
    try:
        resp = session.get(api_url, timeout=15)
        print(f"   API HTTP {resp.status_code}")
        if resp.status_code != 200:
            return False, []
        data = resp.json()

        imax_venues = []
        venues = data.get("ShowDetails", []) or data.get("BookMyShow", {}).get("ShowDetails", [])
        for venue in venues:
            venue_name = venue.get("VenueName", "")
            for show in (venue.get("ShowDetails") or []):
                screen_name = show.get("ScreenName", "").lower()
                format_name = show.get("ScreenFormat", "").lower()
                if "imax" in screen_name or "imax" in format_name:
                    imax_venues.append(f"{venue_name} — {show.get('ScreenName', 'IMAX')}")

        return len(imax_venues) > 0, imax_venues

    except Exception as e:
        print(f"⚠️  API check failed: {e}")
        return False, []


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

    session = make_session()

    # Method 1 — BookMyShow internal API
    print("\n📡 Trying BookMyShow API...")
    imax_found, imax_venues = check_imax_via_api(session, EVENT_CODE)

    # Method 2 — HTML scrape fallback
    print("\n🌐 Fetching movie page...")
    html = fetch_page(session, BMS_URL)
    movie_name = extract_movie_name(html)
    print(f"🎬 Movie: {movie_name}")

    if not imax_found:
        print("🔎 API inconclusive, checking HTML for IMAX...")
        imax_found, imax_venues = check_imax_in_html(html)

    if imax_found:
        print(f"🟢 IMAX booking is OPEN! Details: {imax_venues}")
        send_email(movie_name, BMS_URL, imax_venues)
    else:
        print("🔴 IMAX not available yet (4DX/MX4D may be open, but not IMAX).")
        print("   No email sent. Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
