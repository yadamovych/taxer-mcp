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
| `create_invoice` | Create an invoice. |
| `create_act` | Create an act, including line items. |

Create tools return the new document id. They do not upload files. Update, delete, bank operations, and other document types (waybill, receipt, bill) are not in this version.

`direction` is `0` for a sale and `1` for a purchase. Dates are `YYYY-MM-DD` (midnight UTC) or a full ISO datetime. On an act, `nds: -1` means no VAT.

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

## Get the login cookie

Taxer has no API token. The login is the browser session cookie.

1. Log in at [taxer.ua](https://taxer.ua/uk/login).
2. Open DevTools (F12) → Network.
3. Reload the cabinet, or open any page inside it.
4. Select a request to `taxer.ua/api/` that returned 200, such as `load_account`.
5. In Request Headers, copy the whole `Cookie` value.
6. Paste it into `.env` as `TAXER_COOKIE`.

That value must include `XSRF-TOKEN` and the session cookie. `document.cookie` in the console often omits the session cookie, because browsers hide `HttpOnly` cookies from JavaScript. The Network header includes it.

DevTools → Application → Cookies → `https://taxer.ua` shows when that session cookie expires. Taxer does not publish the lifetime. Log out, or sign in again, and the copied value stops working immediately. When tools return 401, repeat the steps above.

## Tests

```bash
uv run pytest
```

Tests mock Taxer's HTTP API. They do not call the live site.
