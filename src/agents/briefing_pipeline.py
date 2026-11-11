"""Pipeline MVP de briefing revisável (Fase 1).

Pedido em português → perguntas mínimas → Briefing estruturado → revisão → export.
Nenhuma execução automática de código.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from src.agents.planning_agent import PlanningAgent
from src.core.briefing import BRIEFING_JSON_SCHEMA, Briefing, export_briefing
from src.core.json_extract import extract_json_object
from src.core.ollama_client import OllamaClient, OllamaError

AskFn = Callable[[str], str]
PrintFn = Callable[[str], None]


class BriefingPipeline:
    """Orquestra entrevista mínima + geração estruturada via Ollama local."""

    SYSTEM_PROMPT = (
        "Você é o YBY SEED. Gere briefings claros em português. "
        "Não invente requisitos: se faltar informação, coloque em open_questions. "
        "Function Over Form. Sem execução de código."
    )

    def __init__(
        self,
        ollama: OllamaClient | None = None,
        *,
        model: str | None = None,
        owns_client: bool | None = None,
    ):
        self._owns_client = owns_client if owns_client is not None else ollama is None
        self.ollama = ollama or OllamaClient()
        self.planner = PlanningAgent(self.ollama)
        self.model = model or self.planner.model

    def close(self) -> None:
        if self._owns_client:
            self.ollama.close()

    def create_from_answers(
        self,
        request: str,
        answers: list[str],
        *,
        mode: str = "basic",
    ) -> Briefing:
        """Caminho não-interativo (testável com Ollama mockado).

        Usa PlanningAgent.interview_from_answers e depois estrutura em Briefing.
        """
        request = request.strip()
        if not request:
            raise ValueError("pedido inicial vazio")

        prd_md = self.planner.interview_from_answers(request, answers, mode=mode)
        payload = self._structure_from_prd(request, answers, prd_md, mode=mode)
        return Briefing.model_validate(
            {
                **payload,
                "source_request": request,
                "mode": mode,
                "approved": False,
            }
        )

    def run_interactive(
        self,
        *,
        mode: str = "basic",
        request: str | None = None,
        input_fn: AskFn | None = None,
        print_fn: PrintFn | None = None,
        approve: bool | None = None,
    ) -> Briefing:
        """Fluxo CLI: pede pedido, faz perguntas mínimas, mostra e permite revisão."""
        ask = input_fn or (lambda prompt: input(prompt).strip())
        out = print_fn or print

        initial = (request or "").strip() or ask("Pedido (português): ")
        if not initial:
            raise ValueError("pedido inicial vazio")

        max_q = self.planner.max_questions_for(mode)
        answers: list[str] = []
        conversation: list[dict[str, Any]] = [{"role": "user", "content": initial}]

        first_q = self.planner._generate_first_question(initial)  # noqa: SLF001
        out(f"\n{first_q}\n")
        current_q = first_q

        for i in range(max_q):
            answer = ask("Resposta: ")
            if not answer:
                out("Resposta vazia — registrando como pendência.")
                answers.append("(sem resposta)")
            else:
                answers.append(answer)
            conversation.append({"role": "assistant", "content": current_q})
            conversation.append({"role": "user", "content": answer or "(sem resposta)"})

            if i >= max_q - 1:
                break
            next_q = self.planner._generate_next_question(conversation, mode)  # noqa: SLF001
            if not next_q:
                break
            out(f"\n{next_q}\n")
            current_q = next_q

        # create_from_answers chama interview_from_answers de novo (mais chamadas LLM).
        # Para o caminho interativo, estruturamos direto a partir das respostas já coletadas.
        prd_md = self.planner._generate_prd(conversation, initial)  # noqa: SLF001
        payload = self._structure_from_prd(initial, answers, prd_md, mode=mode)
        briefing = Briefing.model_validate(
            {
                **payload,
                "source_request": initial,
                "mode": mode,
                "approved": False,
            }
        )

        out("\n--- Briefing gerado ---\n")
        out(briefing.model_dump_json(indent=2))
        out("")

        if approve is True:
            briefing.approved = True
        elif approve is False:
            briefing.approved = False
        else:
            decision = ask("Aprovar briefing? [s/N]: ").lower()
            briefing.approved = decision in {"s", "sim", "y", "yes"}
            if not briefing.approved:
                note = ask(
                    "Correção / nota (opcional, entra em perguntas em aberto): "
                )
                if note:
                    briefing.open_questions = [*briefing.open_questions, note]

        return briefing

    def export(
        self,
        briefing: Briefing,
        output_dir: Path | None = None,
        *,
        project_root: Path | None = None,
    ) -> tuple[Path, Path]:
        return export_briefing(briefing, output_dir, project_root=project_root)

    def _structure_from_prd(
        self,
        request: str,
        answers: list[str],
        prd_md: str,
        *,
        mode: str,
    ) -> dict[str, Any]:
        answers_block = "\n".join(
            f"- Resposta {idx + 1}: {ans}" for idx, ans in enumerate(answers)
        ) or "- (nenhuma resposta coletada)"
        prompt = f"""
Pedido do usuário: {request}
Modo: {mode}

Respostas da entrevista:
{answers_block}

PRD / rascunho:
{prd_md}

Gere um briefing JSON com exatamente estas chaves:
title, summary, requirements, assumptions, open_questions, tasks.

Regras:
- Português
- requirements/assumptions/open_questions/tasks = arrays de strings
- Se faltar informação, use open_questions (não invente)
- tasks são passos sugeridos, NÃO código a executar
"""
        try:
            raw = self.ollama.generate(
                model=self.model,
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                format=BRIEFING_JSON_SCHEMA,
                options={"temperature": 0.1, "num_predict": 1024},
            )
        except OllamaError:
            raise

        parsed = extract_json_object(raw)
        if parsed is None:
            # Fallback determinístico: não inventa requisitos; marca ambiguidade
            logger.warning("JSON de briefing inválido; usando fallback mínimo")
            return {
                "title": request[:80],
                "summary": request,
                "requirements": [],
                "assumptions": [],
                "open_questions": [
                    "Modelo não retornou JSON válido; revise o pedido e as respostas."
                ],
                "tasks": ["Revisar briefing manualmente"],
            }
        return parsed
