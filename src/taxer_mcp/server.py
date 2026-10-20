"""MCP tools for Taxer.ua finance documents."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from taxer_mcp import template_pdf
from taxer_mcp.client import DEFAULT_DOCUMENT_PAGE_CAP, MAX_DOCUMENT_PAGE_CAP, TaxerClient, TaxerError
from taxer_mcp.models import (
    DOCUMENT_TYPES,
    OPERATION_TYPES,
    PRINT_TEMPLATE_TYPES,
    ActLine,
    MergeField,
    build_document,
    dump_model,
)

mcp = MCPServer("taxer")


def get_client() -> TaxerClient:
    cookie = os.environ.get("TAXER_COOKIE", "").strip()
    if not cookie:
        raise TaxerError("TAXER_COOKIE is not set")
    revision = os.environ.get("TAXER_REVISION", "").strip() or None
    return TaxerClient(
        cookie,
        base_url=os.environ.get("TAXER_BASE_URL", "https://taxer.ua"),
        lang=os.environ.get("TAXER_LANG", "uk"),
        revision=revision,
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
def list_documents(
    user_id: int,
    page_number: int = 1,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List one page of finance documents for a Taxer profile.

    user_id is a profile id from list_profiles. page_number starts at 1.
    The page includes contracts, invoices, and acts. filters is an optional
    object forwarded to Taxer. Omit it to list the page unfiltered.
    """
    if page_number < 1:
        raise ToolError("page_number starts at 1")

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.list_documents(user_id, page_number, filters))

    return _call(run)


@mcp.tool()
def find_document(
    user_id: int,
    document_type: str,
    number: str,
    page_cap: int = DEFAULT_DOCUMENT_PAGE_CAP,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Find one finance document by type and number.

    Walks the document list from page 1, newest first, and stops on the
    first match. page_cap limits how many pages are read (1 to 50, default
    20). filters is an optional object forwarded to Taxer. Returns found
    false when the document is not in those pages, so a monthly run can
    refuse to create a second invoice with the same number.
    """
    _require_document_type(document_type)
    if page_cap < 1 or page_cap > MAX_DOCUMENT_PAGE_CAP:
        raise ToolError(f"page_cap must be from 1 to {MAX_DOCUMENT_PAGE_CAP}")
    if not str(number).strip():
        raise ToolError("number is empty")

    def run(client: TaxerClient) -> dict[str, Any]:
        document = client.find_document(
            user_id,
            document_type,
            number,
            filters=filters,
            page_cap=page_cap,
        )
        if document is None:
            return {"found": False}
        return {"found": True, "document": dump_model(document)}

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
def list_accounts(
    user_id: int,
    page_number: int = 1,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List one page of money accounts for a Taxer profile.

    user_id is a profile id from list_profiles. page_number starts at 1.
    An account id from this list is account_id on an invoice or act.
    filters is an optional object forwarded to Taxer.
    """
    if page_number < 1:
        raise ToolError("page_number starts at 1")

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.list_accounts(user_id, page_number, filters))

    return _call(run)


