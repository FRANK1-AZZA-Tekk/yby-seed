"""Backup local do vault e logs redigidos (sem nuvem)."""

from src.backup.local import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_KEEP,
    BackupError,
    BackupInfo,
    create_backup,
    list_backups,
    restore_backup,
)

__all__ = [
    "DEFAULT_BACKUP_DIR",
    "DEFAULT_KEEP",
    "BackupError",
    "BackupInfo",
    "create_backup",
    "list_backups",
    "restore_backup",
]
