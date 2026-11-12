"""Empacotamento local de jobs remotos antes do provisionamento Vast."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from src.yby_seed.config import get_settings

REMOTE_JOBS = Path(__file__).resolve().parent / "remote_jobs"
FORGE_ROOT = Path("data/forge")
BUNDLE_DIR = FORGE_ROOT / "bundles"
STAGING_DIR = FORGE_ROOT / "staging"

MISSION_ENTRYPOINTS = {
    "rag-embed": {
        "script": "batch_rag_embed.py",
        "command": (
            "python3 remote_jobs/batch_rag_embed.py "
            "--pdf-dir /workspace/input/pdfs "
            "--output /workspace/output/yby_knowledge_dump.sql"
        ),
        "extra_dirs": [("docs", "pdfs")],
    },
    "finetune-qlora": {
        "script": "train_yby_qlora.py",
        "command": (
            "accelerate launch --num_processes 2 --multi_gpu remote_jobs/train_yby_qlora.py "
            "--dataset /workspace/input/validated_pairs.jsonl "
            "--bundle-out /workspace/output/yby-seed-adapter.tar.zst"
        ),
        "extra_files": [("data/datasets/validated_pairs.jsonl", "validated_pairs.jsonl")],
    },
    "quantize": {
        "script": "merge_and_quantize.sh",
        "command": "bash remote_jobs/merge_and_quantize.sh",
        "extra_dirs": [],
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_remote_jobs(staging: Path) -> None:
    target = staging / "remote_jobs"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(REMOTE_JOBS, target)
    for script in target.glob("*.sh"):
        script.chmod(script.stat().st_mode | 0o111)


def build_mission_bundle(mission: str) -> Path:
    """Gera tar.zst com scripts + dataset/ativos locais."""
    if mission not in MISSION_ENTRYPOINTS:
        raise ValueError(f"missão desconhecida: {mission}")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    staging = STAGING_DIR / f"{mission}-{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    _copy_remote_jobs(staging)
    manifest: dict[str, str | list[str]] = {
        "mission": mission,
        "created_at": stamp,
        "entrypoint": MISSION_ENTRYPOINTS[mission]["command"],
        "assets": [],
    }

    settings = get_settings()
    for src_rel, dst_name in MISSION_ENTRYPOINTS[mission].get("extra_files", []):
        src = Path(src_rel)
        if not src.is_file():
            src = settings.datasets_path
        if src.is_file():
            shutil.copy2(src, staging / dst_name)
            manifest["assets"].append(dst_name)

    for src_rel, dst_sub in MISSION_ENTRYPOINTS[mission].get("extra_dirs", []):
        src = Path(src_rel)
        if src.is_dir():
            dst = staging / dst_sub
            dst.mkdir(parents=True, exist_ok=True)
            for pdf in src.rglob("*.pdf"):
                shutil.copy2(pdf, dst / pdf.name)
            manifest["assets"].append(dst_sub)

    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    bundle_path = BUNDLE_DIR / f"yby-forge-{mission}-{stamp}.tar.zst"
    try:
        subprocess.run(
            ["tar", "--zstd", "-cf", str(bundle_path), "-C", str(staging), "."],
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        bundle_path = bundle_path.with_suffix(".tar.gz")
        subprocess.run(
            ["tar", "-czf", str(bundle_path), "-C", str(staging), "."],
            check=True,
        )

    manifest["bundle_path"] = str(bundle_path)
    manifest["bundle_sha256"] = _sha256(bundle_path)
    (BUNDLE_DIR / f"{mission}-{stamp}.manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    shutil.rmtree(staging, ignore_errors=True)
    return bundle_path