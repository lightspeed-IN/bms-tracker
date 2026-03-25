import os
import re
import smtplib
import requests
import time
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
FORMAT       = "IMAX"

# Scrape the cinema page directly — proven most reliable
CINEMA_PAGE_URL = f"https://in.bookmyshow.com/cinemas/mumbai/miraj-cinemas-imax-wadala/buytickets/MCIW/{SHOW_DATE}"


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
    print(f"🌐 Scraping cinema page for {MOVIE_NAME} IMAX...")
    try:
        html = fetch_page(CINEMA_PAGE_URL)
        html_lower = html.lower()

        has_phm  = "project hail mary" in html_lower or EVENT_CODE.lower() in html_lower
        has_imax = "imax" in html_lower

        print(f"   'Project Hail Mary' on page: {has_phm}")
        print(f"   'IMAX' on page: {has_imax}")

        if not has_phm:
            print("   🔴 Project Hail Mary not listed at Miraj IMAX Wadala yet")
            return False, []

        if not has_imax:
            print("   🔴 No IMAX shows on this page yet")
            return False, []

        # Find Project Hail Mary section that contains IMAX within 3000 chars
        phm_positions = [m.start() for m in re.finditer(r'project hail mary', html_lower)]
        for pos in phm_positions:
            window      = html_lower[pos:pos+3000]
            window_orig = html[pos:pos+3000]
            if "imax" in window:
                times = re.findall(
                    r'\b((?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM))\b',
                    window_orig
                )
                if times:
                    print(f"   ✅ Project Hail Mary IMAX section found! Times: {times[:6]}")
                    return True, times

        print("   🔴 IMAX mentioned on page but not linked to Project Hail Mary yet")
        return False, []

    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        return False, []


def send_email(show_times: list):
    formatted = sorted(set(show_times))
    times_html = (
        "<ul>" + "".join(f"<li><b>{t}</b></li>" for v in formatted for t in [v]) + "</ul>"
        if formatted else "<p>Check BookMyShow for show timings.</p>"
    )
    subject = f"🎬 IMAX Shows OPEN — {MOVIE_NAME} at {CINEMA_NAME}!"
    body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <h2 style="color:#e63946;">🎬 IMAX Tickets Are Live!</h2>
  <p><b>IMAX</b> shows for <b>{MOVIE_NAME}</b> are now bookable at <b>{CINEMA_NAME}</b>!</p>
  <h3>🕐 Show Timings on 26 Mar 2026:</h3>
  {times_html}
  <br>
  <a href="https://in.bookmyshow.com/cinemas/mumbai/miraj-cinemas-imax-wadala/buytickets/MCIW/{SHOW_DATE}"
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
    print(f"📅 Date: 26 Mar 2026 | Format: {FORMAT}")
    print(f"🎟️  Event: {EVENT_CODE} | Venue: {CINEMA_CODE}\n")

    found, show_times = check_shows()

    print()
    if found:
        print(f"🟢 IMAX SHOWS BOOKABLE! Times: {show_times}")
        send_email(show_times)
    else:
        print(f"🔴 No IMAX shows for {MOVIE_NAME} at {CINEMA_NAME} yet.")
        print("   Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
