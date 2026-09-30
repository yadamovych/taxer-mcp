"""Fill a Taxer print template and send it to the PDF converter.

The cabinet loads values from ``api/finances/document/load_template_data`` and
the layout from ``api2/finances/template/load_data``. Merge fields are HTML
elements with ``data-name``. A table row marked ``data-multiple`` is repeated
once per line item. The session cookie is not sent to the converter.
"""

from __future__ import annotations

import base64
import re
from html import escape
from typing import Any

import httpx2

from taxer_mcp.client import TaxerClient, TaxerError

DEFAULT_PDF_CONVERTER_URL = (
    "https://ztf2u2xswmuctvqfvbbbezg65m0ubyks.lambda-url.eu-west-1.on.aws/convert"
)
DOCUMENT_STYLESHEETS = ("/pdf-documents.css", "/pdf-finances-documents.css")

_MERGE_TAG = re.compile(
    r"<(span|strong|b)\b([^>]*\bdata-name=\"([^\"]+)\"[^>]*)>([^<]*)</\1>",
    re.IGNORECASE,
)
_TABLE_ROW = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
_FIELD_NAME = re.compile(r'data-name="([^"]+)"')


def fill_template(html: str, fields: dict[str, Any]) -> str:
    """Replace merge-field labels with values from load_template_data."""
    row_count = _row_count(fields)

    def expand_row(match: re.Match[str]) -> str:
        row = match.group(0)
        names = _FIELD_NAME.findall(row)
        repeats = any(isinstance(fields.get(name), list) for name in names)
        if not repeats:
            return _fill_fragment(row, fields, 0)
        return "".join(_fill_fragment(row, fields, index) for index in range(row_count))

    expanded = _TABLE_ROW.sub(expand_row, html)
    return _fill_fragment(expanded, fields, 0, skip_lists=True)


def build_document_html(body: str, css: str) -> str:
    return (
        "<!DOCTYPE html><html><head>"
        '<meta http-equiv="content-type" content="text/html; charset=utf-8" />'
        f"<style>{css}</style></head><body>{body}</body></html>"
    )


def editor_html(filled: str) -> str:
    """Filled template as the document editor stores it: a body element."""
    if filled.strip().lower().startswith("<body"):
        return filled
    return f"<body>{filled}</body>"


def convert_html_to_pdf(html: str, token: str, converter_url: str) -> bytes:
    """POST filled HTML to Taxer's PDF converter. Do not send the session cookie."""
    response = httpx2.post(
        converter_url,
        json={"html": html},
        headers={
            "X-Taxer-Converter-Token": token,
            "Content-Type": "application/json",
            "Accept": "text/plain, application/pdf, */*",
        },
        timeout=60.0,
    )
    if response.status_code != 200:
        raise TaxerError(
            f"Taxer PDF converter {response.status_code}: {response.text[:300]}",
            status_code=response.status_code,
        )
    return _pdf_bytes(response)


def export_document_pdf(
    client: TaxerClient,
    *,
    user_id: int,
    document_id: int,
    document_type: str,
    template_id: int,
    converter_url: str = DEFAULT_PDF_CONVERTER_URL,
) -> tuple[bytes, dict[str, Any]]:
    """Load one document's template values and one print layout, then render a PDF.

    After the PDF is built, the filled template is stored on the document with
    upload_file and generated set, which is the cabinet editor's Save call.
    """
    fields = client.load_document_template_data(user_id, document_id, document_type)
    template = client.load_print_template(template_id)
    body = template.get("data")
    if not isinstance(body, str) or not body:
        raise TaxerError(f"Taxer template {template_id} has no HTML layout")
    filled = fill_template(body, fields)
    css = _stylesheets(client)
    html = build_document_html(filled, css)
    token = client.create_converter_token("pdf")
    pdf = convert_html_to_pdf(html, token, converter_url)
    title = template.get("title")
    filename = title if isinstance(title, str) and title else document_type
    file_id = client.upload_generated_file(
        user_id,
        document_id,
        document_type,
        filename,
        editor_html(filled),
    )
    info = {
        "templateId": template.get("id", template_id),
        "templateTitle": title,
        "templateType": template.get("type"),
        "generatedFileId": file_id,
    }
    return pdf, info


def _stylesheets(client: TaxerClient) -> str:
    parts: list[str] = []
    for path in DOCUMENT_STYLESHEETS:
        try:
            parts.append(client.fetch_text(path))
        except TaxerError:
            continue
    parts.append("body{font-family:Arial,sans-serif;} table{border-collapse:collapse;} p{margin:0;}")
    return "\n".join(parts)


def _row_count(fields: dict[str, Any]) -> int:
    lengths = [len(value) for value in fields.values() if isinstance(value, list)]
    return max(lengths) if lengths else 1


def _fill_fragment(
    fragment: str,
    fields: dict[str, Any],
    index: int,
    *,
    skip_lists: bool = False,
) -> str:
    def replace(match: re.Match[str]) -> str:
        tag, attrs, name, _inner = match.group(1), match.group(2), match.group(3), match.group(4)
        if skip_lists and isinstance(fields.get(name), list):
            return match.group(0)
        text = escape(_text(_field_value(fields, name, index)), quote=False)
        return f"<{tag}{attrs}>{text}</{tag}>"

    return _MERGE_TAG.sub(replace, fragment)


def _field_value(fields: dict[str, Any], name: str, index: int) -> Any:
    if name not in fields or fields[name] is None:
        return ""
    value = fields[name]
    if isinstance(value, list):
        if index < len(value):
            return "" if value[index] is None else value[index]
        return ""
    return value


def _text(value: Any) -> str:
    return str(value)


def _pdf_bytes(response: httpx2.Response) -> bytes:
    raw = response.content
    if raw.startswith(b"%PDF"):
        return raw
    text = response.text.strip()
    try:
        decoded = base64.b64decode(text, validate=True)
    except ValueError as exc:
        raise TaxerError("Taxer PDF converter did not return a PDF") from exc
    if not decoded.startswith(b"%PDF"):
        raise TaxerError("Taxer PDF converter did not return a PDF")
    return decoded
