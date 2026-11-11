from src.yby_zero.privacy import PrivacyPolicy


def test_p3_requires_confirmation_and_blocks_cloud() -> None:
    decision = PrivacyPolicy().classify("P3")
    assert decision.require_confirmation is True
    assert decision.allow_cloud is False
