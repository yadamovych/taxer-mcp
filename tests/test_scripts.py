import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_billing_period_covers_a_kyiv_calendar_month():
    period = _load("billing_period.py").billing_period("2026-10")

    assert period == {
        "month": "2026-10",
        "timezone": "Europe/Kyiv",
        "start": "2026-10-01",
        "end": "2026-10-31",
        "start_en": "October 01, 2026",
        "end_en": "October 31, 2026",
    }


def test_billing_period_uses_the_leap_day():
    period = _load("billing_period.py").billing_period("2024-02")

    assert period["end"] == "2024-02-29"
    assert period["end_en"] == "February 29, 2024"


def test_billing_period_rejects_a_bad_month():
    with pytest.raises(ValueError, match="YYYY-MM"):
        _load("billing_period.py").billing_period("2026-13")


def test_invoice_pdf_check_uses_the_caller_line_and_currency():
    text = "\n".join(
        [
            "Invoice No: 7",
            "October 31, 2026",
            "October 01, 2026 - October 31, 2026",
            "Consulting services",
            "2 hours",
            "100.00",
            "200.00",
            "EUR",
        ]
    )

    missing = _load("validate_invoice_pdf.py").missing_fields(
        text,
        number="7",
        invoice_date_en="October 31, 2026",
        period_start_en="October 01, 2026",
        period_end_en="October 31, 2026",
        line_description="Consulting services",
        quantity=2,
        unit_label="hours",
        unit_price="100.00",
        total="200.00",
        currency="EUR",
    )

    assert missing == []


def test_invoice_pdf_check_reports_a_short_period_and_a_missing_line():
    text = "Invoice No: 7\nOctober 01, 2026 - October 30, 2026\n100.00\n200.00\nEUR"

    missing = _load("validate_invoice_pdf.py").missing_fields(
        text,
        number="7",
        invoice_date_en="October 31, 2026",
        period_start_en="October 01, 2026",
        period_end_en="October 31, 2026",
        line_description="Consulting services",
        quantity=2,
        unit_label="hours",
        unit_price="100.00",
        total="200.00",
        currency="EUR",
    )

    assert missing == [
        "invoice_date",
        "billing_period",
        "line_description",
        "quantity",
        "billing_period_end_mismatch",
    ]
