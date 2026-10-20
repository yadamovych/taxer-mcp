#!/usr/bin/env python3
"""Check exported invoice PDF text for the fields passed on the command line.

Prints one JSON line to stdout: {"ok": true} or {"ok": false, "missing": [...]}.
Exits 0 when ok, 1 when validation fails or the PDF cannot be read.

Line description, unit label, amounts, and currency come from the caller.
This script has no sample invoice of its own.
"""
from __future__ import annotations

import argparse
import json
import re
import sys


def missing_fields(
    text: str,
    *,
    number: str,
    invoice_date_en: str,
    period_start_en: str,
    period_end_en: str,
    line_description: str,
    quantity: int,
    unit_label: str,
    unit_price: str,
    total: str,
    currency: str,
) -> list[str]:
    """Return the names of required strings that are absent from the PDF text."""
    checks = [
        (f"Invoice No: {number}", "invoice_number"),
        (invoice_date_en, "invoice_date"),
        (f"{period_start_en} - {period_end_en}", "billing_period"),
        (line_description, "line_description"),
        (f"{quantity} {unit_label}", "quantity"),
        (unit_price, "unit_price"),
        (total, "total"),
        (currency, "currency"),
    ]
    missing = [label for needle, label in checks if needle not in text]
    period_match = re.search(
        r"([A-Za-z]+ \d{2}, \d{4}) - ([A-Za-z]+ \d{2}, \d{4})",
        text,
    )
    if period_match and period_match.group(2) != period_end_en:
        missing.append("billing_period_end_mismatch")
    return missing


def _extract_text(pdf_path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        json.dump(
            {"ok": False, "missing": ["pypdf is not installed (uv sync --group automation)"]},
            sys.stdout,
        )
        sys.stdout.write("\n")
        raise SystemExit(1) from None
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--number", required=True, help="Invoice number as shown on the PDF")
    parser.add_argument(
        "--invoice-date-en",
        required=True,
        help='English invoice date line, e.g. "October 31, 2026"',
    )
    parser.add_argument(
        "--period-start-en",
        required=True,
        help='Billing period start in English, e.g. "October 01, 2026"',
    )
    parser.add_argument(
        "--period-end-en",
        required=True,
        help='Billing period end in English, e.g. "October 31, 2026"',
    )
    parser.add_argument("--line-description", required=True, help="Line text as shown on the PDF")
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--unit-label", required=True, help='Unit as shown after the quantity, e.g. "hours"')
    parser.add_argument("--unit-price", required=True)
    parser.add_argument("--total", required=True)
    parser.add_argument("--currency", required=True, help='Currency code as shown on the PDF, e.g. "EUR"')
    args = parser.parse_args()

    text = _extract_text(args.pdf)
    missing = missing_fields(
        text,
        number=args.number,
        invoice_date_en=args.invoice_date_en,
        period_start_en=args.period_start_en,
        period_end_en=args.period_end_en,
        line_description=args.line_description,
        quantity=args.quantity,
        unit_label=args.unit_label,
        unit_price=args.unit_price,
        total=args.total,
        currency=args.currency,
    )
    ok = not missing
    json.dump({"ok": ok, "missing": missing}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
