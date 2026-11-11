#!/usr/bin/env python3
"""
Planning Agent - Entrevista usuário, coleta requisitos, gera PRD

Uso:
    planner = PlanningAgent(ollama_client)
    prd = planner.interview_from_answers("Quero backup", ["~/docs", "/backup", "diario"])
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from src.core.ollama_client import OllamaClient


class PlanningAgent:
    """Agente de planejamento baseado em Qwen2.5-Coder 3B."""

    SYSTEM_PROMPT = """
Você é um Planning Agent que entrevista usuários para coletar requisitos.

Sua tarefa:
1. Fazer perguntas claras (uma por vez)
2. Coletar contexto suficiente para gerar PRD
3. Gerar PRD.md estruturado

Modos:
- Basic: 1-2 perguntas, script simples
- Junior: 3-5 perguntas, script + docs
- Pro: 10-15 perguntas, PRD completo
"""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.model = "qwen2.5-coder:3b-instruct-q4_K_M"
        logger.info("📋 Planning Agent inicializado")

    def max_questions_for(self, mode: str) -> int:
        return {"basic": 2, "junior": 5, "pro": 15}.get(mode, 5)

    def interview(
        self,
        initial_request: str,
        mode: str = "junior",
        input_fn: Callable[[str], str] | None = None,
        print_fn: Callable[[str], None] | None = None,
    ) -> str:
        """Entrevista interativa (CLI). Usa input/print por padrão."""
        ask = input_fn or (lambda prompt: input(prompt).strip())
        out = print_fn or print

        first_question = self._generate_first_question(initial_request)
        out(f"\n🤖 {first_question}\n")

        answers: list[str] = []
        current_question = first_question
        max_questions = self.max_questions_for(mode)
        conversation: list[dict[str, Any]] = [
            {"role": "user", "content": initial_request},
        ]

        for i in range(max_questions):
            user_answer = ask("👤 Sua resposta: ")
            answers.append(user_answer)
            conversation.append({"role": "assistant", "content": current_question})
            conversation.append({"role": "user", "content": user_answer})

            if i >= max_questions - 1:
                break

            next_question = self._generate_next_question(conversation, mode)
            if not next_question:
                break
            out(f"\n🤖 {next_question}\n")
            current_question = next_question

        return self._generate_prd(conversation, initial_request)

    def interview_from_answers(
        self,
        initial_request: str,
        answers: list[str],
        mode: str = "junior",
    ) -> str:
        """Caminho não-interativo: gera PRD a partir de respostas já coletadas."""
        logger.info(
            "🎤 Entrevista programática (modo: %s, %s respostas)", mode, len(answers)
        )

        max_questions = self.max_questions_for(mode)
        first_question = self._generate_first_question(initial_request)
        conversation: list[dict[str, Any]] = [
            {"role": "user", "content": initial_request},
        ]
        current_q = first_question

        for idx, answer in enumerate(answers[:max_questions]):
            conversation.append({"role": "assistant", "content": current_q})
            conversation.append({"role": "user", "content": answer})
            if idx >= max_questions - 1 or idx >= len(answers) - 1:
                break
            next_q = self._generate_next_question(conversation, mode)
            if not next_q:
                break
            current_q = next_q

        prd = self._generate_prd(conversation, initial_request)
        logger.info("✅ PRD gerado")
        return prd

    def _generate_first_question(self, request: str) -> str:
        prompt = f"""
Usuário quer: "{request}"

Gere a PRIMEIRA pergunta para entender melhor o que ele precisa.
Seja claro e direto (máx 20 palavras).
"""
        response = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.3, "num_predict": 128},
        )
        return response.strip()

    def _generate_next_question(
        self,
        conversation: list[dict[str, Any]],
        mode: str,
    ) -> str | None:
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in conversation[-6:]
        )
        prompt = f"""
Histórico da conversa:
{history_text}

Gere a PRÓXIMA pergunta para coletar mais detalhes.
Se já tiver informações suficientes, retorne "FINALIZAR".
Seja claro e direto (máx 20 palavras).
"""
        response = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.3, "num_predict": 128},
        )
        if "FINALIZAR" in response.upper():
            return None
        return response.strip()

    def _generate_prd(
        self,
        conversation: list[dict[str, Any]],
        initial_request: str,
    ) -> str:
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in conversation
        )
        prompt = f"""
Pedido inicial: {initial_request}

Entrevista completa:
{history_text}

Gere um PRD.md estruturado com:
- Objetivo
- Requisitos Funcionais
- Requisitos Não-Funcionais
- Fluxo Principal
- Casos de Erro
- APIs Necessárias

Formato Markdown.
"""
        return self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.2, "num_predict": 2048},
        )
