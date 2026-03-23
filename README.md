# 🎬 BookMyShow Booking Alert — GitHub Actions

Get an **email alert the moment booking opens** for any movie on BookMyShow.
Runs automatically in the cloud every 30 minutes — no server, no cost.

---

## ⚙️ Setup (5 minutes)

### Step 1 — Create a GitHub Repository
1. Go to [github.com](https://github.com) → **New repository**
2. Name it anything e.g. `bms-tracker`
3. Set it to **Private** (recommended)
4. Upload these 3 files:
   - `check_availability.py`
   - `requirements.txt`
   - `.github/workflows/tracker.yml`

---

### Step 2 — Create a Gmail App Password
> You need this because Gmail blocks direct password login for scripts.

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** (if not already)
3. Search for **"App Passwords"** → Create one (name it "BMS Tracker")
4. Copy the 16-character password shown (e.g. `abcd efgh ijkl mnop`)

---

### Step 3 — Add GitHub Secrets
1. In your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add all 4:

| Secret Name    | Value                                         |
|----------------|-----------------------------------------------|
| `BMS_URL`      | Full BookMyShow movie URL (see below)         |
| `GMAIL_USER`   | Your Gmail address e.g. `you@gmail.com`       |
| `GMAIL_PASS`   | The 16-char App Password from Step 2          |
| `NOTIFY_EMAIL` | Email to receive alerts (can be same as above)|

#### How to find `BMS_URL`
Go to BookMyShow, search for your movie, open its page — copy the full URL, e.g.:
```
https://in.bookmyshow.com/mumbai/movies/pushpa-2/ET00380707
```

---

### Step 4 — Enable Actions
1. Go to your repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. Click **Run workflow** → **Run workflow** to test it immediately

---

## 📬 How It Works

- GitHub runs the script **every 30 minutes**, automatically
- It fetches your BookMyShow movie page and checks if "Book Tickets" button is live
- The moment booking opens → **you get an email**
- If booking isn't open yet → nothing happens, it checks again in 30 min

---

## ❓ FAQ

**Will it spam me?**
No — it sends an email only when the booking button is detected. But once open, every 30-min run will re-trigger. You can disable the workflow after booking.

**What if GitHub Actions stops the workflow?**
GitHub pauses scheduled workflows on inactive repos after 60 days. Just re-enable from the Actions tab.

**Can I track multiple movies?**
Duplicate the workflow file with a different name and add separate secrets per movie.

---

## 🛑 Disable After Booking
Once you've booked your tickets:
1. Go to **Actions** → select the workflow → **"..."** menu → **Disable workflow**
