# Building the Power BI report (about an hour)

This builds a `.pbix` on Windows from the star schema the pipeline exports. You don't need Python: the Parquet files are committed in `data/powerbi/`. If you'd rather use CSV, run `make all` and take them from `output/powerbi/csv/`.

## 1. Load the tables (10 min)

1. Open Power BI Desktop, then **Get data → Parquet** (or **Text/CSV**). Load all eight files:
   `dim_date`, `dim_route`, `dim_channel`, `dim_fare`, `dim_pos`, `dim_segment`, `fact_booking`, `fact_target`.
2. In Power Query, check these types: `dim_date[date]` = Date; every `*_key` = Whole number; money columns = Fixed decimal; `dim_date[is_weekend]` and `dim_fare[refundable]` = True/False. Click **Close & Apply**.
3. Select `dim_date`, then **Table tools → Mark as date table** and pick the `date` column.
4. Sort columns: `dim_date[year_month]` by `month_start`, and `dim_date[day_name]` by `iso_dow`.

## 2. Relationships (Model view, 10 min)

All relationships are many-to-one (*:1) with single-direction filtering from the dimension to the fact.

| From (many) | To (one) | Active |
|---|---|---|
| `fact_booking[booking_date_key]` | `dim_date[date_key]` | Yes |
| `fact_booking[travel_date_key]` | `dim_date[date_key]` | **No** (used via `USERELATIONSHIP`) |
| `fact_booking[route_key]` | `dim_route[route_key]` | Yes |
| `fact_booking[channel_key]` | `dim_channel[channel_key]` | Yes |
| `fact_booking[fare_key]` | `dim_fare[fare_key]` | Yes |
| `fact_booking[pos_key]` | `dim_pos[pos_key]` | Yes |
| `fact_booking[segment_key]` | `dim_segment[segment_key]` | Yes |
| `fact_target[month_date_key]` | `dim_date[date_key]` | Yes (targets sit on the 1st of each month) |
| `fact_target[route_key]` | `dim_route[route_key]` | Yes |

Hide every `*_key` column in report view. That gives you a clean star: two facts sharing `dim_date` and `dim_route`.

## 3. Measures (20 min)

Create an empty table called `_Measures` (**Enter data**, then OK) and add these measures to it. Format the money measures as Currency and the ratios as Percentage.

```DAX
Fare Revenue        = SUM ( fact_booking[fare_revenue] )
Ancillary Revenue   = SUM ( fact_booking[ancillary_revenue] )
Total Revenue       = [Fare Revenue] + [Ancillary Revenue]
Refunds             = SUM ( fact_booking[refund_amount] )
Net Revenue         = [Total Revenue] - [Refunds]
Distribution Cost   = SUM ( fact_booking[distribution_cost] )
Net Revenue After Distribution = [Net Revenue] - [Distribution Cost]
Bookings            = COUNTROWS ( fact_booking )
Passengers          = SUM ( fact_booking[pax] )
Avg Booking Value   = DIVIDE ( [Total Revenue], [Bookings] )

RPK = SUMX ( fact_booking, fact_booking[pax] * RELATED ( dim_route[distance_km] ) )
Yield (c/RPK) = DIVIDE ( [Fare Revenue], [RPK] ) * 100

-- seat capacity: daily seats x distance for every day in the selected period
ASK =
VAR LastDay = CALCULATE ( MAX ( dim_date[date] ), FILTER ( ALL ( dim_date ), dim_date[date_key] <= MAX ( fact_booking[booking_date_key] ) ) )
VAR Days = COUNTROWS ( FILTER ( dim_date, dim_date[date] <= LastDay && dim_date[date] >= DATE ( 2024, 7, 1 ) ) )
RETURN SUMX ( dim_route, dim_route[daily_seats] * dim_route[distance_km] ) * Days
RASK Proxy (c/ASK) = DIVIDE ( [Net Revenue], [ASK] ) * 100

Channel Share       = DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], ALL ( dim_channel ) ) )
Booking Share       = DIVIDE ( [Bookings], CALCULATE ( [Bookings], ALL ( dim_channel ) ) )
NDC Share of Indirect =
    DIVIDE (
        CALCULATE ( [Bookings], dim_channel[connection] = "NDC" ),
        CALCULATE ( [Bookings], dim_channel[channel_group] = "Indirect" )
    )
Cost of Sale %      = DIVIDE ( [Distribution Cost], [Total Revenue] )
Cost per Booking    = DIVIDE ( [Distribution Cost], [Bookings] )
Ancillary Attach Rate =
    DIVIDE ( CALCULATE ( [Bookings], fact_booking[ancillary_revenue] > 0 ), [Bookings] )
Cancellation Rate   = DIVIDE ( CALCULATE ( [Bookings], fact_booking[status] = "Cancelled" ), [Bookings] )

Target Revenue      = SUM ( fact_target[target_revenue] )
Target Attainment   = DIVIDE ( [Total Revenue], [Target Revenue] )
Variance to Target  = [Total Revenue] - [Target Revenue]

Revenue LY          = CALCULATE ( [Total Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )
YoY %               = DIVIDE ( [Total Revenue] - [Revenue LY], [Revenue LY] )
Revenue PM          = CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
MoM %               = DIVIDE ( [Total Revenue] - [Revenue PM], [Revenue PM] )
Revenue FYTD        = TOTALYTD ( [Total Revenue], dim_date[date], "30/6" )
Yield YoY %         = DIVIDE ( [Yield (c/RPK)] - CALCULATE ( [Yield (c/RPK)], SAMEPERIODLASTYEAR ( dim_date[date] ) ),
                               CALCULATE ( [Yield (c/RPK)], SAMEPERIODLASTYEAR ( dim_date[date] ) ) )

Avg Lead Time (days) = AVERAGE ( fact_booking[lead_time_days] )
Passengers by Travel Date =
    CALCULATE ( [Passengers], USERELATIONSHIP ( fact_booking[travel_date_key], dim_date[date_key] ) )
```

