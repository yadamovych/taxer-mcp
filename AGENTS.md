# Cloud agent: Taxer MCP

Generic notes for agents using this repo. **Do not commit client names, recipient emails, profile ids, template ids, or invoice parameters** — keep those only in the private Cursor automation prompt or a gitignored local file (`AGENTS.local.md`).

## Tools

- **Taxer MCP** only: use the tools documented in the project README. Do not probe undocumented Taxer endpoints. Never print `TAXER_COOKIE`.
- **Gmail**: use only `scripts/create_gmail_draft_with_attachment.py` (not gmail-mcp draft tools).

The Taxer HTTP client retries transient network/SSL errors (up to three attempts). If a Taxer tool still fails, wait a few seconds and call the same tool again once before stopping.

## Gmail draft script

From the repo root (recipient addresses and paths come from the **automation prompt**, not from this file):

```bash
python3 scripts/create_gmail_draft_with_attachment.py \
  --to "<recipient>" \
  --cc "<optional-cc>" \
  --subject "<subject>" \
  --body-file /tmp/invoice_email_body.txt \
  --pdf /tmp/<exported>.pdf \
  --filename <attachment-name>.pdf
```

- **Do not** redirect stderr to `/dev/null`. Failures write `{"error": "..."}` to stderr; success writes one JSON line to stdout with `id` and `viewUrl`.
- Parse stdout **only when exit code is 0**.
- Never log `GMAIL_REFRESH_TOKEN`, access tokens, or base64.

Requires `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN` in the environment (see `.env.example`).

## PDF validation

After `export_document_pdf`, require `generatedFileId` in the tool result when the automation expects it. Optional check:

```bash
uv run --group automation python scripts/validate_invoice_pdf.py \
  --pdf /tmp/<exported>.pdf \
  --number <number> \
  --invoice-date-en "<English invoice date>" \
  --period-start-en "<period start>" \
  --period-end-en "<period end>"
```

Install automation deps once per environment: `uv sync --group automation`.

## Reporting

Report only what the automation prompt asks for. Do not paste OAuth tokens, cookies, or full Gmail compose URLs into git commits, PRs, or public issues.
