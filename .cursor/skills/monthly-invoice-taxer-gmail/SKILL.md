---
name: monthly-invoice-taxer-gmail
description: >-
  Create a monthly invoice on Taxer, export PDF, save on Taxer via
  export_document_pdf, and create a Gmail draft with the PDF attached. Use for
  scheduled cloud runs or "next invoice" when billing constants live in a
  gitignored local config file.
---

# Monthly invoice (Taxer + Gmail)

One agent run. Use **Taxer MCP** (`user-taxer` / `taxer`) and **Gmail MCP** (`plugin-gmail-gmail`). Do **not** send email — only a draft.

## Local config (never commit)

Copy `.cursor/monthly-invoice.local.json.example` to **`.cursor/monthly-invoice.local.json`** (gitignored). Put real Taxer ids, template id, line items, Gmail recipients, and sign-off name there only.

Do not put profile ids, client emails, personal names, or template ids in tracked repo files.

## Do not

- Spawn **`cursor agent -p`** or any nested agent to work around MCP limits.
- Use **Mail.app** / AppleScript instead of Gmail MCP (synced drafts often lack a real PDF attachment).
- Call **`update_draft`** to add attachments (omitted lists drop files; attachments do not merge).
- Truncate PDF **base64** in `create_draft` (typical invoice PDF ≈ 85–90 KB → ≈ 115–120 KB base64).
- Print or log **`TAXER_COOKIE`**, or send the cookie to the PDF converter.
- Hardcode print **template id** in this repo (pass `template_id` only at runtime from local config).
- Probe new Taxer endpoints or commit secrets.

## When to run (scheduled agent)

- Timezone: **Europe/Kyiv**.
- Invoice date: **last calendar day** of the billing month (Kyiv midnight → UTC ISO on `create_invoice` `date`).
  - Kyiv **UTC+3** (summer): last day 00:00 Kyiv = **previous calendar day 21:00:00Z**.
  - Kyiv **UTC+2** (winter): last day 00:00 Kyiv = **previous calendar day 22:00:00Z**.
- Cron that fires on 28–31 must **stop unless today is the last day of the month in Kyiv**.

## Workflow

### 1. Load config and next invoice number

1. Read `.cursor/monthly-invoice.local.json` for `taxer.user_id` and related ids.
2. `list_documents` for that `user_id` — find latest **invoice** number; next = max + 1 (or user-specified month).
3. Build Ukrainian title, e.g. `Рахунок №{n} від DD.MM.YYYY` with **last day of month** in Kyiv on the invoice.

### 2. Create invoice on Taxer

`create_invoice` using config: sale `direction: 0`, `lines` from config, `contractor_id`, `account_id`, `parent_id`, `nds`, `is_foreign`, `currency`, and **`date`** as Kyiv-last-day UTC ISO.

### 3. Export PDF and save on Taxer

1. `export_document_pdf` with `document_type: invoice`, new `document_id`, **`template_id`** from local config (runtime argument), and `output_path` from `pdf_filename_pattern` in config.
2. Confirm returned `path`, `bytes`, and **`generatedFileId`** (save happens inside this tool).

### 4. Gmail draft with PDF (correct pattern)

1. Build payload on disk (full base64, no truncation):

```bash
python3 scripts/prepare_gmail_draft.py \
  --pdf "$PDF_PATH" \
  --month "October" \
  --config .cursor/monthly-invoice.local.json \
  --out /tmp/gmail-create-draft-args.json
```

2. Call **`plugin-gmail-gmail` → `create_draft`** once with the **exact** JSON from that file (`to`, `cc`, `subject`, `body`, `attachments[0].content` complete).
3. **`get_draft`** on the returned id with `messageFormat: FULL_CONTENT` — confirm attachment **filename** and that attachments metadata is present (do not dump PDF bytes in the report).
4. **Subject:** `Invoice for {EnglishMonth}`. Recipients from local config only.

If the runtime **cannot** pass ~120 KB tool arguments for `create_draft`, **stop and report** — do not use nested agents or Mail.app. User can attach manually using the compose `viewUrl` from a body-only draft.

### 5. Report briefly

- Invoice id / number / Taxer title date  
- PDF path and byte size  
- Gmail draft id / `viewUrl` and attachment filename  
- Do **not** paste PDF or base64 into chat  

## Prerequisites (cloud / local)

- **taxer-mcp** with valid `TAXER_COOKIE` (Taxer tab cookie, not `document.cookie` alone).
- **Gmail** MCP authenticated for the sending account.
- **`.cursor/monthly-invoice.local.json`** on the agent machine (cloud secrets or env-specific file), not in git.
- Optional: `uv` / `uvx` if MCP config uses them — install only if startup logs say missing; do not block the invoice flow on unrelated setup.
