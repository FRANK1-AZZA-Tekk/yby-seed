#!/usr/bin/env python3
"""
OpenRouter Sanitizer - Sanitiza dados antes de enviar para APIs externas

Baseado em: OpenRouter Security Center (2026) e Safeguard (2026)

Uso:
    sanitizer = OpenRouterSanitizer()
    sanitized_text = sanitizer.sanitize(prd_text)
"""

import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger


class OpenRouterSanitizer:
    """Sanitiza texto removendo dados sensíveis antes de enviar para OpenRouter"""
    
    # Padrões de dados sensíveis
    SENSITIVE_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "api_key": r"(sk-[a-zA-Z0-9]{32,}|api[_-]?key[_-]?[=:][\s]*[a-zA-Z0-9]{16,})",
        "password": r"(password|senha|passwd)[\s]*[=:][\s]*[^\s]+",
        "token": r"(token|bearer)[\s]*[=:][\s]*[a-zA-Z0-9._-]{20,}",
        "path_absolute": r"(/[a-zA-Z0-9_/-]+){3,}|([A-Z]:\\[a-zA-Z0-9_\\-]+){2,}",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "phone": r"(\+\d{1,3}[\s-]?)?\(?\d{2,3}\)?[\s-]?\d{3,4}[\s-]?\d{4}",
        "cpf": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
        "cnpj": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"
    }
    
    # Substituições
    REPLACEMENTS = {
        "email": "[EMAIL_REDACTED]",
        "api_key": "[API_KEY_REDACTED]",
        "password": "[PASSWORD_REDACTED]",
        "token": "[TOKEN_REDACTED]",
        "path_absolute": "[PATH_REDACTED]",
        "ip_address": "[IP_REDACTED]",
        "phone": "[PHONE_REDACTED]",
        "cpf": "[CPF_REDACTED]",
        "cnpj": "[CNPJ_REDACTED]"
    }
    
    def __init__(self):
        self.stats = {
            "total_sanitizations": 0,
            "by_type": {k: 0 for k in self.SENSITIVE_PATTERNS.keys()}
        }
        logger.info("🔒 OpenRouterSanitizer inicializado")
    
    def sanitize(self, text: str) -> str:
        """Sanitiza texto removendo dados sensíveis"""
        
        logger.info("🔒 Sanitizando texto para OpenRouter...")
        
        sanitized = text
        
        # Aplica cada padrão de sanitização
        for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
            matches = re.findall(pattern, sanitized, re.IGNORECASE)
            
            if matches:
                logger.debug(f"  📍 {pattern_name}: {len(matches)} ocorrências")
                sanitized = re.sub(
                    pattern,
                    self.REPLACEMENTS[pattern_name],
                    sanitized,
                    flags=re.IGNORECASE
                )
                
                self.stats["by_type"][pattern_name] += len(matches)
            
            self.stats["total_sanitizations"] += len(matches)
        
        # Normaliza paths relativos (evita vazar estrutura de diretórios)
        sanitized = self._normalize_relative_paths(sanitized)
        
        # Remove menções a arquivos locais específicos
        sanitized = self._remove_local_file_references(sanitized)
        
        logger.info(f"✅ Sanitização concluída ({self.stats['total_sanitizations']} dados sensíveis removidos)")
        
        return sanitized
    
    def _normalize_relative_paths(self, text: str) -> str:
        """Normaliza paths relativos para evitar vazar estrutura de diretórios"""
        
        # Substitui paths como src/agents/router_agent.py por [SOURCE_FILE]
        pattern = r"\b(src|tests|docs|examples)/[a-zA-Z0-9_/-]+\.py\b"
        return re.sub(pattern, "[SOURCE_FILE]", text)
    
    def _remove_local_file_references(self, text: str) -> str:
        """Remove referências a arquivos locais específicos"""
        
        # Remove menções a arquivos de configuração locais
        patterns_to_remove = [
            r"\b\.env\b",
            r"\b\.gitignore\b",
            r"\brequirements\.txt\b",
            r"\bdocker-compose\.yml\b",
            r"\bMakefile\b"
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, "[CONFIG_FILE]", text)
        
        return text
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de sanitização"""
        
        return self.stats.copy()
    
    def validate_before_send(self, text: str) -> Dict[str, Any]:
        """Valida texto antes de enviar para OpenRouter"""
        
        # Verifica se ainda há dados sensíveis
        remaining = []
        
        for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            if matches:
                remaining.append({
                    "type": pattern_name,
                    "count": len(matches),
                    "examples": matches[:3]  # Mostra até 3 exemplos
                })
        
        is_safe = len(remaining) == 0
        
        return {
            "is_safe": is_safe,
            "remaining_sensitive": remaining,
            "recommendation": "Enviar" if is_safe else "Revisar antes de enviar"
        }
