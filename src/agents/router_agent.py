#!/usr/bin/env python3
"""
Router Agent - Classifica intenção e roteia para agente correto

Uso:
    router = RouterAgent(ollama_client)
    result = router.classify("Crie um script de backup")
    # Output: RouterResult(agent="planning", intent="backup_automation", ...)
"""

import json
import re
from typing import Literal
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from src.core.ollama_client import OllamaClient


class RouterResult(BaseModel):
    """Schema Pydantic para o resultado do RouterAgent."""

    agent: Literal["planning", "execution"] = Field(
        description="Agente de destino"
    )
    intent: str = Field(
        description="Intenção classificada",
        min_length=1,
    )
    confidence: float = Field(
        description="Confiança da classificação (0.0 a 1.0)",
        ge=0.0,
        le=1.0,
    )
    requires_interview: bool = Field(
        description="Se requer entrevista por voz",
        default=False,
    )


class RouterAgent:
    """Agente de roteamento baseado em Llama 3.2 3B com validação Pydantic."""

    SYSTEM_PROMPT = """
Você é um Router Agent que classifica intenções de usuários.

Sua tarefa:
1. Analisar o comando do usuário
2. Classificar a intenção
3. Roteir para o agente correto

Intenções possíveis:
- "backup_automation" → Agent: planning
- "weather_alert" → Agent: planning
- "steps_tracker" → Agent: planning
- "api_integration" → Agent: planning
- "data_processing" → Agent: planning
- "file_operations" → Agent: planning
- "notification_system" → Agent: planning
- "chat_question" → Agent: execution (resposta direta)

Formato de saída (JSON):
{
    "agent": "planning" | "execution",
    "intent": "nome_da_intencao",
    "confidence": 0.0-1.0,
    "requires_interview": true | false
}
"""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.model = "llama3.2:3b-instruct-q4_K_M"
        logger.info("🎯 Router Agent inicializado (com validação Pydantic)")

    def classify(self, user_command: str) -> RouterResult:
        """Classifica intenção do usuário e valida com Pydantic."""

        logger.info(f"🔍 Classificando: {user_command[:50]}...")

        prompt = f"""
Comando do usuário: "{user_command}"

Classifique a intenção e retorne APENAS o JSON:
"""

        response = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={
                "temperature": 0.1,
                "num_predict": 256,
                "top_p": 0.9
            }
        )

        # Extrai JSON da resposta
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)

        if json_match:
            try:
                data = json.loads(json_match.group())
                result = RouterResult(**data)
                logger.info(f"✅ Classificado e validado: {result}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  JSON inválido: {e}")
            except ValidationError as e:
                logger.warning(f"⚠️  Validação Pydantic falhou: {e}")

        # Fallback
        logger.warning("⚠️  Usando fallback (planning, unknown, 0.5)")
        return RouterResult(
            agent="planning",
            intent="unknown",
            confidence=0.5,
            requires_interview=True,
        )

    def should_use_voice_interview(self, intent: str) -> bool:
        """Decide se usa entrevista por voz (complexidade alta)."""

        voice_interview_intents = [
            "backup_automation",
            "api_integration",
            "data_processing",
            "notification_system"
        ]

        return intent in voice_interview_intents
