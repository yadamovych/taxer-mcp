import json
from pathlib import Path

import httpx2
import pytest

from taxer_mcp.client import TaxerClient, TaxerError

FIXTURES = Path(__file__).parent / "fixtures"
COOKIE = "XSRF-TOKEN=abc%3Dtoken; session_hash=sess-1"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _client(handler) -> TaxerClient:
    transport = httpx2.MockTransport(handler)
    http = httpx2.Client(transport=transport)
    return TaxerClient(COOKIE, base_url="https://taxer.test", lang="uk", client=http)


def test_cookie_requires_session_hash():
    with pytest.raises(TaxerError, match="session_hash"):
        TaxerClient("XSRF-TOKEN=only")


def test_session_hash_alone_does_not_send_xsrf_header():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("account.json"))

    transport = httpx2.MockTransport(handler)
    http = httpx2.Client(transport=transport)
    client = TaxerClient("session_hash=sess-1", base_url="https://taxer.test", client=http)
    client.load_account()

    assert "X-XSRF-TOKEN" not in seen["request"].headers
    assert "session_hash=sess-1" in seen["request"].headers["Cookie"]


def test_load_account_sends_xsrf_header_and_ignores_unknown_fields():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("account.json"))

    account = _client(handler).load_account()

    request = seen["request"]
    assert request.method == "GET"
    assert request.url.path == "/api/user/login/load_account"
    assert request.url.params["lang"] == "uk"
    assert request.headers["X-XSRF-TOKEN"] == "abc=token"
    assert request.headers["Revision"] == "app:Y45z63lutzk5p0XR"
    assert request.headers["X-Requested-With"] == "XMLHttpRequest"
    assert "session_hash=sess-1" in request.headers["Cookie"]
    assert account.accountId == 217106
    assert account.users[0].id == 200664
    assert account.users[0].titleName == "ФОП Свиридов С. С."


def test_list_documents_sends_paged_params_query():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("documents.json"))

    page = _client(handler).list_documents(200664, 2)

    request = seen["request"]
    assert request.url.path == "/api/finances/document/load"
    assert json.loads(request.url.params["params"]) == {
        "userId": 200664,
        "pageNumber": 2,
        "sorting": {"date": "DESC"},
        "filters": {},
    }
    assert request.headers["X-XSRF-TOKEN"] == "abc=token"
    assert page.paginator is not None
    assert page.paginator.currentPage == 1
    assert page.documents[0].id == 15
    assert page.documents[0].date is not None
    assert page.documents[0].date.year == 2024


def test_get_document_unwraps_document_object():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("document_act.json"))

    document = _client(handler).get_document(200664, 44, "act")

    params = json.loads(seen["request"].url.params["params"])
    assert seen["request"].url.path == "/api/finances/document/load_data"
    assert params == {"userId": 200664, "document": {"id": 44, "type": "act"}}
    assert document.type == "act"
    assert document.parent is not None
    assert document.parent.number == "15"
    assert document.contents is not None
    assert document.contents[0].price == 250


def test_get_document_accepts_a_bare_document_body():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=_load("document_contract.json"))

    document = _client(handler).get_document(200664, 15, "contract")
    assert document.id == 15
    assert document.place == "Київ"
    assert document.expireDate is not None


def test_create_document_posts_payload_and_returns_id():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json={"id": 91})

    created = _client(handler).create_document(
        200664,
        {"type": "invoice", "number": "1", "timestamp": 1711929600, "file": {}},
    )

    request = seen["request"]
    assert request.method == "POST"
    assert request.url.path == "/api/finances/document/create"
    assert request.url.params["lang"] == "uk"
    assert request.headers["X-XSRF-TOKEN"] == "abc=token"
    assert json.loads(request.content) == {
        "userId": 200664,
        "document": {"type": "invoice", "number": "1", "timestamp": 1711929600, "file": {}},
    }
    assert created.id == 91


def test_http_error_becomes_taxer_error():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, text="unauthenticated")

    with pytest.raises(TaxerError, match="401") as caught:
        _client(handler).load_account()
    assert caught.value.status_code == 401
