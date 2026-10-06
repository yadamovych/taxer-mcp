#!/usr/bin/env python3
"""Create a Gmail draft with one PDF attachment via Gmail API v1."""
import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request


def access_token() -> str:
    data = urllib.parse.urlencode(
        {
            "client_id": os.environ["GMAIL_CLIENT_ID"],
            "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
            "refresh_token": os.environ["GMAIL_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["access_token"]


def build_raw_mime(
    to: list[str],
    cc: list[str],
    subject: str,
    body: str,
    pdf_path: str,
    filename: str,
) -> bytes:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    boundary = "cursor_invoice_draft_boundary"
    parts = [
        f"To: {', '.join(to)}",
        f"Cc: {', '.join(cc)}" if cc else None,
        f"Subject: {subject}",
        "MIME-Version: 1.0",
        f'Content-Type: multipart/mixed; boundary="{boundary}"',
        "",
        f"--{boundary}",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
        "",
        f"--{boundary}",
        f'Content-Type: application/pdf; name="{filename}"',
        "Content-Transfer-Encoding: base64",
        f'Content-Disposition: attachment; filename="{filename}"',
        "",
    ]
    parts = [p for p in parts if p is not None]
    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    for i in range(0, len(b64), 76):
        parts.append(b64[i : i + 76])
    parts.extend(["", f"--{boundary}--", ""])
    return "\r\n".join(parts).encode("utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--to", action="append", required=True)
    p.add_argument("--cc", action="append", default=[])
    p.add_argument("--subject", required=True)
    p.add_argument("--body-file", required=True, help="Plain text body file")
    p.add_argument("--pdf", required=True)
    p.add_argument("--filename", required=True)
    args = p.parse_args()
    body = open(args.body_file, encoding="utf-8").read()
    raw = base64.urlsafe_b64encode(
        build_raw_mime(args.to, args.cc, args.subject, body, args.pdf, args.filename)
    ).decode("ascii")
    token = access_token()
    payload = json.dumps({"message": {"raw": raw}}).encode("utf-8")
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        draft = json.load(resp)
    draft_id = draft["id"]
    out = {
        "id": draft_id,
        "threadId": draft.get("threadId"),
        "viewUrl": f"https://mail.google.com/mail/u/0/#drafts?compose={draft_id}",
    }
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()