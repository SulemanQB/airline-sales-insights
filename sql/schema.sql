-- Star schema for Southern Cross Air sales and distribution.
-- Grain of fact_booking: one booking (PNR). Grain of fact_target: route x month.

CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)      AS date_key,
    CAST(d AS DATE)                             AS date,
    year(d)                                     AS year,
    month(d)                                    AS month,
    strftime(d, '%Y-%m')                        AS year_month,
    CAST(date_trunc('month', d) AS DATE)        AS month_start,
    quarter(d)                                  AS quarter,
    -- Australian financial year runs July to June (FY26 = Jul 2025 to Jun 2026)
    'FY' || right(CAST(CASE WHEN month(d) >= 7 THEN year(d) + 1 ELSE year(d) END AS VARCHAR), 2) AS fin_year,
    dayname(d)                                  AS day_name,
    isodow(d)                                   AS iso_dow,
    isodow(d) >= 6                              AS is_weekend
FROM range(DATE '2024-01-01', DATE '2027-07-01', INTERVAL 1 DAY) t(d);

CREATE OR REPLACE TABLE dim_route AS
SELECT row_number() OVER (ORDER BY route_code) AS route_key, * FROM stg_route;

CREATE OR REPLACE TABLE dim_channel AS
SELECT row_number() OVER (ORDER BY channel_code) AS channel_key, * FROM stg_channel;

CREATE OR REPLACE TABLE dim_fare AS
SELECT row_number() OVER (ORDER BY fare_family) AS fare_key, * FROM stg_fare;

CREATE OR REPLACE TABLE dim_pos AS
SELECT row_number() OVER (ORDER BY pos_code) AS pos_key, * FROM stg_pos;

CREATE OR REPLACE TABLE dim_segment AS
SELECT row_number() OVER (ORDER BY segment_code) AS segment_key, * FROM stg_segment;

CREATE OR REPLACE TABLE fact_booking AS
SELECT
    b.booking_id,
    CAST(strftime(b.booking_date, '%Y%m%d') AS INTEGER) AS booking_date_key,
    CAST(strftime(b.travel_date, '%Y%m%d') AS INTEGER)  AS travel_date_key,
    r.route_key, c.channel_key, f.fare_key, p.pos_key, s.segment_key,
    b.lead_time_days, b.pax, b.status,
    b.fare_revenue, b.ancillary_revenue, b.refund_amount, b.distribution_cost
FROM stg_booking b
JOIN dim_route r   USING (route_code)
JOIN dim_channel c USING (channel_code)
JOIN dim_fare f    USING (fare_family)
JOIN dim_pos p     USING (pos_code)
JOIN dim_segment s USING (segment_code);

CREATE OR REPLACE TABLE fact_target AS
SELECT CAST(strftime(t.month_start, '%Y%m%d') AS INTEGER) AS month_date_key,
       r.route_key, t.target_revenue, t.target_pax
FROM stg_target t JOIN dim_route r USING (route_code);
