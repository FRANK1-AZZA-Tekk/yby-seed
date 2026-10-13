# Lista de apps e repositórios do YBY SEED

Este documento define as ferramentas recomendadas para o YBY SEED no Ubuntu 26.04 LTS, separadas entre **uso inicial**, **futuras** e **avaliação posterior**.

## Critérios de adoção

Uma ferramenta só entra na stack quando atender a estes critérios:

1. Resolve uma necessidade real do YBY SEED.
2. É compatível com o PC Hub: Ryzen 5 4600G, 16 GB RAM, GTX 1650 4 GB VRAM e SSD.
3. Possui documentação ativa e comunidade confiável.
4. Pode ser testada isoladamente antes de entrar em produção.
5. Não adiciona dependência pesada sem benefício mensurável.
6. Possui caminho claro de instalação, atualização e remoção.

## Stack inicial

Estas ferramentas formam a base mínima para desenvolver, testar e executar o YBY SEED.

| # | Ferramenta | Categoria | Função no YBY | Status |
|---:|---|---|---|---|
| 1 | Visual Studio Code | Desenvolvimento | Editor principal, depuração e extensões Python | Inicial |
| 2 | Cursor Pro | Desenvolvimento assistido | Planejamento, revisão, refatoração e geração de testes | Inicial |
| 3 | Git | Versionamento | Histórico, branches, commits e reversão segura | Inicial |
| 4 | GitHub CLI | Versionamento | Pull Requests, issues, CI e automação do GitHub | Inicial |
| 5 | Docker | Infraestrutura | Containers isolados para serviços do YBY | Inicial |
| 6 | Docker Compose | Infraestrutura | Sobe Qdrant, PostgreSQL e Redis juntos | Inicial |
| 7 | tmux | Terminal | Sessões persistentes para API, logs e serviços | Inicial |
| 8 | fzf | Terminal | Busca fuzzy de arquivos, comandos e histórico | Inicial |
| 9 | ripgrep | Terminal | Busca rápida no código-fonte | Inicial |
| 10 | bat | Terminal | Leitura de arquivos com syntax highlight | Inicial |
| 11 | jq | Terminal | Leitura e filtragem de JSON | Inicial |
| 12 | HTTPie | Testes | Testes rápidos de API | Inicial |
| 13 | uv | Python | Criação de ambientes e instalação de dependências | Inicial |
| 14 | Pytest | Qualidade | Testes unitários e de integração | Inicial |
| 15 | pytest-asyncio | Qualidade | Testes de funções assíncronas | Inicial |
| 16 | pytest-cov | Qualidade | Medição de cobertura de testes | Inicial |
| 17 | Ruff | Qualidade | Lint e verificação estática rápida | Inicial |
| 18 | Black | Qualidade | Formatação automática de Python | Inicial |
| 19 | mypy | Qualidade | Verificação de tipos | Inicial |
| 20 | pre-commit | Qualidade | Verificações automáticas antes do commit | Inicial |
| 21 | Pydantic | Qualidade | Validação de configurações, planos e respostas | Inicial |
| 22 | Ollama | IA local | Execução local de LLMs na GTX 1650 | Inicial |
| 23 | LiteLLM | IA | Interface unificada para Ollama e OpenRouter | Inicial |
| 24 | FastAPI | API | Exposição dos agentes e serviços do YBY via HTTP | Inicial |
| 25 | Qdrant | RAG | Banco vetorial local para busca semântica | Inicial |

## Ferramentas futuras

Entram somente após a stack inicial estar estável, testada e documentada.

