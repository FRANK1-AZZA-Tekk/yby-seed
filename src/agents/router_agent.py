#!/usr/bin/env python3
"""
Router Agent - Classifica intenção e roteia para agente correto

Uso:
    router = RouterAgent(ollama_client)
    result = router.classify("Crie um script de backup")
    # Output: {"agent": "planning", "intent": "backup_automation"}
"""

from typing import Any

from loguru import logger

from src.core.ollama_client import OllamaClient


class RouterAgent:
    """Agente de roteamento baseado em Llama 3.2 3B"""
    
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
        logger.info("🎯 Router Agent inicializado")
    
    def classify(self, user_command: str) -> dict[str, Any]:
        """Classifica intenção do usuário"""
        
        logger.info(f"🔍 Classificando: {user_command[:50]}...")
        
        prompt = f"""
Comando do usuário: "{user_command}"

Classifique a intenção e retorne APENAS o JSON:
"""
        
        try:
            response = self.ollama.generate(
                model=self.model,
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                options={
                    "temperature": 0.1,
                    "num_predict": 256,
                    "top_p": 0.9,
                    "num_ctx": 2048,
                },
            )
        except Exception as exc:
            logger.error(f"❌ Ollama indisponível no router: {exc}")
            return {
                "agent": "planning",
                "intent": "ollama_unavailable",
                "confidence": 0.0,
                "requires_interview": False,
                "error": str(exc),
            }

        if not isinstance(response, str) or not response.strip():
            logger.warning("⚠️  Resposta vazia do modelo, usando fallback")
            return {
                "agent": "planning",
                "intent": "unknown",
                "confidence": 0.0,
                "requires_interview": True,
                "error": "empty_model_response",
            }

        result = self._extract_json(response)
        if result is not None:
            logger.info(f"✅ Classificado: {result}")
            return result

        logger.warning("⚠️  JSON inválido, usando fallback")
        return {
            "agent": "planning",
            "intent": "unknown",
            "confidence": 0.5,
            "requires_interview": True,
        }

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extrai o primeiro objeto JSON balanceando chaves (suporta aninhamento)."""
        import json

        start = text.find("{")
        if start < 0:
            return None

        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
                    if isinstance(parsed, dict):
                        return parsed
                    return None
        return None
    
    def should_use_voice_interview(self, intent: str) -> bool:
        """Decide se usa entrevista por voz (complexidade alta)"""
        
        voice_interview_intents = [
            "backup_automation",
            "api_integration",
            "data_processing",
            "notification_system"
        ]
        
        return intent in voice_interview_intents
