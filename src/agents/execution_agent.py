#!/usr/bin/env python3
"""
Execution Agent - Gera código Python baseado no PRD

Uso:
    executor = ExecutionAgent(ollama_client)
    code = executor.generate(prd_text)
"""

from typing import Optional, List
from loguru import logger
from src.core.ollama_client import OllamaClient


class ExecutionAgent:
    """Agente de execução baseado em Qwen2.5-Coder 7B"""
    
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
        logger.info("⚙️  Execution Agent inicializado")
    
    def generate(
        self,
        prd: str,
        context: Optional[str] = None
    ) -> str:
        """Gera código Python baseado no PRD"""
        
        logger.info("📝 Gerando código Python...")
        
        prompt = f"""
PRD:
{prd}

{f'Contexto adicional:\n{context}' if context else ''}

Gere o código Python completo e funcional.
Inclua TODOS os imports necessários.
"""
        
        code = self.ollama.generate(
            model=self.model,
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            options={
                "temperature": 0.2,
                "num_predict": 4096,
                "top_p": 0.9
            }
        )
        
        # Extrai código do bloco Markdown
        import re
        code_match = re.search(r'```python\n(.+?)\n```', code, re.DOTALL)
        
        if code_match:
            code = code_match.group(1)
        
        logger.info("✅ Código gerado")
        return code
    
    def generate_with_rag(
        self,
        prd: str,
        rag_chunks: List[str]
    ) -> str:
        """Gera código com contexto RAG"""
        
        logger.info(f"📚 Gerando código com {len(rag_chunks)} chunks RAG...")
        
        context = "\n\n".join([
            f"Chunk {i+1}:\n{chunk}"
            for i, chunk in enumerate(rag_chunks)
        ])
        
        return self.generate(prd, context)