@mcp.tool()
def list_operations(
    user_id: int,
    page_number: int = 1,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List one page of bank operations for a Taxer profile.

    user_id is a profile id from list_profiles. page_number starts at 1.
    filters is an optional object forwarded to Taxer.
    """
    if page_number < 1:
        raise ToolError("page_number starts at 1")

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.list_operations(user_id, page_number, filters))

    return _call(run)


@mcp.tool()
def get_operation(user_id: int, operation_id: int, operation_type: str) -> dict[str, Any]:
    """Load one Taxer bank operation.

    operation_type is Withdrawal, FlowOutgo, FlowIncome, CurrencyExchange,
    or AutoExchange.
    """
    _require_operation_type(operation_type)

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.get_operation(user_id, operation_id, operation_type))

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
    nds: int = -1,
    lines: list[ActLine] | None = None,
    account_id: int | None = None,
    parent_id: int | None = None,
    parent_type: str = "contract",
    is_foreign: int | None = None,
) -> dict[str, int]:
    """Create an invoice (рахунок) in Taxer.

    date and expire_date are ISO dates (YYYY-MM-DD) or datetimes. direction
    is 0 for a sale and 1 for a purchase. nds is the VAT rate; -1 means no
    VAT and is always sent, because Taxer rejects an invoice without it.
    lines, when set, is at least one item with title, measure, quantity, and
    price. parent_id links a contract when set. account_id is a Taxer money
    account. is_foreign is 1 for a foreign contractor.
    Returns the new document id. This does not upload a file.
    """
    parsed_lines = _parse_lines(lines, "invoice")
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
        nds=nds,
        account_id=account_id,
        parent_id=parent_id,
        parent_type=parent_type,
        is_foreign=is_foreign,
        lines=parsed_lines,
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
    parsed_lines = _parse_lines(lines, "act")
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


@mcp.tool()
def list_print_templates() -> dict[str, Any]:
    """List Taxer print templates, including each template's name.

    templates is the page of layouts. Each item has id, title, and type.
    title is the name shown in the cabinet. isDefault is true for the
    template Taxer selects by default. isPublic is true for a standard
    Taxer template. Pass id to export_document_pdf as template_id.
    """

    def run(client: TaxerClient) -> dict[str, Any]:
        return dump_model(client.list_print_templates())

    return _call(run)


@mcp.tool()
def create_print_template(
    title: str,
    template_type: str,
    html: str | None = None,
    fields: list[MergeField] | None = None,
    copy_public: bool = False,
) -> dict[str, int]:
    """Create a Taxer print template and return its id.

    template_type is one of contract, act_foreign, act_product, act_service,
    act_product_nds, act_service_nds, waybill, waybill_nds, check, check_nds,
    invoice, invoice_foreign, or invoice_nds. html is the layout. fields are
    variables filled later from the document, customer, or bank account: name
    is the variable key, display_name is its label, and multiple marks a
    line-item column. copy_public starts from Taxer's predefined layout for
    that type when html is omitted. The id is template_id for
    export_document_pdf. This stores a template on the account.
    """
    _require_print_template_type(template_type)
    if not title.strip():
        raise ToolError("title is empty")
    parsed_fields = _parse_merge_fields(fields)
    if html is None and not parsed_fields and not copy_public:
        raise ToolError("A template needs html, fields, or copy_public")

    def run(client: TaxerClient) -> dict[str, int]:
        layout = _template_html(client, template_type, html, parsed_fields, copy_public)
        created = client.create_print_template(title.strip(), template_type, layout)
        return {"id": created.id}

    return _call(run)


@mcp.tool()
def update_print_template(
    template_id: int,
    title: str | None = None,
    template_type: str | None = None,
    html: str | None = None,
    fields: list[MergeField] | None = None,
    copy_public: bool = False,
) -> dict[str, int]:
    """Update one saved Taxer print template.

    template_id is an id from list_print_templates. Omit title or
    template_type to keep the saved value. html replaces the layout. fields
    are variables appended to the current layout when html is omitted, or to
    html when it is set. copy_public replaces the layout with Taxer's
    predefined layout for the template type. A public standard template
    cannot be updated. Returns the same template id.
    """
    if template_id < 1:
        raise ToolError("template_id starts at 1")
    if template_type is not None:
        _require_print_template_type(template_type)
    if title is not None and not title.strip():
        raise ToolError("title is empty")
    parsed_fields = _parse_merge_fields(fields)
    if (
        title is None
        and template_type is None
        and html is None
        and not parsed_fields
        and not copy_public
    ):
        raise ToolError("An update needs a title, template_type, html, fields, or copy_public")

    def run(client: TaxerClient) -> dict[str, int]:
        current = client.load_print_template(template_id)
        if current.get("isPublic") is True:
            raise ToolError("A public Taxer template is read-only")
        next_title = _template_title(title, current.get("title"))
        next_type = _template_type(template_type, current.get("type"))
        layout = _updated_template_html(client, current, next_type, html, parsed_fields, copy_public)
        client.update_print_template(template_id, next_title, next_type, layout)
        return {"id": template_id}

    return _call(run)


@mcp.tool()
def export_document_pdf(
    user_id: int,
    document_id: int,
    document_type: str,
    template_id: int,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Render a Taxer document with a saved print template and write a PDF.

    user_id is a profile id from list_profiles. document_type is contract,
    invoice, or act. template_id is the saved print template to fill.
    Values come from load_template_data and the layout from that template.
    The PDF is written to output_path, or to a temporary file when
    output_path is omitted. The filled template is then stored on the
    document in Taxer. Returns the template title, the file path, and the
    stored file id.
    """
    _require_document_type(document_type)
    destination = _pdf_destination(output_path, document_type, document_id)
    converter_url = os.environ.get("TAXER_PDF_CONVERTER_URL", template_pdf.DEFAULT_PDF_CONVERTER_URL)

    def run(client: TaxerClient) -> dict[str, Any]:
        pdf, info = template_pdf.export_document_pdf(
            client,
            user_id=user_id,
            document_id=document_id,
            document_type=document_type,
            template_id=template_id,
            converter_url=converter_url,
        )
        destination.write_bytes(pdf)
        return {**info, "path": str(destination), "bytes": len(pdf)}

    return _call(run)


def _pdf_destination(output_path: str | None, document_type: str, document_id: int) -> Path:
    if output_path:
        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    fd, name = tempfile.mkstemp(prefix=f"taxer-{document_type}-{document_id}-", suffix=".pdf")
    os.close(fd)
    return Path(name)


def _parse_lines(lines: list[ActLine] | None, doc_type: str) -> list[ActLine] | None:
    if lines is None:
        return None
    if not lines:
        raise ToolError(f"An {doc_type} needs at least one line")
    return [ActLine.model_validate(line) for line in lines]


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


def _template_title(title: str | None, current: Any) -> str:
    if title is not None:
        return title.strip()
    if isinstance(current, str) and current.strip():
        return current.strip()
    raise ToolError("title is empty")


def _template_type(template_type: str | None, current: Any) -> str:
    if template_type is not None:
        return template_type
    if isinstance(current, str) and current in PRINT_TEMPLATE_TYPES:
        return current
    raise ToolError("template_type is missing on the saved template")


def _updated_template_html(
    client: TaxerClient,
    current: dict[str, Any],
    template_type: str,
    html: str | None,
    fields: list[MergeField] | None,
    copy_public: bool,
) -> str:
    if html is not None or copy_public:
        return _template_html(client, template_type, html, fields, copy_public)
    data = current.get("data")
    layout = data if isinstance(data, str) else ""
    if fields:
        layout += template_pdf.merge_fields_html(
            [(field.name, field.display_name, field.multiple) for field in fields]
        )
    if not layout.strip():
        raise ToolError("The template has no layout")
    return layout


def _template_html(
    client: TaxerClient,
    template_type: str,
    html: str | None,
    fields: list[MergeField] | None,
    copy_public: bool,
) -> str:
    if html is not None:
        layout = html
    elif copy_public:
        public = client.load_public_print_template(template_type)
        data = public.get("data")
        if not isinstance(data, str):
            raise ToolError(f"Taxer has no public layout for {template_type}")
        layout = data
    else:
        layout = ""
    if fields:
        layout += template_pdf.merge_fields_html(
            [(field.name, field.display_name, field.multiple) for field in fields]
        )
    if not layout.strip():
        raise ToolError("A template needs html, fields, or copy_public")
    return layout


def _parse_merge_fields(fields: list[MergeField] | None) -> list[MergeField] | None:
    if fields is None:
        return None
    if not fields:
        raise ToolError("fields is empty")
    return [MergeField.model_validate(field) for field in fields]


def _require_print_template_type(template_type: str) -> None:
    if template_type not in PRINT_TEMPLATE_TYPES:
        allowed = ", ".join(PRINT_TEMPLATE_TYPES)
        raise ToolError(f"template_type must be one of {allowed}")


def _require_document_type(document_type: str) -> None:
    if document_type not in DOCUMENT_TYPES:
        allowed = ", ".join(DOCUMENT_TYPES)
        raise ToolError(f"document_type must be one of {allowed}")


def _require_operation_type(operation_type: str) -> None:
    if operation_type not in OPERATION_TYPES:
        allowed = ", ".join(OPERATION_TYPES)
        raise ToolError(f"operation_type must be one of {allowed}")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
