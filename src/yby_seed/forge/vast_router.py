"""Roteamento de missões GPU na Vast.ai (TCO + dry-run)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.yby_seed.config import get_settings
from src.yby_seed.forge.deploy_model import preflight_dataset
from src.yby_seed.forge.packaging import MISSION_ENTRYPOINTS, build_mission_bundle

logger = logging.getLogger(__name__)

MISSION_PROFILES = {
    "rag-embed": {
        "num_gpus": 1,
        "gpu_name": "RTX_3090",
        "default_max_usd": 0.80,
        "label": "rag-embed",
        "onstart_note": "vetorizar PDFs e exportar dump .sql",
    },
    "finetune-qlora": {
        "num_gpus": 2,
        "gpu_name": "RTX_3090",
        "default_max_usd": 1.80,
        "label": "finetune-qlora",
        "onstart_note": "QLoRA r=32 NF4 em validated_pairs.jsonl",
    },
    "quantize": {
        "num_gpus": 1,
        "gpu_name": "RTX_3090",
        "default_max_usd": 0.50,
        "label": "quantize",
        "onstart_note": "exportar YBY-SEED-Coder-7B-IQ4_XS.gguf",
    },
}


@dataclass(frozen=True)
class OfferTCO:
    offer_id: int
    dph_total: float
    storage_cost: float
    inet_down_cost: float
    inet_up_cost: float
    reliability: float
    inet_down: float

    @property
    def tco_hourly(self) -> float:
        return self.dph_total + self.storage_cost + self.inet_down_cost + self.inet_up_cost

    def effective_tco(self) -> float:
        """Penaliza hosts com banda cara ou lenta além do TCO base."""
        bandwidth_penalty = max(0.0, (500.0 - self.inet_down) / 10_000.0)
        return self.tco_hourly + self.inet_down_cost * 0.25 + bandwidth_penalty


def _normalize_offer(raw: dict[str, Any]) -> OfferTCO | None:
    try:
        reliability = float(raw.get("reliability") or raw.get("reliability2") or 0.0)
        inet_down = float(raw.get("inet_down") or 0.0)
        if reliability <= 0.98 or inet_down <= 400:
            return None
        return OfferTCO(
            offer_id=int(raw["id"]),
            dph_total=float(raw.get("dph_total") or raw.get("search", {}).get("dph_total", 0)),
            storage_cost=float(raw.get("storage_cost", 0.0)),
            inet_down_cost=float(raw.get("inet_down_cost", 0.0)),
            inet_up_cost=float(raw.get("inet_up_cost", 0.0)),
            reliability=reliability,
            inet_down=inet_down,
        )
    except (KeyError, TypeError, ValueError):
        return None


def search_top_offers(mission: str, max_usd: float) -> list[OfferTCO]:
    profile = MISSION_PROFILES[mission]
    query = (
        f"gpu_name={profile['gpu_name']} "
        f"num_gpus={profile['num_gpus']} "
        "rentable=true verified=true "
        "reliability>0.98 inet_down>400"
    )
    settings = get_settings()
    try:
        from vastai import VastAI
    except ImportError:
        logger.warning("vastai não instalado; ofertas vazias")
        return []

    client = VastAI(api_key=settings.vast_api_key or None)
    try:
        raw_offers = client.search_offers(query=query, order="dph_total", limit=20)
    except Exception as exc:  # noqa: BLE001
        logger.warning("falha ao buscar ofertas vast: %s", exc)
        return []

    offers: list[OfferTCO] = []
    for raw in raw_offers or []:
        offer = _normalize_offer(raw)
        if offer is None:
            continue
        if offer.effective_tco() <= max_usd:
            offers.append(offer)
    offers.sort(key=lambda item: item.effective_tco())
    return offers[:3]


def _verify_vast_budget(client: Any, max_usd: float) -> tuple[bool, str]:
    try:
        info = client.show_user()
        credit = float(info.get("credit") or info.get("balance") or 0.0)
        if credit < max_usd:
            return False, f"saldo Vast insuficiente: ${credit:.2f} < teto horário ${max_usd:.2f}"
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("show_user falhou: %s", exc)
        return False, f"falha ao consultar saldo Vast: {exc}"


def build_onstart_script(mission: str, *, bundle_path: str, entrypoint: str) -> str:
    profile = MISSION_PROFILES[mission]
    models_dir = "./data/models"
    return f"""#!/bin/bash
