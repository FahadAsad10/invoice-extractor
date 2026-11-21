from datetime import date

from invoice_extractor.samples import SAMPLES
from invoice_extractor.schema import Invoice, LineItem
from invoice_extractor.validate import check, find_duplicates, status

TODAY = date(2026, 11, 21)
SAMPLE = dict(SAMPLES)


def make(**kw) -> Invoice:
    base = dict(
        document_type="invoice",
        vendor_name="Acme Ltd",
        vendor_tax_id="GB123",
        invoice_number="A-1",
        invoice_date="2026-10-01",
        due_date="2026-10-31",
        currency="GBP",
        line_items=[LineItem(description="Widget", quantity=2, unit_price=50, vat_rate=20, amount=100)],
        subtotal=100,
        vat_total=20,
        total=120,
    )
    return Invoice(**(base | kw))


def fields(issues):
    return {i.field for i in issues}


def test_clean_invoice_is_ready():
    assert check(make(), TODAY) == []
    assert status([]) == "Ready"


def test_clean_samples_pass_including_mixed_rates_and_vat_inclusive_receipt_lines():
    assert check(SAMPLE["northwind-INV-20417.pdf"], TODAY) == []
    assert check(SAMPLE["druckerei-weber-RE-2026-0893.pdf"], TODAY) == []  # 19% and 7% on one invoice
    assert check(SAMPLE["stratus-cloud-SC-118204.pdf"], TODAY) == []  # unit price 0.084 x 2976 rounds to 249.98
    assert fields(check(SAMPLE["caffe-roma-receipt.jpg"], TODAY)) == {"notes"}


def test_lines_that_dont_add_up_to_subtotal_are_errors():
    issues = check(SAMPLE["brightclean-BC-3391.pdf"], TODAY)
    assert {"subtotal", "vat_total"} <= fields(issues)
    assert status(issues) == "Needs review"
    assert "1,290.00" in next(i.message for i in issues if i.field == "subtotal")


def test_quantity_times_price_mismatch():
    inv = make(line_items=[LineItem(description="Widget", quantity=3, unit_price=50, vat_rate=20, amount=100)])
    assert "line 1" in fields(check(inv, TODAY))


def test_total_must_equal_net_plus_tax():
    assert "total" in fields(check(make(total=125), TODAY))


def test_rounding_within_a_cent_per_line_is_fine():
    inv = make(
        line_items=[LineItem(description=f"x{i}", vat_rate=20, amount=33.33) for i in range(3)],
        subtotal=99.99,
        vat_total=20.00,
        total=119.99,
    )
    assert check(inv, TODAY) == []


def test_dates():
    assert "due_date" in fields(check(make(due_date="2026-09-01"), TODAY))
    assert "invoice_date" in fields(check(make(invoice_date="2027-01-05", due_date=None), TODAY))
    assert "invoice_date" in fields(check(make(invoice_date=None), TODAY))
    assert "invoice_date" in fields(check(make(invoice_date="05/10/2026"), TODAY))


def test_missing_vat_number_or_invoice_number_is_a_warning():
    issues = check(make(vendor_tax_id=None, invoice_number=None), TODAY)
    assert fields(issues) == {"vendor_tax_id", "invoice_number"}
    assert status(issues) == "Check"
    # a receipt without tax doesn't need either
    assert (
        check(
            make(
                document_type="receipt",
                vendor_tax_id=None,
                invoice_number=None,
                vat_total=0,
                total=100,
                line_items=[LineItem(description="x", amount=100)],
            ),
            TODAY,
        )
        == []
    )


def test_duplicates_by_number_or_by_vendor_date_and_total():
    a = make()
    same_number = make(vendor_name="ACME LIMITED", total=999, vat_total=899)
    same_amount = make(invoice_number=None)
    other = make(invoice_number="A-2", total=121, vat_total=21)
    assert find_duplicates([a, same_number, same_amount, other]) == {1: 0, 2: 0}
    assert find_duplicates([inv for _, inv in SAMPLES]) == {5: 0}
