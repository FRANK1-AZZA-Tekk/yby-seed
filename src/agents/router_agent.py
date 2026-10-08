#!/usr/bin/env python3
"""
Router Agent - Classifica intenção e roteia para agente correto

Uso:
    router = RouterAgent(ollama_client)
    result = router.classify("Crie um script de backup")
    # Output: {"agent": "planning", "intent": "backup_automation"}
"""

from typing import Dict, Any
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
    
    def classify(self, user_command: str) -> Dict[str, Any]:
        """Classifica intenção do usuário"""
        
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
        
        # Parse JSON da resposta
        import json
        import re
        
        # Extrai JSON da resposta (pode ter texto antes/depois)
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        
        if json_match:
            try:
                result = json.loads(json_match.group())
                logger.info(f"✅ Classificado: {result}")
                return result
            
            except json.JSONDecodeError:
                logger.warning("⚠️  JSON inválido, usando fallback")
        
        # Fallback
        return {
            "agent": "planning",
            "intent": "unknown",
            "confidence": 0.5,
            "requires_interview": True
        }
    
    def should_use_voice_interview(self, intent: str) -> bool:
        """Decide se usa entrevista por voz (complexidade alta)"""
        
        voice_interview_intents = [
            "backup_automation",
            "api_integration",
            "data_processing",
            "notification_system"
        ]
        
        return intent in voice_interview_intents