set -euo pipefail
CONTAINER_ID="${{VAST_CONTAINER_ID:-$CONTAINER_ID}}"
CONTAINER_API_KEY="${{VAST_API_KEY:-$CONTAINER_API_KEY}}"
trap 'vastai destroy instance "$CONTAINER_ID" --api-key "$CONTAINER_API_KEY" || true' EXIT
timeout 7200 bash -lc '
  echo "[yby-forge] missão {profile["label"]}: {profile["onstart_note"]}"
  tailscale up --auth-key="${{TS_EPHEMERAL_KEY:-}}" --reset --accept-routes=false || true
  mkdir -p /workspace/input /workspace/output {models_dir}
  scp -o StrictHostKeyChecking=no "${{YBY_FORGE_BUNDLE_SRC:-{bundle_path}}}" /workspace/input/yby-forge-bundle.tar.zst
  tar --zstd -xf /workspace/input/yby-forge-bundle.tar.zst -C /workspace/input || \\
    tar -xzf /workspace/input/yby-forge-bundle.tar.zst -C /workspace/input
  cd /workspace/input
  {entrypoint}
  scp -o StrictHostKeyChecking=no /workspace/output/* "${{YBY_SCP_TARGET:-user@tailscale-ip}}:{models_dir}/" || true
'
"""


def _provision_offer(client: Any, offer: OfferTCO, onstart: str, mission: str) -> dict[str, Any]:
    return client.create_instance(
        id=offer.offer_id,
        image="pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
        disk=40,
        onstart_cmd=onstart,
        ssh=True,
        direct=True,
        label=f"yby-{mission}",
    )


def run_mission(
    mission: str,
    *,
    max_usd: float,
    dry_run: bool,
    min_samples: int = 20,
    dataset_path: Path | None = None,
) -> dict[str, Any]:
    if mission == "finetune-qlora":
        settings = get_settings()
        jsonl_path = dataset_path if dataset_path is not None else settings.datasets_path
        report = preflight_dataset(jsonl_path, min_samples=min_samples)
        if not report.ok:
            return {
                "mission": mission,
                "max_usd_hour": max_usd,
                "dry_run": dry_run,
                "status": "aborted_preflight_dataset",
                "dataset_path": str(jsonl_path),
                "valid_count": report.valid_count,
                "min_samples": report.min_samples,
                "preflight_errors": report.summary_errors(),
            }

    offers = search_top_offers(mission, max_usd)
    bundle_path = build_mission_bundle(mission)
    entrypoint = MISSION_ENTRYPOINTS[mission]["command"]
    onstart = build_onstart_script(mission, bundle_path=str(bundle_path), entrypoint=entrypoint)
    plan: dict[str, Any] = {
        "mission": mission,
        "max_usd_hour": max_usd,
        "dry_run": dry_run,
        "offers": [
            {
                "offer_id": offer.offer_id,
                "tco_hourly": round(offer.tco_hourly, 4),
                "effective_tco": round(offer.effective_tco(), 4),
                "reliability": offer.reliability,
                "inet_down_mbps": offer.inet_down,
            }
            for offer in offers
        ],
        "bundle_path": str(bundle_path),
        "onstart_preview": onstart[:400] + ("..." if len(onstart) > 400 else ""),
    }

    if not offers:
        plan["status"] = "aborted_no_offers_within_tco"
        return plan

    if dry_run:
        plan["status"] = "dry_run_ok"
        return plan

    settings = get_settings()
    try:
        from vastai import VastAI
    except ImportError as exc:
        raise RuntimeError("instale vastai: uv sync --extra forge") from exc

    client = VastAI(api_key=settings.vast_api_key or None)
    budget_ok, budget_reason = _verify_vast_budget(client, max_usd)
    if not budget_ok:
        plan["status"] = "aborted_budget"
        plan["budget_reason"] = budget_reason
        return plan

    errors: list[str] = []
    for offer in offers:
        try:
            result = _provision_offer(client, offer, onstart, mission)
            plan["instance"] = result
            plan["chosen_offer_id"] = offer.offer_id
            plan["status"] = "provisioned"
            return plan
        except Exception as exc:  # noqa: BLE001
            logger.warning("falha ao provisionar offer %s: %s", offer.offer_id, exc)
            errors.append(f"{offer.offer_id}: {exc}")

    plan["status"] = "aborted_provision_failed"
    plan["errors"] = errors
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YBY SEED — Vast.ai router")
    parser.add_argument(
        "mission",
        choices=list(MISSION_PROFILES),
        nargs="?",
        default="rag-embed",
    )
    parser.add_argument("--max-usd", type=float, default=None, help="Teto horário TCO (USD)")
    parser.add_argument("--dry-run", action="store_true", help="Simula custos sem criar instância")
    parser.add_argument(
        "--min-samples",
        type=int,
        default=20,
        help="Mínimo de amostras válidas (finetune-qlora)",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Dataset ChatML (finetune-qlora; padrão: data/datasets/validated_pairs.jsonl)",
    )
    args = parser.parse_args(argv)

    profile = MISSION_PROFILES[args.mission]
    max_usd = args.max_usd if args.max_usd is not None else profile["default_max_usd"]

    try:
        plan = run_mission(
            args.mission,
            max_usd=max_usd,
            dry_run=args.dry_run,
            min_samples=args.min_samples,
            dataset_path=args.jsonl,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
