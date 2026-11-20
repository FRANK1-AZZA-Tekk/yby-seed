"""Sessão conversacional do assist (anáfora + confirmação)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.assist.config import AssistConfig
from src.assist.executor import ConfirmFn, execute_proposal
from src.assist.reminders import Clock, ReminderStore
from src.assist.router import AssistPlanner, resolve_turn_proposal
from src.assist.tools import Launcher
from src.assist.types import ToolProposal, TurnOutcome
from src.engine.providers import ProviderError
from src.memory.vault import Vault

_ORDINAL = {
    "primeiro": 0,
    "1": 0,
    "segundo": 1,
    "2": 1,
    "terceiro": 2,
    "3": 2,
    "quarto": 3,
    "4": 3,
    "quinto": 4,
    "5": 4,
}
_SELECT_RE = re.compile(
    r"^\s*(?:o|a|opção|opcao)?\s*"
    r"(primeiro|segundo|terceiro|quarto|quinto|[1-5])\s*$",
    re.IGNORECASE,
)


@dataclass
class AssistSession:
    config: AssistConfig
    planner: AssistPlanner | None = None
    confirm_fn: ConfirmFn | None = None
    launcher: Launcher | None = None
    vault: Vault | None = None
    reminder_store: ReminderStore | None = None
    clock: Clock | None = None
    file_candidates: list[dict[str, str]] = field(default_factory=list)
    pending_reminder: dict[str, Any] | None = None

    def startup_messages(self) -> list[str]:
        """Assist só cadastra; a entrega fica em `yby reminders once`."""

        return []

    def help_text(self) -> str:
        apps = ", ".join(self.config.app_names()) or "(nenhum)"
        routines = ", ".join(self.config.routine_ids()) or "(nenhuma)"
        return (
            "YBY assist — sessão local (sem nuvem).\n"
            "Comandos: ajuda | cancela | sair\n"
            f"Apps: {apps}\n"
            f"Rotinas (alias exato): {routines}\n"
            "Lembretes: o assist só cadastra; a entrega é "
            "`python yby.py reminders once` (timer opcional).\n"
            "Busca de arquivos: candidatos listados; diga 'o segundo' para "
            "selecionar (não abre o arquivo).\n"
            "Voz: `python yby.py assist --voice` (pressionar para falar)."
        )

    def handle(self, utterance: str) -> TurnOutcome:
        text = utterance.strip()
        if not text:
            return TurnOutcome(None, None, None, "Diga um pedido ou 'ajuda'.")

        low = text.casefold()
        if low in {"ajuda", "help", "?"}:
            return TurnOutcome(None, None, None, self.help_text())
        if low in {"cancela", "cancelar", "cancel"}:
            self.pending_reminder = None
            return TurnOutcome(
                None,
                None,
                None,
                "Ação pendente descartada (cancela).",
            )
        if low in {"sair", "exit", "quit"}:
            return TurnOutcome(None, None, None, "__EXIT__")

        # Anáfora: seleção entre candidatos de files.find
        select = _SELECT_RE.match(text)
        if select:
            return self._select_candidate(select.group(1).casefold())

        # Correção de lembrete pendente via nova proposta reminder — handled below

        try:
            proposal = resolve_turn_proposal(
                self.config,
                text,
                self.planner,
                context=self._context_blurb(),
            )
        except ProviderError as exc:
            return TurnOutcome(
                None,
                None,
                None,
                f"Ollama/planner falhou ({exc}). Sem fallback para nuvem.",
            )
        except (ValueError, KeyError) as exc:
            return TurnOutcome(
                None,
                None,
                None,
                f"Proposta inválida — nada executado ({exc}).",
            )

        # Se havia lembrete pendente e veio outro reminder, invalida o anterior
        if proposal.tool == "reminder.create" and self.pending_reminder is not None:
            self.pending_reminder = None

        def _set_pending(data: dict[str, Any] | None) -> None:
            self.pending_reminder = data

        try:
            decision, result = execute_proposal(
                self.config,
                proposal,
                confirm_fn=self.confirm_fn,
                launcher=self.launcher,
                vault=self.vault,
                reminder_store=self.reminder_store
                or ReminderStore(self.config.reminders_path),
                clock=self.clock,
                set_pending_reminder=_set_pending,
            )
        except Exception as exc:  # noqa: BLE001 — isola falha de tool
            return TurnOutcome(
                proposal,
                None,
                None,
                f"Erro na execução (proposta não vira sucesso): {exc}",
            )

        if (
            result.ok
            and result.tool == "files.find"
            and isinstance(result.data.get("hits"), list)
        ):
            self.file_candidates = list(result.data["hits"])

        msg = self._format_outcome(proposal, decision, result)
        return TurnOutcome(proposal, decision, result, msg)

    def _select_candidate(self, token: str) -> TurnOutcome:
        if not self.file_candidates:
            return TurnOutcome(
                None,
                None,
                None,
                "Não há lista de arquivos para selecionar. Faça uma busca antes.",
            )
        idx = _ORDINAL.get(token)
        if idx is None or idx < 0 or idx >= len(self.file_candidates):
            return TurnOutcome(
                None,
                None,
                None,
                f"Referência ambígua. Escolha entre 1 e {len(self.file_candidates)}.",
            )
        chosen = self.file_candidates[idx]
        proposal = ToolProposal(
            tool="files.find",
            args={"query": "(seleção)", "limit": 1},
            source="session",
        )
        # Seleção ≠ abrir
        narration = (
            f"Selecionei o item {idx + 1}: {chosen.get('name')} "
            f"({chosen.get('path')}). Não abri o arquivo."
        )
        from src.assist.types import PolicyDecision, ToolResult

        decision = PolicyDecision("allow", "seleção de candidato em sessão")
        result = ToolResult(
            ok=True,
            tool="files.find",
            data={"selected": chosen, "hits": [chosen], "need_choice": False},
            narration=narration,
        )
        return TurnOutcome(proposal, decision, result, self._format_outcome(proposal, decision, result))

    def _context_blurb(self) -> str:
        parts = []
        if self.file_candidates:
            parts.append(f"candidatos_arquivos={len(self.file_candidates)}")
        if self.pending_reminder:
            parts.append("lembrete_pendente=sim")
        return "; ".join(parts) or "(vazio)"

    def _format_outcome(self, proposal, decision, result) -> str:
        lines = [
            f"[proposta:{proposal.source}] {proposal.tool} {proposal.args}",
            f"[política] {decision.action}: {decision.reason}",
            f"[resultado] {result.narration}",
        ]
        return "\n".join(lines)
