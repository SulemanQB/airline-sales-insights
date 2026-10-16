# Check the numbers after Refresh

These values were computed from the Parquet files in `data/powerbi/` with the same logic as the DAX measures, and each one matches `output/findings.json` (the Excel pack and README use the same figures).

How to check: put a card on a blank page (or use the cards on **Executive summary**) and set the slicers as described.

| Measure and filter | Expected |
|---|---|
| Total Revenue, fin_year = FY26 | $76.37m |
| Total Revenue, fin_year = FY25 | $74.25m |
| YoY %, fin_year = FY26 | 2.8% |
| Net Revenue, FY26 | $71.43m |
| Distribution Cost, FY26 | $2.51m |
| Net Revenue After Distribution, FY26 | $68.92m |
| Passengers, FY26 | 168,590 |
| Target Attainment, Jan-Jun 2026 (month_start slicer) | 93.8% |
| Target Attainment, MEL-SIN, Jan-Jun 2026 | 61.6% |
| NDC Share of Indirect, average of monthly values, Jul-Dec 2024 | 8.1% |
| NDC Share of Indirect, average of monthly values, Jan-Jun 2026 | 48.5% |
| Cost per Booking, average of monthly values, Jul-Dec 2024 | $23.26 |
| Cost per Booking, average of monthly values, Jan-Jun 2026 | $21.75 |

**Note on six-month averages.** `findings.json` averages the six monthly values for NDC share and cost per booking. A card with all six months selected pools them instead, so it shows slightly different numbers:

| Card, six months selected in the Booking month slicer | Expected |
|---|---|
| NDC Share of Indirect card, Jul-Dec 2024 selected | 8.1% |
| NDC Share of Indirect card, Jan-Jun 2026 selected | 48.2% |
| Cost per Booking card, Jul-Dec 2024 selected | $23.33 |
| Cost per Booking card, Jan-Jun 2026 selected | $21.90 |

To see the monthly-average figure, put the measure in a table by `month_start` and average the six rows.

The two headline checks are **FY26 Total Revenue = $76.37m** and **Jan to Jun 2026 Target Attainment = 93.8%**. If those two match, the model and relationships are working.
