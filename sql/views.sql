-- KPI views. Revenue definitions:
--   gross_revenue        = fare + ancillary (booked value)
--   net_revenue          = gross_revenue - refunds
--   net_after_dist       = net_revenue - distribution cost (commission + GDS/NDC fees + card fees)
--   cost_of_sale_pct     = distribution cost / gross_revenue
--   yield (cents/RPK)    = fare revenue / revenue passenger km
--   RASK proxy (c/ASK)   = net revenue / available seat km, ASK = daily seats x distance x days in month

CREATE OR REPLACE VIEW v_booking AS
SELECT b.*, d.date AS booking_date, d.month_start, d.year_month, d.year, d.month, d.fin_year,
       r.route_code, r.haul, r.distance_km, c.channel_code, c.channel, c.channel_group, c.connection,
       f.fare_family, f.cabin, p.pos_code, p.pos_region, s.segment,
       b.fare_revenue + b.ancillary_revenue AS gross_revenue,
       b.fare_revenue + b.ancillary_revenue - b.refund_amount AS net_revenue,
       b.pax * r.distance_km AS rpk,
       CASE WHEN b.lead_time_days <= 7 THEN '0-7'
            WHEN b.lead_time_days <= 21 THEN '8-21'
            WHEN b.lead_time_days <= 60 THEN '22-60'
            ELSE '61+' END AS lead_bucket
FROM fact_booking b
JOIN dim_date d ON d.date_key = b.booking_date_key
JOIN dim_route r USING (route_key)
JOIN dim_channel c USING (channel_key)
JOIN dim_fare f USING (fare_key)
JOIN dim_pos p USING (pos_key)
JOIN dim_segment s USING (segment_key);

CREATE OR REPLACE VIEW v_capacity_monthly AS
SELECT d.month_start, r.route_code,
       sum(r.daily_seats * r.distance_km) AS ask
FROM dim_date d CROSS JOIN dim_route r
WHERE d.date BETWEEN (SELECT min(booking_date) FROM v_booking) AND (SELECT max(booking_date) FROM v_booking)
GROUP BY ALL;

CREATE OR REPLACE VIEW v_kpi_monthly AS
WITH m AS (
    SELECT month_start, count(*) AS bookings, sum(pax) AS pax,
           sum(fare_revenue) AS fare_revenue, sum(ancillary_revenue) AS ancillary_revenue,
           sum(gross_revenue) AS gross_revenue, sum(refund_amount) AS refunds,
           sum(net_revenue) AS net_revenue, sum(distribution_cost) AS distribution_cost,
           sum(rpk) AS rpk
    FROM v_booking GROUP BY month_start
), cap AS (SELECT month_start, sum(ask) AS ask FROM v_capacity_monthly GROUP BY month_start),
tg AS (SELECT d.month_start, sum(t.target_revenue) AS target_revenue
       FROM fact_target t JOIN dim_date d ON d.date_key = t.month_date_key GROUP BY 1)
SELECT m.*, m.net_revenue - m.distribution_cost AS net_after_dist,
       m.distribution_cost / m.gross_revenue AS cost_of_sale_pct,
       100 * m.fare_revenue / m.rpk AS yield_cents_rpk,
       100 * m.net_revenue / cap.ask AS rask_proxy_cents,
       m.gross_revenue / m.bookings AS avg_booking_value,
       tg.target_revenue, m.gross_revenue / tg.target_revenue AS target_attainment
FROM m JOIN cap USING (month_start) LEFT JOIN tg USING (month_start)
ORDER BY month_start;

CREATE OR REPLACE VIEW v_kpi_yoy_mom AS
SELECT *,
       gross_revenue / lag(gross_revenue, 1) OVER w - 1  AS revenue_mom_pct,
       gross_revenue / lag(gross_revenue, 12) OVER w - 1 AS revenue_yoy_pct,
       pax / lag(pax, 12) OVER w - 1                     AS pax_yoy_pct,
       yield_cents_rpk / lag(yield_cents_rpk, 12) OVER w - 1 AS yield_yoy_pct
FROM v_kpi_monthly WINDOW w AS (ORDER BY month_start);

CREATE OR REPLACE VIEW v_channel_mix_monthly AS
SELECT month_start, channel_code, channel, channel_group, connection,
       count(*) AS bookings, sum(pax) AS pax, sum(gross_revenue) AS gross_revenue,
       sum(distribution_cost) AS distribution_cost,
       sum(distribution_cost) / sum(gross_revenue) AS cost_of_sale_pct,
       sum(gross_revenue) / sum(sum(gross_revenue)) OVER (PARTITION BY month_start) AS revenue_share,
       count(*) / sum(count(*)) OVER (PARTITION BY month_start) AS booking_share,
       avg(CASE WHEN ancillary_revenue > 0 THEN 1.0 ELSE 0.0 END) AS ancillary_attach_rate
FROM v_booking GROUP BY month_start, channel_code, channel, channel_group, connection
ORDER BY month_start, channel_code;

CREATE OR REPLACE VIEW v_route_monthly AS
WITH a AS (
    SELECT month_start, route_code, haul, sum(pax) AS pax, sum(gross_revenue) AS gross_revenue,
           sum(net_revenue) AS net_revenue, sum(distribution_cost) AS distribution_cost,
           sum(fare_revenue) AS fare_revenue, sum(rpk) AS rpk
    FROM v_booking GROUP BY ALL
), tg AS (
    SELECT d.month_start, r.route_code, t.target_revenue, t.target_pax
    FROM fact_target t JOIN dim_date d ON d.date_key = t.month_date_key JOIN dim_route r USING (route_key)
)
SELECT a.*, a.net_revenue - a.distribution_cost AS net_after_dist,
       100 * a.fare_revenue / a.rpk AS yield_cents_rpk,
       100 * a.net_revenue / c.ask AS rask_proxy_cents,
       tg.target_revenue, tg.target_pax,
       a.gross_revenue / tg.target_revenue AS target_attainment,
       a.gross_revenue / lag(a.gross_revenue, 12) OVER (PARTITION BY a.route_code ORDER BY a.month_start) - 1 AS revenue_yoy_pct
FROM a JOIN tg USING (month_start, route_code) JOIN v_capacity_monthly c USING (month_start, route_code)
ORDER BY a.month_start, a.route_code;

CREATE OR REPLACE VIEW v_target_attainment AS
SELECT month_start, route_code, gross_revenue, target_revenue, target_attainment,
       gross_revenue - target_revenue AS variance_to_target
FROM v_route_monthly;

CREATE OR REPLACE VIEW v_leadtime_cohort AS
SELECT month_start, lead_bucket, segment, count(*) AS bookings, sum(pax) AS pax,
       sum(fare_revenue) / sum(pax) AS avg_fare_per_pax,
       count(*) / sum(count(*)) OVER (PARTITION BY month_start, segment) AS share_of_segment
FROM v_booking GROUP BY month_start, lead_bucket, segment
ORDER BY month_start, segment, lead_bucket;

CREATE OR REPLACE VIEW v_daily_channel AS
SELECT booking_date, channel_code, count(*) AS bookings, sum(gross_revenue) AS gross_revenue
FROM v_booking GROUP BY ALL ORDER BY booking_date, channel_code;
