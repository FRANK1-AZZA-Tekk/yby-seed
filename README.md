# YBY SEED

**YBY SEED** é um exocórtex de IA distribuído, open-source e local-first para automações educacionais e industriais, usando Programação em Linguagem Natural (NLP).

## Visão Geral

YBY SEED permite que você descreva automações em linguagem natural e o sistema:

1. **Classifica** a intenção (RouterAgent)
2. **Planeja** a automação via entrevista (PlanningAgent)
3. **Gera** código Python (ExecutionAgent)
4. **Valida** segurança do código (CodeSafetyValidator)
5. **Enriquece** contexto com RAG (opcional)

## Fluxo Completo

```text
CLI → OllamaClient (health check) → RouterAgent.classify()
  ├─ planning → PlanningAgent.interview() → PRD
  │    └─ ExecutionAgent.generate_with_rag(PRD, rag_chunks) → código
  └─ execution → ExecutionAgent.generate_with_rag(pergunta, rag_chunks) → resposta
```

## Instalação

```bash
# Clone o repositório
git clone https://github.com/FRANK1-AZZA-Tekk/yby-seed.git
cd yby-seed

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure pre-commit
pre-commit install
```

## Uso

### Comando básico

```bash
python src/main.py run --command "Crie um script de backup"
```

### Com RAG (contexto enriquecido)

```bash
python src/main.py run --command "Crie um script de backup" --rag
```

### Especificando host/porta do Ollama

```bash
python src/main.py run --command "Crie um script de backup" --host localhost --port 11434
```

## RAG (Retrieval-Augmented Generation)

O RAG enriquece o contexto do `ExecutionAgent` com chunks relevantes recuperados de uma base de conhecimento.

### Como funciona

1. Quando você usa `--rag`, o `RAGOptimizer` é instanciado
2. O `RAGOptimizer.retrieve()` busca chunks relevantes para o comando
3. Os chunks são passados como contexto adicional ao `ExecutionAgent`
4. O `ExecutionAgent.generate_with_rag()` usa o contexto para gerar código mais preciso

### Quando usar RAG

- Quando você tem documentação, exemplos de código ou conhecimento específico que quer que o agente considere
- Quando o comando é complexo e se beneficia de contexto adicional
- Quando você quer melhorar a precisão do código gerado

### Exemplo

```bash
# Sem RAG
python src/main.py run --command "Crie um script de backup"

# Com RAG (usa base de conhecimento)
python src/main.py run --command "Crie um script de backup" --rag
```

## Validação de Segurança

Todo código gerado pelo `ExecutionAgent` passa por uma validação de segurança antes de ser exibido ou executado.

### O que é validado

1. **Sintaxe Python** — usa `ast.parse` para verificar se o código é sintaticamente válido
2. **Imports perigosos** — detecta imports como `subprocess`, `socket`, `ctypes`, `multiprocessing`
3. **Chamadas perigosas** — detecta chamadas como `eval`, `exec`, `compile`, `__import__`, `open`, `input`

### Resultado da validação

O `GeneratedCode` inclui campos de segurança:

- `is_safe` — se o código passou na validação
- `safety_issues` — lista de problemas detectados
- `dangerous_imports` — imports perigosos encontrados
- `dangerous_calls` — chamadas perigosas encontradas

### Exemplo de saída

```json
{
  "code": "print('hello')",
  "language": "python",
  "has_main": false,
  "has_docstring": false,
  "imports": [],
  "is_safe": true,
  "safety_issues": []
}
```

### Exemplo de código com problema

```json
{
  "code": "import subprocess\nsubprocess.run(['ls'])",
  "language": "python",
  "has_main": false,
  "has_docstring": false,
  "imports": ["import subprocess"],
  "is_safe": false,
  "safety_issues": ["Import perigoso detectado: subprocess"]
}
```

## Arquitetura

```text
src/
├── agents/
│   ├── router_agent.py       # Classifica intenção
│   ├── planning_agent.py     # Entrevista e gera PRD
│   ├── execution_agent.py    # Gera código Python
│   └── ...
├── core/
│   └── ollama_client.py      # Cliente Ollama com timeout
├── rag/
│   ├── rag_optimizer.py      # Otimização RAG
│   ├── ast_chunker.py        # Chunking AST
│   └── context_pruner.py     # Poda de contexto
├── security/
│   └── code_safety_validator.py  # Validação de segurança
└── main.py                    # CLI principal
```

## Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Rodar testes de um módulo específico
pytest tests/test_ollama_client.py -v
pytest tests/test_router_agent_pydantic.py -v
pytest tests/test_planning_agent_pydantic.py -v
pytest tests/test_execution_agent_pydantic.py -v
pytest tests/test_code_safety_validator.py -v
pytest tests/test_fluxo_completo_integracao.py -v
```

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes sobre como contribuir.

## Licença

Veja [LICENSE](LICENSE) para detalhes.
