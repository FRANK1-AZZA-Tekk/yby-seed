# YBY Core — Framework único do YBY SEED

## Objetivo

O YBY Core é o orquestrador central do YBY SEED. Ele cria a experiência de **um único app**, enquanto mantém serviços especializados isolados por trás.

O usuário interage apenas com o YBY. Os serviços — Ollama, OpenRouter, LiteLLM, Qdrant, PostgreSQL, Redis e Docker — permanecem como infraestrutura gerenciada.

## Princípio

```text
Uma interface.
Um comando para subir.
Um cérebro central.
Vários serviços isolados.
```

## Arquitetura

```text
┌──────────────────────────────┐
│           YBY App            │
│  Terminal / Web / Painel     │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│          FastAPI             │
│ /chat /automations /health   │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│          YBY Core            │
│ Router → Planner → Validator │
│         → Executor           │
└───────┬───────────┬──────────┘
        │           │
┌───────▼─────┐ ┌───▼──────────┐
│   LiteLLM   │ │   Qdrant     │
│ Ollama/Cloud│ │   Memória    │
└─────────────┘ └──────────────┘
        │
┌───────▼──────────────────────┐
│ PostgreSQL + Redis + Docker  │
└──────────────────────────────┘
```

## Responsabilidades

| Componente | Responsabilidade |
|---|---|
| YBY App | Interface do usuário: terminal, web ou painel |
| FastAPI | API HTTP, validação de entrada e endpoints |
| YBY Core | Orquestra agentes, automações e serviços |
| Router Agent | Classifica intenção e solicita esclarecimento |
| Planning Agent | Seleciona skill e cria plano |
| Validation Agent | Valida segurança antes da execução |
| Execution Agent | Executa skills com timeout e limites |
| LiteLLM | Roteia entre Ollama local e OpenRouter |
| Ollama | Executa modelos locais na GTX 1650 |
| OpenRouter | Fallback e modelos maiores na nuvem |
| Qdrant | Memória semântica e busca vetorial |
| PostgreSQL | Histórico, usuários, execuções e metadados |
| Redis | Cache, filas e controle de concorrência |
| Docker Compose | Sobe, isola e monitora os serviços |

## Fluxo principal

```text
Usuário escreve comando
        ↓
FastAPI recebe
        ↓
RouterAgent classifica
        ↓
PlanningAgent cria plano
        ↓
ValidationAgent verifica segurança
        ↓
ExecutionAgent executa
        ↓
PostgreSQL registra histórico
        ↓
Qdrant guarda conhecimento
        ↓
Resposta volta ao usuário
```

## Comandos do usuário

```bash
yby up          # sobe Docker, serviços e API
yby down        # para serviços com segurança
yby chat        # abre conversa com o YBY
yby doctor      # verifica saúde do sistema
yby dashboard   # abre painel local
yby test        # executa testes
```

## Endpoints iniciais

| Método | Endpoint | Função |
|---|---|---|
| GET | `/health` | Verifica API e serviços |
| POST | `/chat` | Conversa e execução de comandos |
| GET | `/automations` | Lista automações |
| POST | `/automations` | Cria automação aprovada |
| GET | `/memory/search` | Busca semântica |
| POST | `/memory/index` | Indexa documento aprovado |
| GET | `/models` | Lista modelos locais e remotos |

## Regras de segurança

1. Ações destrutivas exigem confirmação explícita do usuário.
2. Skills só podem executar a partir de diretórios permitidos.
3. Toda execução deve ter timeout, limite de CPU, memória e tamanho de saída.
4. Segredos nunca devem ficar no repositório.
5. Dados sensíveis devem preferir execução local via Ollama.
6. OpenRouter é fallback, não destino padrão de dados sensíveis.
7. Toda automação deve registrar histórico, resultado e erro.
8. Nenhum serviço deve iniciar antes de passar no healthcheck.

## Estrutura proposta

```text
yby-seed/
├── src/
│   ├── yby/
│   │   ├── cli.py
│   │   ├── core.py
│   │   ├── router.py
│   │   ├── planner.py
│   │   ├── validator.py
│   │   ├── executor.py
│   │   ├── llm.py
│   │   ├── memory.py
│   │   ├── storage.py
│   │   ├── cache.py
│   │   └── scheduler.py
│   ├── api/
│   │   └── main.py
│   └── skills/
│       ├── backup/
│       ├── organizador_arquivos/
│       └── resumo_documentos/
├── docker-compose.yml
├── litellm.config.yaml
└── pyproject.toml
```

## MVP recomendado

### Fase 1 — núcleo funcional

- `yby chat`
- Router Agent
- LiteLLM com Ollama e OpenRouter
- Validation Agent
- Execution Agent para uma skill segura
- Histórico no PostgreSQL
- Docker Compose

### Fase 2 — memória e automações

- Qdrant
- Indexação de documentos
- Busca semântica
- Scheduler de automações
- Redis para cache e filas

### Fase 3 — painel

- Interface web local
- Lista de automações
- Histórico de execuções
- Saúde dos serviços
- Métricas de uso

## Critérios de aceite do MVP

- [ ] `yby up` sobe todos os serviços.
- [ ] `yby doctor` detecta serviços indisponíveis.
- [ ] `yby chat` responde usando Ollama local.
- [ ] OpenRouter é acionado apenas como fallback.
- [ ] Comandos ambíguos pedem esclarecimento.
- [ ] Ações destrutivas exigem confirmação.
- [ ] Skills executam dentro de timeout e limites de recursos.
- [ ] Histórico é persistido no PostgreSQL.
- [ ] Testes cobrem Router, Planner, Validator e Executor.
- [ ] CI valida testes antes do merge.

## Prompt para implementação no Cursor

```text
Leia o repositório YBY SEED e implemente o YBY Core conforme docs/YBY_CORE.md.

Regras:
- Não altere comportamento existente sem teste.
- Comece pelo MVP da Fase 1.
- Use Docker Compose para Qdrant, PostgreSQL e Redis.
- Use LiteLLM como camada única para Ollama e OpenRouter.
- Use FastAPI para expor /health, /chat, /automations e /memory.
- Implemente Router, Planning, Validation e Execution como módulos separados.
- Use Pydantic para validar entradas, planos e respostas.
- Adicione testes para cada agente e para o orquestrador.
- Não inclua segredos no repositório.
- Crie commits atômicos e um Draft PR para revisão.
- Não faça push sem revisão.
```
