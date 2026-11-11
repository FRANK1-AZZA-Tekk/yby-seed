"""
Interview Agent — Entrevista em 3 modos (Basic, Junior, Pro)

Usa OllamaClient (mesmo padrão do Router/Planning), não LiteLLM sync.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.core.json_extract import extract_json_object
from src.core.ollama_client import OllamaClient, OllamaError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASIC_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "slots": {"type": "object"},
        "confidence": {"type": "number"},
    },
    "required": ["intent", "slots", "confidence"],
}


class InterviewAgent:
    """Agente de entrevista em 3 modos."""

    def __init__(
        self,
        ollama: OllamaClient | None = None,
        model: str = "llama3.2:3b-instruct-q4_K_M",
    ):
        self.ollama = ollama or OllamaClient()
        self.model = model
        self._owns_client = ollama is None

    async def interview(
        self,
        user_input: str,
        mode: str = "basic",
        answers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Realizar entrevista.

        Args:
            user_input: Input inicial do usuário
            mode: "basic", "junior" ou "pro"
            answers: Respostas pré-coletadas (obrigatório no modo junior)
        """
        logger.info("🎤 Entrevista iniciada (modo: %s)", mode)

        if mode == "basic":
            return await self._interview_basic(user_input)
        if mode == "junior":
            return await self._interview_junior(user_input, answers or [])
        if mode == "pro":
            return await self._interview_pro(user_input, answers or [])
        raise ValueError(f"Modo inválido: {mode}")

    async def _generate(self, prompt: str, *, format: dict[str, Any] | str | None = None,
                        num_predict: int = 256, temperature: float = 0.1) -> str:
        def _call() -> str:
            return self.ollama.generate(
                model=self.model,
                prompt=prompt,
                format=format,
                options={
                    "temperature": temperature,
                    "num_predict": num_predict,
                    "num_ctx": 2048,
                },
            )

        return await asyncio.to_thread(_call)

    async def _interview_basic(self, user_input: str) -> dict[str, Any]:
        prompt = f"""
Classifique a intenção do usuário e extraia slots:

Comando: "{user_input}"

Intenções possíveis:
- backup_automation
- notification_system
- api_integration
- data_processing
- file_operations
- chat_question

Retorne APENAS JSON:
{{
    "intent": "<intenção>",
    "slots": {{
        "source": "<valor ou null>",
        "destination": "<valor ou null>",
        "schedule": "<valor ou null>"
    }},
    "confidence": 0.0-1.0
}}
"""
        try:
            raw = await self._generate(
                prompt, format=BASIC_JSON_SCHEMA, num_predict=256, temperature=0
            )
        except OllamaError as exc:
            logger.error("Ollama falhou no InterviewAgent: %s", exc)
            return {
                "intent": "ollama_unavailable",
                "slots": {},
                "confidence": 0.0,
                "error": str(exc),
            }

        result = extract_json_object(raw)
        if result is None:
            raise OllamaError(f"JSON inválido na entrevista basic: {raw[:200]}")

        logger.info("✅ Modo Basic: %s", result)
        return result

    async def _interview_junior(
        self, user_input: str, answers: list[str]
    ) -> dict[str, Any]:
        initial = await self._interview_basic(user_input)
        questions = self._generate_clarification_questions(initial.get("intent", ""))

        if not answers:
            raise ValueError(
                "Modo junior requer answers (lista de respostas). "
                "Não há stub silencioso — passe as respostas coletadas."
            )

        paired = list(zip(questions, answers, strict=False))
        slots = dict(initial.get("slots") or {})
        for question, answer in paired:
            slots[question] = answer

        return {
            **initial,
            "mode": "junior",
            "clarification_questions": questions,
            "answers": answers,
            "slots": slots,
            "resumo": self._build_resumo(user_input, paired),
        }

    async def _interview_pro(
        self, user_input: str, answers: list[str]
    ) -> dict[str, Any]:
        if answers:
            base = await self._interview_junior(user_input, answers)
        else:
            base = await self._interview_basic(user_input)
            base["mode"] = "pro"
        prd = await self._generate_prd(user_input, base.get("intent", "unknown"))
        return {**base, "mode": "pro", "prd": prd}

    def _build_resumo(self, user_input: str, paired: list[tuple[str, str]]) -> str:
        lines = [f"Pedido: {user_input}"]
        for q, a in paired:
            lines.append(f"Q: {q}")
            lines.append(f"A: {a}")
        return "\n".join(lines)

    def _generate_clarification_questions(self, intent: str) -> list[str]:
        questions_map = {
            "backup_automation": [
                "Qual pasta você quer fazer backup?",
                "Para onde quer salvar o backup?",
                "Com que frequência (diário, semanal, mensal)?",
                "Quer compactar em ZIP ou TAR.GZ?",
            ],
            "notification_system": [
                "Qual mensagem quer enviar?",
                "Por qual canal (email, push, Telegram)?",
                "Qual prioridade (baixa, normal, alta, urgente)?",
            ],
            "api_integration": [
                "Qual API quer integrar?",
                "Qual endpoint (URL)?",
                "Precisa de autenticação (API key, OAuth)?",
            ],
        }
        return questions_map.get(intent, ["Pode detalhar mais?"])

    async def _generate_prd(self, user_input: str, intent: str) -> str:
        prompt = f"""
Gere um PRD (Documento de Requisitos de Produto) para:

Comando: "{user_input}"
Intenção: {intent}

Estrutura do PRD:
1. Visão Geral
2. Requisitos Funcionais
3. Requisitos Não-Funcionais
4. Fluxo de Usuário
5. Casos de Borda
6. Critérios de Aceite

PRD:
"""
        return await self._generate(prompt, format=None, num_predict=1024, temperature=0.2)

    def close(self) -> None:
        if self._owns_client:
            self.ollama.close()
