"""Seeded synthetic booking generator for Southern Cross Air.

Produces one row per booking (PNR) plus monthly route targets. The data has
seasonality, weekday patterns, lead-time pricing and three planted stories:

1. NDC migration: from March 2025 indirect bookings move from GDS to NDC,
   which has a much lower per-segment fee.
2. Route shock: MEL-SIN loses demand and price from October 2025.
3. Rising OTA share among leisure travellers, plus a 4-day app outage in
   February 2026 that the anomaly detector should find.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import config as C

MONTH_SEASON = np.array([1.25, 0.85, 0.95, 1.10, 0.90, 0.95, 1.15, 0.90, 1.05, 1.05, 0.95, 1.30])
MONTH_PRICE = np.array([1.08, 0.93, 0.97, 1.05, 0.95, 0.97, 1.06, 0.95, 1.00, 1.01, 0.98, 1.10])
DOW = np.array([1.12, 1.10, 1.08, 1.05, 0.98, 0.80, 0.87])  # Mon..Sun


def price_growth(days) -> np.ndarray:
    """Underlying fare inflation of 2.5% a year."""
    return 1.025 ** (np.asarray((pd.DatetimeIndex(days) - pd.Timestamp(C.START)).days) / 365.0)


def _ramp(days: pd.DatetimeIndex, start: date, end: date) -> np.ndarray:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    return np.clip((days - s).days / max((e - s).days, 1), 0, 1)


def demand_intensity(days: pd.DatetimeIndex, with_shock: bool = True) -> np.ndarray:
    """Expected bookings per day x route (shape [n_days, n_routes])."""
    base = np.array([r[7] for r in C.ROUTES], dtype=float)
    season = MONTH_SEASON[days.month - 1]
    dow = DOW[days.dayofweek]
    growth = 1.04 ** ((days - pd.Timestamp(C.START)).days / 365.0)
    lam = np.outer(season * dow * growth, base)
    if with_shock:
        j = [r[0] for r in C.ROUTES].index(C.STORY_ROUTE)
        lam[days >= pd.Timestamp(C.STORY_ROUTE_SHOCK), j] *= 0.70
    return lam


def generate(seed: int = C.SEED, start: date = C.START, end: date = C.END):
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    lam = demand_intensity(days)
    counts = rng.poisson(lam)
    d_idx, r_idx = np.nonzero(counts)
    reps = counts[d_idx, r_idx]
    d_idx, r_idx = np.repeat(d_idx, reps), np.repeat(r_idx, reps)
    n = len(d_idx)

    bdate = days[d_idx]
    t = (bdate - pd.Timestamp(start)).days.values / max((days[-1] - days[0]).days, 1)
    route = np.array(C.ROUTES, dtype=object)[r_idx]
    intl = np.array([r[3] == "International" for r in C.ROUTES])[r_idx]
    weekday = bdate.dayofweek.values < 5

    # customer segment
    p_corp = np.where(intl, 0.18, 0.38) * np.where(weekday, 1.15, 0.55)
    corp = rng.random(n) < p_corp

    # channel choice (OTA share among leisure rises ~7pp over two years)
    ota_lift = 0.07 * t
    p_corp_ch = np.array([0.22, 0.06, 0.66, 0.06])
    p = np.empty((n, 4))
    p[:] = p_corp_ch
    leis = ~corp
    p[leis, 0] = 0.44 - ota_lift[leis]
    p[leis, 1] = 0.18
    p[leis, 2] = 0.08
    p[leis, 3] = 0.30 + ota_lift[leis]
    u = rng.random(n)[:, None]
    ch_group = (u > np.cumsum(p, axis=1)).sum(axis=1)  # 0 web,1 app,2 tmc,3 ota

    # app outage: most app sales lost, ~30% recover on web
    o0, o1 = (pd.Timestamp(x) for x in C.STORY_APP_OUTAGE)
    in_out = (bdate >= o0) & (bdate <= o1)
    app_hit = in_out & (ch_group == 1)
    r_out = rng.random(n)
    to_web = app_hit & (r_out < 0.30)
    lost = app_hit & (r_out >= 0.30) & (r_out < 0.85)
    ch_group[to_web] = 0

    # NDC share of indirect: 8% before programme, ramps to ~58% by end
    ndc_share = 0.08 + 0.50 * _ramp(bdate, C.STORY_NDC_START, C.END)
    ndc = rng.random(n) < ndc_share
    codes = np.array(["WEB", "APP", "TMC_GDS", "OTA_GDS"], dtype=object)[ch_group]
    codes = np.where((ch_group == 2) & ndc, "TMC_NDC", codes)
    codes = np.where((ch_group == 3) & ndc, "OTA_NDC", codes)

    # fare family
    p_ff_c = np.array([0.02, 0.25, 0.43, 0.18, 0.12])
    p_ff_l = np.array([0.30, 0.50, 0.13, 0.05, 0.02])
    pf = np.where(corp[:, None], p_ff_c, p_ff_l)
    ff = (rng.random(n)[:, None] > np.cumsum(pf, axis=1)).sum(axis=1)
    ff = np.minimum(ff, 4)
    fares = C.FARES
    fare_mult = np.array([f[2] for f in fares])[ff]
    attach_base = np.array([f[3] for f in fares])[ff]
    refundable = np.array([f[4] for f in fares])[ff]

    # lead time (days between booking and travel)
    lead = np.where(corp, rng.gamma(1.6, 8.0, n), rng.gamma(1.8, 26.0, n)).round().astype(int)
    lead = np.clip(lead, 0, 330)
    lead_mult = 0.9 + 0.6 * np.exp(-lead / 10.0)

    pax = np.where(corp, 1 + rng.poisson(0.15, n), 1 + rng.poisson(0.7, n))

    base_fare = np.array([r[6] for r in C.ROUTES], dtype=float)[r_idx]
    price = MONTH_PRICE[bdate.month - 1] * price_growth(bdate)
    shock_px = np.where((route[:, 0] == C.STORY_ROUTE) & (bdate >= pd.Timestamp(C.STORY_ROUTE_SHOCK)), 0.90, 1.0)
    fare = base_fare * fare_mult * lead_mult * price * shock_px * rng.lognormal(0, 0.12, n) * pax
    fare = fare.round(2)

    # point of sale
    dest_pos = {"AKL": "NZ", "SIN": "SG", "NRT": "JP", "LAX": "US", "DPS": "ID"}
    dest = route[:, 2]
    pos = np.full(n, "AU", dtype=object)
    r_pos = rng.random(n)
    dom_other = np.array(["NZ", "US", "GB", "SG"], dtype=object)
    pos = np.where(~intl & (r_pos > 0.93), dom_other[rng.integers(0, 4, n)], pos)
    foreign = np.array([dest_pos.get(x, "AU") for x in dest], dtype=object)
    pos = np.where(intl & (r_pos > 0.55) & (r_pos <= 0.85), foreign, pos)
    intl_other = np.array(["GB", "US", "SG", "NZ"], dtype=object)
    pos = np.where(intl & (r_pos > 0.85), intl_other[rng.integers(0, 4, n)], pos)

    # ancillaries: rich content (direct/NDC) sells far better than GDS
    ch_factor = np.select([np.isin(codes, ["WEB", "APP"]), np.char.endswith(codes.astype(str), "NDC")], [1.0, 0.85], 0.35)
    has_anc = rng.random(n) < attach_base * ch_factor
    anc = np.where(has_anc, rng.uniform(25, 65, n) * pax * np.where(intl, 1.6, 1.0), 0.0).round(2)

    # cancellations / refunds
    travel = bdate + pd.to_timedelta(lead, unit="D")
    cancel = rng.random(n) < np.where(refundable, 0.12, 0.05)
    status = np.where(cancel, "Cancelled", np.where(travel > pd.Timestamp(end), "Booked", "Flown"))
    refund = np.where(cancel & refundable, fare + anc, 0.0).round(2)

    # distribution cost
    ch_tab = {c[0]: c for c in C.CHANNELS}
    comm = np.array([ch_tab[c][4] for c in codes])
    fee = np.array([ch_tab[c][5] for c in codes])
    dist_cost = (comm * fare + fee * pax).round(2)

    df = pd.DataFrame({
        "booking_date": bdate.date, "travel_date": travel.date, "route_code": route[:, 0],
        "channel_code": codes, "fare_family": np.array([f[0] for f in fares], dtype=object)[ff],
        "pos_code": pos, "segment_code": np.where(corp, "CORP", "LEIS"),
        "lead_time_days": lead, "pax": pax, "fare_revenue": fare, "ancillary_revenue": anc,
        "status": status, "refund_amount": refund, "distribution_cost": dist_cost,
    })
    df = df[~lost].reset_index(drop=True)
    df.insert(0, "booking_id", np.arange(1, len(df) + 1))
    targets = make_targets(df, days, seed)
    return df, targets


def make_targets(df: pd.DataFrame, days: pd.DatetimeIndex, seed: int) -> pd.DataFrame:
    """Plan built before the route shock: unshocked demand x pre-shock revenue per booking x 1.02."""
    rng = np.random.default_rng(seed + 1)
    lam = demand_intensity(days, with_shock=False)
    price = MONTH_PRICE[days.month - 1] * price_growth(days)
    bd = pd.to_datetime(df["booking_date"])
    pre = df[bd < pd.Timestamp(C.STORY_ROUTE_SHOCK)]
    pre_d = pd.to_datetime(pre["booking_date"])
    pre_px = MONTH_PRICE[pre_d.dt.month - 1] * price_growth(pre_d)
    rpb = ((pre["fare_revenue"] + pre["ancillary_revenue"]) / pre_px).groupby(pre["route_code"]).mean()
    ppb = pre.groupby("route_code")["pax"].mean()
    rows = []
    month = days.to_period("M")
    for j, r in enumerate(C.ROUTES):
        code = r[0]
        tmp = pd.DataFrame({"m": month, "rev": lam[:, j] * price * rpb[code], "pax": lam[:, j] * ppb[code]})
        g = tmp.groupby("m").sum()
        for m, row in g.iterrows():
            k = 1.02 * rng.normal(1.0, 0.02)
            rows.append((m.to_timestamp().date(), code, round(row["rev"] * k, 0), round(row["pax"] * k, 0)))
    return pd.DataFrame(rows, columns=["month_start", "route_code", "target_revenue", "target_pax"])
