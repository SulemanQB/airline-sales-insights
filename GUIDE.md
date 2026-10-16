# Guide: what each part does and how to talk about it

This is a plain-English walkthrough of the project, written so you can explain any part of it to a commercial audience. That means a sales manager, a distribution lead or a finance partner, not just other analysts.

## The one-sentence version

> "I built a monthly sales and distribution reporting pipeline for an airline. It models bookings in a star schema, tracks revenue, yield, channel mix and cost of sale against target, spots trends and problems automatically, and rebuilds the Excel pack and a one-page summary with quantified recommendations in one command."

## 1. The data (`src/asi/generate.py`, `src/asi/config.py`)

**What it is.** Real airline booking data is confidential, so the project creates realistic fake data for a made-up airline, Southern Cross Air. It covers two financial years (July 2024 to June 2026) and 220,569 bookings, each with:
- a **route** (7 domestic, such as SYD-MEL, and 5 international, such as MEL-SIN and SYD-LAX)
- a **sales channel**: direct web, direct app, travel agent/TMC (corporate travel managers) or OTA (online travel agencies)
- for agency sales, a **connection**: GDS (the older booking systems agents use, with a high per-booking fee) or NDC (the newer airline-to-agent connection, with a lower fee and the ability to show and sell extras)
- the **fare family** (Starter, Saver, Flex, Business, Business Flex) and cabin
- the **lead time** (days between booking and flying), the **point of sale** country, and **corporate vs leisure**
- fare and **ancillary** revenue (bags, seats and so on), **cancellations and refunds**, and the **distribution cost** (commission plus GDS/NDC fees plus card fees)
- monthly **revenue targets** per route

It behaves like a real airline: there are peaks in December/January, April and July, corporate travellers book late and pay more, and weekdays are busier. "Seeded" means it produces the same data every run, so the numbers are reproducible.

**Three planted business stories** give the analysis something real to find:
1. From March 2025, agency bookings move from GDS to NDC. That should lower distribution cost.
2. From October 2025, MEL-SIN loses passengers and price, as if a competitor added capacity.
3. Leisure travellers drift towards OTAs, and in February 2026 the app has a 4-day outage.

**How to say it:** "I simulated the data so I could share the work, and planted known events so I could prove the analysis finds them. The tests check that it does."

## 2. The data model (`sql/schema.sql`, `sql/views.sql`)

**Star schema** is the standard way to organise data for reporting tools like Power BI. There is one big table of events (the **fact** table, one row per booking) surrounded by small lookup tables (**dimensions**): date, route, channel, fare, point of sale and customer segment. Targets are a second fact table at route × month level. This layout makes slicing fast and keeps definitions in one place.

**Views** are saved queries that define each KPI once, so the Excel pack, the one-pager and the analysis all use the same definition:

| KPI | Plain meaning |
|---|---|
| Gross revenue | Fare plus extras at time of booking |
| Net revenue | Gross minus refunds |
| Distribution cost / cost of sale % | What it costs to sell the ticket, as dollars and as a share of revenue |
| Net revenue after distribution | What the airline keeps after paying to sell |
| Yield | Fare revenue per passenger-kilometre: "how well are we pricing?" |
| RASK (proxy) | Revenue per seat-kilometre flown: "how well are we filling and pricing the aircraft?" |
| Channel mix | Each channel's share of bookings and revenue |
| Target attainment | Actual divided by plan |
| YoY / MoM | Change against the same month last year and against last month |
| Lead-time cohort | Bookings and average fare by how far ahead people book |

The tests prove that the views add back exactly to the raw data. That is the "do the numbers reconcile?" check every finance partner asks about.

## 3. The analysis (`src/asi/analysis.py`)

Every number is calculated from the data on each run. None are typed in by hand.

