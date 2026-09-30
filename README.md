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

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Log in to Taxer in a browser, open the console, and copy `document.cookie`. The value must include `XSRF-TOKEN`. Put it in the environment as `TAXER_COOKIE`. See `.env.example`.

Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "taxer": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/taxer-mcp", "run", "taxer-mcp"],
      "env": {
        "TAXER_COOKIE": "XSRF-TOKEN=...; ..."
      }
    }
  }
}
```

The server speaks MCP over stdio. `TAXER_BASE_URL` and `TAXER_LANG` override the defaults `https://taxer.ua` and `uk`.

## Tests

```bash
uv run pytest
```

Tests mock Taxer's HTTP API. They do not call the live site.