| # | Ferramenta | Categoria | Função futura no YBY | Quando adotar |
|---:|---|---|---|---|
| 26 | PostgreSQL | Banco de dados | Histórico, usuários, execuções e metadados | Quando o YBY precisar persistir estado |
| 27 | Redis | Cache e filas | Cache de respostas, filas e limites de requisição | Quando houver repetição de chamadas ou tarefas assíncronas |
| 28 | LlamaIndex | RAG | Ingestão e indexação de documentos | Quando houver base documental real |
| 29 | sentence-transformers | RAG | Geração local de embeddings | Junto da primeira implementação de RAG |
| 30 | rank-bm25 | RAG | Busca lexical para RAG híbrido | Quando a busca semântica precisar de complemento lexical |
| 31 | LangGraph | Agentes | Orquestração de fluxos com estados e decisões | Quando o fluxo Router → Planning → Validation → Execution ficar complexo |
| 32 | Pydantic AI | Agentes | Agentes com saída estruturada e validada | Quando respostas de LLM precisarem de contrato rígido |
| 33 | Prometheus | Observabilidade | Coleta de métricas | Quando a API estiver em execução contínua |
| 34 | Grafana | Observabilidade | Dashboards de latência, erros e recursos | Junto do Prometheus |
| 35 | Portainer | Infraestrutura | Administração visual de containers | Quando houver muitos containers locais |
| 36 | Podman | Infraestrutura | Alternativa ao Docker sem daemon central | Se Docker representar limitação operacional |
| 37 | Poetry | Python | Gestão alternativa de dependências e packaging | Somente se substituir uv de forma justificada |
| 38 | Zsh + Oh My Zsh | Terminal | Produtividade no terminal | Opcional, conforme preferência |
| 39 | Postman | Testes | Coleções visuais de requisições | Opcional; HTTPie já cobre testes básicos |
| 40 | Mem0 | Memória de agentes | Memória persistente entre sessões | Quando houver requisito real de personalização e privacidade |

## Repositórios para avaliação futura

Estes projetos devem ser avaliados antes de qualquer adoção. Não devem ser instalados apenas por popularidade.

| # | Repositório | Função potencial | Avaliação |
|---:|---|---|---|
| 41 | LangChain | Orquestração de LLMs, tools e integrações | Avaliar apenas se LangGraph e LlamaIndex não atenderem |
| 42 | CrewAI | Agentes colaborativos com papéis | Avaliar para fluxos multiagente reais |
| 43 | AutoGen | Agentes conversacionais e revisão cruzada | Avaliar para revisão automática de planos |
| 44 | Agno | Framework leve de agentes | Avaliar como alternativa leve ao LangChain |
| 45 | OpenAI Agents SDK | Agentes com tools e instruções | Avaliar se OpenAI for provedor principal |
| 46 | Semantic Kernel | Orquestração corporativa de IA | Avaliar apenas para integração Microsoft/Azure |
| 47 | ChromaDB | Banco vetorial simples | Avaliar para protótipos rápidos |
| 48 | pgvector | Busca vetorial no PostgreSQL | Avaliar se um único banco relacional for preferível |
| 49 | RAGFlow | Plataforma completa de RAG | Avaliar apenas se o RAG interno não atender |
| 50 | FlashRAG | Toolkit de experimentação em RAG | Avaliar para benchmarks e comparação de abordagens |

## Ordem de adoção recomendada

### Fase 1 — base

```text
VS Code
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

### Fase 2 — persistência e RAG

```text
PostgreSQL
Redis
LlamaIndex
sentence-transformers
rank-bm25
```

### Fase 3 — orquestração e observabilidade

```text
LangGraph
Pydantic AI
Prometheus
Grafana
Portainer
```

### Fase 4 — avaliação sob demanda

```text
LangChain
CrewAI
AutoGen
Agno
OpenAI Agents SDK
Semantic Kernel
ChromaDB
pgvector
RAGFlow
FlashRAG
Mem0
Poetry
Zsh + Oh My Zsh
Postman
Podman
```

## Regras para o PC Hub

- Use a GTX 1650 de 4 GB principalmente para modelos pequenos, como `llama3.2:3b`.
- Use a GPU integrada do Ryzen 5 4600G para desktop e tarefas leves.
- Não execute vários modelos grandes simultaneamente.
- Use OpenRouter para tarefas complexas, contexto longo ou fallback do Ollama.
- Rode Qdrant, PostgreSQL e Redis via Docker Compose, com limites de memória definidos.
- Não adote LangChain, CrewAI, AutoGen, RAGFlow ou FlashRAG sem necessidade concreta.

## Checklist antes de adicionar qualquer app

- [ ] Existe um problema real que a ferramenta resolve?
- [ ] Há teste ou métrica que comprove o benefício?
- [ ] A ferramenta cabe nos 16 GB de RAM e na GTX 1650 de 4 GB?
- [ ] Existe documentação oficial atualizada?
- [ ] É possível remover a ferramenta sem quebrar o YBY?
- [ ] A mudança foi documentada em um Pull Request?
- [ ] O custo de manutenção é menor que o benefício?
