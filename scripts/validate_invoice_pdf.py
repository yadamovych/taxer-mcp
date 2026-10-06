#!/usr/bin/env python3
"""Check exported ZEB invoice PDF text for required fields.

Prints one JSON line to stdout: {"ok": true} or {"ok": false, "missing": [...]}.
Exits 0 when ok, 1 when validation fails or the PDF cannot be read.
"""
from __future__ import annotations

import argparse
import json
import re
import sys


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
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", required=True)
    p.add_argument("--number", required=True, help="Invoice number as shown on the PDF")
    p.add_argument(
        "--invoice-date-en",
        required=True,
        help='English invoice date line, e.g. "October 31, 2026"',
    )
    p.add_argument(
        "--period-start-en",
        required=True,
        help='Billing period start in English, e.g. "October 01, 2026"',
    )
    p.add_argument(
        "--period-end-en",
        required=True,
        help='Billing period end in English, e.g. "October 31, 2026"',
    )
    p.add_argument("--quantity", type=int, default=21)
    p.add_argument("--unit-price", default="335.00")
    p.add_argument("--total", default="7035.00")
    args = p.parse_args()

    text = _extract_text(args.pdf)
    checks = [
        (f"Invoice No: {args.number}", "invoice_number"),
        (args.invoice_date_en, "invoice_date"),
        (f"{args.period_start_en} - {args.period_end_en}", "billing_period"),
        ("Computer programming services", "line_description_en"),
        (f"{args.quantity} days", "quantity_days"),
        (args.unit_price, "unit_price"),
        (args.total, "total"),
        ("EUR", "currency"),
    ]
    missing = [label for needle, label in checks if needle not in text]
    # Guard against a period that ends one day early (e.g. Oct 1–30 instead of 1–31).
    period_match = re.search(
        r"([A-Za-z]+ \d{2}, \d{4}) - ([A-Za-z]+ \d{2}, \d{4})",
        text,
    )
    if period_match and period_match.group(2) != args.period_end_en:
        missing.append("billing_period_end_mismatch")

    ok = not missing
    json.dump({"ok": ok, "missing": missing}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
