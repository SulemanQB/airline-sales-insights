import pytest


def test_star_tables(con):
    for t in ["dim_date", "dim_route", "dim_channel", "dim_fare", "dim_pos", "dim_segment", "fact_booking", "fact_target"]:
        assert con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] > 0


def test_no_orphans(data, con):
    assert con.execute("SELECT count(*) FROM fact_booking").fetchone()[0] == len(data[0])
    assert con.execute("SELECT count(*) FROM v_booking").fetchone()[0] == len(data[0])


def test_views_reconcile(data, con):
    b = data[0]
    gross = con.execute("SELECT sum(gross_revenue) FROM v_kpi_monthly").fetchone()[0]
    assert gross == pytest.approx((b.fare_revenue + b.ancillary_revenue).sum(), rel=1e-9)
    nad = con.execute("SELECT sum(net_after_dist) FROM v_kpi_monthly").fetchone()[0]
    exp = (b.fare_revenue + b.ancillary_revenue - b.refund_amount - b.distribution_cost).sum()
    assert nad == pytest.approx(exp, rel=1e-9)
    r = con.execute("SELECT sum(gross_revenue) FROM v_route_monthly").fetchone()[0]
    assert r == pytest.approx(gross, rel=1e-9)


def test_channel_share_sums_to_one(con):
    s = con.execute("SELECT max(abs(t - 1)) FROM (SELECT month_start, sum(revenue_share) t FROM v_channel_mix_monthly GROUP BY 1)").fetchone()[0]
    assert s < 1e-9


def test_yoy_present_after_12_months(con):
    df = con.execute("SELECT * FROM v_kpi_yoy_mom").df()
    assert df.revenue_yoy_pct.iloc[:12].isna().all() and df.revenue_yoy_pct.iloc[12:].notna().all()
