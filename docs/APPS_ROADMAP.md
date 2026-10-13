# Lista consolidada de apps e repositórios do YBY SEED

Este documento é a referência única de ferramentas do YBY SEED no Ubuntu 26.04 LTS. Ele substitui a lista anterior, removendo redundâncias e priorizando um stack local-first adequado ao PC Hub.

## Perfil do PC Hub

- CPU: AMD Ryzen 5 4600G
- RAM: 16 GB DDR4
- GPU dedicada: NVIDIA GTX 1650, 4 GB VRAM
- GPU integrada: Radeon Graphics do Ryzen 5 4600G
- Armazenamento: SSD
- Sistema: Ubuntu 26.04 LTS
- Estratégia: local-first, com OpenRouter como fallback

## Critérios de adoção

Uma ferramenta entra na stack somente se:

1. Resolver uma necessidade real do YBY SEED.
2. Rodar bem com 16 GB RAM e GTX 1650 de 4 GB VRAM.
3. Ter documentação ativa e licença adequada.
4. Poder ser testada isoladamente.
5. Não duplicar função de outra ferramenta já escolhida.
6. Ter caminho claro de instalação, atualização e remoção.
7. Justificar custo de manutenção e consumo de recursos.

## Decisões de deduplicação

| Função | Escolha principal | Removido da lista principal | Motivo |
|---|---|---|---|
| Editor com IA | Cursor Pro | VS Code como obrigatório | Cursor já cobre edição e assistência; VS Code permanece opcional |
| Gerenciamento Python | uv | Poetry | uv é mais leve e cobre o fluxo atual |
| Framework de agentes | LangGraph + Pydantic AI | LangChain, CrewAI, AutoGen, Agno, OpenAI Agents SDK, Semantic Kernel | Evita sobreposição de orquestradores |
| RAG | Qdrant + LlamaIndex + sentence-transformers + rank-bm25 | ChromaDB, pgvector, txtai, RAGFlow, FlashRAG | Uma stack de RAG clara evita duplicação |
| OCR e documentos | Docling + olmOCR | MinerU, Unstructured, PaddleOCR | Docling cobre conversão estruturada; olmOCR cobre PDF escaneado |
| Busca web | MCP Fetch + MCP Brave Search | GPT Researcher | MCP já oferece busca controlada; GPT Researcher é avaliação futura |
| Interface de teste de LLM | Open WebUI | Postman para testes de LLM | Open WebUI é mais direto para Ollama |
| Containers | Docker + Compose | Podman, Portainer | Docker Compose cobre o MVP; alternativas são opcionais |

## Stack final consolidada

### Fase 1 — base obrigatória

| # | Ferramenta | Categoria | Função no YBY | Status |
|---:|---|---|---|---|
| 1 | Cursor Pro | Desenvolvimento assistido | Planejamento, revisão, refatoração e testes | Inicial |
| 2 | Git | Versionamento | Histórico, branches, commits e reversão | Inicial |
| 3 | GitHub CLI | Versionamento | PRs, issues, CI e automação GitHub | Inicial |
| 4 | Docker | Infraestrutura | Containers isolados | Inicial |
| 5 | Docker Compose | Infraestrutura | Orquestração local dos serviços | Inicial |
| 6 | tmux | Terminal | Sessões persistentes | Inicial |
| 7 | fzf | Terminal | Busca fuzzy | Inicial |
| 8 | ripgrep | Terminal | Busca rápida no código | Inicial |
| 9 | bat | Terminal | Leitura de código no terminal | Inicial |
| 10 | jq | Terminal | Manipulação de JSON | Inicial |
| 11 | HTTPie | Testes | Testes rápidos de API | Inicial |
| 12 | uv | Python | Ambientes e dependências | Inicial |
| 13 | Pytest | Qualidade | Testes unitários e integração | Inicial |
| 14 | pytest-asyncio | Qualidade | Testes assíncronos | Inicial |
| 15 | pytest-cov | Qualidade | Cobertura de testes | Inicial |
| 16 | Ruff | Qualidade | Lint e formatação rápida | Inicial |
| 17 | Black | Qualidade | Formatação Python | Inicial |
| 18 | mypy | Qualidade | Verificação de tipos | Inicial |
| 19 | pre-commit | Qualidade | Hooks de qualidade | Inicial |
| 20 | Pydantic | Qualidade | Validação de dados e contratos | Inicial |
| 21 | Ollama | IA local | Modelos locais na GTX 1650 | Inicial |
| 22 | LiteLLM | IA | Roteamento unificado Ollama + OpenRouter | Inicial |
| 23 | FastAPI | API | API do YBY | Inicial |
| 24 | Qdrant | RAG | Busca vetorial local | Inicial |

### Fase 2 — agentes e ferramentas seguras

| # | Ferramenta | Categoria | Função no YBY | Quando adotar |
|---:|---|---|---|---|
| 25 | LangGraph | Agentes | Orquestração de fluxo Router → Planner → Validator → Executor | Quando o fluxo ficar complexo |
| 26 | Pydantic AI | Agentes | Agentes com saída estruturada e validada | Quando respostas de LLM exigirem contrato rígido |
| 27 | smolagents | Agentes | Agentes leves que executam código com controle | Para skills simples e experimentos controlados |
| 28 | MCP Filesystem Server | Tools | Acesso controlado a arquivos locais | Para automações de arquivos |
| 29 | MCP Fetch Server | Tools | Leitura e conversão de páginas web | Para pesquisa e documentação |
| 30 | MCP Git Server | DevOps | Operações seguras em repositórios Git | Para auditoria e automação de código |
| 31 | MCP GitHub Server | DevOps | Issues, PRs e busca de código | Para automação do fluxo GitHub |
| 32 | MCP Brave Search Server | Pesquisa | Busca web com fontes | Para pesquisa atualizada |

