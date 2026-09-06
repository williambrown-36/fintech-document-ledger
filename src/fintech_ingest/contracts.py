from enum import StrEnum

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep lightweight policy usage usable without service extras.
    class _FieldDefault:
        def __init__(self, default=None, **_constraints):
            self.default = default

    def Field(default=None, **constraints):
        return _FieldDefault(default, **constraints)

    class BaseModel:
        def __init__(self, **values):
            annotations = getattr(type(self), "__annotations__", {})
            for name in annotations:
                value = values.get(name, getattr(type(self), name, None))
                if isinstance(value, _FieldDefault):
                    value = value.default
                setattr(self, name, value)


class RiskTag(StrEnum):
    ROUTINE = "routine"
    NEW_BENEFICIARY = "new_beneficiary"
    SANCTIONS_REVIEW = "sanctions_review"


class PaymentEvent(BaseModel):
    event_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    risk_tag: RiskTag


class IngestRequest(BaseModel):
    document_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    payment: PaymentEvent


class Action(StrEnum):
    QUEUE_FOR_POSTING = "queue_for_posting"
    REQUIRE_REVIEW = "require_review"


class AuditNotification(BaseModel):
    audit_ref: str
    event_id: str
    action: Action
    reason: str


class IngestResult(BaseModel):
    document_id: str
    chunks_written: int
    notification: AuditNotification


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    items: list[dict[str, object]]
