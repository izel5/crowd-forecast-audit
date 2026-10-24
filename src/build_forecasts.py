"""
Build the forecasts table: the market's implied probability at fixed horizons
before resolution (1, 7 and 30 days out), paired with what actually happened.

Resolution time is the EARLIER of the market's end date and its close time.
Markets often close days after their end date (resolution/dispute lag); using
the close time there would let "1 day before" land after the outcome was
already public, which inflates apparent accuracy.

Usage: python src/build_forecasts.py
"""
import json

import pandas as pd

from categorize import topic_of
from db import connect

HORIZONS_DAYS = (1, 7, 30)
MAX_STALENESS_HOURS = 48  # drop a forecast if the last price is older than this

SQL = f"""
CREATE OR REPLACE TABLE forecasts AS
WITH horizons AS (
    SELECT unnest([{", ".join(map(str, HORIZONS_DAYS))}]) AS days
),
asks AS (
    SELECT m.platform, m.market_id, t.topic, m.volume, m.resolved_yes, h.days,
           least(m.closed_at, m.end_at) AS resolved_at,
           least(m.closed_at, m.end_at) - to_days(h.days) AS as_of
    FROM markets m
    JOIN market_topics t USING (platform, market_id)
    CROSS JOIN horizons h
    WHERE least(m.closed_at, m.end_at) IS NOT NULL
)
SELECT a.*, p.ts AS price_ts, p.price
FROM asks a
ASOF JOIN prices p
  ON a.platform = p.platform AND a.market_id = p.market_id AND a.as_of >= p.ts
WHERE p.ts >= a.as_of - to_hours({MAX_STALENESS_HOURS})
"""


def build_topics(con):
    rows = con.execute("SELECT platform, market_id, question, raw FROM markets").fetchall()
    topics = pd.DataFrame(
        [
            (platform, market_id,
             topic_of(question, ((json.loads(raw).get("events") or [{}])[0] or {}).get("title")))
            for platform, market_id, question, raw in rows
        ],
        columns=["platform", "market_id", "topic"],
    )
    con.execute("CREATE OR REPLACE TABLE market_topics AS SELECT * FROM topics")


def main():
    con = connect()
    build_topics(con)
    con.execute(SQL)
    print(con.execute(
        "SELECT days AS horizon_days, count(*) AS n, round(avg(resolved_yes), 3) AS base_rate "
        "FROM forecasts GROUP BY 1 ORDER BY 1"
    ).df().to_string(index=False))
    print()
    print(con.execute(
        "SELECT topic, count(DISTINCT market_id) AS markets FROM forecasts GROUP BY 1 ORDER BY 2 DESC"
    ).df().to_string(index=False))


if __name__ == "__main__":
    main()
