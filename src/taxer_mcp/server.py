"""MCP tools for Taxer.ua finance documents."""

from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from taxer_mcp.client import TaxerClient, TaxerError
from taxer_mcp.models import DOCUMENT_TYPES, ActLine, build_document, dump_model

mcp = MCPServer("taxer")


def get_client() -> TaxerClient:
    cookie = os.environ.get("TAXER_COOKIE", "").strip()
    if not cookie:
        raise TaxerError("TAXER_COOKIE is not set")
    return TaxerClient(
        cookie,
        base_url=os.environ.get("TAXER_BASE_URL", "https://taxer.ua"),
        lang=os.environ.get("TAXER_LANG", "uk"),
    )


def _call(action):
    try:
        with get_client() as client:
            return action(client)
    except ToolError:
        raise
    except (TaxerError, ValueError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def list_profiles() -> dict[str, Any]:
    """List FOP and company profiles on the logged-in Taxer account.

    Each profile id is the user_id required by the other document tools.
    """

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.load_account())

    return _call(run)


@mcp.tool()
def list_documents(user_id: int, page_number: int = 1) -> dict[str, Any]:
    """List one page of finance documents for a Taxer profile.

    user_id is a profile id from list_profiles. page_number starts at 1.
    The page includes contracts, invoices, and acts.
    """
    if page_number < 1:
        raise ToolError("page_number starts at 1")

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.list_documents(user_id, page_number))

    return _call(run)


@mcp.tool()
def get_document(user_id: int, document_id: int, document_type: str) -> dict[str, Any]:
    """Load one Taxer finance document.

    document_type is contract, invoice, or act.
    """
    _require_document_type(document_type)

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.get_document(user_id, document_id, document_type))

    return _call(run)


@mcp.tool()
def create_contract(
    user_id: int,
    date: str,
    number: str,
    direction: int,
    currency: str,
    title: str,
    total: float | None = None,
    comment: str | None = None,
    contractor_id: int | None = None,
    expire_date: str | None = None,
    description: str | None = None,
    place: str | None = None,
) -> dict[str, int]:
    """Create a contract (договір) in Taxer.

    date and expire_date are ISO dates (YYYY-MM-DD) or datetimes. A date
    without a time is midnight UTC. direction is 0 for a sale and 1 for a
    purchase. contractor_id is an existing Taxer contractor id.
    Returns the new document id. This does not upload a file.
    """
    return _create(
        "contract",
        user_id=user_id,
        date=date,
        number=number,
        direction=direction,
        currency=currency,
        title=title,
        total=total,
        comment=comment,
        contractor_id=contractor_id,
        expire_date=expire_date,
        description=description,
        place=place,
    )


@mcp.tool()
def create_invoice(
    user_id: int,
    date: str,
    number: str,
    direction: int,
    currency: str,
    title: str,
    total: float | None = None,
    comment: str | None = None,
    contractor_id: int | None = None,
    expire_date: str | None = None,
    description: str | None = None,
    place: str | None = None,
) -> dict[str, int]:
    """Create an invoice (рахунок) in Taxer.

    Fields match create_contract. date and expire_date are ISO dates
    (YYYY-MM-DD) or datetimes. direction is 0 for a sale and 1 for a purchase.
    Returns the new document id. This does not upload a file.
    """
    return _create(
        "invoice",
        user_id=user_id,
        date=date,
        number=number,
        direction=direction,
        currency=currency,
        title=title,
        total=total,
        comment=comment,
        contractor_id=contractor_id,
        expire_date=expire_date,
        description=description,
        place=place,
    )


@mcp.tool()
def create_act(
    user_id: int,
    date: str,
    number: str,
    direction: int,
    currency: str,
    title: str,
    lines: list[ActLine],
    total: float | None = None,
    comment: str | None = None,
    contractor_id: int | None = None,
    nds: int = -1,
    act_place: str | None = None,
    account_id: int | None = None,
    parent_id: int | None = None,
    parent_type: str = "contract",
    act_type: str | None = None,
    act_print_type: str | None = None,
    is_foreign: int | None = None,
) -> dict[str, int]:
    """Create an act (акт) in Taxer.

    lines is at least one item with title, measure, quantity, and price.
    nds is the VAT rate; -1 means no VAT. parent_id links a contract when set.
    date is an ISO date (YYYY-MM-DD) or datetime. direction is 0 for a sale
    and 1 for a purchase.
    Returns the new document id. This does not upload a file.
    """
    if not lines:
        raise ToolError("An act needs at least one line")
    parsed_lines = [ActLine.model_validate(line) for line in lines]
    return _create(
        "act",
        user_id=user_id,
        date=date,
        number=number,
        direction=direction,
        currency=currency,
        title=title,
        total=total,
        comment=comment,
        contractor_id=contractor_id,
        nds=nds,
        act_place=act_place,
        account_id=account_id,
        parent_id=parent_id,
        parent_type=parent_type,
        act_type=act_type,
        act_print_type=act_print_type,
        is_foreign=is_foreign,
        lines=parsed_lines,
    )


def _create(doc_type: str, **fields: Any) -> dict[str, int]:
    user_id = fields.pop("user_id")
    try:
        document = build_document(doc_type=doc_type, **fields)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    def run(client: TaxerClient) -> dict[str, int]:
        created = client.create_document(user_id, document)
        return {"id": created.id}

    return _call(run)


def _require_document_type(document_type: str) -> None:
    if document_type not in DOCUMENT_TYPES:
        allowed = ", ".join(DOCUMENT_TYPES)
        raise ToolError(f"document_type must be one of {allowed}")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
