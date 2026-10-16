# Open the Power BI project (about 5 minutes)

The folder holds three items that belong together. Keep them side by side:

- `SouthernCrossAir_Commercial.pbip`: the file you open
- `SouthernCrossAir_Commercial.SemanticModel\`: tables, relationships, measures (TMDL)
- `SouthernCrossAir_Commercial.Report\`: the five report pages

## 1. One-time setting (only if your Desktop asks for it)

Recent Power BI Desktop versions open `.pbip` files straight away. If yours says it can't open the file, go to **File > Options and settings > Options > Preview features**, tick **Power BI Project (.pbip) save option** (and **Store semantic model using TMDL format** if it's listed), click OK and restart Desktop.

## 2. Open

Double-click `SouthernCrossAir_Commercial.pbip`, or in Desktop use **File > Open** and choose that file.

## 3. Point it at the data

The model reads eight Parquet files (`dim_date`, `dim_route`, `dim_channel`, `dim_fare`, `dim_pos`, `dim_segment`, `fact_booking`, `fact_target`) from the folder in the **DataFolder** parameter.

1. **Home > Transform data > Edit parameters**.
2. Set **DataFolder** to the folder holding the `.parquet` files. Keep the trailing backslash `\`.
3. Click OK. If Desktop asks, choose **Apply changes**.

If a privacy-level prompt appears, choose **Organizational** (or tick "Ignore privacy levels" for this file). It's all local files.

## 4. Refresh

**Home > Refresh**. It loads about 220k bookings and should take under a minute.

## 5. Check the numbers

Open `CHECK.md` and compare. The two that matter most: FY26 **Total Revenue = $76.37m**, and with Booking month set to Jan to Jun 2026, **Target Attainment = 93.8%**.

Also check that **Model view** shows `dim_date` marked as the date table (Table tools > Mark as date table, with the `date` column). If it isn't, mark it there.

## 6. Save as .pbix

**File > Save as**, change "Save as type" to **Power BI file (*.pbix)**, and name it `SouthernCrossAir_Commercial.pbix`.

## If something doesn't look right

- **A visual shows an error or is blank**: click it, look at the field wells on the right, and re-drag the missing field from the `_Measures` table.
- **Route detail** is a normal page with a Route slicer. To make it a drill-through page, select the page, drag `dim_route[route_code]` into the **Drill through** well in the Visualizations pane, and delete the Route slicer.
- **Colours**: conditional formatting (red to amber to teal) is set on the attainment table, the attainment bars and the cost-of-sale column. To change it, right-click the field in the visual and choose **Conditional formatting**.
- **Theme**: apply navy #14365D, teal #1B9AAA and amber #F2A541 under **View > Themes > Customize current theme** if you want the house colours.
