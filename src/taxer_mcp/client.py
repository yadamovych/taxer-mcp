"""HTTP client for the Taxer.ua finance-document API.

Taxer does not publish this API. Calls follow the session-cookie flow used by
https://github.com/maxsivkov/py-taxer-api: send the browser cookie jar and the
XSRF-TOKEN value as X-XSRF-TOKEN.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

import httpx2

from taxer_mcp.models import Account, CreatedEntity, Document, DocumentPage

DEFAULT_BASE_URL = "https://taxer.ua"


class TaxerError(Exception):
    """Taxer rejected a call or the session cookie is unusable."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_cookie_header(cookie: str) -> dict[str, str]:
    """Parse a document.cookie string into a name-to-value mapping."""
    jar: dict[str, str] = {}
    for part in cookie.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        jar[name.strip()] = value.strip()
    return jar


class TaxerClient:
    """Sync client for account lookup and finance documents."""

    def __init__(
        self,
        cookie: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        lang: str = "uk",
        client: httpx2.Client | None = None,
    ) -> None:
        self._cookies = parse_cookie_header(cookie)
        token = self._cookies.get("XSRF-TOKEN")
        if not token:
            raise TaxerError("TAXER_COOKIE must include XSRF-TOKEN")
        self.lang = lang
        self.base_url = base_url.rstrip("/")
        self._token = unquote(token)
        self._owns_client = client is None
        self._client = client or httpx2.Client(base_url=self.base_url, timeout=30.0)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> TaxerClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def load_account(self) -> Account:
        payload = self._execute("GET", "api/user/login/load_account", params={"lang": self.lang})
        account = payload.get("account") if isinstance(payload, dict) else None
        if not isinstance(account, dict):
            raise TaxerError("Taxer account response has no account object")
        return Account.model_validate(account)

    def list_documents(self, user_id: int, page_number: int = 1) -> DocumentPage:
        payload = self._execute(
            "GET",
            "api/finances/document/load",
            params=self._query(
                {
                    "userId": user_id,
                    "pageNumber": page_number,
                    "sorting": {"date": "DESC"},
                    "filters": {},
                }
            ),
        )
        return DocumentPage.model_validate(payload)

    def get_document(self, user_id: int, document_id: int, document_type: str) -> Document:
        payload = self._execute(
            "GET",
            "api/finances/document/load_data",
            params=self._query(
                {
                    "userId": user_id,
                    "document": {"id": document_id, "type": document_type},
                }
            ),
        )
        if isinstance(payload, dict) and isinstance(payload.get("document"), dict):
            payload = payload["document"]
        return Document.model_validate(payload)

    def create_document(self, user_id: int, document: dict[str, Any]) -> CreatedEntity:
        payload = self._execute(
            "POST",
            "api/finances/document/create",
            params={"lang": self.lang},
            json_body={"userId": user_id, "document": document},
        )
        return CreatedEntity.model_validate(payload)

    def _query(self, params: dict[str, Any]) -> dict[str, str]:
        return {
            "lang": self.lang,
            "params": json.dumps(params, ensure_ascii=False, separators=(",", ":")),
        }

    def _execute(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                self._url(path),
                params=params,
                json=json_body,
                headers=self._headers(),
                cookies=self._cookies,
            )
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise TaxerError(
                f"Taxer API {exc.response.status_code} for {method} {path}: {exc.response.text}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx2.HTTPError as exc:
            raise TaxerError(f"Taxer API request failed for {method} {path}: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise TaxerError(f"Taxer API returned non-JSON for {method} {path}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": f"{self.base_url}/{self.lang}/my/dashboard",
            "User-Agent": "taxer-mcp/0.1",
            "X-XSRF-TOKEN": self._token,
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"
