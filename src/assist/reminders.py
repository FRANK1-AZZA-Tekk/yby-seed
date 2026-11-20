"""Lembretes locais do assist (só entregues com sessão aberta)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Reminder:
    id: str
    text: str
    when_iso: str  # UTC ISO
    tz: str
    delivered: bool = False


class ReminderStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Reminder]:
        if not self.path.is_file():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        out: list[Reminder] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                out.append(
                    Reminder(
                        id=str(item["id"]),
                        text=str(item["text"]),
                        when_iso=str(item["when_iso"]),
                        tz=str(item.get("tz") or "UTC"),
                        delivered=bool(item.get("delivered")),
                    )
                )
            except KeyError:
                continue
        return out

    def save(self, reminders: list[Reminder]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": r.id,
                "text": r.text,
                "when_iso": r.when_iso,
                "tz": r.tz,
                "delivered": r.delivered,
            }
            for r in reminders
        ]
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def add(self, reminder: Reminder) -> None:
        items = self.load()
        items.append(reminder)
        self.save(items)

    def mark_delivered(self, reminder_id: str) -> None:
        items = self.load()
        updated = [
            Reminder(r.id, r.text, r.when_iso, r.tz, True)
            if r.id == reminder_id
            else r
            for r in items
        ]
        self.save(updated)

    def due_undelivered(self, now: datetime) -> list[Reminder]:
        due: list[Reminder] = []
        for r in self.load():
            if r.delivered:
                continue
            try:
                when = datetime.fromisoformat(r.when_iso)
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when <= now:
                due.append(r)
        return due


def build_reminder(
    *,
    text: str,
    date: str,
    time: str,
    tz: str,
    new_id: Callable[[], str] | None = None,
) -> Reminder:
    """Monta lembrete; when armazenado em UTC a partir de date+time locais simplificados.

    MVP: interpreta date/time como UTC se tz for UTC; caso contrário grava
    o instante como `date`T`time`:00+00:00 documentado na prévia (tz label).
    """

    stamp = f"{date.strip()}T{time.strip()}:00+00:00"
    # Normaliza HH:MM → HH:MM:00 already; allow HH:MM
    if len(time.strip()) == 5:
        stamp = f"{date.strip()}T{time.strip()}:00+00:00"
    datetime.fromisoformat(stamp)  # validate
    return Reminder(
        id=(new_id or (lambda: uuid.uuid4().hex[:12]))(),
        text=text.strip(),
        when_iso=stamp,
        tz=tz.strip() or "UTC",
        delivered=False,
    )
