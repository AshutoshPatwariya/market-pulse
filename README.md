# 📊 Market Pulse — Ashutosh
### AI-Powered Daily Indian Stock Market Intelligence Dashboard

Live website that auto-refreshes every weekday at 8:00 AM IST with:
- 📈 Live NSE/BSE prices via Yahoo Finance
- 🤖 AI-generated macro outlook, sector strategy, buy recommendations
- 💼 Live portfolio P&L with daily updates
- 📂 Excel/CSV upload for instant AI portfolio analysis
- ⚠️ Daily risk alerts on your specific holdings
- 🏆 Top 3 trades of the day
- 📅 Market events calendar

---

## 🚀 One-Time Setup (30 minutes)

### Step 1 — Get Your OpenAI API Key (5 min)

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in / sign up with your email
3. Click **"Create new secret key"** → name it "market-pulse"
4. **Copy the key** (starts with `sk-...`) — you'll need it in Step 4

> 💰 **Cost**: GPT-4o-mini costs ~$0.00015 per 1K input tokens. One daily report ≈ ~$0.002/day = ~₹5/month. Extremely cheap.

---

### Step 2 — Create GitHub Repository (5 min)

1. Go to [github.com](https://github.com) → Sign in
2. Click **"New repository"** (green button, top right)
3. Name it: `market-pulse`
4. Set to **Public** (required for free GitHub Pages) or Private
5. Click **"Create repository"**

---

### Step 3 — Push This Code to GitHub (5 min)

Open Terminal (Mac/Linux) or Command Prompt (Windows) and run:

```bash
# Navigate to this folder
cd path/to/market-pulse

# Initialize git
git init
git add .
git commit -m "🚀 Initial Market Pulse setup"

# Connect to your GitHub repo (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/market-pulse.git
git branch -M main
git push -u origin main
```

---

### Step 4 — Add Your API Key to GitHub Secrets (3 min)

1. Go to your GitHub repo → **Settings** tab
2. Left sidebar → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Name: `OPENAI_API_KEY`
5. Value: paste your API key from Step 1 (starts with `AIza...`)
6. Click **"Add secret"**

---

### Step 5 — Deploy to Vercel (10 min)

1. Go to [vercel.com](https://vercel.com) → Sign up with GitHub
2. Click **"Add New Project"**
3. Import your `market-pulse` GitHub repository
4. Leave all settings as default
5. Click **"Deploy"**
6. Wait ~30 seconds → **Your site is live!** 🎉

Vercel gives you a URL like: `https://market-pulse-ashutosh.vercel.app`

Every time GitHub Actions pushes an update (8 AM daily), Vercel **automatically rebuilds** your site within 30 seconds.

---

### Step 6 — Test the Daily Report (2 min)

1. Go to your GitHub repo → **Actions** tab
2. Click **"Daily Market Pulse Report"** workflow
3. Click **"Run workflow"** → **"Run workflow"** (manual trigger)
4. Watch it run — takes about 60 seconds
5. Check `data/report.json` in your repo — it should be updated
6. Your Vercel site refreshes automatically

---

## 📂 Uploading New Holdings

When you buy/sell stocks:
1. Export your holdings from your broker (Zerodha/Groww/Upstox/Angel One)
2. Go to your live website → **"Upload Holdings"** tab
3. Enter your Anthropic API key (one-time per session)
4. Upload the Excel/CSV file
5. Get instant AI analysis of your updated portfolio

**Also update `scripts/generate_report.py`** — find the `HOLDINGS_TICKERS` dictionary and update it with your new holdings so the daily 8 AM report reflects your current portfolio.

---

## 🔧 Customization

### Add/Remove Holdings
Edit `scripts/generate_report.py`, find `HOLDINGS_TICKERS`:
```python
HOLDINGS_TICKERS = {
    "NEWSTOCK.NS": {"name": "New Stock Name", "qty": 10, "avg": 500.00},
    # ... add your holdings here
}
```
NSE stocks: add `.NS` suffix (e.g., `INFY.NS`, `TCS.NS`)
BSE stocks: add `.BO` suffix (e.g., `500325.BO`)

### Change Report Time
Edit `.github/workflows/daily.yml`:
```yaml
- cron: '30 2 * * 1-5'  # 2:30 AM UTC = 8:00 AM IST
```
To change to 9 AM IST, use `30 3 * * 1-5`

### Add NSE Holidays
Edit `scripts/generate_report.py`, find the `holidays` list and add dates.

---

## 📁 File Structure
```
market-pulse/
├── index.html              ← Main website (all sections, live data)
├── data/
│   └── report.json         ← Daily AI report (auto-updated by GitHub Actions)
├── scripts/
│   └── generate_report.py  ← Python: fetches NSE prices + calls Claude API
├── .github/
│   └── workflows/
│       └── daily.yml       ← GitHub Actions: runs at 8AM IST Mon-Fri
├── vercel.json             ← Vercel deployment config
└── README.md               ← This file
```

---

## ❓ Troubleshooting

**GitHub Actions failing?**
- Check Actions tab → click the failed run → read the error log
- Most common: API key not set correctly in Secrets (must be named `OPENAI_API_KEY`)

**Vercel not updating?**
- Vercel auto-deploys on every git push — check the Deployments tab
- If manual: go to Vercel dashboard → your project → "Redeploy"

**NSE prices showing as 0?**
- Yahoo Finance occasionally has issues — the report will show last known values
- This self-corrects the next day

**Upload not working?**
- Make sure you entered your OpenAI API key in the upload section
- The key must start with `AIza`

---

## 💡 Tips

- **Bookmark your Vercel URL** — check it every morning at 8:05 AM IST
- **Manual refresh**: Go to GitHub → Actions → Run workflow anytime you want a fresh report
- **Mobile friendly**: The site works on your phone too
- **Free tier limits**: GitHub Actions gives 2,000 free minutes/month — daily reports use ~2 min/day = ~40 min/month, well within limits

---

*Built with Claude AI · Powered by Anthropic API · Hosted on Vercel*
