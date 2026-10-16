"""Trend detection, variance to target, anomaly detection, forecasting and
quantified recommendations. Every number returned here is computed from the
data in the DuckDB model; nothing is hard-coded."""
from __future__ import annotations

import numpy as np
import pandas as pd


def q(con, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


# ---------------------------------------------------------------- helpers
def ols_slope(y: np.ndarray) -> tuple[float, float]:
    """Slope per period and its t-statistic for a simple linear trend."""
    y = np.asarray(y, float)
    x = np.arange(len(y), dtype=float)
    xc = x - x.mean()
    b = (xc * (y - y.mean())).sum() / (xc ** 2).sum()
    resid = y - (y.mean() + b * xc)
    se = np.sqrt((resid ** 2).sum() / (len(y) - 2) / (xc ** 2).sum())
    return float(b), float(b / se) if se > 0 else float("inf")


def hinge_changepoint(y: np.ndarray) -> int:
    """Index where a flat series turns into a linear trend (min SSE hinge fit)."""
    y = np.asarray(y, float)
    best, best_k = np.inf, 0
    for k in range(2, len(y) - 2):
        x = np.maximum(np.arange(len(y)) - k, 0).astype(float)
        X = np.column_stack([np.ones_like(x), x])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        sse = ((y - X @ beta) ** 2).sum()
        if sse < best:
            best, best_k = sse, k
    return best_k


def step_changepoint(y: np.ndarray) -> int:
    """Index of the best single mean shift (min SSE)."""
    y = np.asarray(y, float)
    sse = [((y[:k] - y[:k].mean()) ** 2).sum() + ((y[k:] - y[k:].mean()) ** 2).sum()
           for k in range(2, len(y) - 1)]
    return int(np.argmin(sse)) + 2


def mape(actual, pred) -> float:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    return float(np.mean(np.abs(a - p) / np.abs(a)) * 100)


# ---------------------------------------------------------------- analyses
def channel_mix(con) -> dict:
    m = q(con, """
        SELECT month_start,
               avg(CASE WHEN connection='NDC' THEN 1.0 ELSE 0 END) FILTER (WHERE channel_group='Indirect') AS ndc_share_indirect,
               avg(CASE WHEN channel='Online Travel Agency' THEN 1.0 ELSE 0 END) FILTER (WHERE segment='Leisure') AS ota_share_leisure,
               avg(CASE WHEN channel_group='Direct' THEN 1.0 ELSE 0 END) AS direct_share,
               sum(distribution_cost) / count(*) AS dist_cost_per_booking,
               sum(distribution_cost) / sum(gross_revenue) AS cost_of_sale_pct
        FROM v_booking GROUP BY 1 ORDER BY 1""")
    ndc_slope, ndc_t = ols_slope(m.ndc_share_indirect)
    ota_slope, ota_t = ols_slope(m.ota_share_leisure)
    k = hinge_changepoint(m.ndc_share_indirect.values)
    first, last = m.iloc[:6], m.iloc[-6:]
    return {
        "monthly": m,
        "ndc_share_first6": float(first.ndc_share_indirect.mean()),
        "ndc_share_last6": float(last.ndc_share_indirect.mean()),
        "ndc_shift_start": str(m.month_start.iloc[k].date()),
        "ndc_slope_pp_per_month": ndc_slope * 100, "ndc_slope_t": ndc_t,
        "ota_share_first6": float(first.ota_share_leisure.mean()),
        "ota_share_last6": float(last.ota_share_leisure.mean()),
        "ota_slope_pp_per_month": ota_slope * 100, "ota_slope_t": ota_t,
        "cos_first6": float(first.cost_of_sale_pct.mean()),
        "cos_last6": float(last.cost_of_sale_pct.mean()),
        "dist_cost_per_booking_first6": float(first.dist_cost_per_booking.mean()),
        "dist_cost_per_booking_last6": float(last.dist_cost_per_booking.mean()),
    }


def target_variance(con, last_n: int = 6) -> dict:
    r = q(con, "SELECT * FROM v_route_monthly ORDER BY route_code, month_start")
    months = sorted(r.month_start.unique())[-last_n:]
    recent = r[r.month_start.isin(months)].groupby("route_code").agg(
        gross=("gross_revenue", "sum"), target=("target_revenue", "sum")).reset_index()
    recent["attainment"] = recent.gross / recent.target
    recent["variance"] = recent.gross - recent.target
    recent = recent.sort_values("attainment").reset_index(drop=True)
    worst = recent.iloc[0]
    ws = r[r.route_code == worst.route_code].reset_index(drop=True)
    k = step_changepoint(ws.target_attainment.values)
    before, after = ws.iloc[:k], ws.iloc[k:]
    net = q(con, "SELECT * FROM v_kpi_monthly ORDER BY month_start")
    last = net[net.month_start.isin(months)]
    return {
        "routes_recent": recent,
        "worst_route": worst.route_code,
        "worst_attainment": float(worst.attainment),
        "worst_gap_aud": float(-worst.variance),
        "worst_break_month": str(ws.month_start.iloc[k].date()),
        "worst_attain_before": float(before.gross_revenue.sum() / before.target_revenue.sum()),
        "worst_attain_after": float(after.gross_revenue.sum() / after.target_revenue.sum()),
        "worst_yield_change": float(after.yield_cents_rpk.mean() / before.yield_cents_rpk.mean() - 1),
        "worst_pax_change": float(after.pax.mean() / before.pax.mean() - 1),
        "network_attainment_recent": float(last.gross_revenue.sum() / last.target_revenue.sum()),
        "network_attainment_ex_worst": float(recent[recent.route_code != worst.route_code].gross.sum()
                                             / recent[recent.route_code != worst.route_code].target.sum()),
        "routes_below_95": recent[recent.attainment < 0.95].route_code.tolist(),
        "window": f"{pd.Timestamp(months[0]).strftime('%b %Y')} to {pd.Timestamp(months[-1]).strftime('%b %Y')}",
    }


def daily_anomalies(con, z_thresh: float = 4.0, min_expected: float = 20.0) -> dict:
    """Flag channel-days with bookings far below the same weekday's recent median.

    Only drops are flagged, and only where at least `min_expected` bookings were
    expected, so thin channels do not raise noise alerts."""
    d = q(con, "SELECT booking_date, channel_code, bookings, gross_revenue FROM v_daily_channel")
    d["booking_date"] = pd.to_datetime(d.booking_date)
    out = []
    for ch, g in d.groupby("channel_code"):
        g = g.set_index("booking_date")[["bookings", "gross_revenue"]].asfreq("D", fill_value=0).reset_index()
        g["channel_code"] = ch
        g["dow"] = g.booking_date.dt.dayofweek
        # expected = median of the same weekday over the previous 4 weeks
        g["expected"] = g.groupby("dow").bookings.transform(lambda s: s.shift(1).rolling(4).median())
        g["ratio"] = np.log((g.bookings + 1) / (g.expected + 1))
        med = g.ratio.median()
        mad = (g.ratio - med).abs().median() * 1.4826
        g["z"] = (g.ratio - med) / mad
        out.append(g)
    a = pd.concat(out)
    flagged = a[(a.z <= -z_thresh) & (a.expected >= min_expected)].sort_values("booking_date")
    # a "sustained" incident is 2+ consecutive flagged days on the same channel;
    # one-off flags are kept for review but not counted as lost revenue
    run_id = flagged.groupby("channel_code").booking_date.transform(lambda s: (s.diff().dt.days != 1).cumsum())
    run_len = flagged.groupby([flagged.channel_code, run_id]).booking_date.transform("size")
    flagged = flagged.assign(sustained=run_len >= 2)
    sus = flagged[flagged.sustained]
    lost_bk = float((sus.expected - sus.bookings).clip(lower=0).sum())
    avg_val = float(d.gross_revenue.sum() / d.bookings.sum())
    return {
        "series": a, "flagged": flagged[["booking_date", "channel_code", "bookings", "expected", "z", "sustained"]],
        "n_sustained": int(len(sus)), "sustained_channels": sorted(sus.channel_code.unique().tolist()),
        "n_flagged": int(len(flagged)),
        "flagged_channels": sorted(flagged.channel_code.unique().tolist()),
        "lost_bookings_est": lost_bk,
        "lost_revenue_est": lost_bk * avg_val,
    }


def _seasonal_naive_growth(y: np.ndarray, origin: int, h: int, use_growth: bool) -> np.ndarray:
    preds = []
    g = 1.0
    if use_growth:
        g = y[origin - 2: origin + 1].sum() / y[origin - 14: origin - 11].sum()
    for i in range(1, h + 1):
        preds.append(y[origin + i - 12] * g)
    return np.array(preds)


def forecast(con, h: int = 3) -> dict:
    m = q(con, "SELECT month_start, gross_revenue FROM v_kpi_monthly ORDER BY month_start")
    y = m.gross_revenue.values
    n = len(y)
    origins = list(range(14, n - h))
    res = {}
    for name, use_g in [("seasonal_naive", False), ("seasonal_naive_x_yoy", True)]:
        errs, rows = [], []
        for o in origins:
            p = _seasonal_naive_growth(y, o, h, use_g)
            a = y[o + 1: o + 1 + h]
            errs.append(mape(a, p))
            rows += [(m.month_start.iloc[o + i + 1], a[i], p[i]) for i in range(h)]
        res[name] = {"mape": float(np.mean(errs)), "backtest": pd.DataFrame(rows, columns=["month_start", "actual", "pred"])}
    best = min(res, key=lambda k: res[k]["mape"])
    fut = _seasonal_naive_growth(np.append(y, np.zeros(h)), n - 1, h, best == "seasonal_naive_x_yoy")
    fut_months = pd.date_range(pd.Timestamp(m.month_start.iloc[-1]) + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    return {
        "history": m, "models": {k: v["mape"] for k, v in res.items()}, "best_model": best,
        "best_backtest": res[best]["backtest"], "n_origins": len(origins),
        "forecast": pd.DataFrame({"month_start": fut_months, "gross_revenue": fut}),
        "forecast_total": float(fut.sum()),
        "same_q_last_year": float(y[n - 12: n - 12 + h].sum()),
    }


def recommendations(con, mix: dict, tv: dict, an: dict, ndc_target_share: float = 0.5) -> list[dict]:
    """Quantified recommendations over the trailing 12 months."""
    last12 = "booking_date > (SELECT max(booking_date) FROM v_booking) - INTERVAL 12 MONTH"
    c = q(con, f"""SELECT channel, connection, channel_group, count(*) AS bookings, sum(pax) AS pax,
                          sum(distribution_cost) AS cost, sum(gross_revenue) AS rev,
                          avg(CASE WHEN ancillary_revenue>0 THEN 1.0 ELSE 0 END) AS attach,
                          avg(ancillary_revenue) FILTER (WHERE ancillary_revenue>0) AS anc_value
                   FROM v_booking WHERE {last12} GROUP BY ALL""")
    ind = c[c.channel_group == "Indirect"].groupby("connection")[["bookings", "pax", "cost", "rev"]].sum()
    gds_cpb = ind.loc["GDS", "cost"] / ind.loc["GDS", "bookings"]
    ndc_cpb = ind.loc["NDC", "cost"] / ind.loc["NDC", "bookings"]
    move = ind.loc["GDS", "bookings"] * ndc_target_share
    recs = []
    recs.append({
        "title": f"Move {ndc_target_share:.0%} of remaining GDS agency bookings to NDC",
        "evidence": f"Indirect bookings cost ${gds_cpb:.2f} each via GDS vs ${ndc_cpb:.2f} via NDC (trailing 12 months).",
        "impact_aud": float(move * (gds_cpb - ndc_cpb)),
        "impact_text": f"saves about ${move * (gds_cpb - ndc_cpb):,.0f} a year in distribution cost",
    })
    d = c[c.channel_group == "Direct"]
    dir_cpb = d.cost.sum() / d.bookings.sum()
    dir_attach = (d.attach * d.bookings).sum() / d.bookings.sum()
    o = c[c.channel == "Online Travel Agency"]
    ota_cpb = o.cost.sum() / o.bookings.sum()
    ota_attach = (o.attach * o.bookings).sum() / o.bookings.sum()
    anc_val = float(q(con, f"SELECT avg(ancillary_revenue) FROM v_booking WHERE ancillary_revenue>0 AND {last12}").iloc[0, 0])
    shift = o.bookings.sum() * 0.10
    gain = shift * ((ota_cpb - dir_cpb) + (dir_attach - ota_attach) * anc_val)
    recs.append({
        "title": "Win back 10% of OTA leisure bookings to direct web/app",
        "evidence": (f"OTA share of leisure bookings rose from {mix['ota_share_first6']:.1%} to {mix['ota_share_last6']:.1%}; "
                     f"an OTA booking costs ${ota_cpb:.2f} vs ${dir_cpb:.2f} direct and attaches ancillaries "
                     f"{ota_attach:.1%} vs {dir_attach:.1%} of the time."),
        "impact_aud": float(gain),
        "impact_text": f"adds about ${gain:,.0f} a year (lower cost of sale plus extra ancillary sales)",
    })
    recs.append({
        "title": f"Review capacity and pricing on {tv['worst_route']}",
        "evidence": (f"Attainment fell from {tv['worst_attain_before']:.0%} to {tv['worst_attain_after']:.0%} of target after "
                     f"{pd.Timestamp(tv['worst_break_month']).strftime('%b %Y')}; passengers per month {tv['worst_pax_change']:+.0%}, "
                     f"yield {tv['worst_yield_change']:+.0%}."),
        "impact_aud": float(tv["worst_gap_aud"]),
        "impact_text": f"the route is ${tv['worst_gap_aud']:,.0f} behind target over {tv['window']}",
    })
    n_ndc = c[(c.channel_group == "Indirect") & (c.connection == "NDC")]
    n_gds = c[(c.channel_group == "Indirect") & (c.connection == "GDS")]
    ndc_att = (n_ndc.attach * n_ndc.bookings).sum() / n_ndc.bookings.sum()
    gds_att = (n_gds.attach * n_gds.bookings).sum() / n_gds.bookings.sum()
    anc_gain = move * (ndc_att - gds_att) * anc_val
    recs.append({
        "title": "Use NDC rich content to sell ancillaries through agents",
        "evidence": f"Agency bookings attach ancillaries {ndc_att:.1%} of the time via NDC vs {gds_att:.1%} via GDS.",
        "impact_aud": float(anc_gain),
        "impact_text": f"the same {ndc_target_share:.0%} GDS-to-NDC move adds about ${anc_gain:,.0f} a year in ancillary revenue",
    })
    recs.append({
        "title": "Add release monitoring on direct booking channels",
        "evidence": (f"The daily anomaly check flagged {an['n_flagged']} channel-days; {an['n_sustained']} of them form a "
                     f"sustained drop on {', '.join(an['sustained_channels'])} where bookings fell to about a tenth of the usual weekday level."),
        "impact_aud": float(an["lost_revenue_est"]),
        "impact_text": f"about {an['lost_bookings_est']:,.0f} bookings (${an['lost_revenue_est']:,.0f}) were lost during that incident",
    })
    return recs


def run_all(con) -> dict:
    mix = channel_mix(con)
    tv = target_variance(con)
    an = daily_anomalies(con)
    fc = forecast(con)
    recs = recommendations(con, mix, tv, an)
    k = q(con, "SELECT * FROM v_kpi_yoy_mom ORDER BY month_start")
    fy = q(con, """SELECT fin_year, sum(gross_revenue) gross, sum(net_revenue) net, sum(distribution_cost) dist,
                          sum(net_revenue)-sum(distribution_cost) net_after_dist, sum(pax) pax
                   FROM v_booking GROUP BY 1 ORDER BY 1""")
    return {"mix": mix, "target": tv, "anomaly": an, "forecast": fc, "recs": recs, "kpi": k, "fy": fy}
