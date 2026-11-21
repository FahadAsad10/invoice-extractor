import io
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from invoice_extractor.export import invoices_table, line_items_table, review, to_csv, to_excel, vat_summary
from invoice_extractor.samples import SAMPLES

ROWS = review(SAMPLES, date(2026, 11, 21))


def test_review_statuses():
    assert [r.status for r in ROWS] == ["Ready", "Ready", "Ready", "Check", "Needs review", "Needs review"]
    assert ROWS[5].is_duplicate


def test_tables():
    inv = invoices_table(ROWS)
    assert len(inv) == 6 and inv["Total"].iloc[1] == 1837.37
    lines = line_items_table(ROWS)
    assert len(lines) == sum(len(i.line_items) for _, i in SAMPLES)
    assert lines.loc[0, "Gross"] == 1040.40  # 867.00 + 20%


def test_vat_summary_matches_invoices_and_skips_duplicates():
    vs = vat_summary(ROWS).set_index(["Currency", "VAT %"])
    assert vs.loc[("EUR", 7.0), "VAT"] == 82.95
    assert vs.loc[("EUR", 19.0), "Net"] == 478.50
    # Northwind once (not twice) + BrightClean's lines
    assert vs.loc[("GBP", 20.0), "Net"] == 1751.00 + 1290.00
    assert vs.loc[("GBP", 20.0), "Documents"] == 2


def test_excel_workbook():
    wb = load_workbook(io.BytesIO(to_excel(ROWS)))
    assert wb.sheetnames == ["Invoices", "Line items", "VAT summary"]
    ws = wb["Invoices"]
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref
    header = [c.value for c in ws[1]]
    total = ws.cell(row=2, column=header.index("Total") + 1)
    assert total.value == 2101.20 and total.number_format == "#,##0.00"
    assert ws.cell(row=6, column=header.index("Status") + 1).fill.fgColor.rgb.endswith("FADBD8")


def test_csv_round_trips_with_bom_for_excel():
    data = to_csv(line_items_table(ROWS))
    assert data.startswith(b"\xef\xbb\xbf")
    back = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    assert "Broschüre A5, 24 Seiten (1.000 Stk.)" in back["Description"].tolist()


def test_every_sample_has_its_document_and_preview():
    root = Path(__file__).resolve().parent.parent / "samples"
    for name, _ in SAMPLES:
        assert (root / name).stat().st_size > 1000
        assert (root / "previews" / f"{name}.jpg").exists()
