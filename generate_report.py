#!/usr/bin/env python3
"""
Market Pulse — Ashutosh
Daily report generator: fetches NSE prices via yfinance + calls Gemini API
Runs via GitHub Actions every weekday at 8 AM IST (2:30 AM UTC)
"""

import json
import os
import re
from datetime import datetime, date
import pytz

# ── Install deps ─────────────────────────────────────────────────────────────
try:
    import yfinance as yf
    from google import genai
    from google.genai import types
except ImportError:
    os.system("pip install yfinance google-genai pytz --quiet")
    import yfinance as yf
    from google import genai
    from google.genai import types

IST     = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
TODAY   = now_ist.strftime("%d %B %Y")
WEEKDAY = now_ist.strftime("%A")

# ── NSE tickers — corrected symbols ─────────────────────────────────────────
HOLDINGS_TICKERS = {
    "ADANIENSOL.NS": {"name": "Adani Total Gas",     "qty": 14, "avg": 931.67},
    "ETERNAL.NS":    {"name": "Eternal (Zomato)",    "qty": 70, "avg": 251.62},
    "COALINDIA.NS":  {"name": "Coal India",          "qty": 20, "avg": 416.35},
    "ICICIBANK.NS":  {"name": "ICICI Bank",          "qty": 2,  "avg": 1391.20},
    "IDFCFIRSTB.NS": {"name": "IDFC First Bank",     "qty": 30, "avg": 70.03},
    "IOC.NS":        {"name": "Indian Oil Corp",     "qty": 14, "avg": 160.11},
    "IRFC.NS":       {"name": "IRFC",                "qty": 82, "avg": 146.99},
    "ITC.NS":        {"name": "ITC",                 "qty": 29, "avg": 340.50},
    "NHPC.NS":       {"name": "NHPC",                "qty": 91, "avg": 94.74},
    "RELIANCE.NS":   {"name": "Reliance Industries", "qty": 6,  "avg": 1393.76},
    "ROHLTD.NS":     {"name": "Royal Orchid Hotels", "qty": 10, "avg": 415.00},
    "SWIGGY.NS":     {"name": "Swiggy",              "qty": 1,  "avg": 419.90},
    "TATAMOTORS.NS": {"name": "Tata Motors",         "qty": 14, "avg": 493.81},
    "HINDCOPPER.NS": {"name": "Hindustan Copper",    "qty": 6,  "avg": 532.60},
    "BLS.NS":        {"name": "BLS International",   "qty": 6,  "avg": 314.00},
}

WATCH_TICKERS = {
    "^NSEI":    "Nifty 50",
    "^BSESN":   "Sensex",
    "GC=F":     "Gold",
    "CL=F":     "Crude Oil",
    "USDINR=X": "USD/INR",
}

# ── 1. Fetch prices one-by-one (avoids batch failures) ───────────────────────
def fetch_prices():
    prices = {}
    all_tickers = list(HOLDINGS_TICKERS.keys()) + list(WATCH_TICKERS.keys())
    for ticker in all_tickers:
        try:
            df    = yf.download(ticker, period="5d", interval="1d",
                                auto_adjust=True, progress=False)
            close = df["Close"].dropna()
            if len(close) >= 1:
                latest = float(close.iloc[-1])
                prev   = float(close.iloc[-2]) if len(close) >= 2 else latest
                prices[ticker] = {
                    "price":      round(latest, 2),
                    "prev":       round(prev, 2),
                    "change":     round(latest - prev, 2),
                    "change_pct": round((latest - prev) / prev * 100, 2),
                }
            else:
                prices[ticker] = None
                print(f"  ⚠ No data for {ticker}")
        except Exception as e:
            prices[ticker] = None
            print(f"  ⚠ Failed {ticker}: {e}")
    return prices

