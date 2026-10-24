# Does the Crowd Know the Future?

An audit of prediction-market accuracy. Polymarket and Kalshi odds are now quoted as fact for elections, Fed decisions, and AI releases. This project tests whether they deserve that trust.

**Status:** in progress. Data pipeline and first calibration pass built; results coming.

## Questions

1. **Calibration.** When a market says 70%, does the event happen 70% of the time?
2. **Where the crowd breaks.** Does accuracy change by topic, trading volume, or time to resolution?
3. **How early the market knows.** Do prices move before public news breaks?
4. **Crowd vs. experts.** How do markets compare with polling averages and forecasting models on the same events?

## Data

| Source | What | Access |
|---|---|---|
| Polymarket Gamma API | Resolved binary markets: question, category, volume, outcome | public |
| Polymarket Data API (`/v2/prices-history`) | Full price history per outcome token (12-hour buckets) | public |
| Kalshi Trade API | Settled markets and daily candlesticks | public (in progress) |

All data goes into a local DuckDB database (`data/markets.duckdb`), with these tables:

- `markets`: one row per resolved market
- `prices`: price history
- `forecasts`: the implied probability 1, 7, and 30 days before resolution, paired with what happened

## Method

- Only binary markets that resolved cleanly to 0 or 1 are used. Voided or split markets are dropped.
- Markets with low volume (default under $10k) are filtered out so that dead markets don't distort the results.
- Each forecast is the last traded price before the horizon. If that price is more than 48 hours older than the horizon, it's dropped.
- Accuracy is measured with Brier scores and skill against a base-rate forecaster. Calibration is shown in binned curves with 95% Wilson intervals.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python src/fetch_polymarket.py markets --min-volume 10000 --max-markets 5000
python src/fetch_polymarket.py prices
python src/build_forecasts.py
python src/calibration.py        # prints tables, saves figures/calibration_by_horizon.png
```

Both fetch steps resume if interrupted.

## Layout

```
sql/schema.sql            DuckDB schema
src/fetch_polymarket.py   markets + price history
src/probe_kalshi.py       captures Kalshi response formats
src/build_forecasts.py    horizon forecasts via ASOF join
src/calibration.py        Brier scores, calibration curves
figures/                  output charts
```
