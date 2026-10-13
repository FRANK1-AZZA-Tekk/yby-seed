#!/usr/bin/env python3
"""
Planning Agent - Entrevista usuário, coleta requisitos, gera PRD

Uso:
    planner = PlanningAgent(ollama_client)
    prd = planner.interview("Quero backup de PDFs")
"""

import re
from typing import List, Dict, Optional, Literal
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from src.core.ollama_client import OllamaClient


class PRD(BaseModel):
    """Schema Pydantic para o PRD gerado pelo PlanningAgent."""

    title: str = Field(
        description="Título do PRD",
        min_length=1,
    )
    objective: str = Field(
        description="Objetivo da automação",
        min_length=1,
    )
    functional_requirements: List[str] = Field(
        description="Requisitos funcionais",
        default_factory=list,
    )
    non_functional_requirements: List[str] = Field(
        description="Requisitos não-funcionais",
        default_factory=list,
    )
    main_flow: List[str] = Field(
        description="Fluxo principal",
        default_factory=list,
    )
    error_cases: List[str] = Field(
        description="Casos de erro",
        default_factory=list,
    )
    required_apis: List[str] = Field(
        description="APIs necessárias",
        default_factory=list,
    )


class PlanningAgent:
    """Agente de planejamento baseado em Qwen2.5-Coder 3B com validação Pydantic."""

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

Formato PRD.md:
```markdown
# PRD: [Nome da Automação]

## Objetivo
[Descrição clara]

## Requisitos Funcionais
1. [Requisito 1]
2. [Requisito 2]

## Requisitos Não-Funcionais
- [Requisito 1]
- [Requisito 2]

## Fluxo Principal
1. [Passo 1]
2. [Passo 2]

## Casos de Erro
- [Caso 1]
- [Caso 2]

## APIs Necessárias
- [API 1]
- [API 2]
```
"""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.model = "qwen2.5-coder:3b-instruct-q4_K_M"
        logger.info("📋 Planning Agent inicializado (com validação Pydantic)")

    def interview(
        self,
        initial_request: str,
        mode: Literal["basic", "junior", "pro"] = "junior"
    ) -> PRD:
        """Entrevista usuário e gera PRD validado."""

        logger.info(f"🎤 Iniciando entrevista (modo: {mode})")

        max_questions = {
            "basic": 2,
            "junior": 5,
            "pro": 15
        }.get(mode, 5)

        conversation_history = []

        first_question = self._generate_first_question(initial_request)
        print(f"\n🤖 {first_question}\n")

        conversation_history.append({
            "role": "user",
            "content": initial_request
        })

        for i in range(max_questions):
            user_answer = input("👤 Sua resposta: ").strip()

            conversation_history.append({
                "role": "assistant",
                "content": first_question if i == 0 else f"Pergunta {i}"
            })

            conversation_history.append({
                "role": "user",
                "content": user_answer
            })

            if i < max_questions - 1:
                next_question = self._generate_next_question(
                    conversation_history,
                    mode
                )

                if next_question:
                    print(f"\n🤖 {next_question}\n")
                    first_question = next_question
                else:
                    break
            else:
                break

        prd = self._generate_prd(conversation_history, initial_request)
        logger.info("✅ PRD gerado e validado")
        return prd

    def _generate_first_question(self, request: str) -> str:
        """Gera primeira pergunta da entrevista."""

        prompt = f"""
Usuário quer: "{request}"

Gere a PRIMEIRA pergunta para entender melhor o que ele precisa.
Seja claro e direto (máx 20 palavras).
"""

        response = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.3, "num_predict": 128}
        )

        return response.strip()

    def _generate_next_question(
        self,
        conversation: List[Dict],
        mode: str
    ) -> Optional[str]:
        """Gera próxima pergunta baseada no histórico."""

        history_text = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in conversation[-6:]
        ])

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
            options={"temperature": 0.3, "num_predict": 128}
        )

        if "FINALIZAR" in response.upper():
            return None

        return response.strip()

    def _generate_prd(
        self,
        conversation: List[Dict],
        initial_request: str
    ) -> PRD:
        """Gera PRD validado com Pydantic baseado na entrevista."""

        history_text = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in conversation
        ])

        prompt = f"""
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

        raw = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.2, "num_predict": 2048}
        )

        return self._parse_prd(raw, initial_request)

    def _parse_prd(self, raw: str, fallback_title: str) -> PRD:
        """Extrai e valida PRD do texto Markdown gerado."""

        # Extrai título
        title_match = re.search(r'#\s*PRD:\s*(.+)', raw)
        title = title_match.group(1).strip() if title_match else fallback_title

        # Extrai objetivo
        objective_match = re.search(
            r'##\s*Objetivo\s*\n+(.+?)(?=\n##|$)', raw, re.DOTALL
        )
        objective = objective_match.group(1).strip() if objective_match else ""

        # Extrai seções em lista
        def extract_list(section_name: str) -> List[str]:
            pattern = rf'##\s*{section_name}\s*\n+(.+?)(?=\n##|$)'
            match = re.search(pattern, raw, re.DOTALL)
            if not match:
                return []
            lines = match.group(1).strip().split('\n')
            return [
                re.sub(r'^[-*\d.\s]+', '', line).strip()
                for line in lines if line.strip()
            ]

        try:
            prd = PRD(
                title=title,
                objective=objective or "Objetivo não especificado",
                functional_requirements=extract_list("Requisitos Funcionais"),
                non_functional_requirements=extract_list("Requisitos Não-Funcionais"),
                main_flow=extract_list("Fluxo Principal"),
                error_cases=extract_list("Casos de Erro"),
                required_apis=extract_list("APIs Necessárias"),
            )
            logger.info(f"✅ PRD validado: {prd.title}")
            return prd
        except ValidationError as e:
            logger.warning(f"⚠️  Validação Pydantic falhou: {e}")
            # Fallback: PRD mínimo
            return PRD(
                title=fallback_title,
                objective="Objetivo não especificado",
            )