- **Channel-mix shift.** The NDC share of agency bookings went from 8.1% to 48.5%. A simple trend line confirms it is a real trend and not noise (t-statistic 16). A "hinge" fit finds the month the trend started, March 2025, which matches the planted programme start. Cost of sale fell from 3.41% to 3.25% of revenue.
- **OTA drift.** OTA share of leisure bookings rose from 30.6% to 36.3%. That matters because an OTA booking costs about $54 to sell, against about $8 direct.
- **Variance to target.** The network was at 93.8% of target in Jan to Jun 2026, and 97.6% without MEL-SIN. The analysis ranks routes by attainment, then finds the month MEL-SIN broke (October 2025) and splits the cause into volume (−29% passengers) and price (−8% yield).
- **Anomaly alerts.** Each day, each channel's bookings are compared with the median of the same weekday over the previous four weeks. Days far below normal are flagged. It caught the 4-day app outage (bookings at about a tenth of normal, roughly $115k lost) and one single-day web dip. Single-day dips are shown but not counted as lost revenue, which keeps the alert honest.
- **Forecast.** Next quarter's revenue is "same month last year × recent year-on-year growth". It was tested by pretending to stand at 7 different past months and forecasting 3 months ahead each time. The average error (MAPE) was 2.1%, against 2.7% for a plain same-month-last-year forecast. The forecast for Jul to Sep 2026 is $19.8m.

**How to say it:** "I keep the methods simple and explainable, then backtest them, so a commercial manager can trust and challenge the numbers."

## 4. The recommendations

Each recommendation is tied to a dollar figure from the last 12 months:
1. **Move half of the remaining GDS agency bookings to NDC**: about $251k a year saved in distribution cost.
2. **Win back 10% of OTA leisure bookings to direct**: about $164k a year from lower selling cost plus more extras sold.
3. **Review MEL-SIN capacity and pricing**: it is $1.57m behind target over six months.
4. **Use NDC to sell extras through agents**: NDC bookings attach extras 27.6% of the time against 11.6% via GDS, worth about $234k a year.
5. **Monitor app releases**: the February outage cost about 169 bookings ($115k).

**How to talk about them:** start with the business question, give the number, say how it was measured, then name the assumption. For example: "If we move half our GDS agency volume to NDC, we save about a quarter of a million a year. That's the $13.80 per-booking cost gap times the volume, and it assumes agents will switch."

## 5. Automated reporting (`src/asi/excel_pack.py`, `src/asi/onepager.py`)

`make report` rebuilds:
- **Commercial_Pack.xlsx** with these sheets:
  - **Summary**: month KPIs against last month and last year, with green/red formatting, plus the recommendations
  - **Trend**: all months, with an attainment colour scale and a line chart
  - **Channel Mix**: a revenue pivot, a stacked share chart and a cost-of-sale heatmap
  - **Routes**: attainment, variance, YoY, yield and RASK, with a bar chart
  - **Lead Time**: pivots
  - **Alerts & Forecast**
  - **Definitions**
- **OnePager.html / .pdf**: six headline numbers, four charts and the five recommendations.

**How to say it:** "The monthly pack used to be a manual copy-paste job. Here it's one command, so the time goes into the insight instead of the formatting."

## 6. Power BI (`POWERBI.md`, `data/powerbi/`)

The same star schema is exported for Power BI. POWERBI.md lists the relationships, about 30 DAX measures (Total Revenue, Yield, Channel Share, Cost of Sale %, Target Attainment, YoY %, and more) and a five-page layout. It ends with check numbers, so you know the dashboard matches the Excel pack.

## 7. Quality (`tests/`, `.github/workflows/ci.yml`)

18 automated tests check that:
- the data is reproducible and covers every route and channel
- the views reconcile to the raw data to the cent
- each planted story is detected at the right time
- the forecast error is reasonable
- the Excel and PDF files are produced with the expected sheets, charts and formatting

On every push, GitHub Actions runs the tests and the full pipeline, and saves the pack as a downloadable artefact.

## Likely questions and short answers

- **"Is this real data?"** "No. It's simulated, so I can share it. The patterns are realistic, and I planted known events to prove the analysis finds them."
- **"Why DuckDB and not SQL Server?"** "It's portable for a demo. The SQL is standard, and the star schema loads straight into Power BI."
- **"How would you do this with real data?"** "I'd swap the generator for the booking and revenue-accounting extracts, keep the views as the single KPI definitions, and schedule the pack to refresh monthly."
- **"What would you look at next?"** "Fare-family mix by channel, the corporate account mix, and the booking curve for MEL-SIN against the competitor's schedule."
