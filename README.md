# 🎬 BookMyShow IMAX Tracker

Get an **automatic email the moment IMAX booking opens** for any movie on BookMyShow — runs every 30 minutes in the cloud for free. No server, no laptop needed.

> Built for Mumbai but works for any city on BookMyShow!

---

## ✨ How It Works

1. GitHub runs the script every 30 minutes automatically
2. It checks if IMAX is actually bookable (not just listed)
3. **No IMAX yet** → does nothing, checks again in 30 min
4. **IMAX opens** → sends you an email instantly 🎉

---

## 🚀 Setup Guide (5 minutes)

### Step 1 — Fork this repo
Click the **Fork** button at the top right of this page → **Create fork**

---

### Step 2 — Get a free ScraperAPI key
BookMyShow blocks cloud servers, so we use ScraperAPI to get around it.

1. Go to **[scraperapi.com](https://scraperapi.com)** → Sign up free
2. Copy your **API Key** from the dashboard
> Free tier gives 1000 calls/month — enough for ~3 weeks of 30-min checks

---

### Step 3 — Get your Gmail App Password
> You need this because Gmail blocks scripts from using your regular password.

1. Go to **[myaccount.google.com](https://myaccount.google.com)** → **Security**
2. Make sure **2-Step Verification** is ON
3. Search **"App Passwords"** at the top → Create one (name it anything)
4. Copy the **16-character password** shown — save it immediately!

---

### Step 4 — Find your movie URL
1. Go to **[in.bookmyshow.com](https://in.bookmyshow.com)**
2. Search for your movie → open its page
3. Copy the full URL, e.g:
```
https://in.bookmyshow.com/movies/mumbai/project-hail-mary/ET00451760
```
> Change `mumbai` to your city if needed!

---

### Step 5 — Add your secrets
In your forked repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add all 5 secrets:

| Secret Name | Value |
|---|---|
| `BMS_URL` | Your BookMyShow movie URL from Step 4 |
| `GMAIL_USER` | Your Gmail address e.g. `you@gmail.com` |
| `GMAIL_PASS` | The 16-char App Password from Step 3 |
| `NOTIFY_EMAIL` | Email to receive the alert (can be same Gmail) |
| `SCRAPERAPI_KEY` | Your ScraperAPI key from Step 2 |

---

### Step 6 — Enable Actions & Test
1. Go to your forked repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. Click **BookMyShow Availability Tracker** → **Run workflow** → **Run workflow**
4. Wait ~30 seconds → click the run → expand **"Run availability check"**

**You should see:**
```
✅ ScraperAPI succeeded
🎬 Movie: Your Movie Name
🔴 IMAX not available yet for booking.
   No email sent. Checking again at next scheduled run.
```
That means everything is working perfectly — just wait for the email!

---

## 📧 What the email looks like

When IMAX opens, you'll get a nicely formatted email with:
- Movie name
- IMAX venues available
- A big **"Book IMAX Tickets Now"** button linking directly to BookMyShow

---

## ❓ FAQ

**Will it spam me with emails?**
No — it only sends when IMAX is detected as bookable. Once sent, you can disable the workflow from the Actions tab.

**Can I track a different movie or city?**
Yes! Just update the `BMS_URL` secret to any BookMyShow movie URL from any city.

**Can I track multiple movies at once?**
Yes — duplicate `.github/workflows/tracker.yml`, give it a new name, and add a new set of secrets (e.g. `BMS_URL_2`, `SCRAPERAPI_KEY_2` etc.)

**GitHub paused my workflow — why?**
GitHub auto-pauses scheduled workflows on repos with no activity after 60 days. Just go to Actions → re-enable it.

**ScraperAPI ran out of free calls — what now?**
Sign up for a new free account, or upgrade to their $49/month plan. Alternatively reduce check frequency in `tracker.yml` from `*/30` to `*/60` (every 60 min).

---

## 🛑 Disable after booking
Once you've booked your tickets:
1. **Actions** tab → **BookMyShow Availability Tracker**
2. Click **"..."** → **Disable workflow**

---

## 🙌 Credits
Built with ❤️ using Python, GitHub Actions and ScraperAPI.
Originally made to catch IMAX tickets for Project Hail Mary in Mumbai!
