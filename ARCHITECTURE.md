# Arquitetura — YBY SEED

## Visão geral

YBY SEED é um PC Hub local-first para automações e IA. A fase atual é exclusivamente PC-first; mobile e ESP32 são expansões futuras.

Detalhes do framework único: [docs/YBY_CORE.md](docs/YBY_CORE.md).  
Mapa dos repositórios: [docs/REPO_MAP.md](docs/REPO_MAP.md).

## Componentes do núcleo

```text
Usuário
  ↓
CLI (src/main.py)
  ↓
yby_zero (privacidade + provider + degradação)
  ↓
orchestrator.classify_task → choose_model
  ↓
RouterAgent (intenção)
  ↓
Planner → Validation → Executor
  ↓
Skill segura / tools (~/yby)
  ↓
Resultado
```

## Camadas absorvidas

| Camada | Origem | Pacote |
|---|---|---|
| Eventos versionados | YBY | `src/yby_zero/events` |
| Privacidade P0–P3 | YBY | `src/yby_zero/privacy` |
| Degradação segura | YBY | `src/yby_zero/degradation` |
| Roteamento de provider | YBY | `src/yby_zero/routing` |
| Tipo de tarefa + modelo | yby-core | `src/orchestrator` |
| Jail de arquivos | yby-core | `src/tools` |
| Agentes NL2Code | yby-seed | `src/agents` |

## Serviços opcionais

| Serviço | Função | Fase |
|---|---|---|
| SQLite + sqlite-vec | Memória semântica | 5 |
| FastAPI | API local / SSE | 6 |
| LangGraph (`integrations/yby-core`) | Orquestração rica | opcional |
| Redis / PostgreSQL | Só se SQLite não bastar | 7+ |

## Regras

- O núcleo funciona sem Docker e sem LangGraph.
- Um serviço por vez.
- Automações em dry-run antes de executar.
- Local-first; nuvem apenas como fallback.
- Function over Form.
