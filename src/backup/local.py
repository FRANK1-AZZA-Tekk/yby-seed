"""Backup local: tar.gz do vault + logs redigidos; restore sem sobrescrever o vault ativo."""

from __future__ import annotations

import json
import os
import re
import shutil
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from src.engine.cloud_usage_log import DEFAULT_LOG_PATH
from src.engine.secret_gate import redact_for_cloud

DEFAULT_BACKUP_DIR = "backups/yby"
DEFAULT_KEEP = 7
ARCHIVE_PREFIX = "yby-backup-"
ARCHIVE_SUFFIX = ".tar.gz"
_STAMP = re.compile(
    rf"^{re.escape(ARCHIVE_PREFIX)}(\d{{8}}-\d{{6}}){re.escape(ARCHIVE_SUFFIX)}$"
)


class BackupError(ValueError):
    """Falha de backup ou restore local."""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    stamp: str
    size_bytes: int


def create_backup(
    *,
    vault_path: Path,
    backup_dir: Path,
    log_paths: list[Path] | None = None,
    keep: int = DEFAULT_KEEP,
    now: float | None = None,
) -> BackupInfo:
    """Empacota vault + logs redigidos em tar.gz e aplica retenção."""

    if keep < 1:
        raise BackupError("YBY_BACKUP_KEEP deve ser >= 1")
    vault = vault_path.resolve()
    if not vault.is_dir():
        raise BackupError(f"vault inexistente: {vault}")

    dest = backup_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(now if now is not None else time.time()))
    archive = dest / f"{ARCHIVE_PREFIX}{stamp}{ARCHIVE_SUFFIX}"
    if archive.exists():
        raise BackupError(f"arquivo de backup já existe: {archive}")

    logs = list(log_paths) if log_paths is not None else _default_log_paths()

    with tempfile.TemporaryDirectory(prefix="yby-backup-") as tmp:
        root = Path(tmp)
        vault_dst = root / "vault"
        logs_dst = root / "logs"
        vault_dst.mkdir(parents=True)
        logs_dst.mkdir(parents=True)

        _copy_tree(vault, vault_dst)
        included_logs: list[str] = []
        for log_path in logs:
            if not log_path.is_file():
                continue
            name = _safe_log_name(log_path)
            _write_redacted_log(log_path, logs_dst / name)
            included_logs.append(name)

        manifest = {
            "format": "yby-backup-v1",
            "created_utc": stamp,
            "vault_source": str(vault),
            "logs": included_logs,
            "keep": keep,
            "note": "Restore extrai para diretório alvo; não sobrescreve o vault ativo.",
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with tarfile.open(archive, "w:gz") as tar:
            tar.add(root / "manifest.json", arcname="manifest.json")
            tar.add(vault_dst, arcname="vault")
            tar.add(logs_dst, arcname="logs")

    try:
        archive.chmod(0o600)
    except OSError:
        pass

    pruned = _prune(dest, keep=keep)
    if archive.name in pruned:
        raise BackupError("retenção removeu o backup recém-criado; aumente YBY_BACKUP_KEEP")

    return BackupInfo(path=archive, stamp=stamp, size_bytes=archive.stat().st_size)


def list_backups(backup_dir: Path) -> list[BackupInfo]:
    dest = backup_dir.resolve()
    if not dest.is_dir():
        return []
    items: list[BackupInfo] = []
    for path in sorted(dest.iterdir()):
        match = _STAMP.match(path.name)
        if not match or not path.is_file():
            continue
        items.append(
            BackupInfo(path=path, stamp=match.group(1), size_bytes=path.stat().st_size)
        )
    items.sort(key=lambda item: item.stamp, reverse=True)
    return items


def restore_backup(
    archive: Path,
    target_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Extrai o vault do archive para `target_dir`. Recusa sobrescrever conteúdo existente."""

    source = archive.resolve()
    if not source.is_file():
        raise BackupError(f"backup inexistente: {source}")
    if not _STAMP.match(source.name):
        raise BackupError(f"nome de archive inválido: {source.name}")

    target = target_dir.resolve()
    if target.exists():
        if not target.is_dir():
            raise BackupError(f"alvo não é diretório: {target}")
        if any(target.iterdir()) and not force:
            raise BackupError(
                f"alvo não vazio: {target}. Use --force só se quiser misturar/sobrescrever."
            )
    else:
        target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="yby-restore-") as tmp:
        staging = Path(tmp)
        with tarfile.open(source, "r:gz") as tar:
            _safe_extract(tar, staging)
        vault_src = staging / "vault"
        if not vault_src.is_dir():
            raise BackupError("archive sem pasta vault/")
        manifest_path = staging / "manifest.json"
        if not manifest_path.is_file():
            raise BackupError("archive sem manifest.json")
        try:
            json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BackupError("manifest.json inválido") from exc

        for child in vault_src.iterdir():
            dest = target / child.name
            if dest.exists() and not force:
                raise BackupError(f"já existe no alvo: {dest.name}")
            if dest.exists() and force:
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)

    return target


def backup_dir_from_env(environ: dict[str, str] | None = None) -> Path:
    source = environ if environ is not None else os.environ
    raw = source.get("YBY_BACKUP_DIR", DEFAULT_BACKUP_DIR).strip() or DEFAULT_BACKUP_DIR
    return Path(raw)


def keep_from_env(environ: dict[str, str] | None = None) -> int:
    source = environ if environ is not None else os.environ
    raw = source.get("YBY_BACKUP_KEEP", "").strip()
    if not raw:
        return DEFAULT_KEEP
    try:
        value = int(raw)
    except ValueError as exc:
        raise BackupError(f"YBY_BACKUP_KEEP inválido: {raw!r}") from exc
    if value < 1:
        raise BackupError("YBY_BACKUP_KEEP deve ser >= 1")
    return value


def _default_log_paths() -> list[Path]:
    paths = [Path(DEFAULT_LOG_PATH)]
    logs_root = Path("logs")
    if logs_root.is_dir():
        for path in sorted(logs_root.glob("yby_seed_*.log")):
            paths.append(path)
    return paths


def _safe_log_name(path: Path) -> str:
    name = path.name.replace("/", "_").replace("\\", "_")
    if not name or name in {".", ".."}:
        raise BackupError(f"nome de log inválido: {path}")
    return name


def _write_redacted_log(source: Path, dest: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    if source.suffix == ".jsonl":
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                lines.append(redact_for_cloud(stripped))
                continue
            if isinstance(row, dict):
                for key in ("prompt", "api_key", "response", "text", "audio", "Authorization"):
                    row.pop(key, None)
                for key, value in list(row.items()):
                    if isinstance(value, str):
                        row[key] = redact_for_cloud(value)
                lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            else:
                lines.append(redact_for_cloud(stripped))
        dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    else:
        dest.write_text(redact_for_cloud(text), encoding="utf-8")
    try:
        dest.chmod(0o600)
    except OSError:
        pass


def _copy_tree(src: Path, dst: Path) -> None:
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        # ignora sockets/symlinks especiais


def _prune(backup_dir: Path, *, keep: int) -> list[str]:
    archives = list_backups(backup_dir)
    removed: list[str] = []
    for info in archives[keep:]:
        info.path.unlink(missing_ok=True)
        removed.append(info.path.name)
    return removed


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for member in tar.getmembers():
        name = member.name
        if name.startswith("/") or ".." in Path(name).parts:
            raise BackupError(f"entrada de archive insegura: {name}")
        target = (dest / name).resolve()
        try:
            target.relative_to(dest_resolved)
        except ValueError as exc:
            raise BackupError(f"entrada de archive fora do destino: {name}") from exc
        if member.issym() or member.islnk():
            raise BackupError(f"links não permitidos no backup: {name}")
    tar.extractall(dest, filter="data")
