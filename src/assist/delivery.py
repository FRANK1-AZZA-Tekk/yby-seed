"""Entrega em segundo plano dos lembretes — único responsável por notificar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.assist.reminders import Clock, ReminderStore, SystemClock, effective_delivery
from src.sentinel.config import QuietHours
from src.sentinel.notify import DesktopNotifier, Notifier
from src.sentinel.quiet import in_quiet_hours


@dataclass
class DeliveryResult:
    notified: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def deliver_due(
    store: ReminderStore,
    *,
    clock: Clock | None = None,
    notifier: Notifier | None = None,
    quiet_hours: QuietHours | None = None,
) -> DeliveryResult:
    """Verifica vencidos e notifica. Só marca `delivered` se notify retornar True.

    Grava `pending` antes de notificar. Se o processo cair depois do notify
    verdadeiro e antes do save de `delivered`, o registro fica `pending` e a
    passagem seguinte pode avisar de novo (pelo menos uma vez).
    """

    clk = clock or SystemClock()
    note = notifier or DesktopNotifier()
    now = clk.now()
    result = DeliveryResult()

    for rem in store.due_undelivered(now):
        state = effective_delivery(rem, now)
        if state == "delivered":
            result.skipped.append(rem.id)
            continue

        if in_quiet_hours(now, quiet_hours):
            store.mark_pending(rem.id)
            result.pending.append(rem.id)
            result.notes.append(f"horário silencioso — pendente {rem.id}")
            continue

        # Marca pending antes de tentar (desktop ausente / crash → não entregue)
        store.mark_pending(rem.id)

        title = "YBY Lembrete"
        message = f"{rem.text} (previsto {rem.when_iso}, tz={rem.tz})"
        ok = note.notify(title, message)
        if ok:
            store.mark_delivered(rem.id)
            result.notified.append(rem.id)
            result.notes.append(f"notificado {rem.id}")
        else:
            result.pending.append(rem.id)
            result.notes.append(
                f"desktop indisponível — não marco entregue ({rem.id})"
            )

    return result


def format_when_detail(delivery: str, when_iso: str, now: datetime) -> str:
    if delivery == "delivered":
        return "entregue"
    if delivery == "pending":
        return f"entrega pendente (venceu {when_iso})"
    return f"vence em {when_iso}"
