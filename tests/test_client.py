import json
from pathlib import Path

import httpx2
import pytest

from taxer_mcp.client import TaxerClient, TaxerError

FIXTURES = Path(__file__).parent / "fixtures"
COOKIE = (
    "XSRF-TOKEN=abc%3Dtoken; PHPSESSID=php-1; session_key=key-1; "
    "session_hash=sess-1; session_key_hash=hash-1"
)
SESSION_COOKIE = "PHPSESSID=php-1; session_key=key-1; session_hash=sess-1; session_key_hash=hash-1"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _client(handler) -> TaxerClient:
    transport = httpx2.MockTransport(handler)
    http = httpx2.Client(transport=transport)
    return TaxerClient(COOKIE, base_url="https://taxer.test", lang="uk", client=http)


def test_cookie_names_every_missing_session_cookie():
    with pytest.raises(TaxerError, match="PHPSESSID, session_key, session_hash, session_key_hash"):
        TaxerClient("XSRF-TOKEN=only")


def test_cookie_names_only_the_missing_session_cookies():
    with pytest.raises(TaxerError, match="session_key, session_key_hash"):
        TaxerClient("PHPSESSID=php-1; session_hash=sess-1")


def test_full_cookie_without_xsrf_does_not_send_xsrf_header():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("account.json"))

    transport = httpx2.MockTransport(handler)
    http = httpx2.Client(transport=transport)
    client = TaxerClient(SESSION_COOKIE, base_url="https://taxer.test", client=http)
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


def test_list_documents_forwards_filters():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("documents.json"))

    _client(handler).list_documents(200664, 1, {"type": "invoice"})

    assert json.loads(seen["request"].url.params["params"])["filters"] == {"type": "invoice"}


def test_revision_header_uses_the_constructor_value():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("account.json"))

    transport = httpx2.MockTransport(handler)
    http = httpx2.Client(transport=transport)
    client = TaxerClient(COOKIE, base_url="https://taxer.test", revision="app:override", client=http)
    client.load_account()

    assert seen["request"].headers["Revision"] == "app:override"


def test_find_document_stops_on_the_first_page_match():
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        params = json.loads(request.url.params["params"])
        seen.append(params["pageNumber"])
        body = _load("documents.json")
        body["paginator"]["totalPages"] = 4
        return httpx2.Response(200, json=body)

    found = _client(handler).find_document(200664, "contract", "15")

    assert seen == [1]
    assert found is not None
    assert found.id == 15


def test_find_document_reads_the_next_page_and_honors_the_page_cap():
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        params = json.loads(request.url.params["params"])
        page_number = params["pageNumber"]
        seen.append(page_number)
        documents = []
        if page_number == 2:
            documents = [{"id": 20, "type": "invoice", "number": "INV-2", "timestamp": 1711929600}]
        return httpx2.Response(
            200,
            json={
                "paginator": {
                    "currentPage": page_number,
                    "recordsOnPage": 20,
                    "totalPages": 5,
                    "totalRecords": 80,
                },
                "documents": documents,
            },
        )

    client = _client(handler)
    found = client.find_document(200664, "invoice", "INV-2", page_cap=3)
    missing = client.find_document(200664, "invoice", "INV-9", page_cap=2)

    assert found is not None
    assert found.id == 20
    assert missing is None
    assert seen == [1, 2, 1, 2]


def test_find_document_rejects_a_page_cap_above_the_limit():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("request should not be sent")

    with pytest.raises(TaxerError, match="page_cap"):
        _client(handler).find_document(200664, "invoice", "1", page_cap=51)


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


def test_list_print_templates_sends_empty_params_and_keeps_titles():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("templates.json"))

    page = _client(handler).list_print_templates()

    request = seen["request"]
    assert request.method == "GET"
    assert request.url.path == "/api2/finances/template/load"
    assert json.loads(request.url.params["params"]) == {}
    assert request.url.params["lang"] == "uk"
    assert page.paginator is not None
    assert page.paginator.totalRecords == 2
    assert page.templates[0].id == 8
    assert page.templates[0].title == "Invoice (standard template)"
    assert page.templates[0].type == "invoice_foreign"
    assert page.templates[0].isPublic is True
    assert page.templates[1].title == "Invoice"
    assert page.templates[1].isDefault is True


