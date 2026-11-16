"""Aprendizado diário local (JSONL + relatório; sem auto-merge)."""

from src.learn.daily import (
    DEFAULT_LEARN_LOG_PATH,
    LEARN_KINDS,
    LearnError,
    LearnEntry,
    DailyReport,
    append_entry,
    format_report,
    learn_log_path_from_env,
    read_entries,
    report_for_day,
)

__all__ = [
    "DEFAULT_LEARN_LOG_PATH",
    "LEARN_KINDS",
    "DailyReport",
    "LearnEntry",
    "LearnError",
    "append_entry",
    "format_report",
    "learn_log_path_from_env",
    "read_entries",
    "report_for_day",
]
