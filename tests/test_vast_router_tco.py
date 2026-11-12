import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.yby_seed.forge.packaging import build_mission_bundle
from src.yby_seed.forge.vast_router import OfferTCO, run_mission, search_top_offers


def test_effective_tco_penalizes_slow_inet() -> None:
    fast = OfferTCO(1, 0.4, 0.05, 0.01, 0.01, 0.99, 900)
    slow = OfferTCO(2, 0.4, 0.05, 0.08, 0.02, 0.99, 420)
    assert fast.effective_tco() < slow.effective_tco()


def test_aborts_when_no_offer_within_max_usd() -> None:
    with patch("src.yby_seed.forge.vast_router.search_top_offers", return_value=[]):
        with patch(
            "src.yby_seed.forge.vast_router.build_mission_bundle", return_value=Path("x.tar.zst")
        ):
            plan = run_mission("quantize", max_usd=0.1, dry_run=False)
    assert plan["status"] == "aborted_no_offers_within_tco"


def test_fallback_top3_provision() -> None:
    offers = [
        OfferTCO(1, 0.5, 0.1, 0.02, 0.01, 0.99, 500),
        OfferTCO(2, 0.5, 0.1, 0.02, 0.01, 0.99, 600),
    ]
    mock_client = MagicMock()
    mock_client.show_user.return_value = {"credit": 10.0}
    mock_client.create_instance.side_effect = [RuntimeError("net"), {"new_contract": 99}]
    fake_vast = MagicMock(VastAI=MagicMock(return_value=mock_client))

    with (
        patch("src.yby_seed.forge.vast_router.search_top_offers", return_value=offers),
        patch(
            "src.yby_seed.forge.vast_router.build_mission_bundle", return_value=Path("b.tar.zst")
        ),
        patch.dict(sys.modules, {"vastai": fake_vast}),
    ):
        plan = run_mission("rag-embed", max_usd=1.0, dry_run=False)

    assert plan.get("status") == "provisioned"
    assert mock_client.create_instance.call_count == 2


def test_dry_run_builds_bundle() -> None:
    plan = run_mission("quantize", max_usd=0.5, dry_run=True)
    assert plan["dry_run"] is True
    assert Path(plan["bundle_path"]).exists()


def test_search_offers_empty_without_sdk() -> None:
    assert search_top_offers("rag-embed", 1.0) == []


def test_build_mission_bundle_quantize() -> None:
    bundle = build_mission_bundle("quantize")
    assert bundle.exists()


def test_finetune_aborts_before_vast_when_preflight_fails() -> None:
    fake_report = type(
        "Report",
        (),
        {
            "ok": False,
            "valid_count": 0,
            "min_samples": 20,
            "summary_errors": lambda self: ["arquivo não encontrado"],
        },
    )()

    with (
        patch(
            "src.yby_seed.forge.vast_router.preflight_dataset",
            return_value=fake_report,
        ),
        patch("src.yby_seed.forge.vast_router.search_top_offers") as search_mock,
        patch("src.yby_seed.forge.vast_router.build_mission_bundle") as bundle_mock,
    ):
        plan = run_mission("finetune-qlora", max_usd=1.8, dry_run=False)

    assert plan["status"] == "aborted_preflight_dataset"
    search_mock.assert_not_called()
    bundle_mock.assert_not_called()
