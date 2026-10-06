#!/usr/bin/env python3
"""Create a Gmail draft with one PDF attachment via Gmail API v1.

On success prints one JSON object to stdout with keys id and viewUrl.
On failure prints one JSON object to stderr with key error, then exits 1.
Never prints tokens or base64 attachment data.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_GMAIL_ATTEMPTS = 3
_GMAIL_RETRY_BACKOFF_SEC = (1.0, 2.5)
_REQUIRED_ENV = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")


def _fail(message: str) -> None:
    json.dump({"error": message}, sys.stderr, ensure_ascii=False)
    sys.stderr.write("\n")
    raise SystemExit(1)


def _require_env() -> None:
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        _fail(f"Missing environment variable(s): {', '.join(missing)}")


def _urlopen_with_retry(req: urllib.request.Request):
    last_error: urllib.error.URLError | None = None
    for attempt in range(_GMAIL_ATTEMPTS):
        try:
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < _GMAIL_ATTEMPTS:
                time.sleep(_GMAIL_RETRY_BACKOFF_SEC[min(attempt, len(_GMAIL_RETRY_BACKOFF_SEC) - 1)])
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt + 1 < _GMAIL_ATTEMPTS:
                time.sleep(_GMAIL_RETRY_BACKOFF_SEC[min(attempt, len(_GMAIL_RETRY_BACKOFF_SEC) - 1)])
                continue
            raise
    assert last_error is not None
    raise last_error


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
    with _urlopen_with_retry(req) as resp:
        payload = json.load(resp)
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        _fail("OAuth token response did not include access_token")
    return token


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

    _require_env()
    if not os.path.isfile(args.pdf):
        _fail(f"PDF not found: {args.pdf}")
    if not os.path.isfile(args.body_file):
        _fail(f"Body file not found: {args.body_file}")

    try:
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
        with _urlopen_with_retry(req) as resp:
            draft = json.load(resp)
    except urllib.error.HTTPError as exc:
        _fail(f"Gmail API HTTP {exc.code}: {exc.reason}")
    except urllib.error.URLError as exc:
        _fail(f"Gmail network error: {exc.reason}")

    draft_id = draft.get("id")
    if not isinstance(draft_id, str) or not draft_id:
        _fail("Gmail draft response did not include id")

    out = {
        "id": draft_id,
        "threadId": draft.get("threadId"),
        "viewUrl": f"https://mail.google.com/mail/u/0/#drafts?compose={draft_id}",
    }
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
