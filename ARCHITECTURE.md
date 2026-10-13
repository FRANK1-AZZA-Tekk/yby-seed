# Arquitetura — YBY SEED

## Visão geral

YBY SEED é um PC Hub local-first para automações e IA. A fase atual é exclusivamente PC-first; mobile e ESP32 são expansões futuras.

## Componentes do núcleo

```text
Usuário
  ↓
CLI yby.py
  ↓
RouterAgent
  ↓
Planner
  ↓
Validation
  ↓
Executor
  ↓
Skill segura
  ↓
Resultado
```

## Serviços opcionais

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
