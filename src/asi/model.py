"""Load generated data into DuckDB and build the star schema + KPI views."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import config as C

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def _ref_frames() -> dict[str, pd.DataFrame]:
    return {
        "stg_route": pd.DataFrame(C.ROUTES, columns=["route_code", "origin", "destination", "haul",
                                                     "distance_km", "daily_seats", "base_fare_aud", "_bpd"]).drop(columns="_bpd"),
        "stg_channel": pd.DataFrame(C.CHANNELS, columns=["channel_code", "channel", "channel_group",
                                                         "connection", "commission_pct", "fee_per_segment_aud"]),
        "stg_fare": pd.DataFrame(C.FARES, columns=["fare_family", "cabin", "_m", "_a", "refundable"]).drop(columns=["_m", "_a"]),
        "stg_pos": pd.DataFrame(C.POS, columns=["pos_code", "pos_country", "pos_region"]),
        "stg_segment": pd.DataFrame(C.SEGMENTS, columns=["segment_code", "segment"]),
    }


def build(bookings: pd.DataFrame, targets: pd.DataFrame, db_path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    frames = _ref_frames() | {"stg_booking": bookings, "stg_target": targets}
    for name, df in frames.items():
        con.register(f"_{name}", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _{name}")
        con.unregister(f"_{name}")
    con.execute((SQL_DIR / "schema.sql").read_text())
    con.execute((SQL_DIR / "views.sql").read_text())
    for name in frames:
        con.execute(f"DROP TABLE {name}")
    return con


STAR_TABLES = ["dim_date", "dim_route", "dim_channel", "dim_fare", "dim_pos", "dim_segment",
               "fact_booking", "fact_target"]


def export_star(con: duckdb.DuckDBPyConnection, out_dir: str | Path) -> list[Path]:
    """Write every star-schema table as CSV and Parquet for Power BI."""
    out = Path(out_dir)
    (out / "csv").mkdir(parents=True, exist_ok=True)
    (out / "parquet").mkdir(parents=True, exist_ok=True)
    paths = []
    for t in STAR_TABLES:
        q = f"SELECT * FROM {t}"
        if t == "dim_date":
            q += " WHERE date BETWEEN DATE '2024-07-01' AND DATE '2027-06-30'"
        df = con.execute(q).df()
        p1, p2 = out / "csv" / f"{t}.csv", out / "parquet" / f"{t}.parquet"
        df.to_csv(p1, index=False)
        df.to_parquet(p2, index=False)
        paths += [p1, p2]
    return paths
