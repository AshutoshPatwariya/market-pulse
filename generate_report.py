#!/usr/bin/env python3
"""
Market Pulse — Ashutosh
Daily report generator: fetches NSE prices via yfinance + calls Gemini API
Runs via GitHub Actions every weekday at 8 AM IST (2:30 AM UTC)
"""

import json
import os
import sys
from datetime import datetime, date
import pytz

# ── Install deps if needed ──────────────────────────────────────────────────
try:
    import yfinance as yf
    import google.generativeai as genai
    import requests
except ImportError:
    os.system("pip install yfinance google-generativeai requests --quiet")
    import yfinance as yf
    import google.generativeai as genai
    import requests

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
TODAY = now_ist.strftime("%d %B %Y")
WEEKDAY = now_ist.strftime("%A")

# ── NSE tickers (your holdings + key indices) ───────────────────────────────
HOLDINGS_TICKERS = {
    "ADANIGAS.NS":   {"name": "Adani Total Gas", "qty": 14, "avg": 931.67},
    "ETERNAL.NS":    {"name": "Eternal (Zomato)", "qty": 70, "avg": 251.62},
    "COALINDIA.NS":  {"name": "Coal India",       "qty": 20, "avg": 416.35},
    "ICICIBANK.NS":  {"name": "ICICI Bank",        "qty": 2,  "avg": 1391.20},
    "IDFCFIRSTB.NS": {"name": "IDFC First Bank",   "qty": 30, "avg": 70.03},
    "IOC.NS":        {"name": "Indian Oil Corp",   "qty": 14, "avg": 160.11},
    "IRFC.NS":       {"name": "IRFC",              "qty": 82, "avg": 146.99},
    "ITC.NS":        {"name": "ITC",               "qty": 29, "avg": 340.50},
    "NHPC.NS":       {"name": "NHPC",              "qty": 91, "avg": 94.74},
    "RELIANCE.NS":   {"name": "Reliance Industries","qty": 6,  "avg": 1393.76},
    "ROYALORCHID.NS":{"name": "Royal Orchid Hotels","qty": 10, "avg": 415.00},
    "SWIGGY.NS":     {"name": "Swiggy",            "qty": 1,  "avg": 419.90},
    "TATAMOTORS.NS": {"name": "Tata Motors",       "qty": 14, "avg": 493.81},
    "HINDUCOPER.NS": {"name": "Hindustan Copper",  "qty": 6,  "avg": 532.60},
    "BLSINTL.NS":    {"name": "BLS International", "qty": 6,  "avg": 314.00},
}

WATCH_TICKERS = {
    "^NSEI":       "Nifty 50",
    "^BSESN":      "Sensex",
    "GC=F":        "Gold Futures",
    "SI=F":        "Silver Futures",
    "CL=F":        "Crude Oil",
    "USDINR=X":    "USD/INR",
}

# ── 1. Fetch live prices ─────────────────────────────────────────────────────
def fetch_prices():
    all_tickers = list(HOLDINGS_TICKERS.keys()) + list(WATCH_TICKERS.keys())
    data = yf.download(all_tickers, period="2d", interval="1d",
                       group_by="ticker", auto_adjust=True, progress=False)

    prices = {}
    for ticker in all_tickers:
        try:
            if len(all_tickers) == 1:
                df = data
            else:
                df = data[ticker]
            if df is not None and len(df) >= 1:
                latest = df["Close"].dropna().iloc[-1]
                prev   = df["Close"].dropna().iloc[-2] if len(df["Close"].dropna()) >= 2 else latest
                prices[ticker] = {
                    "price": round(float(latest), 2),
                    "prev":  round(float(prev), 2),
                    "change": round(float(latest - prev), 2),
                    "change_pct": round(float((latest - prev) / prev * 100), 2)
                }
        except Exception:
            prices[ticker] = None

    return prices


