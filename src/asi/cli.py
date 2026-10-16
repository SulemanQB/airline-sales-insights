"""Command line entry point: `python -m asi.cli all` (or `asi all` once installed)."""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import pandas as pd

from . import analysis, charts, excel_pack, onepager
from .generate import generate
from .model import build, export_star

ROOT = Path(__file__).resolve().parents[2]


def findings_dict(res: dict, timings: dict) -> dict:
    fy = res["fy"].set_index("fin_year")
    mix = {k: v for k, v in res["mix"].items() if k != "monthly"}
    tv = {k: v for k, v in res["target"].items() if k != "routes_recent"}
    fc = res["forecast"]
    return {
        "fy": {i: {c: float(v) for c, v in r.items()} for i, r in fy.iterrows()},
        "channel_mix": mix, "target": tv,
        "anomalies": {"n_flagged": res["anomaly"]["n_flagged"],
                      "flagged": [{"date": str(r.booking_date.date()), "channel": r.channel_code,
                                   "bookings": int(r.bookings), "expected": float(r.expected), "z": round(float(r.z), 2),
                                   "sustained": bool(r.sustained)}
                                  for r in res["anomaly"]["flagged"].itertuples()],
                      "n_sustained": res["anomaly"]["n_sustained"],
                      "lost_bookings_est": res["anomaly"]["lost_bookings_est"],
                      "lost_revenue_est": res["anomaly"]["lost_revenue_est"]},
        "forecast": {"mape_by_model": fc["models"], "best_model": fc["best_model"], "n_backtest_origins": fc["n_origins"],
                     "next_quarter": {str(r.month_start.date()): float(r.gross_revenue) for r in fc["forecast"].itertuples()},
                     "next_quarter_total": fc["forecast_total"], "same_quarter_last_year": fc["same_q_last_year"]},
        "recommendations": res["recs"], "timings_s": timings,
    }


def run(out: Path, seed: int, month: str | None, export: bool = True) -> dict:
    t = {}
    t0 = time.perf_counter()
    bookings, targets = generate(seed=seed)
    t["generate"] = time.perf_counter() - t0
    out.mkdir(parents=True, exist_ok=True)
    db = out / "sales.duckdb"
    db.unlink(missing_ok=True)
    t0 = time.perf_counter()
    con = build(bookings, targets, db)
    t["build_model"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    res = analysis.run_all(con)
    t["analysis"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    imgs = charts.make_all(res, out / "charts")
    xl = excel_pack.build_pack(con, res, imgs, out / "Commercial_Pack.xlsx", month)
    html = onepager.build_html(res, imgs, out / "OnePager.html")
    pdf = onepager.build_pdf(res, imgs, out / "OnePager.pdf")
    t["reporting"] = time.perf_counter() - t0
    if export:
        export_star(con, out / "powerbi")
    con.close()
    f = findings_dict(res, {k: round(v, 2) for k, v in t.items()})
    f["rows"] = {"bookings": int(len(bookings)), "targets": int(len(targets))}
    (out / "findings.json").write_text(json.dumps(f, indent=2, default=str))
    print(f"bookings={len(bookings):,}  pack={xl}  onepager={html}, {pdf}")
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(prog="asi", description="Southern Cross Air commercial analytics")
    ap.add_argument("command", choices=["all", "report", "export"])
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--month", default=None, help="pack month, e.g. 2026-06-01 (default: latest)")
    ap.add_argument("--docs", action="store_true", help="copy charts into docs/img for the README")
    a = ap.parse_args(argv)
    from . import config as C
    out = Path(a.out)
    run(out, a.seed or C.SEED, a.month, export=a.command in ("all", "export"))
    if a.docs:
        d = ROOT / "docs" / "img"
        d.mkdir(parents=True, exist_ok=True)
        for p in (out / "charts").glob("*.png"):
            shutil.copy(p, d / p.name)


if __name__ == "__main__":
    main()
