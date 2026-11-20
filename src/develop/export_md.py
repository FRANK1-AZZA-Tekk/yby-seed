"""Exporta uma camada para Markdown revisável (só contexto necessário)."""

from __future__ import annotations

from pathlib import Path

from src.develop.schemas import DevelopPlan, Layer
from src.develop.store import exports_dir


def render_layer_markdown(plan: DevelopPlan, layer: Layer) -> str:
    lines = [
        f"# Develop {plan.id} / {layer.id}",
        "",
        f"**Status:** `{layer.status}`",
        f"**Pedido:** {plan.pedido}",
        f"**base_commit:** `{plan.base_commit}`",
        f"**depends_on:** {', '.join(layer.depends_on) or '(nenhuma)'}",
        "",
        "## Objetivo",
        layer.objetivo,
        "",
        "## Arquivos candidatos",
    ]
    if layer.allowed_files:
        lines.extend(f"- `{p}`" for p in layer.allowed_files)
    else:
        lines.append("- (nenhum)")
    lines.extend(["", "## Não-objetivos (restrições)"])
    if layer.non_goals:
        lines.extend(f"- {x}" for x in layer.non_goals)
    else:
        lines.append("- (nenhum)")
    lines.extend(["", "## Critérios de aceite"])
    if layer.acceptance:
        lines.extend(f"- {x}" for x in layer.acceptance)
    else:
        lines.append("- (nenhum)")
    lines.extend(["", "## Verificações"])
    if layer.verification:
        lines.extend(f"- {x}" for x in layer.verification)
    else:
        lines.append("- (nenhuma)")
    if layer.optional_patch:
        lines.extend(
            [
                "",
                "## optional_patch (texto — NÃO aplicar automaticamente)",
                "```",
                layer.optional_patch,
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "---",
            "Envie este pacote ao Cursor CLI só após revisão humana. "
            "Exit code 0 do Cursor **não** significa camada aceita.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_layer(
    plan: DevelopPlan,
    layer_id: str,
    *,
    root: Path | None = None,
) -> Path:
    layer = plan.layer(layer_id)
    if layer is None:
        raise KeyError(f"camada inexistente: {layer_id}")
    out_dir = exports_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{plan.id}__{layer_id}.md"
    path.write_text(render_layer_markdown(plan, layer), encoding="utf-8")
    return path