### Fase 3 — conhecimento e documentos

| # | Ferramenta | Categoria | Função no YBY | Quando adotar |
|---:|---|---|---|---|
| 33 | LlamaIndex | RAG | Ingestão e indexação de documentos | Quando houver base documental real |
| 34 | sentence-transformers | RAG | Geração local de embeddings | Junto do primeiro RAG |
| 35 | rank-bm25 | RAG | Busca lexical para RAG híbrido | Quando busca semântica precisar de complemento |
| 36 | Docling | Documentos | Conversão estruturada de PDFs e documentos | Para indexar documentos complexos |
| 37 | olmOCR | OCR | Extração de texto de PDFs escaneados | Quando houver documentos digitalizados |
| 38 | PostgreSQL | Banco de dados | Histórico, usuários, execuções e metadados | Quando o YBY precisar persistir estado |
| 39 | Redis | Cache e filas | Cache, filas e limites de requisição | Quando houver repetição ou tarefas assíncronas |

### Fase 4 — interface, voz e observabilidade

| # | Ferramenta | Categoria | Função no YBY | Quando adotar |
|---:|---|---|---|---|
| 40 | Open WebUI | Interface | Teste visual de modelos Ollama | Para validar modelos antes da interface própria |
| 41 | Whisper | Voz | Transcrição local de áudio | Para comandos por voz |
| 42 | Piper | Voz | Text-to-speech local | Para respostas faladas |
| 43 | Prometheus | Observabilidade | Coleta de métricas | Quando a API rodar continuamente |
| 44 | Grafana | Observabilidade | Dashboards de saúde e desempenho | Junto do Prometheus |
| 45 | spaCy | NLP | Extração de entidades e pré-processamento | Para automações de texto estruturado |

## Repositórios para avaliação futura

Estes itens não entram na stack por padrão. Devem ser avaliados apenas quando houver requisito concreto.

| # | Repositório | Função potencial | Critério para adoção |
|---:|---|---|---|
| 46 | LangChain | Orquestração ampla de LLMs | Somente se LangGraph e LlamaIndex não atenderem |
| 47 | CrewAI | Agentes colaborativos | Somente para fluxos multiagente reais |
| 48 | AutoGen | Agentes conversacionais | Somente para revisão cruzada avançada |
| 49 | Agno | Framework leve de agentes | Somente se substituir LangGraph com ganho real |
| 50 | OpenAI Agents SDK | Agentes com tools | Somente se OpenAI for provedor principal |
| 51 | Semantic Kernel | Orquestração corporativa | Somente para integração Microsoft/Azure |
| 52 | ChromaDB | Banco vetorial simples | Somente para protótipos descartáveis |
| 53 | pgvector | Vetores no PostgreSQL | Somente se um único banco for preferível |
| 54 | RAGFlow | Plataforma completa de RAG | Somente se o RAG interno não atender |
| 55 | FlashRAG | Experimentação em RAG | Somente para benchmarks |
| 56 | MinerU | Extração avançada de PDF | Somente se Docling não atender layouts complexos |
| 57 | Unstructured | ETL multiformato | Somente para muitos formatos distintos |
| 58 | PaddleOCR | OCR multilíngue | Somente se olmOCR não atender |
| 59 | txtai | RAG leve | Somente para protótipos muito leves |
| 60 | GPT Researcher | Pesquisa web automatizada | Somente se MCP Fetch + Brave não atenderem |
| 61 | OpenHands | Agente autônomo de código | Somente em ambiente isolado e com aprovação humana |
| 62 | Podman | Alternativa a Docker | Somente se Docker representar limitação |
| 63 | Portainer | Administração visual de containers | Somente se houver muitos containers |
| 64 | Poetry | Gestão de dependências | Somente se substituir uv com justificativa |
| 65 | Postman | Testes visuais de API | Opcional; HTTPie cobre o essencial |
| 66 | VS Code | Editor tradicional | Opcional; Cursor já cobre edição assistida |
| 67 | Zsh + Oh My Zsh | Produtividade no terminal | Opcional |

## Ordem de adoção

### Fase 1 — começar agora

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

## Regras para o PC Hub

- Use a GTX 1650 de 4 GB principalmente para modelos pequenos, como `llama3.2:3b`.
- Use a GPU integrada do Ryzen 5 4600G para desktop e tarefas leves.
- Não execute vários modelos grandes simultaneamente.
- Use OpenRouter para tarefas complexas, contexto longo ou fallback.
- Prefira Ollama para dados sensíveis e tarefas simples.
- Rode Qdrant, PostgreSQL e Redis via Docker Compose.
- Não adote múltiplos frameworks de agentes ao mesmo tempo.
- Não adote múltiplas soluções de RAG, OCR ou banco vetorial para a mesma função.

## Checklist antes de adicionar qualquer app

- [ ] Existe um problema real que a ferramenta resolve?
- [ ] Há teste ou métrica que comprove o benefício?
- [ ] A ferramenta cabe nos 16 GB de RAM e na GTX 1650 de 4 GB?
- [ ] Não duplica função de outra ferramenta já adotada?
- [ ] Existe documentação oficial atualizada?
- [ ] É possível remover sem quebrar o YBY?
- [ ] A mudança está documentada em um Pull Request?
- [ ] O custo de manutenção é menor que o benefício?
