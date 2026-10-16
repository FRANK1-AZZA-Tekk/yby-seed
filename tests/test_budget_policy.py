from decimal import Decimal

MONTHLY_LIMIT = Decimal("10.00")
DAILY_LIMIT = Decimal("0.35")


def available_balance(committed: Decimal, reserved: Decimal) -> Decimal:
    return MONTHLY_LIMIT - committed - reserved


def can_call_cloud(committed: Decimal, reserved: Decimal, estimated: Decimal) -> bool:
    return available_balance(committed, reserved) >= estimated


def test_monthly_limit_dominates_daily_projection():
    assert DAILY_LIMIT * 30 > MONTHLY_LIMIT


def test_reservation_reduces_available_balance():
    assert available_balance(Decimal("9.00"), Decimal("0.50")) == Decimal("0.50")


def test_cloud_call_blocked_when_budget_exceeded():
    assert not can_call_cloud(Decimal("9.80"), Decimal("0.20"), Decimal("0.01"))


def test_cloud_call_allowed_with_reservation():
    assert can_call_cloud(Decimal("9.00"), Decimal("0.50"), Decimal("0.10"))


def test_zero_cost_local_call_is_allowed():
    assert can_call_cloud(Decimal("10.00"), Decimal("0.00"), Decimal("0.00"))
