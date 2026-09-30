"""Pydantic models for Taxer account and finance-document payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

DOCUMENT_TYPES = ("contract", "invoice", "act")


class TaxerModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class User(TaxerModel):
    id: int | None = None
    idKey: str | None = None
    titleName: str | None = None
    isCompany: bool | None = None


class Account(TaxerModel):
    accountId: int | None = None
    accountName: str | None = None
    users: list[User] = Field(default_factory=list)


class Contractor(TaxerModel):
    id: int | None = None
    title: str | None = None


class OperationAccount(TaxerModel):
    id: int | None = None
    title: str | None = None
    currency: str | None = None


class ParentDocument(TaxerModel):
    id: int | None = None
    type: str | None = None
    number: str | None = None
    num: str | None = None
    title: str | None = None
    timestamp: int | None = None
    date: datetime | None = None
    direction: int | None = None
    contractor: Contractor | None = None

    @model_validator(mode="after")
    def copy_num_to_number(self) -> ParentDocument:
        if self.number is None and self.num is not None:
            self.number = self.num
        return self


class DocumentLine(TaxerModel):
    id: int | None = None
    title: str | None = None
    titleTf: str | None = None
    measure: str | None = None
    measureTf: str | None = None
    quantity: float | None = None
    price: float | None = None


class Document(TaxerModel):
    id: int | None = None
    type: str | None = None
    direction: int | None = None
    number: str | None = None
    contractor: Contractor | None = None
    currency: str | None = None
    paid: float | None = None
    total: float | None = None
    title: str | None = None
    comment: str | None = None
    description: str | None = None
    place: str | None = None
    account: OperationAccount | None = None
    parent: ParentDocument | None = None
    nds: int | None = None
    actPlace: str | None = None
    actType: str | None = None
    actPrintType: str | None = None
    isForeign: int | None = None
    file: dict[str, Any] | None = None
    contents: list[DocumentLine] | None = None
    timestamp: int | None = None
    date: datetime | None = None
    expireTimestamp: int | None = None
    expireDate: datetime | None = None

    @model_validator(mode="after")
    def fill_dates_from_timestamps(self) -> Document:
        self.date = _date_from_timestamp(self.timestamp, self.date)
        self.expireDate = _date_from_timestamp(self.expireTimestamp, self.expireDate)
        return self


class Paginator(TaxerModel):
    currentPage: int | None = None
    recordsOnPage: int | None = None
    totalPages: int | None = None
    totalRecords: int | None = None


class DocumentPage(TaxerModel):
    paginator: Paginator | None = None
    documents: list[Document] = Field(default_factory=list)


class CreatedEntity(TaxerModel):
    id: int


class ActLine(BaseModel):
    """One service or goods line on an act."""

    title: str
    measure: str
    quantity: float
    price: float
    title_tf: str | None = None
    measure_tf: str | None = None


def iso_to_timestamp(value: str) -> int:
    """Convert an ISO date or datetime to a Unix timestamp.

    A date without a time is midnight UTC. Taxer stores document dates as
    timestamps, which is what the create call sends.
    """
    text = value.strip()
    if not text:
        raise ValueError("date is empty")
    try:
        if len(text) == 10:
            parsed = datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"{value!r} is not an ISO date (YYYY-MM-DD) or datetime"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def build_document(
    *,
    doc_type: str,
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
    nds: int | None = None,
    act_place: str | None = None,
    act_type: str | None = None,
    act_print_type: str | None = None,
    is_foreign: int | None = None,
    account_id: int | None = None,
    parent_id: int | None = None,
    parent_type: str | None = None,
    lines: list[ActLine] | None = None,
) -> dict[str, Any]:
    """Build the document object sent to api/finances/document/create."""
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError(f"document type must be one of {', '.join(DOCUMENT_TYPES)}")

    document: dict[str, Any] = {
        "type": doc_type,
        "timestamp": iso_to_timestamp(date),
        "number": number,
        "direction": direction,
        "currency": currency,
        "title": title,
        "file": {},
    }
    _put(document, "total", total)
    _put(document, "comment", comment)
    _put(document, "description", description)
    _put(document, "place", place)
    _put(document, "nds", nds)
    _put(document, "actPlace", act_place)
    _put(document, "actType", act_type)
    _put(document, "actPrintType", act_print_type)
    _put(document, "isForeign", is_foreign)
    if expire_date:
        document["expireTimestamp"] = iso_to_timestamp(expire_date)
    if contractor_id is not None:
        document["contractor"] = {"id": contractor_id}
    if account_id is not None:
        document["account"] = {"id": account_id}
    if parent_id is not None:
        parent: dict[str, Any] = {"id": parent_id}
        if parent_type:
            parent["type"] = parent_type
        document["parent"] = parent
    if lines is not None:
        document["contents"] = [_line_payload(line) for line in lines]
    return document


def dump_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


def _date_from_timestamp(timestamp: int | None, current: datetime | None) -> datetime | None:
    if current is None and timestamp is not None:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return current


def _put(document: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        document[key] = value


def _line_payload(line: ActLine) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": line.title,
        "measure": line.measure,
        "quantity": line.quantity,
        "price": line.price,
    }
    if line.title_tf:
        payload["titleTf"] = line.title_tf
    if line.measure_tf:
        payload["measureTf"] = line.measure_tf
    return payload
