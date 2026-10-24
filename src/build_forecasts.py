"""
Build the forecasts table: the market's implied probability at fixed horizons
before resolution (1, 7 and 30 days out), paired with what actually happened.

Usage: python src/build_forecasts.py
"""
from db import connect

HORIZONS_DAYS = (1, 7, 30)
MAX_STALENESS_HOURS = 48  # drop a forecast if the last price is older than this

SQL = f"""
CREATE OR REPLACE TABLE forecasts AS
WITH horizons AS (
    SELECT unnest([{", ".join(map(str, HORIZONS_DAYS))}]) AS days
),
asks AS (
    SELECT m.platform, m.market_id, m.category, m.volume, m.resolved_yes, h.days,
           coalesce(m.closed_at, m.end_at) AS resolved_at,
           coalesce(m.closed_at, m.end_at) - to_days(h.days) AS as_of
    FROM markets m CROSS JOIN horizons h
    WHERE coalesce(m.closed_at, m.end_at) IS NOT NULL
)
SELECT a.*, p.ts AS price_ts, p.price
FROM asks a
ASOF JOIN prices p
  ON a.platform = p.platform AND a.market_id = p.market_id AND a.as_of >= p.ts
WHERE p.ts >= a.as_of - to_hours({MAX_STALENESS_HOURS})
"""


def main():
    con = connect()
    con.execute(SQL)
    print(con.execute(
        "SELECT days AS horizon_days, count(*) AS n, round(avg(resolved_yes), 3) AS base_rate "
        "FROM forecasts GROUP BY 1 ORDER BY 1"
    ).df().to_string(index=False))


if __name__ == "__main__":
    main()
