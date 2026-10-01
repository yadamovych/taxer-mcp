#!/usr/bin/env python3
"""Build plugin-gmail-gmail create_draft JSON (with full PDF base64) on disk.

The agent should call create_draft once using this file — not truncate attachment
content and not spawn a nested cursor agent.

Recipients and sign-off come from flags or a local JSON config (gitignored).
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

BODY_TEMPLATE = (
    "Have a nice day!\n\n"
    "In the attachment you should find an invoice for {month}.\n\n"
    "Regards,\n"
    "{sign_off}"
)


def load_gmail_config(path: Path | None) -> dict:
    if path is None:
        return {}
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    return data.get("gmail", data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True, help="Invoice PDF path")
    parser.add_argument("--month", required=True, help="English month name for subject/body, e.g. October")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(".cursor/monthly-invoice.local.json"),
        help="Local JSON with gmail.to, gmail.cc, gmail.sign_off (default: .cursor/monthly-invoice.local.json)",
    )
    parser.add_argument("--to", nargs="+", help="To addresses (overrides config)")
    parser.add_argument("--cc", nargs="*", help="Cc addresses (overrides config)")
    parser.add_argument("--sign-off", help="Closing name in body (overrides config)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/tmp/gmail-create-draft-args.json"),
        help="Where to write create_draft arguments JSON",
    )
    args = parser.parse_args()

    cfg = load_gmail_config(args.config if args.config.is_file() else None)
    to = args.to or cfg.get("to")
    cc = args.cc if args.cc is not None else cfg.get("cc", [])
    sign_off = args.sign_off or cfg.get("sign_off")
    if not to:
        print("Missing recipients: set gmail.to in --config or pass --to", file=sys.stderr)
        return 1
    if not sign_off:
        print("Missing sign-off: set gmail.sign_off in --config or pass --sign-off", file=sys.stderr)
        return 1

    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    pdf_bytes = pdf_path.read_bytes()
    payload = {
        "to": list(to),
        "cc": list(cc) if cc else [],
        "subject": f"Invoice for {args.month}",
        "body": BODY_TEMPLATE.format(month=args.month, sign_off=sign_off),
        "attachments": [
            {
                "filename": pdf_path.name,
                "mimeType": "application/pdf",
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False))
    print(
        json.dumps(
            {
                "out": str(args.out),
                "pdf_bytes": len(pdf_bytes),
                "base64_len": len(payload["attachments"][0]["content"]),
                "subject": payload["subject"],
                "filename": pdf_path.name,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
