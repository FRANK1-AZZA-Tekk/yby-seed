"""Bloqueio de envio: deps devem estar aceitas."""

from __future__ import annotations

from src.develop.schemas import DevelopPlan


def can_send(plan: DevelopPlan, layer_id: str) -> tuple[bool, str]:
    layer = plan.layer(layer_id)
    if layer is None:
        return False, f"camada inexistente: {layer_id}"
    if layer.status == "rejeitada":
        return False, f"camada {layer_id} está rejeitada"
    if layer.status == "aceita":
        return False, f"camada {layer_id} já aceita"
    missing: list[str] = []
    for dep in layer.depends_on:
        other = plan.layer(dep)
        if other is None:
            missing.append(f"{dep} (ausente)")
        elif other.status != "aceita":
            missing.append(f"{dep} ({other.status})")
    if missing:
        return False, "deps não aceitas: " + ", ".join(missing)
    return True, "ok"
