import openpyxl

from asi import charts, excel_pack, onepager
from asi.model import export_star


def test_reports(tmp_path, con, res):
    imgs = charts.make_all(res, tmp_path / "charts")
    assert all(p.stat().st_size > 5000 for p in imgs.values())
    xl = excel_pack.build_pack(con, res, imgs, tmp_path / "pack.xlsx")
    wb = openpyxl.load_workbook(xl)
    assert {"Summary", "Trend", "Channel Mix", "Routes", "Lead Time", "Alerts & Forecast", "Definitions"} <= set(wb.sheetnames)
    assert wb["Summary"].conditional_formatting and wb["Routes"].conditional_formatting
    assert wb["Trend"]._charts and wb["Channel Mix"]._charts and wb["Routes"]._charts
    h = onepager.build_html(res, imgs, tmp_path / "one.html").read_text()
    assert "Recommendations" in h and h.count("<li>") == len(res["recs"])
    pdf = onepager.build_pdf(res, imgs, tmp_path / "one.pdf")
    assert pdf.read_bytes()[:4] == b"%PDF"


def test_export(tmp_path, con):
    paths = export_star(con, tmp_path)
    assert len(paths) == 16 and all(p.exists() for p in paths)
