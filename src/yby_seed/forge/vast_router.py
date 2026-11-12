"""Roteamento de missões GPU na Vast.ai (TCO + dry-run)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

from src.yby_seed.config import get_settings
from src.yby_seed.forge.packaging import build_mission_bundle

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
        return []

    client = VastAI(api_key=settings.vast_api_key or None)
    try:
        raw_offers = client.search_offers(query=query, order="dph_total", limit=20)
    except Exception:
        return []
    offers: list[OfferTCO] = []
    for raw in raw_offers or []:
        offer = _normalize_offer(raw)
        if offer is None:
            continue
        if offer.tco_hourly <= max_usd:
            offers.append(offer)
    offers.sort(key=lambda item: item.tco_hourly)
    return offers[:3]


def build_onstart_script(mission: str, *, bundle_path: str, entrypoint: str) -> str:
    profile = MISSION_PROFILES[mission]
    models_dir = "./data/models"
    return f"""#!/bin/bash
set -euo pipefail
CONTAINER_ID="${{VAST_CONTAINER_ID:-$CONTAINER_ID}}"
CONTAINER_API_KEY="${{VAST_API_KEY:-$CONTAINER_API_KEY}}"
trap 'vastai destroy instance "$CONTAINER_ID" --api-key "$CONTAINER_API_KEY"' EXIT
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


def run_mission(
    mission: str,
    *,
    max_usd: float,
    dry_run: bool,
) -> dict[str, Any]:
    offers = search_top_offers(mission, max_usd)
    bundle_path = build_mission_bundle(mission)
    from src.yby_seed.forge.packaging import MISSION_ENTRYPOINTS

    entrypoint = MISSION_ENTRYPOINTS[mission]["command"]
    onstart = build_onstart_script(mission, bundle_path=str(bundle_path), entrypoint=entrypoint)
    plan = {
        "mission": mission,
        "max_usd_hour": max_usd,
        "dry_run": dry_run,
        "offers": [
            {
                "offer_id": offer.offer_id,
                "tco_hourly": round(offer.tco_hourly, 4),
                "reliability": offer.reliability,
                "inet_down_mbps": offer.inet_down,
            }
            for offer in offers
        ],
        "bundle_path": str(bundle_path),
        "onstart_preview": onstart[:400] + ("..." if len(onstart) > 400 else ""),
    }
    if dry_run or not offers:
        return plan

    settings = get_settings()
    try:
        from vastai import VastAI
    except ImportError as exc:
        raise RuntimeError("instale vastai: uv sync --extra forge") from exc

    client = VastAI(api_key=settings.vast_api_key or None)
    chosen = offers[0]
    result = client.create_instance(
        id=chosen.offer_id,
        image="pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
        disk=40,
        onstart_cmd=onstart,
        ssh=True,
        direct=True,
        label=f"yby-{mission}",
    )
    plan["instance"] = result
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
    args = parser.parse_args(argv)

    profile = MISSION_PROFILES[args.mission]
    max_usd = args.max_usd if args.max_usd is not None else profile["default_max_usd"]

    try:
        plan = run_mission(args.mission, max_usd=max_usd, dry_run=args.dry_run)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
