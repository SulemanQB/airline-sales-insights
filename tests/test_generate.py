import pandas as pd

from asi import config as C
from asi.generate import generate


def test_deterministic(data):
    a, ta = data
    b, tb = generate()
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(ta, tb)


def test_coverage(data):
    b, t = data
    d = pd.to_datetime(b.booking_date)
    assert d.min().date() == C.START and d.max().date() == C.END
    assert (d.max() - d.min()).days >= 729
    assert set(b.channel_code) == {c[0] for c in C.CHANNELS}
    assert set(b.route_code) == {r[0] for r in C.ROUTES}
    assert set(b.fare_family) == {f[0] for f in C.FARES}
    assert {"Flown", "Cancelled", "Booked"} <= set(b.status)
    assert len(t) == 24 * len(C.ROUTES)


def test_money_sane(data):
    b, _ = data
    assert (b.fare_revenue > 0).all()
    assert (b.distribution_cost >= 0).all()
    assert (b.refund_amount <= b.fare_revenue + b.ancillary_revenue + 0.01).all()
    assert (b.refund_amount[b.status != "Cancelled"] == 0).all()
    assert (b.lead_time_days >= 0).all()


def test_seasonality(data):
    b, _ = data
    m = b.groupby(pd.to_datetime(b.booking_date).dt.month).size()
    assert m[12] > m[2] * 1.3  # December peak vs February trough
