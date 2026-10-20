# Cloud agent: Taxer MCP

Generic notes for agents using this repo. Do not commit client names, recipient emails, profile ids, template ids, or invoice parameters. Keep those in the private automation prompt or a gitignored `AGENTS.local.md`.

## Tools

Use the Taxer MCP tools documented in the project README. Do not probe undocumented Taxer endpoints. Never print `TAXER_COOKIE`.

The Taxer HTTP client retries transient network errors (up to three attempts). If a Taxer tool still fails, wait a few seconds and call the same tool again once before stopping.

Before creating an invoice, call `find_document` with the same type and number. When it returns `found: true`, do not create another document with that number.

## Billing period

Resolve the month in Europe/Kyiv before filling dates. The script takes no profile, amount, or client name:

```bash
python scripts/billing_period.py 2026-10
```

It prints `start`, `end`, `start_en`, and `end_en`. Pass `start_en` and `end_en` to the PDF check.

## PDF validation

After `export_document_pdf`, pass the line description, unit label, currency, and amounts from the private prompt. This file does not contain them.

```bash
uv run --group automation python scripts/validate_invoice_pdf.py \
  --pdf /tmp/invoice.pdf \
  --number "<number>" \
  --invoice-date-en "<English invoice date>" \
  --period-start-en "<period start>" \
  --period-end-en "<period end>" \
  --line-description "<line text>" \
  --quantity <quantity> \
  --unit-label "<unit>" \
  --unit-price "<unit price>" \
  --total "<total>" \
  --currency "<currency>"
```

Install automation deps once per environment: `uv sync --group automation`.
