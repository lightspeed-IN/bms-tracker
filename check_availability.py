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

CINEMA_PAGE_URL = f"https://in.bookmyshow.com/cinemas/mumbai/miraj-cinemas-imax-wadala/buytickets/MCIW/{SHOW_DATE}"

# Format labels BMS uses for IMAX — must appear RIGHT NEXT TO show times
# NOT in the cinema header/name
IMAX_FORMAT_LABELS = ["imax", "imax 2d", "imax 3d", "imax laser"]

# Formats to explicitly ignore — these are NOT what we want
NON_IMAX_FORMATS = ["auromax", "2d", "3d", "4dx", "mx4d", "screenx", "4k"]


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


def extract_movie_blocks(html: str) -> list:
    """
    Split the cinema page into per-movie blocks.
    Each block starts at a movie title and ends at the next movie title.
    Returns list of (movie_title, block_text) tuples.
    """
    # BMS cinema pages have movie titles in a recognizable pattern
    # Split by movie title markers — look for patterns like:
    # "Movie Title (A)" or "Movie Title (UA)" followed by language/format
    movie_pattern = re.compile(
        r'((?:[A-Z][^\n<]{3,80}?)\s*(?:\([A-Z0-9+]+\))\s*[\r\n])',
        re.MULTILINE
    )

    # Simpler approach: split HTML into sections between show time clusters
    # Find all positions where a movie title appears
    # BMS wraps each movie in a section — find by looking for the movie name pattern in JSON

    # Extract the __NEXT_DATA__ JSON which has clean structured data
    next_data = re.search(
        r'window\.__NEXT_DATA__\s*=\s*({.+?})\s*;?\s*</script>|'
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>({.+?})</script>',
        html, re.DOTALL
    )

    if next_data:
        json_str = next_data.group(1) or next_data.group(2)
        return [("__NEXT_DATA__", json_str)]

    # Fallback: return whole HTML as one block
    return [("__HTML__", html)]


def check_shows() -> tuple:
    print(f"🌐 Scraping cinema page...")
    try:
        html = fetch_page(CINEMA_PAGE_URL)
        html_lower = html.lower()

        # ── Step 1: Find all PHM sections on the page ─────────────────────────
        phm_positions = [m.start() for m in re.finditer(r'project hail mary', html_lower)]
        print(f"   'Project Hail Mary' found at {len(phm_positions)} position(s) on page")

        if not phm_positions:
            print("   🔴 Project Hail Mary not listed at this cinema yet")
            return False, []

        # ── Step 2: For each PHM mention, extract format + show times ─────────
        imax_shows = []

        for pos in phm_positions:
            # Get a window of text after this PHM mention (up to next movie)
            window_end = min(pos + 2000, len(html))
            window      = html[pos:window_end]
            window_lower = window.lower()

            # Extract format labels — BMS shows them as small text under show times
            # They appear as: "IMAX 2D", "AUROMAX", "2D" etc.
            # Look for format labels within first 500 chars of PHM mention
            format_window = window_lower[:500]

            detected_formats = []
            for fmt in IMAX_FORMAT_LABELS:
                if fmt in format_window:
                    detected_formats.append(fmt.upper())
            for fmt in NON_IMAX_FORMATS:
                if fmt in format_window and fmt.upper() not in detected_formats:
                    detected_formats.append(f"[non-IMAX: {fmt.upper()}]")

            # Extract show times from this window
            times = re.findall(
                r'\b((?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM))\b',
                window[:1000]
            )

            print(f"   PHM section → Formats: {detected_formats} | Times: {times[:4]}")

            # Only alert if IMAX format label is detected (not just cinema name)
            has_imax_format = any(
                fmt in format_window
                for fmt in IMAX_FORMAT_LABELS
            )
            # Make sure it's not just "auromax" being mistaken
            # "imax" must appear as standalone word, not inside "auromax" etc.
            imax_standalone = bool(re.search(
                r'(?<![a-z])imax(?!\s*[a-z]{3,})',  # imax not preceded/followed by other letters
                format_window
            ))

            if has_imax_format and imax_standalone and times:
                imax_shows.extend(times)
                print(f"   ✅ IMAX format confirmed for Project Hail Mary!")

        if imax_shows:
            return True, imax_shows

        # ── Step 3: Summary ────────────────────────────────────────────────────
        print("   🔴 Project Hail Mary found but no IMAX format label detected")
        print("      (May be showing in 2D/AUROMAX but not IMAX)")
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
    subject = f"🎬 IMAX Shows OPEN — {MOVIE_NAME} at {CINEMA_NAME}!"
    body = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <h2 style="color:#e63946;">🎬 IMAX Tickets Are Live!</h2>
  <p><b>IMAX</b> shows for <b>{MOVIE_NAME}</b> are now bookable at <b>{CINEMA_NAME}</b>!</p>
  <h3>🕐 Show Timings on 26 Mar 2026:</h3>
  {times_html}
  <br>
  <a href="{CINEMA_PAGE_URL}"
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
    print(f"📅 Date: {SHOW_DATE} | Format: IMAX only")
    print(f"🎟️  Event: {EVENT_CODE} | Venue: {CINEMA_CODE}\n")

    found, show_times = check_shows()

    print()
    if found:
        print(f"🟢 IMAX SHOWS BOOKABLE! Times: {show_times}")
        send_email(show_times)
    else:
        print(f"🔴 No IMAX shows for {MOVIE_NAME} at {CINEMA_NAME} yet.")
        print("   (2D/AUROMAX may be open but we only alert for IMAX)")
        print("   Will check again at next scheduled run.")


if __name__ == "__main__":
    main()
