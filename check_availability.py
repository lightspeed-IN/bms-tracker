import os
import re
import smtplib
import requests
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG (set these as GitHub Secrets) ────────────────────────────────────
BMS_URL      = os.environ.get("BMS_URL", "https://in.bookmyshow.com/movies/mumbai/project-hail-mary/ET00451760")
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
# ─────────────────────────────────────────────────────────────────────────────

EVENT_CODE = BMS_URL.rstrip("/").split("/")[-1]   # ET00451760

IMAX_KEYWORDS = ["imax", "imax 3d", "imax 2d", "imax laser"]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept":         "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


# ─── METHOD 1: ScrapingBee free proxy (100 free calls/month) ─────────────────
def fetch_via_scrapingbee(url: str) -> str:
    api_key = os.environ.get("SCRAPINGBEE_KEY", "")
    if not api_key:
        raise Exception("No SCRAPINGBEE_KEY set")
    resp = requests.get(
        "https://app.scrapingbee.com/api/v1/",
        params={
            "api_key":        api_key,
            "url":            url,
            "render_js":      "false",
            "country_code":   "in",
        },
        timeout=30,
    )
    print(f"   ScrapingBee HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.text


# ─── METHOD 2: ScraperAPI free proxy (1000 free calls/month) ─────────────────
def fetch_via_scraperapi(url: str) -> str:
    api_key = os.environ.get("SCRAPERAPI_KEY", "")
    if not api_key:
        raise Exception("No SCRAPERAPI_KEY set")
    resp = requests.get(
        "http://api.scraperapi.com/",
        params={
            "api_key":      api_key,
            "url":          url,
            "country_code": "in",
        },
        timeout=30,
    )
    print(f"   ScraperAPI HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.text


# ─── METHOD 3: AllOrigins CORS proxy (free, no key needed) ───────────────────
def fetch_via_allorigins(url: str) -> str:
    import urllib.parse
    proxy = f"https://api.allorigins.win/get?url={urllib.parse.quote(url)}"
    resp  = requests.get(proxy, timeout=20)
    print(f"   AllOrigins HTTP {resp.status_code}")
    resp.raise_for_status()
    data = resp.json()
    return data.get("contents", "")


# ─── METHOD 4: Direct request (sometimes works depending on runner IP) ────────
def fetch_direct(url: str) -> str:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    session.get("https://in.bookmyshow.com/", timeout=15)   # get cookies first
    resp = session.get(url, timeout=15)
    print(f"   Direct HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def fetch_page(url: str) -> str:
    """Try multiple methods in order until one works."""
    methods = []

    if os.environ.get("SCRAPINGBEE_KEY"):
        methods.append(("ScrapingBee",  lambda: fetch_via_scrapingbee(url)))
    if os.environ.get("SCRAPERAPI_KEY"):
        methods.append(("ScraperAPI",   lambda: fetch_via_scraperapi(url)))

    methods.append(("AllOrigins",   lambda: fetch_via_allorigins(url)))
    methods.append(("Direct",       lambda: fetch_direct(url)))

    last_error = None
    for name, fn in methods:
        try:
            print(f"   Trying {name}...")
            html = fn()
            if html and len(html) > 500:
                print(f"   ✅ {name} succeeded ({len(html)} chars)")
                return html
            else:
                print(f"   ⚠️  {name} returned empty/short response")
        except Exception as e:
            print(f"   ❌ {name} failed: {e}")
            last_error = e
            time.sleep(2)

    raise Exception(f"All fetch methods failed. Last error: {last_error}")


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

    print("\n🌐 Fetching movie page...")
    html = fetch_page(BMS_URL)
    movie_name = extract_movie_name(html)
    print(f"🎬 Movie: {movie_name}")

    imax_found, imax_venues = check_imax_in_html(html)

    if imax_found:
        print(f"🟢 IMAX booking is OPEN! Details: {imax_venues}")
        send_email(movie_name, BMS_URL, imax_venues)
    else:
        print("🔴 IMAX not available yet (4DX/MX4D may be open, but not IMAX).")
        print("   No email sent. Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
