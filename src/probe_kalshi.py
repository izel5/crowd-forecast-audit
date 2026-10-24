"""
One-time probe: save raw Kalshi API responses so the Kalshi fetcher can be
written against the real field names.

Usage: python src/probe_kalshi.py   -> writes data/probe/kalshi_*.json
"""
import json
import time

import requests

from db import ROOT

BASE = "https://api.elections.kalshi.com/trade-api/v2"
OUT = ROOT / "data" / "probe"
OUT.mkdir(parents=True, exist_ok=True)


def save(name, url, params=None):
    r = requests.get(url, params=params, timeout=30)
    body = r.json() if "json" in r.headers.get("content-type", "") else r.text[:2000]
    (OUT / f"kalshi_{name}.json").write_text(json.dumps({"url": r.url, "status": r.status_code, "body": body}, indent=2))
    print(f"{r.status_code}  {name}")
    return body if r.ok else None


now = int(time.time())
settled = save("markets_settled", f"{BASE}/markets", {"status": "settled", "limit": 5})
save("historical_markets", f"{BASE}/historical/markets", {"limit": 5})
save("historical_cutoff", f"{BASE}/historical/cutoff")

markets = (settled or {}).get("markets") or []
if markets:
    m = markets[0]
    ticker, series = m.get("ticker"), m.get("series_ticker") or (m.get("event_ticker") or "").split("-")[0]
    window = {"start_ts": now - 90 * 86400, "end_ts": now, "period_interval": 1440}
    save("candles_live", f"{BASE}/series/{series}/markets/{ticker}/candlesticks", window)
    save("candles_historical", f"{BASE}/historical/markets/{ticker}/candlesticks", window)
print(f"Saved probe files to {OUT}")
