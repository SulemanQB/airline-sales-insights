"""Generate a Power BI Project (PBIP) for the star schema in data/powerbi/.

Writes powerbi/<NAME>.pbip, <NAME>.SemanticModel (TMDL) and <NAME>.Report
(PBIR-Legacy report.json). Usage:

    python scripts/build_pbip.py [--data-folder "C:\\path\\to\\parquet\\"] [--out powerbi]
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

NAME = "SouthernCrossAir_Commercial"
DEFAULT_FOLDER = "C:\\Users\\Public\\Documents\\airline-sales-insights\\data\\powerbi\\"
NS = uuid.UUID("6f1c2a52-8d0e-4f43-9a5e-0c5b7d1e2a10")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


# ---------------------------------------------------------------- tables
# (name, dataType, M type, formatString, extra props)
INT, STR, DBL, DEC, DT, BOOL = "int64", "string", "double", "decimal", "dateTime", "boolean"
MTYPE = {INT: "Int64.Type", STR: "type text", DBL: "type number", DEC: "Currency.Type",
         DT: "type date", BOOL: "type logical"}

TABLES: dict[str, list[tuple]] = {
    "dim_date": [
        ("date_key", INT), ("date", DT), ("year", INT), ("month", INT), ("year_month", STR),
        ("month_start", DT), ("quarter", INT), ("fin_year", STR), ("day_name", STR),
        ("iso_dow", INT), ("is_weekend", BOOL)],
    "dim_route": [
        ("route_key", INT), ("route_code", STR), ("origin", STR), ("destination", STR),
        ("haul", STR), ("distance_km", INT), ("daily_seats", INT), ("base_fare_aud", INT)],
    "dim_channel": [
        ("channel_key", INT), ("channel_code", STR), ("channel", STR), ("channel_group", STR),
        ("connection", STR), ("commission_pct", DBL), ("fee_per_segment_aud", DEC)],
    "dim_fare": [("fare_key", INT), ("fare_family", STR), ("cabin", STR), ("refundable", BOOL)],
    "dim_pos": [("pos_key", INT), ("pos_code", STR), ("pos_country", STR), ("pos_region", STR)],
    "dim_segment": [("segment_key", INT), ("segment_code", STR), ("segment", STR)],
    "fact_booking": [
        ("booking_id", INT), ("booking_date_key", INT), ("travel_date_key", INT),
        ("route_key", INT), ("channel_key", INT), ("fare_key", INT), ("pos_key", INT),
        ("segment_key", INT), ("lead_time_days", INT), ("pax", INT), ("status", STR),
        ("fare_revenue", DEC), ("ancillary_revenue", DEC), ("refund_amount", DEC),
        ("distribution_cost", DEC)],
    "fact_target": [("month_date_key", INT), ("route_key", INT), ("target_revenue", DEC),
                    ("target_pax", DBL)],
}
SORT_BY = {("dim_date", "year_month"): "month_start", ("dim_date", "day_name"): "iso_dow"}
CALC_COLS = {
    "fact_booking": [("Lead Bucket", STR,
        'SWITCH ( TRUE (), fact_booking[lead_time_days] <= 7, "0-7", '
        'fact_booking[lead_time_days] <= 21, "8-21", fact_booking[lead_time_days] <= 60, "22-60", "61+" )')],
}

RELATIONSHIPS = [
    ("fact_booking", "booking_date_key", "dim_date", "date_key", True),
    ("fact_booking", "travel_date_key", "dim_date", "date_key", False),
    ("fact_booking", "route_key", "dim_route", "route_key", True),
    ("fact_booking", "channel_key", "dim_channel", "channel_key", True),
    ("fact_booking", "fare_key", "dim_fare", "fare_key", True),
    ("fact_booking", "pos_key", "dim_pos", "pos_key", True),
    ("fact_booking", "segment_key", "dim_segment", "segment_key", True),
    ("fact_target", "month_date_key", "dim_date", "date_key", True),
    ("fact_target", "route_key", "dim_route", "route_key", True),
]

CUR = '\\$#,0;(\\$#,0);\\$#,0'
CUR2 = '\\$#,0.00;(\\$#,0.00);\\$#,0.00'
PCT = '0.0%;-0.0%;0.0%'
NUM = '#,0'
NUM2 = '#,0.00'
MEASURES = [
    ("Fare Revenue", "SUM ( fact_booking[fare_revenue] )", CUR),
    ("Ancillary Revenue", "SUM ( fact_booking[ancillary_revenue] )", CUR),
    ("Total Revenue", "[Fare Revenue] + [Ancillary Revenue]", CUR),
    ("Refunds", "SUM ( fact_booking[refund_amount] )", CUR),
    ("Net Revenue", "[Total Revenue] - [Refunds]", CUR),
    ("Distribution Cost", "SUM ( fact_booking[distribution_cost] )", CUR),
    ("Net Revenue After Distribution", "[Net Revenue] - [Distribution Cost]", CUR),
    ("Bookings", "COUNTROWS ( fact_booking )", NUM),
    ("Passengers", "SUM ( fact_booking[pax] )", NUM),
    ("Avg Booking Value", "DIVIDE ( [Total Revenue], [Bookings] )", CUR2),
    ("Avg Fare per Pax", "DIVIDE ( [Fare Revenue], [Passengers] )", CUR2),
    ("RPK", "SUMX ( fact_booking, fact_booking[pax] * RELATED ( dim_route[distance_km] ) )", NUM),
    ("Yield (c/RPK)", "DIVIDE ( [Fare Revenue], [RPK] ) * 100", NUM2),
    ("ASK",
     "VAR LastDay = CALCULATE ( MAX ( dim_date[date] ), FILTER ( ALL ( dim_date ), dim_date[date_key] <= MAX ( fact_booking[booking_date_key] ) ) ) "
     "VAR Days = COUNTROWS ( FILTER ( dim_date, dim_date[date] <= LastDay && dim_date[date] >= DATE ( 2024, 7, 1 ) ) ) "
     "RETURN SUMX ( dim_route, dim_route[daily_seats] * dim_route[distance_km] ) * Days", NUM),
    ("RASK Proxy (c/ASK)", "DIVIDE ( [Net Revenue], [ASK] ) * 100", NUM2),
    ("Channel Share", "DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], ALL ( dim_channel ) ) )", PCT),
    ("Booking Share", "DIVIDE ( [Bookings], CALCULATE ( [Bookings], ALL ( dim_channel ) ) )", PCT),
    ("NDC Share of Indirect",
     'DIVIDE ( CALCULATE ( [Bookings], dim_channel[connection] = "NDC" ), CALCULATE ( [Bookings], dim_channel[channel_group] = "Indirect" ) )', PCT),
    ("Cost of Sale %", "DIVIDE ( [Distribution Cost], [Total Revenue] )", PCT),
    ("Cost per Booking", "DIVIDE ( [Distribution Cost], [Bookings] )", CUR2),
    ("Ancillary Attach Rate", "DIVIDE ( CALCULATE ( [Bookings], fact_booking[ancillary_revenue] > 0 ), [Bookings] )", PCT),
    ("Cancellation Rate", 'DIVIDE ( CALCULATE ( [Bookings], fact_booking[status] = "Cancelled" ), [Bookings] )', PCT),
    ("Target Revenue", "SUM ( fact_target[target_revenue] )", CUR),
    ("Target Attainment", "DIVIDE ( [Total Revenue], [Target Revenue] )", PCT),
    ("Variance to Target", "[Total Revenue] - [Target Revenue]", CUR),
    ("Revenue LY", "CALCULATE ( [Total Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )", CUR),
    ("YoY %", "DIVIDE ( [Total Revenue] - [Revenue LY], [Revenue LY] )", PCT),
    ("Revenue PM", "CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )", CUR),
    ("MoM %", "DIVIDE ( [Total Revenue] - [Revenue PM], [Revenue PM] )", PCT),
    ("Revenue FYTD", 'TOTALYTD ( [Total Revenue], dim_date[date], "30/6" )', CUR),
    ("Yield YoY %",
     "DIVIDE ( [Yield (c/RPK)] - CALCULATE ( [Yield (c/RPK)], SAMEPERIODLASTYEAR ( dim_date[date] ) ), "
     "CALCULATE ( [Yield (c/RPK)], SAMEPERIODLASTYEAR ( dim_date[date] ) ) )", PCT),
    ("Avg Lead Time (days)", "AVERAGE ( fact_booking[lead_time_days] )", "#,0.0"),
    ("Passengers by Travel Date",
     "CALCULATE ( [Passengers], USERELATIONSHIP ( fact_booking[travel_date_key], dim_date[date_key] ) )", NUM),
]
MT = "_Measures"


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    if all(c.isalnum() or c == "_" for c in name):
        return name
    return "'" + name.replace("'", "''") + "'"


def table_tmdl(name: str) -> str:
    cols = TABLES[name]
    out = [f"table {name}", f"\tlineageTag: {tag(name)}"]
    if name == "dim_date":
        out.append("\tdataCategory: Time")
    out.append("")
    for col, dt in cols:
        out.append(f"\tcolumn {q(col)}")
        out.append(f"\t\tdataType: {dt}")
        if name == "dim_date" and col == "date":
            out.append("\t\tisKey")
        if dt == DT:
            out.append("\t\tformatString: dd/mm/yyyy")
        elif dt == DEC:
            out.append(f"\t\tformatString: {CUR2}")
        elif dt in (INT, DBL):
            out.append("\t\tformatString: 0")
        if col.endswith("_key") or col == "booking_id":
            out.append("\t\tisHidden")
        out.append(f"\t\tlineageTag: {tag(name, col)}")
        out.append("\t\tsummarizeBy: " + ("sum" if dt in (DEC, DBL) or col in ("pax", "lead_time_days") else "none"))
        out.append(f"\t\tsourceColumn: {col}")
        if (name, col) in SORT_BY:
            out.append(f"\t\tsortByColumn: {SORT_BY[(name, col)]}")
        out.append("")
        out.append("\t\tannotation SummarizationSetBy = Automatic")
        out.append("")
    for col, dt, expr in CALC_COLS.get(name, []):
        out.append(f"\tcolumn {q(col)} = {expr}")
        out.append(f"\t\tdataType: {dt}")
        out.append(f"\t\tlineageTag: {tag(name, col)}")
        out.append("\t\tsummarizeBy: none")
        out.append("")
        out.append("\t\tannotation SummarizationSetBy = Automatic")
        out.append("")
    types = ", ".join(f'{{"{c}", {MTYPE[d]}}}' for c, d in cols)
    out += [
        f"\tpartition {name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Parquet.Document(File.Contents(DataFolder & "{name}.parquet")),',
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Source, {{{types}}})",
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(out)


def measures_tmdl() -> str:
    out = [f"table {MT}", f"\tlineageTag: {tag(MT)}", ""]
    for n, expr, fmt in MEASURES:
        out.append(f"\tmeasure {q(n)} = {expr}")
        out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tlineageTag: {tag(MT, n)}")
        out.append("")
    out += [
        "\tcolumn Dummy", "\t\tdataType: string", "\t\tisHidden",
        f"\t\tlineageTag: {tag(MT, 'Dummy')}", "\t\tsummarizeBy: none", "\t\tsourceColumn: Dummy", "",
        "\t\tannotation SummarizationSetBy = Automatic", "",
        f"\tpartition {MT} = m", "\t\tmode: import", "\t\tsource =",
        "\t\t\t\tlet",
        "\t\t\t\t    Source = #table(type table [Dummy = text], {})",
        "\t\t\t\tin",
        "\t\t\t\t    Source", "",
        "\tannotation PBI_ResultType = Table", "",
    ]
    return "\n".join(out)


def model_files(data_folder: str) -> dict[str, str]:
    tables = list(TABLES) + [MT]
    files = {}
    files["database.tmdl"] = "database\n\tcompatibilityLevel: 1567\n"
    files["model.tmdl"] = "\n".join(
        ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
         "\tdiscourageImplicitMeasures", "\tsourceQueryCulture: en-AU",
         "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
         "annotation __PBI_TimeIntelligenceEnabled = 0", "",
         'annotation PBI_QueryOrder = ["DataFolder",' + ",".join(f'"{t}"' for t in tables) + "]", "",
         "annotation PBI_ProTooling = [\"DevMode\"]", ""]
        + [f"ref table {t}" for t in tables] + [""])
    m_folder = data_folder.replace('"', '""')
    files["expressions.tmdl"] = (
        f'expression DataFolder = "{m_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag('DataFolder')}\n\n"
        "\tannotation PBI_ResultType = Text\n\n"
        "\tannotation PBI_NavigationStepName = Navigation\n")
    rel = []
    for ft, fc, tt, tc, active in RELATIONSHIPS:
        rel.append(f"relationship {tag('rel', ft, fc, tt, tc)}")
        if not active:
            rel.append("\tisActive: false")
        rel.append(f"\tfromColumn: {ft}.{fc}")
        rel.append(f"\ttoColumn: {tt}.{tc}")
        rel.append("")
    files["relationships.tmdl"] = "\n".join(rel)
    for t in TABLES:
        files[f"tables/{t}.tmdl"] = table_tmdl(t)
    files[f"tables/{MT}.tmdl"] = measures_tmdl()
    return files


# ---------------------------------------------------------------- report
ALIAS = {"dim_date": "d", "dim_route": "r", "dim_channel": "c", "dim_fare": "f", "dim_pos": "p",
         "dim_segment": "s", "fact_booking": "b", "fact_target": "t", MT: "m"}
MEASURE_NAMES = {m[0] for m in MEASURES}


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


class Field:
    def __init__(self, ref: str):
        self.table, self.prop = ref.split(".", 1)
        self.is_measure = self.table == MT
        if self.is_measure:
            assert self.prop in MEASURE_NAMES, ref
        else:
            names = [c[0] for c in TABLES[self.table]] + [c[0] for c in CALC_COLS.get(self.table, [])]
            assert self.prop in names, ref
        self.ref = ref

    def expr(self) -> dict:
        kind = "Measure" if self.is_measure else "Column"
        return {kind: {"Expression": {"SourceRef": {"Source": ALIAS[self.table]}}, "Property": self.prop}}


def visual(vid: str, vtype: str, pos: tuple, roles: dict[str, list[str]], title: str | None = None,
           objects: dict | None = None, order: tuple | None = None, vc_objects: dict | None = None) -> dict:
    x, y, w, h = pos
    fields: list[Field] = []
    seen = set()
    for refs in roles.values():
        for r in refs:
            if r not in seen:
                seen.add(r)
                fields.append(Field(r))
    used_tables = []
    for f in fields:
        if f.table not in used_tables:
            used_tables.append(f.table)
    if order and Field(order[0]).table not in used_tables:
        used_tables.append(Field(order[0]).table)
    pq = {"Version": 2,
          "From": [{"Name": ALIAS[t], "Entity": t, "Type": 0} for t in used_tables],
          "Select": [dict(f.expr(), Name=f.ref) for f in fields]}
    if order:
        pq["OrderBy"] = [{"Direction": order[1], "Expression": Field(order[0]).expr()}]
    sv = {"visualType": vtype,
          "projections": {role: [{"queryRef": r} | ({"active": True} if role in ("Category", "Rows") and i == 0 else {})
                                 for i, r in enumerate(refs)] for role, refs in roles.items()},
          "prototypeQuery": pq,
          "drillFilterOtherVisuals": True}
    if objects:
        sv["objects"] = objects
    vco = dict(vc_objects or {})
    if title:
        vco["title"] = [{"properties": {"show": lit("true"), "text": lit("'" + title.replace("'", "''") + "'")}}]
    if vco:
        sv["vcObjects"] = vco
    cfg = {"name": vid, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
           "singleVisual": sv}
    return {"x": x, "y": y, "z": 0, "width": w, "height": h, "config": json.dumps(cfg), "filters": "[]"}


def textbox(vid: str, text: str, pos: tuple) -> dict:
    x, y, w, h = pos
    cfg = {"name": vid, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
           "singleVisual": {"visualType": "textbox", "drillFilterOtherVisuals": True,
                            "objects": {"general": [{"properties": {"paragraphs": [
                                {"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": "18pt", "color": "#14365D"}}]}]}}]}}}
    return {"x": x, "y": y, "z": 0, "width": w, "height": h, "config": json.dumps(cfg), "filters": "[]"}


def slicer(vid: str, ref: str, pos: tuple, between: bool = False, title: str | None = None) -> dict:
    mode = "'Between'" if between else "'Dropdown'"
    return visual(vid, "slicer", pos, {"Values": [ref]}, title=title,
                  objects={"data": [{"properties": {"mode": lit(mode)}}]})


def gradient_rule(measure: str, lo: float, mid: float, hi: float, low_good: bool = False) -> dict:
    red, amber, teal = "'#D64550'", "'#F2A541'", "'#1B9AAA'"
    a, c = (teal, red) if low_good else (red, teal)
    f = Field(measure)
    return {"FillRule": {"Input": f.expr(), "FillRule": {"linearGradient3": {
        "min": {"color": {"Literal": {"Value": a}}, "value": {"Literal": {"Value": f"{lo}D"}}},
        "mid": {"color": {"Literal": {"Value": amber}}, "value": {"Literal": {"Value": f"{mid}D"}}},
        "max": {"color": {"Literal": {"Value": c}}, "value": {"Literal": {"Value": f"{hi}D"}}},
        "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}


def cf_values(measure: str, rule: dict, prop: str = "backColor") -> list:
    return [{"properties": {prop: {"solid": {"color": {"expr": rule}}}},
             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": measure}}]


def std_slicers(prefix: str, extra: list[tuple] = ()) -> list[dict]:
    items = [slicer(f"{prefix}s1", "dim_date.month_start", (20, 70, 300, 60), between=True, title="Booking month"),
             slicer(f"{prefix}s2", "dim_date.fin_year", (330, 70, 150, 60), title="Financial year"),
             slicer(f"{prefix}s3", "dim_route.route_code", (490, 70, 160, 60), title="Route"),
             slicer(f"{prefix}s4", "dim_channel.channel", (660, 70, 180, 60), title="Channel")]
    for i, (ref, t) in enumerate(extra):
        items.append(slicer(f"{prefix}s{5 + i}", ref, (850 + i * 210, 70, 200, 60), title=t))
    return items


def pages() -> list[dict]:
    m = lambda n: f"{MT}.{n}"
    p = []
    # 1 Executive summary
    cards = ["Total Revenue", "YoY %", "Net Revenue After Distribution", "Target Attainment", "Cost of Sale %", "Yield (c/RPK)"]
    v = [textbox("p1title", "Executive summary", (20, 10, 800, 50))] + std_slicers(
        "p1", [("dim_route.haul", "Haul"), ("dim_segment.segment", "Segment")])
    for i, c in enumerate(cards):
        v.append(visual(f"p1c{i}", "card", (20 + i * 207, 145, 197, 110), {"Values": [m(c)]}, title=c))
    v.append(visual("p1combo", "lineClusteredColumnComboChart", (20, 270, 1240, 430),
                    {"Category": ["dim_date.month_start"], "Y": [m("Total Revenue")], "Y2": [m("Target Revenue")]},
                    title="Revenue vs target by month", order=("dim_date.month_start", 1)))
    p.append(("Executive summary", v))
    # 2 Channel and distribution
    v = [textbox("p2title", "Channel and distribution", (20, 10, 800, 50))] + std_slicers("p2")
    v.append(visual("p2mix", "hundredPercentStackedColumnChart", (20, 145, 620, 300),
                    {"Category": ["dim_date.month_start"], "Series": ["dim_channel.channel"], "Y": [m("Channel Share")]},
                    title="Channel mix (share of revenue)", order=("dim_date.month_start", 1)))
    v.append(visual("p2ndc", "lineChart", (650, 145, 610, 300),
                    {"Category": ["dim_date.month_start"], "Y": [m("NDC Share of Indirect")], "Y2": [m("Cost of Sale %")]},
                    title="NDC share of indirect bookings and cost of sale", order=("dim_date.month_start", 1)))
    v.append(visual("p2mat", "pivotTable", (20, 455, 1240, 250),
                    {"Rows": ["dim_channel.channel", "dim_channel.connection"],
                     "Values": [m("Bookings"), m("Total Revenue"), m("Cost per Booking"), m("Cost of Sale %"), m("Ancillary Attach Rate")]},
                    title="Channel economics",
                    objects={"values": cf_values(m("Cost of Sale %"), gradient_rule(m("Cost of Sale %"), 0.01, 0.04, 0.08, low_good=True))}))
    p.append(("Channel and distribution", v))
    # 3 Route performance
    v = [textbox("p3title", "Route performance", (20, 10, 800, 50))] + std_slicers("p3")
    v.append(visual("p3bar", "barChart", (20, 145, 400, 560),
                    {"Category": ["dim_route.route_code"], "Y": [m("Target Attainment")]},
                    title="Target attainment by route", order=(m("Target Attainment"), 1),
                    objects={"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": gradient_rule(m("Target Attainment"), 0.85, 0.95, 1.05)}}}},
                                            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}))
    v.append(visual("p3tab", "tableEx", (430, 145, 830, 270),
                    {"Values": ["dim_route.route_code", "dim_route.haul", m("Total Revenue"), m("Target Revenue"),
                                m("Variance to Target"), m("Target Attainment")]},
                    title="Route attainment",
                    objects={"values": cf_values(m("Target Attainment"), gradient_rule(m("Target Attainment"), 0.85, 0.95, 1.05))}))
    v.append(visual("p3mat", "pivotTable", (430, 425, 500, 280),
                    {"Rows": ["dim_route.route_code"], "Columns": ["dim_date.year_month"], "Values": [m("Variance to Target")]},
                    title="Variance to target by route and month",
                    objects={"values": cf_values(m("Variance to Target"), gradient_rule(m("Variance to Target"), -150000, 0, 150000))}))
    v.append(visual("p3sc", "scatterChart", (940, 425, 320, 280),
                    {"Category": ["dim_route.route_code"], "X": [m("Yield (c/RPK)")], "Y": [m("RASK Proxy (c/ASK)")], "Size": [m("Passengers")]},
                    title="Yield vs RASK proxy"))
    p.append(("Route performance", v))
    # 4 Customer and booking curve
    v = [textbox("p4title", "Customer and booking curve", (20, 10, 800, 50))] + std_slicers("p4")
    v.append(visual("p4col", "clusteredColumnChart", (20, 145, 620, 280),
                    {"Category": ["fact_booking.Lead Bucket"], "Series": ["dim_segment.segment"], "Y": [m("Passengers")]},
                    title="Passengers by lead time and segment", order=("fact_booking.Lead Bucket", 1)))
    v.append(visual("p4line", "lineChart", (650, 145, 610, 280),
                    {"Category": ["fact_booking.Lead Bucket"], "Y": [m("Avg Fare per Pax")]},
                    title="Average fare per passenger by lead time", order=("fact_booking.Lead Bucket", 1)))
    v.append(visual("p4pos", "barChart", (20, 435, 1240, 270),
                    {"Category": ["dim_pos.pos_country"], "Y": [m("Total Revenue")]},
                    title="Revenue by point of sale", order=(m("Total Revenue"), 2)))
    p.append(("Customer and booking curve", v))
    # 5 Route detail
    v = [textbox("p5title", "Route detail (pick a route)", (20, 10, 800, 50))] + std_slicers("p5")
    v.append(visual("p5trend", "lineClusteredColumnComboChart", (20, 145, 1240, 280),
                    {"Category": ["dim_date.month_start"], "Y": [m("Total Revenue")], "Y2": [m("Target Revenue")]},
                    title="Monthly revenue vs target", order=("dim_date.month_start", 1)))
    v.append(visual("p5ch", "donutChart", (20, 435, 610, 270),
                    {"Category": ["dim_channel.channel"], "Y": [m("Total Revenue")]}, title="Channel mix"))
    v.append(visual("p5fare", "donutChart", (650, 435, 610, 270),
                    {"Category": ["dim_fare.fare_family"], "Y": [m("Total Revenue")]}, title="Fare family mix"))
    p.append(("Route detail", v))
    return p


def report_json() -> dict:
    sections = []
    for i, (title, vcs) in enumerate(pages()):
        sections.append({"name": f"ReportSection{i + 1:02d}", "displayName": title, "ordinal": i,
                         "displayOption": 1, "width": 1280, "height": 720,
                         "config": "{}", "filters": "[]", "visualContainers": vcs})
    cfg = {"version": "5.43",
           "themeCollection": {"baseTheme": {"name": "CY24SU06", "version": "5.55", "type": 2}},
           "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
           "linguisticSchemaSyncVersion": 0,
           "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                        "useStylableVisualContainerHeader": True, "exportDataMode": 1},
           "objects": {"outspacePane": [{"properties": {"expanded": lit("false")}}]}}
    return {"config": json.dumps(cfg), "layoutOptimization": 0,
            "resourcePackages": [{"resourcePackage": {"name": "SharedResources", "type": 2, "disabled": False,
                                  "items": [{"type": 202, "path": "BaseThemes/CY24SU06.json", "name": "CY24SU06"}]}}],
            "sections": sections, "filters": "[]"}


def build(out: Path, data_folder: str) -> None:
    sm = out / f"{NAME}.SemanticModel"
    rp = out / f"{NAME}.Report"
    for rel, text in model_files(data_folder).items():
        f = sm / "definition" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\r\n" if False else "\n")
    (sm / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2))
    rp.mkdir(parents=True, exist_ok=True)
    (rp / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    (rp / "report.json").write_text(json.dumps(report_json(), indent=2))
    (out / f"{NAME}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    (out / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-folder", default=DEFAULT_FOLDER)
    ap.add_argument("--out", default="powerbi")
    a = ap.parse_args()
    build(Path(a.out), a.data_folder if a.data_folder.endswith("\\") else a.data_folder + "\\")
    print("built", Path(a.out) / f"{NAME}.pbip")
