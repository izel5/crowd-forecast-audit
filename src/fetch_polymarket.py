"""
Fetch resolved binary Polymarket markets and their full price history into DuckDB.

Usage:
    python src/fetch_polymarket.py markets --min-volume 10000
    python src/fetch_polymarket.py prices
Both steps resume where they left off if interrupted.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd
import requests
from tqdm import tqdm

from db import connect

GAMMA_KEYSET = "https://gamma-api.polymarket.com/markets/keyset"
PRICE_HISTORY = "https://data-api.polymarket.com/v2/prices-history"
PLATFORM = "polymarket"

session = requests.Session()
session.headers["User-Agent"] = "crowd-forecast-audit (academic research)"


def get_json(url, params, tries=6):
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Gave up on {url} {params}")


def unpack(payload):
    """Return (records, next_cursor) whatever wrapper key the API uses."""
    if isinstance(payload, list):
        return payload, None
    cursor = payload.get("next_cursor") or (payload.get("pagination") or {}).get("next_cursor")
    for key in ("markets", "data", "results"):
        if isinstance(payload.get(key), list):
            return payload[key], cursor
    return [], cursor


def as_list(value):
    # Gamma returns outcomes / outcomePrices / clobTokenIds as JSON-encoded strings.
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def as_ts(value):
    if not value:
        return None
    t = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(t) else t.to_pydatetime()


def category_of(m):
    event = (m.get("events") or [{}])[0] or {}
    if m.get("category"):
        return m["category"]
    if event.get("category"):
        return event["category"]
    tags = event.get("tags") or m.get("tags") or []
    if tags and isinstance(tags[0], dict):
        return tags[0].get("label")
    return None


def parse_market(m):
    outcomes = as_list(m.get("outcomes"))
    final = as_list(m.get("outcomePrices"))
    tokens = as_list(m.get("clobTokenIds"))
    if not (outcomes and final and tokens) or len(outcomes) != 2 or len(tokens) != 2:
        return None
    try:
        final = [float(x) for x in final]
    except (TypeError, ValueError):
        return None
    if sorted(final) != [0.0, 1.0]:  # skip unresolved, voided, or 50/50 splits
        return None
    return {
        "platform": PLATFORM,
        "market_id": str(m.get("conditionId") or m.get("id")),
        "question": m.get("question"),
        "slug": m.get("slug"),
        "category": category_of(m),
        "yes_token": str(tokens[0]),
        "outcome_label": outcomes[0],
        "resolved_yes": int(final[0] == 1.0),
        "created_at": as_ts(m.get("createdAt") or m.get("startDate")),
        "end_at": as_ts(m.get("endDate")),
        "closed_at": as_ts(m.get("closedTime")),
        "volume": float(m.get("volumeNum") or m.get("volume") or 0),
        "raw": json.dumps(m),
    }


def fetch_markets(con, min_volume, max_markets, page_size):
    have = con.execute("SELECT count(*) FROM markets WHERE platform = ?", [PLATFORM]).fetchone()[0]
    cursor, kept, seen = None, have, 0
    bar = tqdm(desc="markets kept", initial=have, total=max_markets)
    while kept < max_markets:
        params = {"closed": "true", "limit": page_size}
        if cursor:
            params["after_cursor"] = cursor
        records, cursor = unpack(get_json(GAMMA_KEYSET, params))
        if not records:
            break
        rows = []
        for m in records:
            seen += 1
            row = parse_market(m)
            if row and row["volume"] >= min_volume:
                rows.append(row)
        if rows:
            df = pd.DataFrame(rows)
            before = con.execute("SELECT count(*) FROM markets").fetchone()[0]
            con.execute("INSERT OR IGNORE INTO markets SELECT * FROM df")
            added = con.execute("SELECT count(*) FROM markets").fetchone()[0] - before
            kept += added
            bar.update(added)
        if not cursor:
            break
    bar.close()
    print(f"Scanned {seen:,} closed markets; {kept:,} resolved binary markets with volume >= ${min_volume:,.0f} stored.")


def fetch_history(token_id):
    points, cursor = [], None
    while True:
        params = {"token_id": token_id, "interval": "max"}  # full history, 12h buckets
        if cursor:
            params["cursor"] = cursor
        payload = get_json(PRICE_HISTORY, params)
        data, cursor = unpack(payload)
        points.extend(data)
        has_more = (payload.get("pagination") or {}).get("has_more") if isinstance(payload, dict) else False
        if not (has_more and cursor):
            return points


def fetch_prices(con, workers):
    todo = con.execute(
        """
        SELECT m.market_id, m.yes_token FROM markets m
        LEFT JOIN fetch_log f ON f.platform = m.platform AND f.market_id = m.market_id
        WHERE m.platform = ? AND f.market_id IS NULL
        """,
        [PLATFORM],
    ).fetchall()

    def task(item):
        market_id, token = item
        try:
            return market_id, fetch_history(token), None
        except Exception as e:  # keep going; log and retry later with --retry-errors
            return market_id, None, e

    # Downloads run in parallel threads; all database writes stay on this thread.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(task, item) for item in todo]
        for fut in tqdm(as_completed(futures), total=len(futures), desc="price histories"):
            market_id, pts, err = fut.result()
            save_history(con, market_id, pts, err)


def save_history(con, market_id, pts, err):
    now = datetime.now(timezone.utc)
    if err is not None:
        con.execute("INSERT OR REPLACE INTO fetch_log VALUES (?, ?, 'error', 0, ?)", [PLATFORM, market_id, now])
        tqdm.write(f"error on {market_id}: {err}")
        return
    if pts:
        df = pd.DataFrame(
            {
                "platform": PLATFORM,
                "market_id": market_id,
                "ts": pd.to_datetime([p.get("timestamp", p.get("t")) for p in pts], unit="s", utc=True),
                "price": [float(p.get("price", p.get("p"))) for p in pts],
            }
        )
        con.execute("INSERT OR IGNORE INTO prices SELECT * FROM df")
    status = "ok" if pts else "empty"
    con.execute("INSERT OR REPLACE INTO fetch_log VALUES (?, ?, ?, ?, ?)", [PLATFORM, market_id, status, len(pts), now])

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("markets")
    m.add_argument("--min-volume", type=float, default=10_000)
    m.add_argument("--max-markets", type=int, default=1_000_000)
    m.add_argument("--page-size", type=int, default=500)
    p = sub.add_parser("prices")
    p.add_argument("--retry-errors", action="store_true")
    p.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    con = connect()
    if args.cmd == "markets":
        fetch_markets(con, args.min_volume, args.max_markets, args.page_size)
    else:
        if args.retry_errors:
            con.execute("DELETE FROM fetch_log WHERE platform = ? AND status = 'error'", [PLATFORM])
        fetch_prices(con, args.workers)


if __name__ == "__main__":
    main()
