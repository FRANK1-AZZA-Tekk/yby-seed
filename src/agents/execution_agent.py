#!/usr/bin/env python3
"""
Execution Agent - Gera código Python baseado no PRD

Uso:
    executor = ExecutionAgent(ollama_client)
    result = executor.generate(prd_text)
    # result: GeneratedCode(code="...", language="python", ...)
"""

import re
from typing import Optional, List, Literal
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from src.core.ollama_client import OllamaClient
from src.security.code_safety_validator import CodeSafetyValidator


class GeneratedCode(BaseModel):
    """Schema Pydantic para o código gerado pelo ExecutionAgent."""

    code: str = Field(
        description="Código Python gerado",
        min_length=1,
    )
    language: Literal["python"] = Field(
        description="Linguagem do código",
        default="python",
    )
    has_main: bool = Field(
        description="Se o código tem função main()",
        default=False,
    )
    has_docstring: bool = Field(
        description="Se o código tem docstring",
        default=False,
    )
    imports: List[str] = Field(
        description="Imports detectados",
        default_factory=list,
    )
    is_safe: bool = Field(
        description="Se o código passou na validação de segurança",
        default=False,
    )
    safety_issues: List[str] = Field(
        description="Problemas de segurança detectados",
        default_factory=list,
    )


class ExecutionAgent:
    """Agente de execução baseado em Qwen2.5-Coder 7B com validação Pydantic e segurança."""

    SYSTEM_PROMPT = """
Você é um Execution Agent que gera código Python baseado em PRDs.

Sua tarefa:
1. Ler PRD.md
2. Gerar código Python completo e funcional
3. Incluir imports, funções, tratamento de erros
4. Adicionar comentários explicativos em português

Regras:
- Código deve ser executável imediatamente
- Usar bibliotecas padrão sempre que possível
- Incluir docstrings em todas as funções
- Tratar erros comuns (FileNotFoundError, ConnectionError, etc.)
- Adicionar exemplo de uso no final

Formato:
```python
#!/usr/bin/env python3
\"\"\"Descrição do script\"\"\"

import ...

def main():
    ...

if __name__ == "__main__":
    main()
```
"""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.model = "qwen2.5-coder:7b-instruct-q4_K_M"
        self.safety_validator = CodeSafetyValidator()
        logger.info(
            "⚙️  Execution Agent inicializado "
            "(com validação Pydantic e segurança)"
        )

    def generate(
        self,
        prd: str,
        context: Optional[str] = None
    ) -> GeneratedCode:
        """Gera código Python validado com Pydantic e segurança."""

        logger.info("📝 Gerando código Python...")

        prompt = f"""
PRD:
{prd}

{f'Contexto adicional:\n{context}' if context else ''}

Gere o código Python completo e funcional.
Inclua TODOS os imports necessários.
"""

        raw = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={
                "temperature": 0.2,
                "num_predict": 4096,
                "top_p": 0.9
            }
        )

        return self._parse_code(raw)

    def generate_with_rag(
        self,
        prd: str,
        rag_chunks: List[str]
    ) -> GeneratedCode:
        """Gera código com contexto RAG."""

        logger.info(f"📚 Gerando código com {len(rag_chunks)} chunks RAG...")

        context = "\n\n".join([
            f"Chunk {i+1}:\n{chunk}"
            for i, chunk in enumerate(rag_chunks)
        ])

        return self.generate(prd, context)

    def _parse_code(self, raw: str) -> GeneratedCode:
        """Extrai, valida segurança e valida código do bloco Markdown gerado."""

        # Extrai código do bloco Markdown
        code_match = re.search(r'```python\n(.+?)\n```', raw, re.DOTALL)
        code = code_match.group(1) if code_match else raw.strip()

        # Detecta imports
        imports = re.findall(r'^\s*(?:import|from)\s+\S+', code, re.MULTILINE)

        # Detecta main() e docstring
        has_main = bool(re.search(r'def\s+main\s*\(', code))
        has_docstring = bool(re.search(r'"""', code) or re.search(r"'''", code))

        # Valida segurança
        safety = self.safety_validator.validate(code)

        try:
            result = GeneratedCode(
                code=code,
                language="python",
                has_main=has_main,
                has_docstring=has_docstring,
                imports=imports,
                is_safe=safety.is_safe,
                safety_issues=safety.issues,
            )
            logger.info(
                f"✅ Código validado: "
                f"main={result.has_main}, "
                f"docstring={result.has_docstring}, "
                f"imports={len(result.imports)}, "
                f"safe={result.is_safe}"
            )
            return result
        except ValidationError as e:
            logger.warning(f"⚠️  Validação Pydantic falhou: {e}")
            # Fallback: código mínimo
            return GeneratedCode(
                code="# Código não pôde ser gerado\nprint('Erro na geração')",
                language="python",
                has_main=False,
                has_docstring=False,
                imports=[],
                is_safe=False,
                safety_issues=["Validação Pydantic falhou"],
            )
