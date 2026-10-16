import numpy as np

from asi import analysis as A
from asi import config as C


def test_ndc_shift_detected(res):
    m = res["mix"]
    assert m["ndc_share_last6"] - m["ndc_share_first6"] > 0.25
    assert m["ndc_slope_t"] > 5
    # the hinge fit should find the programme start within two months
    import pandas as pd
    assert abs((pd.Timestamp(m["ndc_shift_start"]) - pd.Timestamp(C.STORY_NDC_START)).days) <= 62


def test_ota_rise_detected(res):
    assert res["mix"]["ota_share_last6"] > res["mix"]["ota_share_first6"]
    assert res["mix"]["ota_slope_t"] > 3


def test_underperforming_route_found(res):
    t = res["target"]
    assert t["worst_route"] == C.STORY_ROUTE
    assert t["worst_break_month"] == str(C.STORY_ROUTE_SHOCK)
    assert t["worst_attain_after"] < t["worst_attain_before"] - 0.2


def test_outage_flagged(res):
    f = res["anomaly"]["flagged"]
    app = f[f.channel_code == "APP"].booking_date.dt.date.tolist()
    assert res["anomaly"]["sustained_channels"] == ["APP"]
    d0, d1 = C.STORY_APP_OUTAGE
    assert all(d0 <= d <= d1 for d in app) and len(app) >= 3


def test_forecast_backtest(res):
    fc = res["forecast"]
    assert all(np.isfinite(v) and v > 0 for v in fc["models"].values())
    assert fc["models"][fc["best_model"]] < 10
    assert len(fc["forecast"]) == 3


def test_recommendations_quantified(res):
    assert 3 <= len(res["recs"]) <= 5
    assert all(r["impact_aud"] > 0 for r in res["recs"])


def test_helpers():
    y = np.r_[np.zeros(10), np.arange(1, 11)]
    assert abs(A.hinge_changepoint(y) - 9) <= 1
    assert A.step_changepoint(np.r_[np.ones(8), np.ones(8) * 5]) == 8
    assert A.mape([100, 200], [110, 180]) == 10.0
