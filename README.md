# taxer-mcp

MCP server for [Taxer.ua](https://taxer.ua) finance documents: contracts (договір), invoices (рахунок), and acts (акт).

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

Create tools return the new document id. They do not upload files. Update, delete, bank operations, and other document types (waybill, receipt, bill) are not in this version.

`direction` is `0` for a sale and `1` for a purchase. Dates are `YYYY-MM-DD` (midnight UTC) or a full ISO datetime. `nds: -1` means no VAT. Invoices always send `nds`, because Taxer rejects an invoice without it. Invoices and acts can include line items, a money account, a parent contract, and `is_foreign`.

## Setup in Cursor

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) on the `PATH` Cursor uses.

```bash
uv sync
```

[`.cursor/mcp.json`](.cursor/mcp.json) starts this server over stdio and loads [`.env`](.env.example). `.env` is gitignored. Copy the example and paste your cookie:

```bash
cp .env.example .env
```

```
TAXER_COOKIE="paste the Cookie header here"
```

Keep the double quotes. The cookie contains semicolons. `TAXER_BASE_URL` and `TAXER_LANG` override the defaults `https://taxer.ua` and `uk`.

Reload the window, then enable **taxer** under Customize. Cursor asks before each tool call. Output → MCP Logs shows startup errors. If `uv` is missing from that log, install it or put its full path in `command`.

Ask Cursor to list your Taxer profiles. A 401 means the cookie is incomplete or expired: copy a fresh `Cookie` header and reload MCP.

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
