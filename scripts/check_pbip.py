"""Static checks for the generated PBIP plus expected values for CHECK.md."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_pbip as B  # noqa: E402

ROOT = Path("powerbi")
errors: list[str] = []
n = {"json": 0, "tmdl": 0, "dax": 0, "refs": 0, "visual_fields": 0}

# 1. JSON files parse (including embedded config strings)
for f in list(ROOT.rglob("*.json")) + list(ROOT.rglob("*.pbi*")):
    if f.is_file():
        doc = json.loads(f.read_text())
        n["json"] += 1
        if f.name == "report.json":
            json.loads(doc["config"])
            for s in doc["sections"]:
                for vc in s["visualContainers"]:
                    json.loads(vc["config"]); json.loads(vc["filters"])
pbir = json.loads((ROOT / f"{B.NAME}.Report/definition.pbir").read_text())
if not (ROOT / f"{B.NAME}.Report" / pbir["datasetReference"]["byPath"]["path"]).resolve().is_dir():
    errors.append("pbir byPath does not resolve")

# 2. TMDL structure: tabs only, indentation steps of at most one (except M source blocks)
KEY = re.compile(r"^(table|column|measure|partition|relationship|expression|model|database|ref table|annotation|"
                 r"dataType|formatString|lineageTag|summarizeBy|sourceColumn|sortByColumn|isHidden|isKey|isActive|"
                 r"dataCategory|mode|source|fromColumn|toColumn|culture|defaultPowerBIDataSourceVersion|"
                 r"discourageImplicitMeasures|sourceQueryCulture|dataAccessOptions|legacyRedirects|"
                 r"returnErrorValuesAsNull|compatibilityLevel)\b")
model_cols: dict[str, set[str]] = {}
for f in sorted(ROOT.rglob("*.tmdl")):
    n["tmdl"] += 1
    prev, in_src = 0, False
    for i, line in enumerate(f.read_text().splitlines(), 1):
        if not line.strip():
            continue
        if line.startswith(" "):
            errors.append(f"{f.name}:{i} space indentation")
        depth = len(line) - len(line.lstrip("\t"))
        body = line.strip()
        if in_src and depth >= 4:
            continue
        in_src = body == "source ="
        if not KEY.match(body):
            errors.append(f"{f.name}:{i} unknown keyword: {body[:40]}")
        if depth > prev + 1:
            errors.append(f"{f.name}:{i} indentation jump")
        prev = depth
        m = re.match(r"^(table) (\S+)", body)
        if m:
            cur = m.group(2); model_cols[cur] = set()
        m = re.match(r"^column ('([^']+)'|\S+)", body)
        if m:
            model_cols[cur].add(m.group(2) or m.group(1))

for ft, fc, tt, tc, _ in B.RELATIONSHIPS:
    for t, c in ((ft, fc), (tt, tc)):
        if c not in model_cols.get(t, ()):
            errors.append(f"relationship column missing {t}.{c}")

# 3. DAX: balanced brackets/quotes, references exist, functions known
FUNCS = {"SUM", "SUMX", "DIVIDE", "COUNTROWS", "RELATED", "CALCULATE", "MAX", "FILTER", "ALL", "DATE", "AVERAGE",
         "SAMEPERIODLASTYEAR", "DATEADD", "TOTALYTD", "USERELATIONSHIP", "SWITCH", "TRUE", "VAR", "RETURN"}
measures = {m[0] for m in B.MEASURES}
exprs = [(m[0], m[1]) for m in B.MEASURES] + [(c[0], c[2]) for cs in B.CALC_COLS.values() for c in cs]
for name, e in exprs:
    n["dax"] += 1
    s = re.sub(r'"[^"]*"', '""', e)
    if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
        errors.append(f"DAX brackets unbalanced: {name}")
    for t, c in re.findall(r"(\w+)\[([^\]]+)\]", s):
        n["refs"] += 1
        if c not in model_cols.get(t, ()):
            errors.append(f"DAX {name}: missing column {t}[{c}]")
    for c in re.findall(r"(?<![\w\]])\[([^\]]+)\]", s):
        n["refs"] += 1
        if c not in measures:
            errors.append(f"DAX {name}: missing measure [{c}]")
    for fn in re.findall(r"\b([A-Z][A-Z0-9]+)\s*\(", s):
        if fn not in FUNCS:
            errors.append(f"DAX {name}: unknown function {fn}")
    if re.search(r"\b(\w+)\s*\(", re.sub(r"\b[A-Z][A-Z0-9]+\s*\(", "", re.sub(r"\[[^\]]*\]", "", s))):
        errors.append(f"DAX {name}: lowercase call")
# measure dependency cycle check
deps = {m[0]: set(re.findall(r"(?<![\w\]])\[([^\]]+)\]", m[1])) & measures for m in B.MEASURES}
def visit(x, stack=()):
    if x in stack: errors.append(f"cycle {stack}"); return
    for d in deps[x]: visit(d, stack + (x,))
for x in deps: visit(x)

# 4. report fields exist (Field() asserts) and queryRefs match Select names
rep = json.loads((ROOT / f"{B.NAME}.Report/report.json").read_text())
for s in rep["sections"]:
    for vc in s["visualContainers"]:
        sv = json.loads(vc["config"])["singleVisual"]
        if "prototypeQuery" not in sv: continue
        names = {x["Name"] for x in sv["prototypeQuery"]["Select"]}
        for refs in sv["projections"].values():
            for r in refs:
                n["visual_fields"] += 1
                if r["queryRef"] not in names: errors.append(f"queryRef {r['queryRef']} not selected")
                t, p = r["queryRef"].split(".", 1)
                if not (p in measures if t == B.MT else p in model_cols.get(t, ())):
                    errors.append(f"visual field missing {r['queryRef']}")

# 5. expected values from the data (pandas reimplementation of the measures)
D = Path("data/powerbi")
b = pd.read_parquet(D / "fact_booking.parquet"); d = pd.read_parquet(D / "dim_date.parquet")
t = pd.read_parquet(D / "fact_target.parquet"); c = pd.read_parquet(D / "dim_channel.parquet")
r = pd.read_parquet(D / "dim_route.parquet")
b = b.merge(d[["date_key", "fin_year", "month_start"]], left_on="booking_date_key", right_on="date_key").merge(c, on="channel_key")
b["rev"] = b.fare_revenue + b.ancillary_revenue
t = t.merge(d[["date_key", "fin_year", "month_start"]], left_on="month_date_key", right_on="date_key")
fy = b.groupby("fin_year").agg(rev=("rev", "sum"), refund=("refund_amount", "sum"), dist=("distribution_cost", "sum"),
                               pax=("pax", "sum"), n=("booking_id", "size"))
f26, f25 = fy.loc["FY26"], fy.loc["FY25"]
win = (b.month_start >= "2026-01-01") & (b.month_start < "2026-07-01")
twin = (t.month_start >= "2026-01-01") & (t.month_start < "2026-07-01")
att = b[win].rev.sum() / t[twin].target_revenue.sum()
bw = b[win].merge(r, on="route_key").groupby("route_code").rev.sum()
tw = t[twin].merge(r, on="route_key").groupby("route_code").target_revenue.sum()
worst = (bw / tw).sort_values()
months = sorted(b.month_start.unique())
def ndc1(x):
    ind = x[x.channel_group == "Indirect"]; return (ind.connection == "NDC").sum() / len(ind)
def cpb1(x):
    return x.distribution_cost.sum() / len(x)
def mean_monthly(fn, ms):  # findings.json averages the six monthly values
    return sum(fn(b[b.month_start == m]) for m in ms) / len(ms)
def pooled(fn, ms):  # what a card shows with the six months selected
    return fn(b[b.month_start.isin(ms)])
ndc = lambda ms: mean_monthly(ndc1, ms)
cpb = lambda ms: mean_monthly(cpb1, ms)
F = json.loads(Path("output/findings.json").read_text())
checks = [
    ("Total Revenue, fin_year = FY26", f26.rev, F["fy"]["FY26"]["gross"], "$"),
    ("Total Revenue, fin_year = FY25", f25.rev, F["fy"]["FY25"]["gross"], "$"),
    ("YoY %, fin_year = FY26", f26.rev / f25.rev - 1, F["fy"]["FY26"]["gross"] / F["fy"]["FY25"]["gross"] - 1, "%"),
    ("Net Revenue, FY26", f26.rev - f26.refund, F["fy"]["FY26"]["net"], "$"),
    ("Distribution Cost, FY26", f26.dist, F["fy"]["FY26"]["dist"], "$"),
    ("Net Revenue After Distribution, FY26", f26.rev - f26.refund - f26.dist, F["fy"]["FY26"]["net_after_dist"], "$"),
    ("Passengers, FY26", f26.pax, F["fy"]["FY26"]["pax"], "n"),
    ("Target Attainment, Jan-Jun 2026 (month_start slicer)", att, F["target"]["network_attainment_recent"], "%"),
    (f"Target Attainment, {worst.index[0]}, Jan-Jun 2026", worst.iloc[0], F["target"]["worst_attainment"], "%"),
    ("NDC Share of Indirect, average of monthly values, Jul-Dec 2024", ndc(months[:6]), F["channel_mix"]["ndc_share_first6"], "%"),
    ("NDC Share of Indirect, average of monthly values, Jan-Jun 2026", ndc(months[-6:]), F["channel_mix"]["ndc_share_last6"], "%"),
    ("Cost per Booking, average of monthly values, Jul-Dec 2024", cpb(months[:6]), F["channel_mix"]["dist_cost_per_booking_first6"], "$2"),
    ("Cost per Booking, average of monthly values, Jan-Jun 2026", cpb(months[-6:]), F["channel_mix"]["dist_cost_per_booking_last6"], "$2"),
]
fmt = {"$": lambda v: f"${v / 1e6:,.2f}m", "$2": lambda v: f"${v:,.2f}", "%": lambda v: f"{v:.1%}", "n": lambda v: f"{v:,.0f}"}
rows = []
for label, got, want, k in checks:
    ok = abs(got - want) <= 1e-6 * max(1, abs(want))
    if not ok: errors.append(f"value mismatch {label}: {got} vs {want}")
    rows.append((label, fmt[k](got), "match" if ok else "MISMATCH"))

extra = [("NDC Share of Indirect card, Jul-Dec 2024 selected", f"{pooled(ndc1, months[:6]):.1%}", "card value"),
         ("NDC Share of Indirect card, Jan-Jun 2026 selected", f"{pooled(ndc1, months[-6:]):.1%}", "card value"),
         ("Cost per Booking card, Jul-Dec 2024 selected", f"${pooled(cpb1, months[:6]):,.2f}", "card value"),
         ("Cost per Booking card, Jan-Jun 2026 selected", f"${pooled(cpb1, months[-6:]):,.2f}", "card value")]
rows += extra
print(json.dumps(n))
for e in errors: print("ERROR", e)
print("errors:", len(errors))
Path("/tmp/check_values.json").write_text(json.dumps(rows, indent=1))
for row in rows: print(row)
sys.exit(1 if errors else 0)
