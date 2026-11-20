"""Entrega de notificação — substituível; sem desktop ≠ entregue."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Protocol


class Notifier(Protocol):
    def notify(self, title: str, message: str) -> bool:
        """True só se a entrega foi confirmada."""


class DesktopNotifier:
    """notify-send no Ubuntu; falha se sem DISPLAY/binário."""

    def notify(self, title: str, message: str) -> bool:
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return False
        binary = shutil.which("notify-send")
        if not binary:
            return False
        try:
            completed = subprocess.run(
                [binary, "--app-name=YBY Sentinela", title, message],
                check=False,
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0


class RecordingNotifier:
    """Testes: registra chamadas; sucesso configurável."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.calls: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> bool:
        self.calls.append((title, message))
        return self.succeed
