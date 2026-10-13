#!/usr/bin/env python3
"""
Validação de segurança para código gerado pelo ExecutionAgent.

Uso:
    validator = CodeSafetyValidator()
    result = validator.validate(code)
    # result: SafetyResult(is_safe=True, issues=[], ...)
"""

import ast
import re
from typing import List
from loguru import logger
from pydantic import BaseModel, Field


class SafetyResult(BaseModel):
    """Schema Pydantic para o resultado da validação de segurança."""

    is_safe: bool = Field(
        description="Se o código é seguro",
    )
    issues: List[str] = Field(
        description="Lista de problemas de segurança detectados",
        default_factory=list,
    )
    syntax_valid: bool = Field(
        description="Se o código tem sintaxe Python válida",
    )
    dangerous_imports: List[str] = Field(
        description="Imports perigosos detectados",
        default_factory=list,
    )
    dangerous_calls: List[str] = Field(
        description="Chamadas perigosas detectadas",
        default_factory=list,
    )


class CodeSafetyValidator:
    """Validador de segurança para código Python gerado."""

    # Imports considerados perigosos
    DANGEROUS_IMPORTS = [
        "os.system",
        "subprocess",
        "shutil.rmtree",
        "socket",
        "ctypes",
        "multiprocessing",
    ]

    # Chamadas consideradas perigosas
    DANGEROUS_CALLS = [
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
    ]

    def __init__(self):
        logger.info("🔒 CodeSafetyValidator inicializado")

    def validate(self, code: str) -> SafetyResult:
        """Valida segurança do código gerado."""

        issues: List[str] = []
        dangerous_imports: List[str] = []
        dangerous_calls: List[str] = []

        # 1. Valida sintaxe
        syntax_valid = self._check_syntax(code, issues)

        # 2. Valida imports perigosos
        dangerous_imports = self._check_dangerous_imports(code, issues)

        # 3. Valida chamadas perigosas
        dangerous_calls = self._check_dangerous_calls(code, issues)

        is_safe = syntax_valid and not issues

        result = SafetyResult(
            is_safe=is_safe,
            issues=issues,
            syntax_valid=syntax_valid,
            dangerous_imports=dangerous_imports,
            dangerous_calls=dangerous_calls,
        )

        if is_safe:
            logger.info("✅ Código seguro")
        else:
            logger.warning(f"⚠️  Código com problemas: {issues}")

        return result

    def _check_syntax(self, code: str, issues: List[str]) -> bool:
        """Verifica se o código tem sintaxe Python válida."""

        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            issues.append(f"Erro de sintaxe: {e}")
            return False

    def _check_dangerous_imports(
        self, code: str, issues: List[str]
    ) -> List[str]:
        """Detecta imports perigosos."""

        found = []
        for dangerous in self.DANGEROUS_IMPORTS:
            pattern = rf'^\s*(?:import|from)\s+{re.escape(dangerous)}'
            if re.search(pattern, code, re.MULTILINE):
                found.append(dangerous)
                issues.append(f"Import perigoso detectado: {dangerous}")

        return found

    def _check_dangerous_calls(
        self, code: str, issues: List[str]
    ) -> List[str]:
        """Detecta chamadas perigosas."""

        found = []
        for dangerous in self.DANGEROUS_CALLS:
            pattern = rf'\b{re.escape(dangerous)}\s*\('
            if re.search(pattern, code):
                found.append(dangerous)
                issues.append(f"Chamada perigosa detectada: {dangerous}")

        return found
