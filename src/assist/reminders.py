"""Lembretes locais do assist — cadastro aqui; entrega só pelo processo agendado."""

from __future__ import annotations

import fcntl
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Literal, Protocol

DeliveryState = Literal["scheduled", "pending", "delivered"]


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
    delivery: DeliveryState = "scheduled"

    @property
    def delivered(self) -> bool:
        return self.delivery == "delivered"


def parse_when(when_iso: str) -> datetime | None:
    try:
        when = datetime.fromisoformat(when_iso)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when


def effective_delivery(reminder: Reminder, now: datetime) -> DeliveryState:
    """Resolve estado legível: legado sem `delivery` usa `when_iso` + delivered."""

    if reminder.delivery == "delivered" or reminder.delivered:
        return "delivered"
    if reminder.delivery == "pending":
        return "pending"
    when = parse_when(reminder.when_iso)
    if when is None:
        return "scheduled"
    if when <= now:
        return "pending"
    return "scheduled"


class ReminderStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with open(lock_path, "a+", encoding="utf-8") as lockf:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

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
                out.append(_from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def save(self, reminders: list[Reminder]) -> None:
        with self._lock():
            self._save_unlocked(reminders)

    def _save_unlocked(self, reminders: list[Reminder]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [_to_dict(r) for r in reminders]
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def add(self, reminder: Reminder) -> None:
        with self._lock():
            items = self.load()
            items.append(reminder)
            self._save_unlocked(items)

    def update(self, reminder_id: str, *, delivery: DeliveryState) -> Reminder | None:
        """Atualiza delivery sob lock. Devolve o lembrete novo ou None."""

        with self._lock():
            items = self.load()
            updated: list[Reminder] = []
            found: Reminder | None = None
            for r in items:
                if r.id == reminder_id:
                    found = Reminder(r.id, r.text, r.when_iso, r.tz, delivery)
                    updated.append(found)
                else:
                    updated.append(r)
            if found is None:
                return None
            self._save_unlocked(updated)
            return found

    def mark_delivered(self, reminder_id: str) -> None:
        self.update(reminder_id, delivery="delivered")

    def mark_pending(self, reminder_id: str) -> None:
        self.update(reminder_id, delivery="pending")

    def due_undelivered(self, now: datetime) -> list[Reminder]:
        due: list[Reminder] = []
        for r in self.load():
            if effective_delivery(r, now) == "delivered":
                continue
            when = parse_when(r.when_iso)
            if when is None:
                continue
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
    if len(time.strip()) == 5:
        stamp = f"{date.strip()}T{time.strip()}:00+00:00"
    datetime.fromisoformat(stamp)  # validate
    return Reminder(
        id=(new_id or (lambda: uuid.uuid4().hex[:12]))(),
        text=text.strip(),
        when_iso=stamp,
        tz=tz.strip() or "UTC",
        delivery="scheduled",
    )


def _from_dict(item: dict) -> Reminder:
    delivery_raw = item.get("delivery")
    if delivery_raw in {"scheduled", "pending", "delivered"}:
        delivery: DeliveryState = delivery_raw  # type: ignore[assignment]
    elif bool(item.get("delivered")):
        delivery = "delivered"
    else:
        delivery = "scheduled"
    return Reminder(
        id=str(item["id"]),
        text=str(item["text"]),
        when_iso=str(item["when_iso"]),
        tz=str(item.get("tz") or "UTC"),
        delivery=delivery,
    )


def _to_dict(r: Reminder) -> dict:
    return {
        "id": r.id,
        "text": r.text,
        "when_iso": r.when_iso,
        "tz": r.tz,
        "delivery": r.delivery,
        "delivered": r.delivered,
    }
