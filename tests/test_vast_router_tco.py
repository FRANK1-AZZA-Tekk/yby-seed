from pathlib import Path
from unittest.mock import patch

from src.yby_seed.forge.packaging import build_mission_bundle
from src.yby_seed.forge.vast_router import OfferTCO, run_mission, search_top_offers


def test_offer_tco_hourly_sum() -> None:
    offer = OfferTCO(
        offer_id=1,
        dph_total=0.5,
        storage_cost=0.1,
        inet_down_cost=0.05,
        inet_up_cost=0.02,
        reliability=0.99,
        inet_down=500.0,
    )
    assert round(offer.tco_hourly, 2) == 0.67


@patch("src.yby_seed.forge.vast_router.search_top_offers", return_value=[])
def test_run_mission_dry_run_builds_bundle(mock_search) -> None:
    with patch("src.yby_seed.forge.vast_router.build_mission_bundle") as mock_bundle:
        mock_bundle.return_value = Path("data/forge/bundles/test.tar.zst")
        plan = run_mission("quantize", max_usd=0.5, dry_run=True)
    assert plan["dry_run"] is True
    assert plan["mission"] == "quantize"
    assert "bundle_path" in plan
    mock_bundle.assert_called_once_with("quantize")


def test_build_mission_bundle_quantize() -> None:
    bundle = build_mission_bundle("quantize")
    assert bundle.exists()


def test_search_offers_without_vast_sdk() -> None:
    offers = search_top_offers("rag-embed", max_usd=1.0)
    assert offers == []
