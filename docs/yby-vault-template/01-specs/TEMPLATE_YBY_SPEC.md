---
spec_id: YBY-SPEC-000
title: "{{title}}"
target_node: pc-hub
status: draft
offline_ready: true
ui_palette:
  theme: yby-zero
  obsidian: "#0D0D0D"
  off_white: "#F5F5F2"
  silicon_green: "#00FF66"
  titanium_gray: "#8E8E93"
tags:
  - yby-spec
  - local-first
  - obsidian-first
  - knap
---

# {{spec_id}} — {{title}}

> [!info] Contrato Obsidian-First & Spec-First
> Esta especificação é a fonte determinística da verdade antes de gerar ou alterar código/PWA no `src/yby_machine/` ou nos serviços do [[pc-hub]]. Compatível com `obsidian-markdown` e compilação de conhecimento via `knap`.

## 1. Contexto e Objetivo

- **Nó alvo:** [[pc-hub]] (ajustar para [[xiaomi-12]], [[moto-edge-30-phonebox]], [[t-watch-s3-plus]], [[yby-glass]] ou [[cybertupa]])
- **Inventário de hardware:** [[INVENTARIO_NOS_YBY.base]]
- **Topologia da malha:** [[TOPOLOGIA_MALHA_YBY.canvas]]
- **Problema resolvido:** Descreva o objetivo funcional mínimo em uma frase verificável.

## 2. Restrições Local-First (D12)

- **Operação offline:** `offline_ready: true` (nenhuma dependência obrigatória de nuvem).
- **Orçamento de recursos:** Respeitar o limite do hardware alvo (ex.: PC Hub GTX 1650 4 GB VRAM / 16 GB RAM).
- **Fallback degradado:** Definir comportamento determinístico quando Redis, PostgreSQL/`pgvector` ou Mosquitto MQTT estiverem indisponíveis.

## 3. Contrato Determinístico (`YBY-Spec`)

### 3.1 Entidades e Dados

- `entity_name`: campos, tipos (`texto`, `numero`, `data`, `cpf`, `cnpj`, `cep`, `moeda_brl`, `telefone_br`) e persistência local (`IndexedDB` / `SQLite WAL` / `pgvector`).

### 3.2 Interfaces e Eventos

- **HTTP Local (FastAPI):** rotas, payloads Pydantic v2 e autenticação (`YBY_COCKPIT_TOKEN` / `YBY_EDGE_SYNC_TOKEN`).
- **MQTT Local:** tópicos (`yby/cockpit/action`, `yby/audio/state`, `yby/nodes/<node>/telemetry`) com QoS 1.
- **Superfície Tátil (PhoneBox):** widgets de telemetria (`GET /api/v1/cockpit/status`) e gatilhos (`POST /api/v1/cockpit/webhook`).

### 3.3 Identidade Visual (YBY ZERO)

- Fundo primário: `#0D0D0D` (Obsidian)
- Texto principal: `#F5F5F2` (Off-White)
- Sinal ativo / ação primária: `#00FF66` (Silicon Green)
- Metadados / contornos secundários: `#8E8E93` (Titanium Gray)

## 4. Critérios de Aceite e Testes

- [ ] Schema Pydantic validado sem warnings.
- [ ] Testes unitários 100% offline verdes (`make test`).
- [ ] Lint limpo (`make lint`) e ambiente íntegro (`make doctor`).
- [ ] Nota indexada no RAG local (`trigger_reindex` via PhoneBox ou `ObsidianVaultIndexer`).

## 5. Referências Relacionadas

- [[TOPOLOGIA_MALHA_YBY.canvas]]
- [[INVENTARIO_NOS_YBY.base]]
- [[pc-hub]]
- [[moto-edge-30-phonebox]]
