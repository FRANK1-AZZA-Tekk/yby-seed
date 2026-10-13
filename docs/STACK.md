# Stack de ferramentas do YBY SEED

Este documento define a stack oficial e consolidada do YBY SEED para Ubuntu 26.04 LTS.

## Perfil do PC Hub

- CPU: AMD Ryzen 5 4600G
- RAM: 16 GB DDR4
- GPU dedicada: NVIDIA GTX 1650, 4 GB VRAM
- GPU integrada: Radeon Graphics do Ryzen 5 4600G
- Armazenamento: SSD
- Sistema: Ubuntu 26.04 LTS
- Estratégia: local-first, com OpenRouter como fallback

## Arquitetura da stack

```text
YBY App
   ↓
FastAPI
   ↓
YBY Core
   ↓
LangGraph + Pydantic AI
   ↓
LiteLLM
   ├── Ollama local
   └── OpenRouter fallback
   ↓
LlamaIndex + Qdrant
   ↓
PostgreSQL + Redis
```

## Ferramentas selecionadas

### Desenvolvimento

| Ferramenta | Função no YBY | Status |
|---|---|---|
| Cursor Pro | Planejamento, revisão, refatoração e testes assistidos | Selecionada |
| Git | Histórico, branches e reversão | Selecionada |
| GitHub CLI | PRs, issues, CI e automação GitHub | Selecionada |
| Docker | Isolamento de serviços | Selecionada |
| Docker Compose | Orquestração local | Selecionada |
| tmux | Sessões persistentes | Selecionada |
| fzf | Busca fuzzy | Selecionada |
| ripgrep | Busca no código | Selecionada |
| bat | Leitura de arquivos | Selecionada |
| jq | Manipulação de JSON | Selecionada |
| HTTPie | Testes de API | Selecionada |

### Qualidade Python

| Ferramenta | Função no YBY | Status |
|---|---|---|
| uv | Ambientes e dependências | Selecionada |
| Pytest | Testes automatizados | Selecionada |
| pytest-asyncio | Testes assíncronos | Selecionada |
| pytest-cov | Cobertura de testes | Selecionada |
| Ruff | Lint e formatação | Selecionada |
| Black | Formatação Python | Selecionada |
| mypy | Verificação de tipos | Selecionada |
| pre-commit | Hooks de qualidade | Selecionada |
| Pydantic | Validação de dados | Selecionada |

### IA e agentes

| Ferramenta | Função no YBY | Status |
|---|---|---|
| Ollama | IA local | Selecionada |
| LiteLLM | Roteamento Ollama + OpenRouter | Selecionada |
| OpenRouter | Fallback na nuvem | Selecionada |
| LangGraph | Orquestração de agentes | Selecionada |
| Pydantic AI | Agentes com saída validada | Selecionada |
| smolagents | Agentes leves | Selecionada |

### RAG e conhecimento

| Ferramenta | Função no YBY | Status |
|---|---|---|
| LlamaIndex | Ingestão e indexação | Selecionada |
| Qdrant | Banco vetorial | Selecionada |
| sentence-transformers | Embeddings locais | Selecionada |
| rank-bm25 | Busca lexical | Selecionada |
| Docling | Conversão de documentos | Selecionada |
| olmOCR | OCR de PDFs escaneados | Selecionada condicional |

### Serviços e observabilidade

| Ferramenta | Função no YBY | Status |
|---|---|---|
| FastAPI | API do YBY | Selecionada |
| PostgreSQL | Histórico e estado | Selecionada |
| Redis | Cache e filas | Selecionada |
| Prometheus | Métricas | Selecionada |
| Grafana | Dashboards | Selecionada |
| Open WebUI | Interface de teste | Selecionada |
| Whisper | Transcrição de voz | Selecionada condicional |
| Piper | Text-to-speech | Selecionada condicional |
| spaCy | NLP leve | Selecionada condicional |

### MCP Servers

| Ferramenta | Função no YBY | Status |
|---|---|---|
| MCP Filesystem | Acesso a arquivos | Selecionada |
| MCP Fetch | Leitura de web | Selecionada |
| MCP Git | Operações Git | Selecionada |
| MCP GitHub | GitHub | Selecionada |
| MCP Brave Search | Busca web | Selecionada |

## Fases de adoção

### Fase 1 — base obrigatória

```text
Cursor Pro
Git
GitHub CLI
Docker + Compose
tmux
fzf
ripgrep
bat
jq
HTTPie
uv
Pytest
pytest-asyncio
pytest-cov
Ruff
Black
mypy
pre-commit
Pydantic
Ollama
LiteLLM
FastAPI
Qdrant
```

### Fase 2 — agentes e tools

```text
LangGraph
Pydantic AI
smolagents
MCP Filesystem
MCP Fetch
MCP Git
MCP GitHub
MCP Brave Search
```

### Fase 3 — RAG e persistência

```text
LlamaIndex
sentence-transformers
rank-bm25
Docling
olmOCR
PostgreSQL
Redis
```

### Fase 4 — interface, voz e métricas

```text
Open WebUI
Whisper
Piper
Prometheus
Grafana
spaCy
```

## Ferramentas removidas da stack principal

Estas ferramentas não entram por padrão. Podem ser avaliadas apenas quando houver necessidade concreta.

| Ferramenta | Substituída por | Motivo |
|---|---|---|
| VS Code | Cursor Pro | Cursor cobre edição assistida |
| Poetry | uv | uv é mais leve |
| LangChain | LangGraph + LlamaIndex | Evita sobreposição |
| CrewAI | LangGraph | Só para multiagente real |
| AutoGen | LangGraph | Só para revisão cruzada avançada |
| Agno | LangGraph + Pydantic AI | Redundante |
| OpenAI Agents SDK | LiteLLM + LangGraph | Acoplamento a OpenAI |
| Semantic Kernel | LangGraph | Foco Microsoft/Azure |
| ChromaDB | Qdrant | Qdrant é mais robusto |
| pgvector | Qdrant | Evita misturar funções no PostgreSQL |
| txtai | LlamaIndex + Qdrant | Redundante |
| RAGFlow | LlamaIndex + Qdrant | Muito pesado |
| FlashRAG | LlamaIndex + Qdrant | Benchmark |
| MinerU | Docling | Docling cobre maioria |
| Unstructured | Docling | Só para muitos formatos |
| PaddleOCR | olmOCR | olmOCR cobre caso inicial |
| GPT Researcher | MCP Fetch + Brave | MCP cobre busca básica |
| OpenHands | YBY Core + MCP | Exige isolamento |
| Podman | Docker | Docker atende |
| Portainer | Docker CLI | Opcional |
| Postman | HTTPie | HTTPie cobre testes |
| Zsh + Oh My Zsh | Bash | Conforto |

## Regras para o PC Hub

- Use Ollama para dados sensíveis e tarefas simples.
- Use OpenRouter para tarefas complexas ou fallback.
- Use modelos pequenos na GTX 1650, como llama3.2:3b.
- Use Docker Compose para Qdrant, PostgreSQL e Redis.
- Não rode vários modelos grandes ao mesmo tempo.
- Não adote múltiplos frameworks de agentes ao mesmo tempo.
- Não adote múltiplas soluções de RAG, OCR ou banco vetorial para a mesma função.

## Checklist antes de adicionar ferramenta

- [ ] Resolve problema real?
- [ ] Há teste ou métrica?
- [ ] Cabe no hardware?
- [ ] Não duplica função?
- [ ] Tem documentação?
- [ ] É removível?
- [ ] Está em PR?
- [ ] Custo < benefício?
