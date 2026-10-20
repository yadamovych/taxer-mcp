#!/usr/bin/env python3
"""Print the Europe/Kyiv calendar month for a YYYY-MM billing period.

The script takes no profile, amount, or client name. Example:

    python scripts/billing_period.py 2026-10
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from datetime import date

# Civil dates for one Europe/Kyiv calendar month.
KYIV = "Europe/Kyiv"
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def billing_period(month: str) -> dict[str, str]:
    """Return ISO dates and English lines for one Europe/Kyiv calendar month."""
    match = _MONTH.fullmatch(month.strip())
    if match is None:
        raise ValueError("month must be YYYY-MM")
    year = int(match.group(1))
    month_number = int(match.group(2))
    if year < 1 or not 1 <= month_number <= 12:
        raise ValueError("month must be YYYY-MM")
    last_day = calendar.monthrange(year, month_number)[1]
    start = date(year, month_number, 1)
    end = date(year, month_number, last_day)
    return {
        "month": f"{year:04d}-{month_number:02d}",
        "timezone": KYIV,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "start_en": _english_date(start),
        "end_en": _english_date(end),
    }


def _english_date(value: date) -> str:
    return f"{_MONTH_NAMES[value.month - 1]} {value.day:02d}, {value.year}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Europe/Kyiv billing month as JSON")
    parser.add_argument("month", help="Billing month as YYYY-MM")
    args = parser.parse_args()
    try:
        payload = billing_period(args.month)
    except ValueError as exc:
        json.dump({"error": str(exc)}, sys.stderr)
        sys.stderr.write("\n")
        raise SystemExit(1) from exc
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
