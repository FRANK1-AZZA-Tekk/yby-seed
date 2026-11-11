from src.yby_zero.routing import Router, RoutingContext


def test_p2_prefers_local_pc() -> None:
    decision = Router().decide(
        RoutingContext(text="manual", privacy_level="P2", pc_available=True)
    )
    assert decision.provider == "ollama"
    assert decision.allow_cloud is False


def test_no_pc_uses_deterministic_when_offline() -> None:
    decision = Router().decide(
        RoutingContext(
            text="status",
            pc_available=False,
            network_available=False,
            budget_mode="offline",
        )
    )
    assert decision.provider == "deterministic"
