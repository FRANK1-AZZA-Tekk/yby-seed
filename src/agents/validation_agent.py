#!/usr/bin/env python3
"""
Validation Agent - Valida código gerado (segurança, sintaxe, lógica)

Uso:
    validator = ValidationAgent()
    is_valid, errors = validator.validate(code)
"""

import ast
import re
from typing import Tuple, List, Dict, Any
from loguru import logger


class ValidationAgent:
    """Agente de validação de código Python"""
    
    DANGEROUS_PATTERNS = [
        "os.system",
        "subprocess.call",
        "subprocess.run",
        "eval(",
        "exec(",
        "__import__",
        "rm -rf",
        "chmod 777",
        "shutil.rmtree"
    ]
    
    REQUIRED_SECTIONS = [
        "import",
        "def",
        "if __name__"
    ]
    
    def __init__(self):
        logger.info("🛡️  Validation Agent inicializado")
    
    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """Valida código Python"""
        
        errors = []
        
        # 1. Valida sintaxe
        syntax_valid, syntax_errors = self._validate_syntax(code)
        if not syntax_valid:
            errors.extend(syntax_errors)
        
        # 2. Valida segurança
        security_valid, security_errors = self._validate_security(code)
        if not security_valid:
            errors.extend(security_errors)
        
        # 3. Valida estrutura
        structure_valid, structure_errors = self._validate_structure(code)
        if not structure_valid:
            errors.extend(structure_errors)
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✅ Código válido")
        else:
            logger.warning(f"⚠️  {len(errors)} erros encontrados")
        
        return is_valid, errors
    
    def _validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Valida sintaxe Python"""
        
        errors = []
        
        try:
            ast.parse(code)
        
        except SyntaxError as e:
            errors.append(f"Erro de sintaxe linha {e.lineno}: {e.msg}")
        
        return len(errors) == 0, errors
    
    def _validate_security(self, code: str) -> Tuple[bool, List[str]]:
        """Valida segurança (padrões perigosos)"""
        
        errors = []
        
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in code:
                errors.append(f"⚠️  Padrão perigoso detectado: {pattern}")
        
        return len(errors) == 0, errors
    
    def _validate_structure(self, code: str) -> Tuple[bool, List[str]]:
        """Valida estrutura mínima"""
        
        errors = []
        
        for section in self.REQUIRED_SECTIONS:
            if section not in code:
                errors.append(f"⚠️  Seção ausente: {section}")
        
        return len(errors) == 0, errors
    
    def suggest_fixes(self, code: str, errors: List[str]) -> str:
        """Sugere correções para erros"""
        
        if not errors:
            return "✅ Código válido, sem correções necessárias."
        
        suggestions = []
        
        for error in errors:
            if "os.system" in error:
                suggestions.append(
                    "💡 Substitua os.system() por subprocess.run() com shell=False"
                )
            
            elif "eval(" in error or "exec(" in error:
                suggestions.append(
                    "💡 Evite eval()/exec(). Use ast.literal_eval() para dados seguros."
                )
            
            elif "Erro de sintaxe" in error:
                suggestions.append(
                    "💡 Verifique indentação e parênteses."
                )
        
        return "\n".join(suggestions)
