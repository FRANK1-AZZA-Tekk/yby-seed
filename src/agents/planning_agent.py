#!/usr/bin/env python3
"""
Planning Agent - Entrevista usuário, coleta requisitos, gera PRD

Uso:
    planner = PlanningAgent(ollama_client)
    prd = planner.interview("Quero backup de PDFs")
"""

from typing import List, Dict, Any, Optional
from loguru import logger
from src.core.ollama_client import OllamaClient


class PlanningAgent:
    """Agente de planejamento baseado em Qwen2.5-Coder 3B"""
    
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
        logger.info("📋 Planning Agent inicializado")
    
    def interview(
        self,
        initial_request: str,
        mode: str = "junior"
    ) -> str:
        """Entrevista usuário e gera PRD"""
        
        logger.info(f"🎤 Iniciando entrevista (modo: {mode})")
        
        # Define número de perguntas por modo
        max_questions = {
            "basic": 2,
            "junior": 5,
            "pro": 15
        }.get(mode, 5)
        
        # Histórico da conversa
        conversation_history = []
        
        # Primeira pergunta
        first_question = self._generate_first_question(initial_request)
        print(f"\n🤖 {first_question}\n")
        
        conversation_history.append({
            "role": "user",
            "content": initial_request
        })
        
        # Loop de entrevista
        for i in range(max_questions):
            # Resposta do usuário
            user_answer = input("👤 Sua resposta: ").strip()
            
            conversation_history.append({
                "role": "assistant",
                "content": first_question if i == 0 else f"Pergunta {i}"
            })
            
            conversation_history.append({
                "role": "user",
                "content": user_answer
            })
            
            # Gera próxima pergunta ou finaliza
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
        
        # Gera PRD
        prd = self._generate_prd(conversation_history, initial_request)
        
        logger.info("✅ PRD gerado")
        return prd
    
    def _generate_first_question(self, request: str) -> str:
        """Gera primeira pergunta da entrevista"""
        
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
        """Gera próxima pergunta baseada no histórico"""
        
        # Converte histórico para texto
        history_text = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in conversation[-6:]  # Últimas 6 mensagens
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
    ) -> str:
        """Gera PRD baseado na entrevista"""
        
        # Converte histórico para texto
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
        
        prd = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.2, "num_predict": 2048}
        )
        
        return prd
