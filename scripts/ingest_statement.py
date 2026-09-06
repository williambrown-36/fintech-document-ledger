import json

from fintech_ingest.contracts import IngestRequest, PaymentEvent, RiskTag
from fintech_ingest.infrai_gateway import InfraiGateway
from fintech_ingest.ledger_service import LedgerService


request = IngestRequest(
    document_id="statement_2026_09_02",
    text=(
        "Payment instruction for supplier Northwind Parts. "
        "Settlement is due on 2026-09-05 against invoice NW-1048. "
        "The beneficiary was added during this payment session."
    ),
    payment=PaymentEvent(
        event_id="pay_evt_1048",
        account_id="treasury_ops",
        amount_minor=245_000,
        currency="USD",
        risk_tag=RiskTag.NEW_BENEFICIARY,
    ),
)

result = LedgerService(InfraiGateway()).ingest(request)
print(json.dumps(result.model_dump(mode="json"), indent=2))
