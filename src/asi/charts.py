"""Matplotlib charts used by the README, the Excel pack and the one-pager."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

NAVY, TEAL, GOLD, RED, GREY = "#14365d", "#1b9aaa", "#f2a541", "#c0392b", "#8a8f98"
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9, "axes.titleweight": "bold"})


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def make_all(res: dict, out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    p = {}
    k = res["kpi"]
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(k.month_start, k.gross_revenue / 1e6, width=20, color=TEAL, label="Gross revenue")
    ax.plot(k.month_start, k.target_revenue / 1e6, color=NAVY, marker="o", ms=3, label="Target")
    ax.set_ylabel("A$ million"); ax.set_title("Monthly revenue vs target"); ax.legend(frameon=False)
    p["revenue_vs_target"] = _save(fig, out / "revenue_vs_target.png")

    mix = res["mix"]["monthly"]
    fig, ax1 = plt.subplots(figsize=(7, 3))
    ax1.plot(mix.month_start, mix.ndc_share_indirect * 100, color=NAVY, marker="o", ms=3, label="NDC share of agency bookings")
    ax1.plot(mix.month_start, mix.ota_share_leisure * 100, color=GOLD, marker="o", ms=3, label="OTA share of leisure bookings")
    ax1.set_ylabel("% of bookings"); ax1.set_title("Distribution mix shift")
    ax2 = ax1.twinx()
    ax2.plot(mix.month_start, mix.cost_of_sale_pct * 100, color=RED, ls="--", label="Cost of sale % (rhs)")
    ax2.set_ylabel("Cost of sale %")
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, frameon=False, fontsize=7, loc="upper left")
    p["channel_mix"] = _save(fig, out / "channel_mix.png")

    r = res["target"]["routes_recent"].sort_values("attainment")
    fig, ax = plt.subplots(figsize=(7, 3))
    cols = [RED if a < 0.9 else (GOLD if a < 0.95 else TEAL) for a in r.attainment]
    ax.barh(r.route_code, r.attainment * 100, color=cols)
    ax.axvline(100, color=NAVY, lw=1)
    ax.set_xlabel("% of revenue target"); ax.set_title(f"Route target attainment, {res['target']['window']}")
    p["route_attainment"] = _save(fig, out / "route_attainment.png")

    fc = res["forecast"]
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(fc["history"].month_start, fc["history"].gross_revenue / 1e6, color=NAVY, label="Actual")
    bt = fc["best_backtest"].groupby("month_start").pred.mean()
    ax.scatter(bt.index, bt.values / 1e6, color=GOLD, s=12, label="Backtest forecasts")
    ax.plot(fc["forecast"].month_start, fc["forecast"].gross_revenue / 1e6, color=TEAL, marker="o", ls="--", label="Next-quarter forecast")
    ax.set_ylabel("A$ million"); ax.set_title(f"Revenue forecast (backtest MAPE {fc['models'][fc['best_model']]:.1f}%)")
    ax.legend(frameon=False, fontsize=7)
    p["forecast"] = _save(fig, out / "forecast.png")

    s = res["anomaly"]["series"]
    app = s[s.channel_code == "APP"].set_index("booking_date")
    win = app.loc["2026-01-12":"2026-03-15"]
    fl = res["anomaly"]["flagged"]
    fl = fl[(fl.booking_date >= win.index.min()) & (fl.booking_date <= win.index.max())]
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(win.index, win.bookings, color=NAVY, label="Daily bookings")
    ax.plot(win.index, win.expected, color=GREY, ls="--", label="Expected (same weekday, 4-wk median)")
    sel = fl[fl.channel_code == "APP"]
    ax.scatter(sel.booking_date, sel.bookings, color=RED, zorder=3, label="Flagged anomaly")
    ax.set_title("Direct app bookings: anomaly detection"); ax.legend(frameon=False, fontsize=7)
    p["app_anomaly"] = _save(fig, out / "app_anomaly.png")
    return p