Add a lead-time bucket as a **calculated column** on `fact_booking`:

```DAX
Lead Bucket =
SWITCH ( TRUE (),
    fact_booking[lead_time_days] <= 7, "0-7",
    fact_booking[lead_time_days] <= 21, "8-21",
    fact_booking[lead_time_days] <= 60, "22-60",
    "61+" )
```

**Check your numbers.** With no filters, `Total Revenue` for `dim_date[fin_year]` = FY26 should show **$76.37m**, and `Target Attainment` for Jan to Jun 2026 should show **93.8%**. Those are the same figures as the Excel pack and the README.

## 4. Suggested pages (20 min)

**Page 1: Executive summary**
- Top row of cards: Total Revenue, YoY %, Net Revenue After Distribution, Target Attainment, Cost of Sale %, Yield (c/RPK).
- A line and clustered column chart: `month_start` on the axis, Total Revenue as columns, Target Revenue as the line.
- Slicers: `fin_year`, `haul`, `segment`.

**Page 2: Channel and distribution**
- A 100% stacked column chart: `month_start` × Channel Share, with `dim_channel[channel]` as the legend.
- A line chart of NDC Share of Indirect and Cost of Sale % (secondary axis) by month.
- A matrix: rows are channel and connection; values are Bookings, Total Revenue, Cost per Booking, Cost of Sale % and Ancillary Attach Rate. Put conditional formatting on Cost of Sale %.

**Page 3: Route performance**
- A bar chart of Target Attainment by `route_code`, sorted ascending. Colour it with rules: red below 90%, amber below 95%, otherwise teal.
- A matrix: route × month with Variance to Target, using a background colour scale.
- A scatter of Yield (c/RPK) against RASK Proxy, sized by Passengers.

**Page 4: Customer and booking curve**
- A clustered column chart of Passengers by Lead Bucket, split by segment.
- A line chart of average fare per passenger (`DIVIDE([Fare Revenue],[Passengers])`) by Lead Bucket.
- A map or bar chart by `dim_pos[pos_country]`.

**Page 5: Drill-through** on `route_code`: the route's monthly trend, its channel mix and its fare-family mix.

Finish by setting a theme (navy #14365D, teal #1B9AAA, amber #F2A541), adding a title text box to each page, and saving the file as `SouthernCrossAir_Commercial.pbix`.
