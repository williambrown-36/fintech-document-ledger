from fintech_ingest.contracts import Action, PaymentEvent, RiskTag
from fintech_ingest.risk_policy import decide_action


def test_new_beneficiary_creates_stable_review_notification() -> None:
    payment = PaymentEvent(
        event_id="pay_evt_1048",
        account_id="treasury_ops",
        amount_minor=245_000,
        currency="USD",
        risk_tag=RiskTag.NEW_BENEFICIARY,
    )

    first = decide_action(payment)
    second = decide_action(payment)

    assert first.action is Action.REQUIRE_REVIEW
    assert first.reason == "risk tag new_beneficiary requires approval"
    assert first.audit_ref == second.audit_ref