# ── 2. Build holdings P&L from live prices ──────────────────────────────────
def build_holdings(prices):
    holdings = []
    total_invested = 0
    total_current = 0

    for ticker, meta in HOLDINGS_TICKERS.items():
        p = prices.get(ticker)
        cmp = p["price"] if p else meta["avg"]
        buy_val = round(meta["qty"] * meta["avg"], 2)
        curr_val = round(meta["qty"] * cmp, 2)
        pnl = round(curr_val - buy_val, 2)
        pnl_pct = round(pnl / buy_val * 100, 2)

        total_invested += buy_val
        total_current += curr_val

        holdings.append({
            "ticker": ticker.replace(".NS", ""),
            "name": meta["name"],
            "qty": meta["qty"],
            "avg": meta["avg"],
            "cmp": cmp,
            "buy_value": buy_val,
            "curr_value": curr_val,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "change_today": p["change"] if p else 0,
            "change_pct_today": p["change_pct"] if p else 0
        })

    holdings.sort(key=lambda x: x["pnl"])
    return holdings, round(total_invested, 2), round(total_current, 2)


# ── 3. Call Gemini API for AI analysis ──────────────────────────────────────
def call_gemini(prices, holdings, total_invested, total_current):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")

    nifty  = prices.get("^NSEI", {}) or {}
    crude  = prices.get("CL=F", {})  or {}
    gold   = prices.get("GC=F", {})  or {}
    usdinr = prices.get("USDINR=X", {}) or {}

    holdings_summary = "\n".join([
        f"- {h['name']}: CMP ₹{h['cmp']}, Avg ₹{h['avg']}, P&L {h['pnl_pct']:+.1f}% (₹{h['pnl']:+,.0f})"
        for h in holdings
    ])

    prompt = f"""You are a senior Indian stock market analyst with 20+ years experience.
Today is {TODAY} ({WEEKDAY}). Generate a complete daily market intelligence report.

LIVE MARKET DATA:
- Nifty 50: {nifty.get('price', 'N/A')} ({nifty.get('change_pct', 0):+.2f}%)
- Crude Oil: ${crude.get('price', 'N/A')}/bbl ({crude.get('change_pct', 0):+.2f}%)
- Gold: ${gold.get('price', 'N/A')}/oz
- USD/INR: ₹{usdinr.get('price', 'N/A')}

CURRENT PORTFOLIO (Ashutosh Patwariya):
Total Invested: ₹{total_invested:,.0f}
Current Value: ₹{total_current:,.0f}
Overall P&L: ₹{total_current - total_invested:+,.0f} ({(total_current - total_invested)/total_invested*100:+.1f}%)

Holdings:
{holdings_summary}

Generate a JSON report (no markdown, pure JSON) with this exact structure:
{{
  "market_mood": {{
    "score": <0-100 where 0=extreme fear, 100=extreme greed>,
    "label": "<EXTREME FEAR | FEAR | NEUTRAL | GREED | EXTREME GREED>",
    "color": "<red | orange | yellow | lightgreen | green>",
    "description": "<1 sentence why>"
  }},
  "macro_outlook": {{
    "headline": "<punchy 8-10 word headline for today>",
    "summary": "<3-4 sentences. Be specific with today's data. Reference crude, FII, INR, Nifty PE.>",
    "key_points": ["<5 bullet points with specific data>"],
    "short_term": "<1 sentence bearish/bullish with reason>",
    "medium_term": "<1 sentence>",
    "long_term": "<1 sentence>"
  }},
  "fii_dii": {{
    "fii_net": <estimated net FII flow in crores, negative=selling>,
    "dii_net": <estimated net DII flow in crores>,
    "fii_label": "<NET SELLERS | NET BUYERS>",
    "dii_label": "<NET SELLERS | NET BUYERS>",
    "signal": "<1 actionable sentence>"
  }},
  "risk_alerts": [
    {{"stock": "<name>", "alert": "<specific actionable alert>", "severity": "<low|medium|high>"}}
  ],
  "sector_strategy": [
    {{"sector": "<name>", "war_impact": "<POSITIVE|NEUTRAL|NEGATIVE>", "short_term": "<Outperform|In-line|Underperform>", "long_term": "<same>", "strategy": "<OVERWEIGHT|NEUTRAL|UNDERWEIGHT|BUY ON DIPS|AVOID>", "key_risk": "<short risk>"}}
  ],
  "buy_recommendations": [
    {{"ticker": "<NSE symbol>", "name": "<full name>", "reason": "<2-3 sentences specific to today>", "entry": "<specific entry strategy>", "risk": "<LOW|MODERATE|HIGH>", "horizon": "<SHORT|MEDIUM|LONG-TERM>", "target": "<specific price or % target>", "type": "<safe_haven|compounder|tactical|defensive|index|mutual_fund>"}}
  ],
  "top_trades": [
    {{"rank": 1, "stock": "<name>", "call": "<BUY|SELL|ADD|HOLD>", "reason": "<specific to today's data>", "horizon": "<timeframe>"}}
  ],
  "ipo_events": [
    {{"date": "<DD Mon>", "event": "<name>", "impact": "<HIGH|MEDIUM|LOW>", "note": "<why it matters>"}}
  ],
  "portfolio_insights": {{
    "summary": "<2-3 sentences on overall portfolio health today>",
    "best_hold": "<which stock to hold strongest today and why>",
    "action_today": "<1 specific thing to do TODAY with the portfolio>"
  }}
}}

Be data-driven. Reference today's specific numbers. Give 8 buy recommendations and 3 top trades. Give 10 sectors. Give 4 risk alerts for the worst performing holdings. Give 4 upcoming events. Be specific, not generic.
Return ONLY valid JSON — no markdown fences, no explanation before or after."""

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=4000)
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── 4. Assemble final report ─────────────────────────────────────────────────
def build_report():
    print(f"[{now_ist.strftime('%H:%M:%S')} IST] Fetching NSE prices...")
    prices = fetch_prices()

    nifty_data = prices.get("^NSEI", {})
    sensex_data = prices.get("^BSESN", {})

    print("Building holdings P&L...")
    holdings, total_invested, total_current = build_holdings(prices)

    print("Calling Gemini API for AI analysis...")
    ai = call_gemini(prices, holdings, total_invested, total_current)

    report = {
        "generated_at": now_ist.isoformat(),
        "market_date": TODAY,
        "market_open": True,
        "nifty": {
            "price": nifty_data.get("price", 0),
            "change": nifty_data.get("change", 0),
            "change_pct": nifty_data.get("change_pct", 0),
            "pe": 18.4,
            "mood": "BEARISH" if nifty_data.get("change_pct", 0) < -0.5 else "BULLISH" if nifty_data.get("change_pct", 0) > 0.5 else "NEUTRAL"
        },
        "sensex": {
            "price": sensex_data.get("price", 0),
            "change": sensex_data.get("change", 0),
            "change_pct": sensex_data.get("change_pct", 0)
        },
        "crude": {
            "price": prices.get("CL=F", {}).get("price", 0),
            "change_pct": prices.get("CL=F", {}).get("change_pct", 0)
        },
        "gold": {
            "price": prices.get("GC=F", {}).get("price", 0),
            "change_pct": prices.get("GC=F", {}).get("change_pct", 0)
        },
        "usdinr": prices.get("USDINR=X", {}).get("price", 0),
        "holdings": holdings,
        "total_invested": total_invested,
        "total_current": total_current,
        "total_pnl": round(total_current - total_invested, 2),
        "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2),
        **ai
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"✅ Report saved to data/report.json")
    print(f"   Nifty: {report['nifty']['price']} ({report['nifty']['change_pct']:+.2f}%)")
    print(f"   Portfolio: ₹{total_current:,.0f} ({report['total_pnl_pct']:+.1f}%)")


if __name__ == "__main__":
    build_report()
