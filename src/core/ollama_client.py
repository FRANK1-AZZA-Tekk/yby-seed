#!/usr/bin/env python3
"""
Cliente Ollama para inferência local de modelos

Uso:
    ollama = OllamaClient(host="localhost", port=11434)
    response = ollama.generate("llama3.2:3b", "Olá!")
"""

import requests
from typing import Optional, Dict, Any
from loguru import logger


class OllamaClient:
    """Cliente HTTP para API Ollama"""
    
    def __init__(self, host: str = "localhost", port: int = 11434):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        logger.info(f"🦙 OllamaClient conectado em {self.base_url}")
    
    def pull(self, model: str) -> bool:
        """Baixa modelo Ollama"""
        try:
            logger.info(f"📥 Baixando modelo: {model}")
            response = self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
                stream=True
            )
            
            for line in response.iter_lines():
                if line:
                    logger.debug(f"  {line.decode()}")
            
            logger.info(f"✅ Modelo {model} baixado")
            return True
        
        except Exception as e:
            logger.error(f"❌ Erro ao baixar {model}: {e}")
            return False
    
    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Gera resposta com modelo Ollama"""
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
        
        if system:
            payload["system"] = system
        
        if options:
            payload["options"] = options
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=stream
            )
            
            if stream:
                # Stream: retorna generator
                def stream_generator():
                    for line in response.iter_lines():
                        if line:
                            yield line.decode()
                
                return stream_generator()
            
            else:
                # Não-stream: retorna texto completo
                result = response.json()
                return result.get("response", "")
        
        except Exception as e:
            logger.error(f"❌ Erro ao gerar com {model}: {e}")
            return ""
    
    def chat(
        self,
        model: str,
        messages: list,
        stream: bool = False
    ) -> str:
        """Chat com histórico de mensagens"""
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=stream
            )
            
            if stream:
                def stream_generator():
                    for line in response.iter_lines():
                        if line:
                            yield line.decode()
                
                return stream_generator()
            
            else:
                result = response.json()
                return result.get("message", {}).get("content", "")
        
        except Exception as e:
            logger.error(f"❌ Erro no chat com {model}: {e}")
            return ""
    
    def list_models(self) -> list:
        """Lista modelos disponíveis"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            result = response.json()
            return [m["name"] for m in result.get("models", [])]
        
        except Exception as e:
            logger.error(f"❌ Erro ao listar modelos: {e}")
            return []
    
    def is_healthy(self) -> bool:
        """Verifica se Ollama está rodando"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        
        except Exception:
            return False
