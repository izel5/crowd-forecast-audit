from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "markets.duckdb"


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("SET TimeZone = 'UTC'")
    con.execute((ROOT / "sql" / "schema.sql").read_text())
    return con
