"""Formata respostas do CLI em blocos claros (PT-BR). Não altera execução."""

from __future__ import annotations

from dataclasses import dataclass

from src.engine.secret_gate import redact_for_cloud
from src.safety.policy import Decision

_VAGUE = frozenset(
    {
        "oi",
        "olá",
        "ola",
        "hey",
        "ajuda",
        "help",
        "?",
        "o que",
        "oque",
        "faz",
        "como",
    }
)

# Atrito confirmado (SEED): ask não abre brief — orientar criação manual.
_CREATION_HINTS = (
    "cria ",
    "criar ",
    "crie ",
    "monte ",
    "montar ",
    "gere ",
    "gerar ",
    "scaffold",
    "projeto",
    "aplicativo",
    " app",
    "ferramenta",
    "cli ",
)


@dataclass(frozen=True)
class ExplainBlocks:
    """Seções do modo professor."""

    understood: str
    missing: str
    proposal: str
    risk: str
    next_step: str
    revert: str
    questions: tuple[str, ...] = ()


def is_vague_request(text: str) -> bool:
    """Pedido curto demais para agir sem esclarecimento."""

    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return True
    if len(cleaned) < 8 and cleaned.casefold() in _VAGUE:
        return True
    if len(cleaned) <= 3:
        return True
    return False


def looks_like_creation_request(text: str) -> bool:
    """Heurística leve: pedido parece querer artefato/projeto (não muda D10)."""

    cleaned = f" {' '.join(text.strip().casefold().split())} "
    return any(hint in cleaned for hint in _CREATION_HINTS)


def clarify_questions(text: str) -> tuple[str, ...]:
    """Até três perguntas curtas; só o necessário."""

    if not is_vague_request(text):
        return ()
    return (
        "O que você quer fazer agora: perguntar, decidir um comando ou gravar uma nota?",
        "Há alguma restrição (só local, sem nuvem, sem alterar arquivos)?",
        "Como você saberia que deu certo?",
    )


def format_blocks(blocks: ExplainBlocks) -> str:
    """Monta o envelope; redige segredos na exibição."""

    lines = [
        f"Entendi: {_safe(blocks.understood)}",
        f"Falta: {_safe(blocks.missing)}",
        f"Proposta: {_safe(blocks.proposal)}",
        f"Risco: {_safe(blocks.risk)}",
        f"Próximo passo: {_safe(blocks.next_step)}",
        f"Como reverter: {_safe(blocks.revert)}",
    ]
    if blocks.questions:
        lines.append("Perguntas:")
        for index, question in enumerate(blocks.questions[:3], start=1):
            lines.append(f"  {index}. {_safe(question)}")
    return "\n".join(lines)


def format_engine_reply(
    *,
    prompt: str,
    text: str,
    provider: str,
    model: str,
    reasons: tuple[str, ...],
    notice: str | None,
) -> str:
    """Envelope para `yby ask --explain` (após resposta do motor)."""

    motivo = "; ".join(reasons) if reasons else "roteamento padrão"
    missing = "nada crítico" if text.strip() else "uma resposta utilizável do modelo"
    if notice:
        missing = f"{missing}; aviso: {notice}"
        lowered = notice.casefold()
        if "ollama" in lowered and (
            "cloud_api_key" in lowered or "local_only" in lowered or "nuvem" in lowered
        ):
            missing = (
                f"{missing} | dica: suba o Ollama local ou, se quiser nuvem, "
                "YBY_CLOUD_MODE=ask e YBY_CLOUD_API_KEY no .env"
            )
    risk = (
        "a nuvem pode receber trechos do pedido (já filtrados por política de segredos)"
        if provider in {"cloud", "openrouter", "cache"}
        else "resposta local pode estar incompleta ou imprecisa"
    )
    if looks_like_creation_request(prompt):
        next_step = (
            "para criar com trilha controlada: "
            f'`yby brief start "{prompt.strip()}"` → plan → scaffold '
            "(ask não abre brief sozinho)"
        )
    else:
        next_step = (
            "se quiser executar um comando no terminal, use `yby gate \"...\"` "
            "antes de `yby run` (gate = só decide; run = executa se permitido)"
        )
    blocks = ExplainBlocks(
        understood=f"você pediu: {prompt.strip()}",
        missing=missing,
        proposal=text.strip() or "(sem texto)",
        risk=risk,
        next_step=next_step,
        revert="nada foi alterado no disco por este `ask`; ignore a resposta se não servir",
        questions=(),
    )
    header = f"modelo: {provider} {model} ({motivo})"
    return f"{header}\n{format_blocks(blocks)}"


def format_vague_ask(prompt: str) -> str:
    """Pedido vago: esclarece sem chamar o motor."""

    questions = clarify_questions(prompt)
    blocks = ExplainBlocks(
        understood="o pedido está curto ou genérico demais para uma ação útil",
        missing="objetivo concreto, restrições e critério de sucesso",
        proposal="responder só depois do esclarecimento (nenhuma chamada ao modelo)",
        risk="inferir demais pode gerar ação ou conselho inadequado",
        next_step='responda às perguntas abaixo e rode de novo: yby ask --explain "..."',
        revert="nada foi executado nem enviado à nuvem",
        questions=questions,
    )
    return format_blocks(blocks)


def format_cli_error(*, kind: str, detail: str, next_step: str) -> str:
    """Erros comuns (vault, nuvem cancelada) no mesmo envelope."""

    blocks = ExplainBlocks(
        understood=f"falha: {kind}",
        missing="concluir a operação pedida",
        proposal=detail,
        risk="repetir o mesmo comando sem corrigir a causa tende a falhar de novo",
        next_step=next_step,
        revert="nada foi alterado além do que a mensagem descreve",
    )
    return format_blocks(blocks)


def format_command_decision(command: str, decision: Decision) -> str:
    """Explica run/ask/refuse sem executar."""

    action = decision.action
    if action == "run":
        proposal = "o comando está na allowlist de inspeção e poderia rodar sem pergunta"
        risk = "ainda assim pode ler arquivos locais sensíveis (paths não são sandboxed)"
        next_step = f'para executar de fato: yby run "{command}"'
        revert = "gate não executa; se já rodou, desfaça manualmente o efeito do comando"
        missing = "nada — classificação concluída"
    elif action == "refuse":
        proposal = "não executar; o comando casa com padrão destrutivo ou regra estrutural"
        risk = "forçar a execução fora do YBY ignora esta porta"
        next_step = "reformule o comando ou use uma alternativa de leitura"
        revert = "nada foi executado"
        missing = "um comando seguro equivalente, se ainda precisar do efeito"
    else:
        proposal = "pedir confirmação sim/não antes de qualquer subprocesso"
        risk = "confirmar sem entender o comando pode alterar o sistema"
        next_step = "responda s/n no gate, ou use yby run (que também pergunta se for ask)"
        revert = "responda n; nada executa"
        missing = "sua confirmação explícita"

    blocks = ExplainBlocks(
        understood=f"comando candidato: {command}",
        missing=missing,
        proposal=f"{action} — {proposal}. Motivo: {decision.reason}",
        risk=risk,
        next_step=next_step,
        revert=revert,
    )
    return f"{action}: {decision.reason}\n{format_blocks(blocks)}"


def _safe(text: str) -> str:
    return redact_for_cloud(text)
