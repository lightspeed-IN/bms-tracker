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
FORMAT       = "IMAX"

# ✅ Working API — no subRegion param
ALL_VENUES_API = (
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
    f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
    f"&eventCode={EVENT_CODE}&regionCode=MUMBAI"
    f"&format=json&date={SHOW_DATE}"
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
    print(f"📡 Checking API for {CINEMA_CODE} + {FORMAT}...")
    try:
        data_str = fetch_page(ALL_VENUES_API)

        # Find the CSWO venue block
        cswo_block = re.search(
            rf'"VenueCode"\s*:\s*"{CINEMA_CODE}".{{0,8000}}?(?="VenueCode"|\Z)',
            data_str, re.DOTALL
        )

        if not cswo_block:
            print(f"   🔴 {CINEMA_CODE} not in API response yet")
            venues = re.findall(r'"VenueCode"\s*:\s*"([^"]+)"', data_str)
            names  = re.findall(r'"VenueName"\s*:\s*"([^"]+)"', data_str)
            print(f"   Venues currently listed: {list(zip(venues[:5], names[:5]))}")
            return False, []

        block = cswo_block.group(0)
        print(f"   ✅ {CINEMA_CODE} found in API!")

        times   = re.findall(r'"ShowTime"\s*:\s*"(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)"', block)
        screens = re.findall(r'"ScreenName"\s*:\s*"([^"]+)"', block)
        formats = re.findall(r'"ScreenFormat"\s*:\s*"([^"]+)"', block)

        print(f"   Screens: {list(set(screens))[:5]}")
        print(f"   Formats: {list(set(formats))[:5]}")
        print(f"   Show times: {times[:8]}")

        block_lower = block.lower()
        is_imax = "imax" in block_lower
        is_4dx  = "4dx" in block_lower

        if times and is_imax:
            print(f"   ✅ IMAX shows confirmed at {CINEMA_NAME}!")
            return True, times
        elif times and not is_imax:
            print(f"   ⚠️  Shows exist ({('4DX' if is_4dx else 'other format')}) but NOT IMAX — not alerting")
        else:
            print(f"   🔴 Venue found but no shows yet")

    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    return False, []


def send_email(show_times: list):
    formatted = sorted(set(show_times))
    times_html = (
        "<ul>" + "".join(f"<li><b>{t}</b></li>" for t in formatted) + "</ul>"
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
  <a href="https://in.bookmyshow.com/movies/mumbai/project-hail-mary/{EVENT_CODE}"
     style="background:#e63946;color:white;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:bold;font-size:16px;">
    👉 Book IMAX Tickets Now
  </a>
  <br><br>
  <p style="color:#888;font-size:12px;">⚡ IMAX seats sell out fast — book now!</p>
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
        print(f"🟢 IMAX SHOWS BOOKABLE! Times: {show_times}")
        send_email(show_times)
    else:
        print(f"🔴 No IMAX shows for {MOVIE_NAME} at {CINEMA_NAME}.")
        print(f"   (4DX may be available but we only alert for IMAX)")


if __name__ == "__main__":
    main()
