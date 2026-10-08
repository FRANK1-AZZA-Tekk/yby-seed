"""
Interview Agent — Entrevista em 3 modos (Basic, Junior, Pro)

Responsabilidade:
- Coletar requisitos via conversa em linguagem natural
- Fazer perguntas de clarificação (modo Junior/Pro)
- Gerar PRD (Documento de Requisitos de Produto)

3 Modos:
- Basic: <1 min, resposta direta
- Junior: 5-15 min, entrevista progressiva
- Pro: 15-30 min, PRD completo obrigatório

Modelo:
- Llama 3.2 3B (Q4_K_M, 100% VRAM, 28-100 t/s)

Licença: MIT
"""

from typing import Dict, Any, List
import logging
from litellm import completion  # LiteLLM wrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InterviewAgent:
    """
    Agente de entrevista em 3 modos.
    """
    
    def __init__(self, model: str = "llama3.2:3b"):
        """
        Inicializar agente.
        
        Args:
            model: Modelo Ollama (3B para velocidade)
        """
        self.model = model
    
    async def interview(self, user_input: str, mode: str = "basic") -> Dict[str, Any]:
        """
        Realizar entrevista.
        
        Args:
            user_input: Input inicial do usuário
            mode: "basic", "junior" ou "pro"
        
        Returns:
            Dict com intent, slots, PRD (se mode="pro")
        """
        logger.info(f"🎤 Entrevista iniciada (modo: {mode})")
        
        if mode == "basic":
            return await self._interview_basic(user_input)
        
        elif mode == "junior":
            return await self._interview_junior(user_input)
        
        elif mode == "pro":
            return await self._interview_pro(user_input)
        
        else:
            raise ValueError(f"Modo inválido: {mode}")
    
    async def _interview_basic(self, user_input: str) -> Dict[str, Any]:
        """
        Modo Basic: resposta direta, sem entrevista.
        
        Args:
            user_input: Input do usuário
        
        Returns:
            Dict com intent e slots
        """
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
        
        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.1
        )
        
        import json
        result = json.loads(response.choices[0].message.content.strip())
        
        logger.info(f"✅ Modo Basic: {result}")
        return result
    
    async def _interview_junior(self, user_input: str) -> Dict[str, Any]:
        """
        Modo Junior: entrevista progressiva (5-15 min).
        
        Fluxo:
        1. Classificar intenção inicial
        2. Fazer 3-5 perguntas de clarificação
        3. Gerar resumo de requisitos
        
        Args:
            user_input: Input inicial do usuário
        
        Returns:
            Dict com intent, slots, resumo
        """
        # 1. Classificar intenção inicial
        initial = await self._interview_basic(user_input)
        
        # 2. Perguntas de clarificação
        questions = self._generate_clarification_questions(initial["intent"])
        
        logger.info(f"📋 Perguntas de clarificação: {questions}")
        
        # TODO: Implementar loop de entrevista (interagir com usuário)
        # Por enquanto, retornar inicial
        
        return {
            **initial,
            "mode": "junior",
            "clarification_questions": questions,
            "resumo": "Entrevista em andamento..."
        }
    
    async def _interview_pro(self, user_input: str) -> Dict[str, Any]:
        """
        Modo Pro: entrevista exaustiva (15-30 min) + PRD completo.
        
        Fluxo:
        1. Classificar intenção inicial
        2. Entrevista profunda (10+ perguntas)
        3. Gerar PRD.md estruturado
        
        Args:
            user_input: Input inicial do usuário
        
        Returns:
            Dict com intent, slots, PRD.md
        """
        # 1. Classificar intenção inicial
        initial = await self._interview_basic(user_input)
        
        # 2. Gerar PRD completo
        prd = await self._generate_prd(user_input, initial["intent"])
        
        logger.info(f"✅ Modo Pro: PRD gerado ({len(prd)} chars)")
        
        return {
            **initial,
            "mode": "pro",
            "prd": prd
        }
    
    def _generate_clarification_questions(self, intent: str) -> List[str]:
        """
        Gerar perguntas de clarificação para a intenção.
        
        Args:
            intent: Intenção classificada
        
        Returns:
            Lista de perguntas
        """
        questions_map = {
            "backup_automation": [
                "Qual pasta você quer fazer backup?",
                "Para onde quer salvar o backup?",
                "Com que frequência (diário, semanal, mensal)?",
                "Quer compactar em ZIP ou TAR.GZ?"
            ],
            "notification_system": [
                "Qual mensagem quer enviar?",
                "Por qual canal (email, push, Telegram)?",
                "Qual prioridade (baixa, normal, alta, urgente)?"
            ],
            "api_integration": [
                "Qual API quer integrar?",
                "Qual endpoint (URL)?",
                "Precisa de autenticação (API key, OAuth)?"
            ]
        }
        
        return questions_map.get(intent, ["Pode detalhar mais?"])
    
    async def _generate_prd(self, user_input: str, intent: str) -> str:
        """
        Gerar PRD (Documento de Requisitos de Produto).
        
        Args:
            user_input: Input do usuário
            intent: Intenção classificada
        
        Returns:
            PRD.md em Markdown
        """
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
        
        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2
        )
        
        prd = response.choices[0].message.content.strip()
        return prd


# Instância global
interview_agent = InterviewAgent()


if __name__ == "__main__":
    import asyncio
    
    # Teste
    async def test():
        # Modo Basic
        result = await interview_agent.interview("Crie um backup dos meus PDFs", mode="basic")
        print(f"\nModo Basic: {result}")
        
        # Modo Pro
        result = await interview_agent.interview("Sistema de gestão de estoque", mode="pro")
        print(f"\nModo Pro PRD:\n{result['prd']}")
    
    asyncio.run(test())
