#!/usr/bin/env python3
"""
Execution Agent - Gera código Python baseado no PRD

Uso:
    executor = ExecutionAgent(ollama_client)
    code = executor.generate(prd_text)
"""

import os
from typing import List, Optional

from loguru import logger

from src.core.ollama_client import OllamaClient
from src.engine.config import DEFAULT_LOCAL_MODEL


class ExecutionAgent:
    """Agente de execução. O modelo sai de YBY_LOCAL_MODEL."""

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

    def __init__(self, ollama: OllamaClient, model: str | None = None):
        self.ollama = ollama
        configured = os.getenv("YBY_LOCAL_MODEL", DEFAULT_LOCAL_MODEL).strip()
        self.model = model or configured or DEFAULT_LOCAL_MODEL
        logger.info("⚙️  Execution Agent inicializado")

    def generate(self, prd: str, context: Optional[str] = None) -> str:
        """Gera código Python baseado no PRD"""

        logger.info("📝 Gerando código Python...")

        extra = f"Contexto adicional:\n{context}" if context else ""
        prompt = f"""
PRD:
{prd}

{extra}

Gere o código Python completo e funcional.
Inclua TODOS os imports necessários.
"""

        code = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={"temperature": 0.2, "num_predict": 4096, "top_p": 0.9},
        )

        # Extrai código do bloco Markdown
        import re

        code_match = re.search(r"```python\n(.+?)\n```", code, re.DOTALL)

        if code_match:
            code = code_match.group(1)

        logger.info("✅ Código gerado")
        return code

    def generate_with_rag(self, prd: str, rag_chunks: List[str]) -> str:
        """Gera código com contexto RAG"""

        logger.info(f"📚 Gerando código com {len(rag_chunks)} chunks RAG...")

        context = "\n\n".join([f"Chunk {i + 1}:\n{chunk}" for i, chunk in enumerate(rag_chunks)])

        return self.generate(prd, context)
