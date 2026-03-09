#!/usr/bin/env python3
"""
Market Pulse — Ashutosh
Daily report generator: fetches NSE prices via yfinance + calls OpenAI API
Runs via GitHub Actions every weekday at 8 AM IST (2:30 AM UTC)
"""

import json
import os
import re
import time
from datetime import datetime
import pytz

try:
    import yfinance as yf
    from openai import OpenAI
except ImportError:
    os.system("pip install yfinance openai pytz --quiet")
    import yfinance as yf
    from openai import OpenAI

IST     = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
TODAY   = now_ist.strftime("%d %B %Y")
WEEKDAY = now_ist.strftime("%A")

# ── Holdings — verified NSE/BSE symbols ─────────────────────────────────────
HOLDINGS_TICKERS = {
    "ADANIENSOL.NS": {"name": "Adani Total Gas",     "qty": 14, "avg": 931.67},
    "ETERNAL.NS":    {"name": "Eternal (Zomato)",    "qty": 70, "avg": 251.62},
    "COALINDIA.NS":  {"name": "Coal India",          "qty": 20, "avg": 416.35},
    "ICICIBANK.NS":  {"name": "ICICI Bank",          "qty":  2, "avg": 1391.20},
    "IDFCFIRSTB.NS": {"name": "IDFC First Bank",     "qty": 30, "avg": 70.03},
    "IOC.NS":        {"name": "Indian Oil Corp",     "qty": 14, "avg": 160.11},
    "IRFC.NS":       {"name": "IRFC",                "qty": 82, "avg": 146.99},
    "ITC.NS":        {"name": "ITC",                 "qty": 29, "avg": 340.50},
    "NHPC.NS":       {"name": "NHPC",                "qty": 91, "avg": 94.74},
    "RELIANCE.NS":   {"name": "Reliance Industries", "qty":  6, "avg": 1393.76},
    "ROHLTD.NS":     {"name": "Royal Orchid Hotels", "qty": 10, "avg": 415.00},
    "SWIGGY.NS":     {"name": "Swiggy",              "qty":  1, "avg": 419.90},
    "TATAMOTORS.BO": {"name": "Tata Motors",         "qty": 14, "avg": 493.81},
    "HINDCOPPER.NS": {"name": "Hindustan Copper",    "qty":  6, "avg": 532.60},
    "BLS.NS":        {"name": "BLS International",   "qty":  6, "avg": 314.00},
}

WATCH_TICKERS = {
    "^NSEI":    "Nifty 50",
    "^BSESN":   "Sensex",
    "GC=F":     "Gold",
    "CL=F":     "Crude Oil",
    "USDINR=X": "USD/INR",
}

# ── 1. Fetch prices ──────────────────────────────────────────────────────────
def get_price(ticker: str):
    try:
        t     = yf.Ticker(ticker)
        df    = t.history(period="5d", interval="1d", auto_adjust=True)
        if df is None or df.empty:
            print(f"  ⚠ No data for {ticker}")
            return None
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].dropna()
        if len(close) == 0:
            return None
        latest = float(close.iloc[-1])
        prev   = float(close.iloc[-2]) if len(close) >= 2 else latest
        return {
            "price":      round(latest, 2),
            "prev":       round(prev, 2),
            "change":     round(latest - prev, 2),
            "change_pct": round((latest - prev) / prev * 100, 2),
        }
    except Exception as e:
        print(f"  ⚠ Failed {ticker}: {e}")
        return None

def fetch_prices():
    prices = {}
    for ticker in list(HOLDINGS_TICKERS.keys()) + list(WATCH_TICKERS.keys()):
        prices[ticker] = get_price(ticker)
        time.sleep(0.3)
    return prices

# ── 2. Build holdings P&L ────────────────────────────────────────────────────
def build_holdings(prices):
    holdings = []
    total_invested = total_current = 0.0
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
            "ticker":           ticker.replace(".NS", "").replace(".BO", ""),
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

