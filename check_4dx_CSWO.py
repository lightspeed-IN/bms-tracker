import os
import re
import smtplib
import requests
import time
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

# Scrape the cinema page directly — most reliable source
CINEMA_PAGE_URL = f"https://in.bookmyshow.com/cinemas/mumbai/cinepolis-nexus-seawoods-nerul-navi-mumbai/buytickets/CSWO/{SHOW_DATE}"


def fetch_via_scraperapi(url: str) -> str:
    api_key = os.environ.get("SCRAPERAPI_KEY", "")
    if not api_key:
        raise Exception("No SCRAPERAPI_KEY set")
    resp = requests.get(
        "http://api.scraperapi.com/",
        params={"api_key": api_key, "url": url, "country_code": "in"},
        timeout=30,
    )
    print(f"   HTTP {resp.status_code} ({len(resp.text)} chars)")
    resp.raise_for_status()
    return resp.text


def fetch_page(url: str) -> str:
    for attempt in range(3):
        try:
            html = fetch_via_scraperapi(url)
            if html and len(html) > 500:
                return html
        except Exception as e:
            print(f"   ❌ Attempt {attempt+1} failed: {e}")
            time.sleep(3)
    raise Exception("All fetch attempts failed")


def check_shows() -> tuple:
    print(f"🌐 Scraping cinema page for Project Hail Mary 4DX...")
    try:
        html = fetch_page(CINEMA_PAGE_URL)

        # Find all movie sections on the page
        # Each movie block looks like: "Project Hail Mary" ... "4DX" ... show times
        # Strategy: find "Project Hail Mary" + "4DX" appearing together

        # Split HTML into per-movie sections by looking for movie title anchors
        # BMS cinema page has sections like: <div>...Project Hail Mary...4DX...times...</div>

        html_lower = html.lower()
        has_phm = "project hail mary" in html_lower or EVENT_CODE.lower() in html_lower
        has_4dx = "4dx" in html_lower

        print(f"   'Project Hail Mary' on page: {has_phm}")
        print(f"   '4DX' on page: {has_4dx}")

        if not has_phm:
            print("   🔴 Project Hail Mary not listed at this cinema yet")
            return False, []

        # Find the section with Project Hail Mary AND 4DX together
        # Look for PHM block that contains 4DX within 2000 chars
        phm_positions = [m.start() for m in re.finditer(r'project hail mary', html_lower)]
        show_times = []

        for pos in phm_positions:
            # Get a window around this mention
            window = html_lower[pos:pos+3000]
            if "4dx" in window:
                # Extract times from this window using original case html
                window_orig = html[pos:pos+3000]
                times = re.findall(
                    r'\b((?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM))\b',
                    window_orig
                )
                if times:
                    show_times = times
                    print(f"   ✅ Found Project Hail Mary 4DX section with times: {times[:6]}")
                    return True, show_times

        # Fallback: PHM is on page and 4DX is on page — check if they're close
        if has_phm and has_4dx:
            for phm_pos in phm_positions:
                phm_window = html_lower[max(0,phm_pos-100):phm_pos+2000]
                if "4dx" in phm_window:
                    # Extract all times near this section
                    orig_window = html[max(0,phm_pos-100):phm_pos+2000]
                    times = re.findall(
                        r'\b((?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM))\b',
                        orig_window
                    )
                    if times:
                        show_times = times
                        print(f"   ✅ PHM + 4DX found nearby. Times: {times[:6]}")
                        return True, show_times

        print("   🔴 Project Hail Mary 4DX section not found or no times yet")
        return False, []

    except Exception as e:
        print(f"   ⚠️  Error: {e}")
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


if __name__ == "__main__":
    main()