def test_create_print_template_posts_title_type_and_html():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json={"id": 15})

    created = _client(handler).create_print_template(
        "Example invoice",
        "invoice_foreign",
        "<p>Example</p>",
    )

    request = seen["request"]
    assert request.method == "POST"
    assert request.url.path == "/api2/finances/template/create"
    assert json.loads(request.content) == {
        "template": {
            "title": "Example invoice",
            "type": "invoice_foreign",
            "data": "<p>Example</p>",
        }
    }
    assert created.id == 15


def test_update_print_template_posts_the_existing_id():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json={})

    updated = _client(handler).update_print_template(
        15,
        "Example invoice",
        "invoice_foreign",
        "<p>Updated</p>",
    )

    request = seen["request"]
    assert request.method == "POST"
    assert request.url.path == "/api2/finances/template/update"
    assert json.loads(request.content) == {
        "template": {
            "id": 15,
            "title": "Example invoice",
            "type": "invoice_foreign",
            "data": "<p>Updated</p>",
        }
    }
    assert updated.id == 15


def test_update_print_template_accepts_an_empty_body():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"")

    updated = _client(handler).update_print_template(
        15,
        "Example invoice",
        "invoice_foreign",
        "<p>Updated</p>",
    )
    assert updated.id == 15


def test_load_public_print_template_requests_the_type():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("public_template.json"))

    template = _client(handler).load_public_print_template("invoice_foreign")

    request = seen["request"]
    assert request.url.path == "/api2/finances/template/load_public_data"
    assert json.loads(request.url.params["params"]) == {"type": "invoice_foreign"}
    assert template["data"].startswith("<p>")


def test_list_accounts_sends_paged_params_query():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("accounts.json"))

    page = _client(handler).list_accounts(200664, 1)

    request = seen["request"]
    assert request.method == "GET"
    assert request.url.path == "/api/finances/account/load"
    assert json.loads(request.url.params["params"]) == {
        "userId": 200664,
        "pageNumber": 1,
        "filters": {},
    }
    assert page.accounts[0].id == 3
    assert page.accounts[0].balance == 1500.5
    assert page.accountsCurrencies == ["UAH"]


def test_list_operations_fills_content_date():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("operations.json"))

    page = _client(handler).list_operations(200664, 2)

    request = seen["request"]
    assert request.url.path == "/api/finances/operation/load"
    assert json.loads(request.url.params["params"]) == {
        "userId": 200664,
        "pageNumber": 2,
        "sorting": {"date": "DESC"},
        "filters": {},
    }
    content = page.operations[0].contents
    assert content is not None
    assert content[0].date is not None
    assert content[0].date.year == 2024
    assert content[0].sumCurrency == 1000.0


def test_get_operation_sends_id_and_type():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request"] = request
        return httpx2.Response(200, json=_load("operation_income.json"))

    operation = _client(handler).get_operation(200664, 10, "FlowIncome")

    params = json.loads(seen["request"].url.params["params"])
    assert seen["request"].url.path == "/api/finances/operation/load_data"
    assert params == {"userId": 200664, "id": 10, "type": "FlowIncome"}
    assert operation.total == 1000.0
    assert operation.account is not None
    assert operation.account.id == 3
    assert operation.date is not None
    assert operation.contractor is not None
    assert operation.contractor.title == "ТОВ Приклад"


def test_http_error_becomes_taxer_error():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, text="unauthenticated")

    with pytest.raises(TaxerError, match="401") as caught:
        _client(handler).load_account()
    assert caught.value.status_code == 401


def test_transient_transport_error_is_retried(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx2.ReadError("UNEXPECTED_EOF_WHILE_READING")
        return httpx2.Response(200, json=_load("account.json"))

    monkeypatch.setattr("taxer_mcp.client.time.sleep", lambda _sec: None)
    account = _client(handler).load_account()
    assert account.accountId == 217106
    assert calls["n"] == 3
