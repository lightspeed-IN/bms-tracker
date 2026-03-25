import os
import re
import requests
import time

GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]

EVENT_CODE = "ET00451760"
SHOW_DATE  = "20260326"

# Try multiple API endpoints to find which one has venue data
URLS = [
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event?appCode=MOBAND2&appVersion=14.3.4&language=en&eventCode={EVENT_CODE}&regionCode=MUMBAI&subRegion=MUMBAI&format=json&date={SHOW_DATE}",
    f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event?appCode=MOBAND2&appVersion=14.3.4&language=en&eventCode={EVENT_CODE}&regionCode=MUMBAI&format=json&date={SHOW_DATE}",
    f"https://in.bookmyshow.com/buytickets/{EVENT_CODE}/cinema/CSWO/{SHOW_DATE}",
    f"https://in.bookmyshow.com/movies/mumbai/project-hail-mary/{EVENT_CODE}",
    f"https://in.bookmyshow.com/cinemas/mumbai/cinepolis-nexus-seawoods-nerul-navi-mumbai/buytickets/CSWO/{SHOW_DATE}",
]


def fetch(url):
    api_key = os.environ.get("SCRAPERAPI_KEY", "")
    resp = requests.get(
        "http://api.scraperapi.com/",
        params={"api_key": api_key, "url": url, "country_code": "in"},
        timeout=30,
    )
    return resp.status_code, resp.text


for url in URLS:
    print(f"\n🔍 URL: {url[:80]}...")
    try:
        status, html = fetch(url)
        print(f"   Status: {status} | Size: {len(html)} chars")

        # Check for venue codes
        venues = re.findall(r'"VenueCode"\s*:\s*"([^"]+)"', html)
        venue_names = re.findall(r'"VenueName"\s*:\s*"([^"]+)"', html)
        show_times = re.findall(r'"ShowTime"\s*:\s*"([^"]+)"', html)
        formats = re.findall(r'"ScreenFormat"\s*:\s*"([^"]+)"', html)

        # Check for CSWO specifically
        has_cswo = "CSWO" in html or "cswo" in html.lower()
        has_4dx  = "4dx" in html.lower() or "4DX" in html
        has_imax = "imax" in html.lower()

        print(f"   Venues: {list(zip(venues[:5], venue_names[:5]))}")
        print(f"   Show times: {show_times[:5]}")
        print(f"   Formats: {list(set(formats))[:5]}")
        print(f"   Has CSWO: {has_cswo} | Has 4DX: {has_4dx} | Has IMAX: {has_imax}")

        # Print first 500 chars to see structure
        print(f"   Preview: {html[:300].strip()}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
    time.sleep(2)

print("\n✅ Debug complete")
