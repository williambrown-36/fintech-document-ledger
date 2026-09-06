import hashlib

from .contracts import Action, AuditNotification, PaymentEvent, RiskTag

REVIEW_AMOUNT_MINOR = 1_000_000


def decide_action(payment: PaymentEvent) -> AuditNotification:
    if payment.risk_tag in {RiskTag.NEW_BENEFICIARY, RiskTag.SANCTIONS_REVIEW}:
        action = Action.REQUIRE_REVIEW
        reason = f"risk tag {payment.risk_tag.value} requires approval"
    elif payment.amount_minor >= REVIEW_AMOUNT_MINOR:
        action = Action.REQUIRE_REVIEW
        reason = "payment meets the high-value review threshold"
    else:
        action = Action.QUEUE_FOR_POSTING
        reason = "routine payment is ready for posting"

    digest = hashlib.sha256(
        f"{payment.account_id}:{payment.event_id}:{action.value}".encode()
    ).hexdigest()[:16]
    return AuditNotification(
        audit_ref=f"audit_{digest}",
        event_id=payment.event_id,
        action=action,
        reason=reason,
    )
