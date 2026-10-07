import base64
import json

import httpx2
import pytest

from taxer_mcp.client import TaxerClient, TaxerError
from taxer_mcp.server import ToolError, export_document_pdf
from taxer_mcp.template_pdf import convert_html_to_pdf, fill_template

LAYOUT = """
<p><span data-name="invoiceNum" data-decorator-type="mergefield">Номер рахунку</span></p>
<table><tr><th>Item</th></tr>
<tr><td><span data-name="nomenclatureNumber" data-multiple="true">Номер(N)</span></td>
<td><strong data-name="contentTfNomenclature" data-decorator-type="mergefield">Line description</strong></td>
</tr></table>
"""


def test_fill_template_replaces_labels_and_repeats_line_rows():
    filled = fill_template(
        LAYOUT,
        {
            "invoiceNum": "INV-1",
            "nomenclatureNumber": [1, 2],
            "contentTfNomenclature": ["Computer programming services", "Support"],
        },
    )

    assert "Номер рахунку" not in filled
    assert "Line description" not in filled
    assert filled.count("INV-1") == 1
    assert filled.count("<tr>") == 3
    assert "Computer programming services" in filled
    assert "Support" in filled
    assert ">1<" in filled
    assert ">2<" in filled


def test_fill_template_handles_split_closing_tag():
    html = (
        '<span\n        data-name="invoiceNum"\n        data-decorator-type="mergefield"\n        '
        ">Номер рахунку</span\n      >"
    )
    filled = fill_template(html, {"invoiceNum": "4"})
    assert "4" in filled
    assert "Номер рахунку" not in filled


def test_fill_template_leaves_static_text():
    html = '<p>Static contact</p><span data-name="contractorName">Customer name</span>'
    filled = fill_template(html, {"contractorName": "Example customer"})
    assert "Static contact" in filled
    assert "Example customer" in filled


def test_convert_html_decodes_base64_pdf():
    pdf = b"%PDF-1.4\n"
    token = "converter-token"

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["X-Taxer-Converter-Token"] == token
        assert "Cookie" not in request.headers
        assert json.loads(request.content)["html"] == "<p>Invoice</p>"
        return httpx2.Response(200, text=base64.b64encode(pdf).decode("ascii"))

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    original = httpx2.post

    def post(url, **kwargs):
        assert url == "https://converter.test/convert"
        return client.post(url, **kwargs)

    httpx2.post = post
    try:
        assert convert_html_to_pdf("<p>Invoice</p>", token, "https://converter.test/convert") == pdf
    finally:
        httpx2.post = original


def test_convert_html_rejects_a_non_pdf():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, text="not-a-pdf")

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    original = httpx2.post
    httpx2.post = lambda url, **kwargs: client.post(url, **kwargs)
    try:
        with pytest.raises(TaxerError, match="did not return a PDF"):
            convert_html_to_pdf("<p></p>", "token", "https://converter.test/convert")
    finally:
        httpx2.post = original


def test_export_document_pdf_tool_writes_filled_template(monkeypatch, tmp_path):
    from taxer_mcp import template_pdf

    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.setdefault("paths", []).append(request.url.path)
        if request.url.path == "/api/finances/document/load_template_data":
            assert json.loads(request.url.params["params"]) == {
                "userId": 200664,
                "documentId": 5,
                "documentType": "invoice",
            }
            return httpx2.Response(200, json={"data": {"invoiceNum": "INV-1", "nomenclatureNumber": [1]}})
        if request.url.path == "/api2/finances/template/load_data":
            assert json.loads(request.url.params["params"]) == {"id": 7}
            return httpx2.Response(
                200,
                json={
                    "template": {
                        "id": 7,
                        "title": "Invoice",
                        "type": "invoice_foreign",
                        "data": LAYOUT,
                    }
                },
            )
        if request.url.path == "/api2/generator/file/converter_token":
            assert json.loads(request.content) == {"format": "pdf"}
            return httpx2.Response(200, json={"token": "tok"})
        if request.url.path == "/api/finances/document/upload_file":
            body = json.loads(request.content)
            seen["upload"] = body
            stored = base64.b64decode(body["file"]["content"]).decode()
            assert stored.startswith("<body>")
            assert "INV-1" in stored
            assert "<style>" not in stored
            return httpx2.Response(200, json={"id": 44})
        if request.url.path in {"/pdf-documents.css", "/pdf-finances-documents.css"}:
            return httpx2.Response(200, text="p{margin:0}")
        return httpx2.Response(404, text=request.url.path)

    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    client = TaxerClient("session_hash=token", base_url="https://taxer.test", client=http)
    monkeypatch.setattr("taxer_mcp.server.get_client", lambda: client)

    def fake_convert(html: str, token: str, url: str) -> bytes:
        seen["html"] = html
        seen["token"] = token
        seen["url"] = url
        return b"%PDF-1.4"

    monkeypatch.setattr(template_pdf, "convert_html_to_pdf", fake_convert)
    destination = tmp_path / "invoice.pdf"
    result = export_document_pdf(200664, 5, "invoice", 7, str(destination))

    assert result["templateTitle"] == "Invoice"
    assert result["templateType"] == "invoice_foreign"
    assert result["generatedFileId"] == 44
    assert result["path"] == str(destination)
    assert destination.read_bytes() == b"%PDF-1.4"
    assert seen["token"] == "tok"
    assert "INV-1" in seen["html"]
    assert "Номер рахунку" not in seen["html"]
    assert seen["paths"].index("/api2/generator/file/converter_token") < seen["paths"].index(
        "/api/finances/document/upload_file"
    )
    upload = seen["upload"]
    assert upload["generated"] is True
    assert upload["userId"] == 200664
    assert upload["documentId"] == 5
    assert upload["documentType"] == "invoice"
    assert upload["file"]["filename"] == "Invoice"


def test_export_document_pdf_rejects_unknown_type():
    with pytest.raises(ToolError, match="document_type"):
        export_document_pdf(1, 2, "waybill", 7)
