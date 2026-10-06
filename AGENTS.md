# Cloud agent: monthly ZEB invoice

This repo supports a scheduled automation that creates a Taxer invoice, exports PDF, and creates a Gmail draft. Follow these notes so runs fail clearly instead of silently.

## Tools

- **Taxer MCP** only: `list_profiles`, `list_documents`, `create_invoice`, `get_document`, `export_document_pdf`. Do not probe other Taxer endpoints. Never print `TAXER_COOKIE`.
- **Gmail**: use only `scripts/create_gmail_draft_with_attachment.py` (not gmail-mcp draft tools).

The Taxer HTTP client retries transient network/SSL errors (up to three attempts). If a Taxer tool still fails, wait a few seconds and call the same tool again once before stopping.

## Date gate

Unless the user explicitly overrides (e.g. “continue today”), run only when **today in `Europe/Kyiv` is the last calendar day of the month**. Bill that month. If an invoice for that month already exists in `list_documents`, stop.

Invoice `date` must be **midnight on the last day of the billing month in Europe/Kyiv**, as a UTC ISO datetime (use the Kyiv offset for that calendar day; October uses +02 → e.g. `2026-10-30T22:00:00Z` for 31 Oct 2026).

## Gmail draft script

From the repo root:

```bash
python3 scripts/create_gmail_draft_with_attachment.py \
  --to invoices@zeb.de \
  --cc jhuebner@zeb.de \
  --subject "Invoice for {Month}" \
  --body-file /tmp/invoice_email_body.txt \
  --pdf /tmp/YYYY_MM_DD_{number}_ZEB_ЗЕД.pdf \
  --filename YYYY_MM_DD_{number}_ZEB_ЗЕД.pdf
```

- **Do not** redirect stderr to `/dev/null`. Failures write `{"error": "..."}` to stderr; success writes one JSON line to stdout with `id` and `viewUrl`.
- Parse stdout **only when exit code is 0**.
- Never log `GMAIL_REFRESH_TOKEN`, access tokens, or base64.

Requires `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN` in the environment (see `.env.example`).

## PDF validation

After `export_document_pdf`, require `generatedFileId` in the tool result. Validate the PDF with:

```bash
uv run --group automation python scripts/validate_invoice_pdf.py \
  --pdf /tmp/YYYY_MM_DD_{number}_ZEB_ЗЕД.pdf \
  --number {number} \
  --invoice-date-en "{Month} {DD}, {YYYY}" \
  --period-start-en "{Month} 01, {YYYY}" \
  --period-end-en "{Month} {DD}, {YYYY}"
```

Install automation deps once per environment: `uv sync --group automation`.

## Report

On success, report: Taxer document id, invoice number, `generatedFileId`, and Gmail draft `viewUrl`. Leave the draft unsent.
