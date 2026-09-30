import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from taxer_mcp.client import TaxerClient
from taxer_mcp.models import ActLine
from taxer_mcp.server import (
    ToolError,
    create_act,
    create_contract,
    create_invoice,
    get_document,
    list_documents,
    list_profiles,
    mcp,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _install(monkeypatch, handler):
    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    client = TaxerClient("session_hash=token", base_url="https://taxer.test", client=http)
    monkeypatch.setattr("taxer_mcp.server.get_client", lambda: client)
    return client


def test_server_registers_document_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "list_profiles",
        "list_documents",
        "get_document",
        "create_contract",
        "create_invoice",
        "create_act",
    }


def test_list_profiles_tool(monkeypatch):
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=_load("account.json"))

    _install(monkeypatch, handler)
    result = list_profiles()
    assert result["accountId"] == 217106
    assert result["users"][0]["id"] == 200664
    assert "unknownExtra" not in result


def test_list_documents_rejects_page_zero():
    with pytest.raises(ToolError, match="page_number"):
        list_documents(1, 0)


def test_get_document_rejects_unknown_type():
    with pytest.raises(ToolError, match="document_type"):
        get_document(1, 2, "waybill")


def test_create_contract_and_invoice_share_payload_shape(monkeypatch):
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json={"id": 7})

    _install(monkeypatch, handler)
    kwargs = dict(
        user_id=200664,
        date="2024-04-01",
        number="15",
        direction=0,
        currency="UAH",
        title="Договір",
        total=100.0,
        contractor_id=9,
        expire_date="2025-04-01",
        description="Опис",
        place="Київ",
    )
    assert create_contract(**kwargs) == {"id": 7}
    assert create_invoice(**kwargs) == {"id": 7}

    contract, invoice = seen
    assert contract["userId"] == 200664
    assert contract["document"]["type"] == "contract"
    assert invoice["document"]["type"] == "invoice"
    assert contract["document"]["timestamp"] == 1711929600
    assert contract["document"]["expireTimestamp"] == 1743465600
    assert contract["document"]["contractor"] == {"id": 9}
    assert contract["document"]["file"] == {}
    assert "date" not in contract["document"]


def test_create_act_sends_lines_and_parent(monkeypatch):
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"id": 44})

    _install(monkeypatch, handler)
    result = create_act(
        user_id=200664,
        date="2024-04-01",
        number="44",
        direction=0,
        currency="UAH",
        title="Акт",
        lines=[ActLine(title="Консультація", measure="год", quantity=2, price=250)],
        nds=-1,
        act_place="Київ",
        account_id=3,
        parent_id=15,
    )

    document = seen["body"]["document"]
    assert result == {"id": 44}
    assert document["type"] == "act"
    assert document["nds"] == -1
    assert document["actPlace"] == "Київ"
    assert document["account"] == {"id": 3}
    assert document["parent"] == {"id": 15, "type": "contract"}
    assert document["contents"] == [
        {"title": "Консультація", "measure": "год", "quantity": 2, "price": 250}
    ]


def test_create_act_requires_a_line():
    with pytest.raises(ToolError, match="at least one line"):
        create_act(
            user_id=1,
            date="2024-04-01",
            number="1",
            direction=0,
            currency="UAH",
            title="Акт",
            lines=[],
        )


def test_missing_cookie_is_a_tool_error(monkeypatch):
    monkeypatch.delenv("TAXER_COOKIE", raising=False)
    with pytest.raises(ToolError, match="TAXER_COOKIE"):
        list_profiles()


def test_bad_date_is_a_tool_error(monkeypatch):
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("request should not be sent")

    _install(monkeypatch, handler)
    with pytest.raises(ToolError, match="ISO date"):
        create_invoice(
            user_id=1,
            date="01.04.2024",
            number="1",
            direction=1,
            currency="UAH",
            title="Рахунок",
        )