# ── 2. Build holdings P&L ────────────────────────────────────────────────────
def build_holdings(prices):
    holdings = []
    total_invested = total_current = 0
    for ticker, meta in HOLDINGS_TICKERS.items():
        p        = prices.get(ticker)
        cmp      = p["price"] if p else meta["avg"]
        buy_val  = round(meta["qty"] * meta["avg"], 2)
        curr_val = round(meta["qty"] * cmp, 2)
        pnl      = round(curr_val - buy_val, 2)
        pnl_pct  = round(pnl / buy_val * 100, 2)
        total_invested += buy_val
        total_current  += curr_val
        holdings.append({
            "ticker":           ticker.replace(".NS", ""),
            "name":             meta["name"],
            "qty":              meta["qty"],
            "avg":              meta["avg"],
            "cmp":              cmp,
            "buy_value":        buy_val,
            "curr_value":       curr_val,
            "pnl":              pnl,
            "pnl_pct":          pnl_pct,
            "change_today":     p["change"]      if p else 0,
            "change_pct_today": p["change_pct"]  if p else 0,
        })
    holdings.sort(key=lambda x: x["pnl"])
    return holdings, round(total_invested, 2), round(total_current, 2)

# ── 3. Call Gemini 2.0 Flash ─────────────────────────────────────────────────
def call_gemini(prices, holdings, total_invested, total_current):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)

    nifty  = prices.get("^NSEI",    {}) or {}
    crude  = prices.get("CL=F",     {}) or {}
    gold   = prices.get("GC=F",     {}) or {}
    usdinr = prices.get("USDINR=X", {}) or {}

    holdings_summary = "\n".join([
        f"- {h['name']}: CMP Rs{h['cmp']}, Avg Rs{h['avg']}, "
        f"P&L {h['pnl_pct']:+.1f}% (Rs{h['pnl']:+,.0f})"
        for h in holdings
    ])

    prompt = f"""You are a senior Indian stock market analyst with 20+ years of experience.
Today is {TODAY} ({WEEKDAY}).

LIVE MARKET DATA:
- Nifty 50: {nifty.get('price','N/A')} ({nifty.get('change_pct',0):+.2f}%)
- Crude Oil: ${crude.get('price','N/A')}/bbl ({crude.get('change_pct',0):+.2f}%)
- Gold: ${gold.get('price','N/A')}/oz
- USD/INR: Rs{usdinr.get('price','N/A')}

PORTFOLIO (Ashutosh Patwariya):
Invested: Rs{total_invested:,.0f} | Current: Rs{total_current:,.0f} | P&L: Rs{total_current-total_invested:+,.0f} ({(total_current-total_invested)/total_invested*100:+.1f}%)

Holdings:
{holdings_summary}

Return ONLY a valid JSON object. No markdown. No explanation. No text before or after.
The JSON must have exactly these keys:

{{
  "market_mood": {{"score": 0, "label": "FEAR", "color": "red", "description": "sentence"}},
  "macro_outlook": {{
    "headline": "short headline",
    "summary": "3-4 sentence summary",
    "key_points": ["point1","point2","point3","point4","point5"],
    "short_term": "sentence",
    "medium_term": "sentence",
    "long_term": "sentence"
  }},
  "fii_dii": {{"fii_net": -5000, "dii_net": 3000, "fii_label": "NET SELLERS", "dii_label": "NET BUYERS", "signal": "sentence"}},
  "risk_alerts": [
    {{"stock": "name", "alert": "text", "severity": "high"}},
    {{"stock": "name", "alert": "text", "severity": "medium"}},
    {{"stock": "name", "alert": "text", "severity": "medium"}},
    {{"stock": "name", "alert": "text", "severity": "low"}}
  ],
  "sector_strategy": [
    {{"sector": "name", "war_impact": "POSITIVE", "short_term": "Outperform", "long_term": "Outperform", "strategy": "OVERWEIGHT", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "NEUTRAL", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEGATIVE", "short_term": "Underperform", "long_term": "Neutral", "strategy": "AVOID", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "POSITIVE", "short_term": "Outperform", "long_term": "Outperform", "strategy": "OVERWEIGHT", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "BUY ON DIPS", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "NEUTRAL", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEGATIVE", "short_term": "Underperform", "long_term": "Neutral", "strategy": "REDUCE", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "POSITIVE", "short_term": "Outperform", "long_term": "Outperform", "strategy": "OVERWEIGHT", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "NEUTRAL", "key_risk": "text"}},
    {{"sector": "name", "war_impact": "NEGATIVE", "short_term": "Underperform", "long_term": "Neutral", "strategy": "AVOID", "key_risk": "text"}}
  ],
  "buy_recommendations": [
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "LOW", "horizon": "LONG-TERM", "target": "target", "type": "compounder"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "LOW", "horizon": "LONG-TERM", "target": "target", "type": "safe_haven"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "MODERATE", "horizon": "MEDIUM-TERM", "target": "target", "type": "defensive"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "MODERATE", "horizon": "LONG-TERM", "target": "target", "type": "compounder"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "LOW", "horizon": "LONG-TERM", "target": "target", "type": "index"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "HIGH", "horizon": "SHORT-TERM", "target": "target", "type": "tactical"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "MODERATE", "horizon": "LONG-TERM", "target": "target", "type": "mutual_fund"}},
    {{"ticker": "SYM", "name": "full name", "reason": "2-3 sentences", "entry": "strategy", "risk": "LOW", "horizon": "MEDIUM-TERM", "target": "target", "type": "defensive"}}
  ],
  "top_trades": [
    {{"rank": 1, "stock": "name", "call": "BUY", "reason": "specific reason", "horizon": "timeframe"}},
    {{"rank": 2, "stock": "name", "call": "ADD", "reason": "specific reason", "horizon": "timeframe"}},
    {{"rank": 3, "stock": "name", "call": "HOLD", "reason": "specific reason", "horizon": "timeframe"}}
  ],
  "ipo_events": [
    {{"date": "10 Mar", "event": "event name", "impact": "HIGH", "note": "why it matters"}},
    {{"date": "12 Mar", "event": "event name", "impact": "MEDIUM", "note": "why it matters"}},
    {{"date": "15 Mar", "event": "event name", "impact": "MEDIUM", "note": "why it matters"}},
    {{"date": "17 Mar", "event": "event name", "impact": "LOW", "note": "why it matters"}}
  ],
  "portfolio_insights": {{
    "summary": "2-3 sentences",
    "best_hold": "stock and reason",
    "action_today": "specific action"
  }}
}}"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
        ),
    )

    raw = response.text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw.strip())


# ── 4. Build & save report ───────────────────────────────────────────────────
def build_report():
    print(f"[{now_ist.strftime('%H:%M:%S')} IST] Fetching NSE prices...")
    prices = fetch_prices()

    nifty_d  = prices.get("^NSEI",  {}) or {}
    sensex_d = prices.get("^BSESN", {}) or {}

    print("Building holdings P&L...")
    holdings, total_invested, total_current = build_holdings(prices)

    print("Calling Gemini 2.0 Flash...")
    ai = call_gemini(prices, holdings, total_invested, total_current)

    report = {
        "generated_at":  now_ist.isoformat(),
        "market_date":   TODAY,
        "market_open":   True,
        "nifty": {
            "price":      nifty_d.get("price", 0),
            "change":     nifty_d.get("change", 0),
            "change_pct": nifty_d.get("change_pct", 0),
            "pe":         18.4,
            "mood": ("BEARISH" if nifty_d.get("change_pct", 0) < -0.5
                     else "BULLISH" if nifty_d.get("change_pct", 0) > 0.5
                     else "NEUTRAL"),
        },
        "sensex": {
            "price":      sensex_d.get("price", 0),
            "change":     sensex_d.get("change", 0),
            "change_pct": sensex_d.get("change_pct", 0),
        },
        "crude": {
            "price":      (prices.get("CL=F") or {}).get("price", 0),
            "change_pct": (prices.get("CL=F") or {}).get("change_pct", 0),
        },
        "gold": {
            "price":      (prices.get("GC=F") or {}).get("price", 0),
            "change_pct": (prices.get("GC=F") or {}).get("change_pct", 0),
        },
        "usdinr":         (prices.get("USDINR=X") or {}).get("price", 0),
        "holdings":       holdings,
        "total_invested": total_invested,
        "total_current":  total_current,
        "total_pnl":      round(total_current - total_invested, 2),
        "total_pnl_pct":  round((total_current - total_invested) / total_invested * 100, 2),
        **ai,
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path   = os.path.join(script_dir, "..", "data", "report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved → data/report.json")
    print(f"   Nifty: {report['nifty']['price']} ({report['nifty']['change_pct']:+.2f}%)")
    print(f"   Portfolio: Rs{total_current:,.0f} ({report['total_pnl_pct']:+.1f}%)")


if __name__ == "__main__":
    build_report()
