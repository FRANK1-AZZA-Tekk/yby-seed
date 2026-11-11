# Arquitetura — YBY SEED

## Visão geral

YBY SEED é um PC Hub local-first para automações e IA. A fase atual é exclusivamente PC-first; mobile e ESP32 são expansões futuras.

## Forma do produto (Camada A)

```text
Usuário
  ↓
yby_seed.py  (fachada)
  ├─ sem args  → src.app.App.repl()   (chat + /comandos)
  └─ com args  → src.main.cli (Click) (doctor/setup/test/brief/run/…)
       ↓
src/app/kernel.py  (despacho)
  ├─ /brief  → BriefingPipeline (Camada B)
  ├─ /chat   → modules.llm_brain (LiteLLM)
  ├─ /status → settings + LayerRegistry
  └─ /layers → A–D
```

## Camadas

| Camada | Nome | Status |
|---|---|---|
| A | Forma (kernel + entrypoint) | ready |
| B | Briefing revisável | ready |
| C | Skills dry-run | planned |
| D | Memória local | planned |

## Componentes do núcleo

```text
RouterAgent → Planner → Validation → Executor → Skill (dry-run)
```

## Serviços opcionais (congelados no MVP)

| Serviço | Função | Fase |
|---|---|---|
| Qdrant | Memória semântica | 5 |
| FastAPI | API local | 6 |
| PostgreSQL | Histórico | 7 |
| Redis | Cache | 7 |

## Regras

- O núcleo funciona sem Docker.
- Um serviço por vez.
- Automações em dry-run antes de executar.
- Local-first; nuvem apenas como fallback.
- Nenhum comando reporta sucesso sem ação verificável.