# ── 3. Call OpenAI API ───────────────────────────────────────────────────────
def call_openai(prices, holdings, total_invested, total_current):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")

    client = OpenAI(api_key=api_key)

    nifty  = prices.get("^NSEI",    {}) or {}
    crude  = prices.get("CL=F",     {}) or {}
    gold   = prices.get("GC=F",     {}) or {}
    usdinr = prices.get("USDINR=X", {}) or {}

    holdings_text = "\n".join(
        f"- {h['name']}: CMP Rs{h['cmp']}, Avg Rs{h['avg']}, "
        f"P&L {h['pnl_pct']:+.1f}% (Rs{h['pnl']:+,.0f})"
        for h in holdings
    )

    system_prompt = """You are a senior Indian stock market analyst with 20+ years of experience.
You provide data-driven, actionable analysis. You always respond with pure valid JSON only — 
no markdown fences, no explanation text before or after, just the JSON object."""

    user_prompt = f"""Today: {TODAY} ({WEEKDAY})

LIVE MARKET DATA:
- Nifty 50: {nifty.get('price','N/A')} ({nifty.get('change_pct',0):+.2f}%)
- Crude Oil: ${crude.get('price','N/A')}/bbl ({crude.get('change_pct',0):+.2f}%)
- Gold: ${gold.get('price','N/A')}/oz
- USD/INR: Rs{usdinr.get('price','N/A')}

PORTFOLIO (Ashutosh Patwariya):
Invested: Rs{total_invested:,.0f} | Current: Rs{total_current:,.0f} | P&L: Rs{total_current-total_invested:+,.0f} ({(total_current-total_invested)/total_invested*100:+.1f}%)

Holdings:
{holdings_text}

Generate a complete daily market intelligence report as a JSON object with exactly this structure:
{{
  "market_mood": {{
    "score": <0-100, 0=extreme fear>,
    "label": "<EXTREME FEAR|FEAR|NEUTRAL|GREED|EXTREME GREED>",
    "color": "<red|orange|yellow|lightgreen|green>",
    "description": "one sentence explanation"
  }},
  "macro_outlook": {{
    "headline": "8-10 word punchy headline referencing today's data",
    "summary": "3-4 sentences with specific numbers from today's data",
    "key_points": ["5 specific data-driven bullet points"],
    "short_term": "one sentence bearish/bullish view",
    "medium_term": "one sentence",
    "long_term": "one sentence"
  }},
  "fii_dii": {{
    "fii_net": <crores, negative=selling>,
    "dii_net": <crores, positive=buying>,
    "fii_label": "<NET SELLERS|NET BUYERS>",
    "dii_label": "<NET SELLERS|NET BUYERS>",
    "signal": "one actionable sentence"
  }},
  "risk_alerts": [
    {{"stock": "IRFC", "alert": "specific alert text", "severity": "high"}},
    {{"stock": "Adani Total Gas", "alert": "specific alert text", "severity": "high"}},
    {{"stock": "Tata Motors", "alert": "specific alert text", "severity": "medium"}},
    {{"stock": "NHPC", "alert": "specific alert text", "severity": "low"}}
  ],
  "sector_strategy": [
    {{"sector": "Defence & Aerospace", "war_impact": "POSITIVE", "short_term": "Outperform", "long_term": "Outperform", "strategy": "OVERWEIGHT", "key_risk": "stretched valuations"}},
    {{"sector": "Gold / Precious Metals", "war_impact": "POSITIVE", "short_term": "Outperform", "long_term": "Outperform", "strategy": "OVERWEIGHT", "key_risk": "peace deal reversal"}},
    {{"sector": "Pharma & Healthcare", "war_impact": "POSITIVE", "short_term": "Outperform", "long_term": "Outperform", "strategy": "OVERWEIGHT", "key_risk": "US FDA risks"}},
    {{"sector": "Private Banks", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "BUY ON DIPS", "key_risk": "credit quality"}},
    {{"sector": "IT / Technology", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "NEUTRAL", "key_risk": "US recession risk"}},
    {{"sector": "FMCG / Staples", "war_impact": "NEUTRAL", "short_term": "In-line", "long_term": "Outperform", "strategy": "NEUTRAL", "key_risk": "input cost inflation"}},
    {{"sector": "PSU Power / Renewables", "war_impact": "NEUTRAL", "short_term": "Underperform", "long_term": "Outperform", "strategy": "HOLD", "key_risk": "high valuations"}},
    {{"sector": "Auto (Passenger)", "war_impact": "NEGATIVE", "short_term": "Underperform", "long_term": "Neutral", "strategy": "REDUCE", "key_risk": "commodity cost surge"}},
    {{"sector": "Aviation / Travel", "war_impact": "NEGATIVE", "short_term": "Underperform", "long_term": "Neutral", "strategy": "AVOID", "key_risk": "crude shock"}},
    {{"sector": "OMCs (BPCL/IOC/HPCL)", "war_impact": "NEGATIVE", "short_term": "Underperform", "long_term": "Neutral", "strategy": "HOLD ONLY", "key_risk": "under-recovery risk"}}
  ],
  "buy_recommendations": [
    {{"ticker": "GOLDBEES", "name": "Nippon India Gold ETF", "reason": "2-3 sentences specific to today", "entry": "entry strategy", "risk": "LOW", "horizon": "LONG-TERM", "target": "target", "type": "safe_haven"}},
    {{"ticker": "ICICIBANK", "name": "ICICI Bank", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "MODERATE", "horizon": "LONG-TERM", "target": "target", "type": "compounder"}},
    {{"ticker": "NIFTYBEES", "name": "Nifty 50 Index ETF", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "LOW", "horizon": "LONG-TERM", "target": "target", "type": "index"}},
    {{"ticker": "COALINDIA", "name": "Coal India", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "LOW", "horizon": "MEDIUM-TERM", "target": "target", "type": "defensive"}},
    {{"ticker": "BEL", "name": "Bharat Electronics Ltd", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "HIGH", "horizon": "SHORT-TERM", "target": "target", "type": "tactical"}},
    {{"ticker": "HDFCBANK", "name": "HDFC Bank", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "MODERATE", "horizon": "LONG-TERM", "target": "target", "type": "compounder"}},
    {{"ticker": "SILVRETF", "name": "Nippon Silver ETF", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "LOW", "horizon": "MEDIUM-TERM", "target": "target", "type": "safe_haven"}},
    {{"ticker": "PPFCF", "name": "Parag Parikh Flexi Cap Fund", "reason": "2-3 sentences", "entry": "entry strategy", "risk": "MODERATE", "horizon": "LONG-TERM", "target": "target", "type": "mutual_fund"}}
  ],
  "top_trades": [
    {{"rank": 1, "stock": "name", "call": "BUY", "reason": "specific to today's data", "horizon": "timeframe"}},
    {{"rank": 2, "stock": "name", "call": "ADD", "reason": "specific to today's data", "horizon": "timeframe"}},
    {{"rank": 3, "stock": "name", "call": "HOLD", "reason": "specific to today's data", "horizon": "timeframe"}}
  ],
  "ipo_events": [
    {{"date": "10 Mar", "event": "RBI MPC Minutes", "impact": "HIGH", "note": "Watch for rate cut signals"}},
    {{"date": "12 Mar", "event": "India CPI Inflation", "impact": "HIGH", "note": "Key inflation reading"}},
    {{"date": "15 Mar", "event": "F&O Expiry Week", "impact": "MEDIUM", "note": "Expect elevated volatility"}},
    {{"date": "17 Mar", "event": "US Fed Minutes", "impact": "MEDIUM", "note": "FII flow directional cue"}}
  ],
  "portfolio_insights": {{
    "summary": "2-3 sentences on portfolio health today referencing actual holdings data",
    "best_hold": "specific stock name and why to hold today",
    "action_today": "one specific actionable thing to do today"
  }}
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",      # Fast, cheap, excellent for structured JSON
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=3000,
        response_format={"type": "json_object"},  # Forces pure JSON output — no fences
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ── 4. Build & save report ───────────────────────────────────────────────────
def build_report():
    print(f"[{now_ist.strftime('%H:%M:%S')} IST] Fetching prices...")
    prices = fetch_prices()

    nifty_d  = prices.get("^NSEI",  {}) or {}
    sensex_d = prices.get("^BSESN", {}) or {}

    print("Building holdings P&L...")
    holdings, total_invested, total_current = build_holdings(prices)

    print("Calling OpenAI GPT-4o-mini...")
    ai = call_openai(prices, holdings, total_invested, total_current)

    report = {
        "generated_at":   now_ist.isoformat(),
        "market_date":    TODAY,
        "market_open":    True,
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
    print(f"   Nifty:     {report['nifty']['price']} ({report['nifty']['change_pct']:+.2f}%)")
    print(f"   Portfolio: Rs{total_current:,.0f} ({report['total_pnl_pct']:+.1f}%)")


if __name__ == "__main__":
    build_report()
