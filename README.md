# taxer-mcp

MCP server for [Taxer.ua](https://taxer.ua) finance documents (договір, рахунок, акт), money accounts, and bank operations.

Taxer does not publish a public API. This server calls the same internal endpoints as [py-taxer-api](https://github.com/maxsivkov/py-taxer-api), using the browser session cookie from a logged-in Taxer tab. It runs on your machine and sends that cookie only to `taxer.ua`.

## Tools

| Tool | What it does |
| --- | --- |
| `list_profiles` | Account name and each FOP or company profile. The profile `id` is `user_id` for the other tools. |
| `list_documents` | One page of documents for a profile. |
| `get_document` | One contract, invoice, or act. |
| `create_contract` | Create a contract. |
| `create_invoice` | Create an invoice, including VAT (`nds`) and optional line items. |
| `create_act` | Create an act, including line items. |
| `list_accounts` | One page of money accounts (bank and cash) for a profile. |
| `list_operations` | One page of bank operations for a profile. |
| `get_operation` | One operation: Withdrawal, FlowOutgo, FlowIncome, CurrencyExchange, or AutoExchange. |
| `export_document_pdf` | Fill a saved print template, write a PDF, and store that filled template on the document. Document and template id are inputs. |

Create tools return the new document id. They do not upload files. Account and operation tools are read-only. `export_document_pdf` loads `load_template_data` and `api2/finances/template/load_data`, fills the template's merge fields, and sends the HTML to Taxer's PDF converter. The session cookie is not sent to the converter. It then stores the filled template on the document with `upload_file` and `generated` set, the same call the cabinet uses when you save from the document editor. Update, delete, and other document types (waybill, receipt, bill) are not in this version. Do not probe taxer.ua for new endpoints.

`direction` is `0` for a sale and `1` for a purchase. Dates are `YYYY-MM-DD` (midnight UTC) or a full ISO datetime. `nds: -1` means no VAT. Invoices always send `nds`, because Taxer rejects an invoice without it. Invoices and acts can include line items, a money account, a parent contract, and `is_foreign`.

## Setup in Cursor

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) on the `PATH` Cursor uses.

```bash
uv sync
```

Configure MCP in your user config ([`~/.cursor/mcp.json`](https://cursor.com/docs/context/mcp), or `%USERPROFILE%\.cursor\mcp.json` on Windows). For a local clone, point `command`/`args` at this repo and set `envFile` to [`.env`](.env.example). `.env` is gitignored. Copy the example and paste your cookie:

```bash
cp .env.example .env
```

```
TAXER_COOKIE="paste the Cookie header here"
```

Keep the double quotes. The cookie contains semicolons. `TAXER_BASE_URL` and `TAXER_LANG` override the defaults `https://taxer.ua` and `uk`.

Reload the window, then enable **taxer** (and optionally **gmail-mcp**) under Customize. Cursor asks before each tool call. Output → MCP Logs shows startup errors. If `uv` is missing from that log, install it or put its full path in `command`.

The **gmail-mcp** server is Google’s remote MCP ([configure guide](https://developers.google.com/workspace/gmail/api/guides/configure-mcp-server#configure-mcp-client)): Streamable HTTP at `https://gmailmcp.googleapis.com/mcp/v1`. You need Gmail API and **Gmail MCP API** enabled on your Cloud project (Developer Preview). Create an OAuth **Web application** client; add Cursor redirect URIs `http://localhost:8787/callback` and `https://www.cursor.com/agents/mcp/oauth/callback` ([Cursor MCP OAuth](https://cursor.com/docs/context/mcp#static-oauth-for-remote-servers)). Add scopes `gmail.readonly` and `gmail.compose` on the consent screen as in Google’s doc.

Optional **gmail-mcp** in the same `mcp.json`: set `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` in `.env`, then **export** them (or use [direnv](https://direnv.net/)) before launching Cursor — the remote server uses `${env:GMAIL_*}` in `auth`, not `envFile`. Enable **gmail-mcp** under Customize and complete Cursor’s OAuth flow when prompted. Tools include `create_draft`, `search_threads`, and `list_drafts`.

Ask Cursor to list your Taxer profiles. A 401 means the cookie is incomplete or expired: copy a fresh `Cookie` header and reload MCP.

## Use on another computer

Install [uv](https://docs.astral.sh/uv/) on that machine. You do not need to clone this repo. Cursor can start the server from GitHub with `uvx`.

Put this in the user MCP config (`~/.cursor/mcp.json`, or `%USERPROFILE%\.cursor\mcp.json` on Windows). Paste the cookie from [Get the full cookie](#get-the-full-cookie). Keep it in quotes; it contains semicolons.

```json
{
  "mcpServers": {
    "taxer": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/yadamovych/taxer-mcp",
        "taxer-mcp"
      ],
      "env": {
        "TAXER_COOKIE": "paste the Cookie header here"
      }
    }
  }
}
```

Reload the window, then enable **taxer**. If `uvx` is missing from Output → MCP Logs, install uv or put its full path in `command`.

## Get the full cookie

Taxer has no API token. The login is the whole `Cookie` header from a logged-in tab. `session_hash` alone is rejected with 401. `document.cookie` in the console is also incomplete: the browser hides `HttpOnly` cookies from JavaScript, including `PHPSESSID`, `session_key`, and `session_key_hash`.

1. Log in at [taxer.ua](https://taxer.ua/uk/login) and open the cabinet, for example [Documents](https://taxer.ua/uk/my/finances/documents).
2. Open DevTools (F12) → **Network**.
3. Reload the page.
4. Select a request to `taxer.ua` that returned 200, such as `load_account` or the documents list.
5. Open **Headers** → **Request Headers**.
6. Copy the entire `Cookie` value. It is one line of `name=value` pairs separated by semicolons. Do not stop at `session_hash`.

The copied line must include all of these:

- `PHPSESSID`
- `session_key`
- `session_hash`
- `session_key_hash`

Analytics cookies such as `_ga` and `_clck` can stay in the string. There is no `XSRF-TOKEN` cookie. If one is present, leave it in.

Paste the line into `.env` inside double quotes:

```
TAXER_COOKIE="PHPSESSID=...; session_key=...; session_hash=...; session_key_hash=..."
```

DevTools → **Application** → **Cookies** → `https://taxer.ua` shows when those cookies expire. Taxer does not publish the lifetime. Log out, or sign in again, and the copied value stops working immediately. When tools return 401, copy a fresh `Cookie` header and reload MCP.

## Tests

```bash
uv run pytest
```

Tests mock Taxer's HTTP API. They do not call the live site.
