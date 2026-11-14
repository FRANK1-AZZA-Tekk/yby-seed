# Plano do ecossistema wearable + gateway (pós-v1)

> **Escopo:** planejamento e documentação. **Não** implementar firmware/mobile neste repositório (D1, [FORA-DO-V1.md](../archive/FORA-DO-V1.md)).  
> **v1 agora:** PC Hub — `engine`, `safety`, `voice`, agente P0 no [ROADMAP.md](../../ROADMAP.md).  
> **Princípio:** FUNCTION OVER FORM; local-first; IA no hub; wearable = sensor + UI fina + fila.

Documentos irmãos: [FICHA_INVESTIGACAO.md](FICHA_INVESTIGACAO.md), [METRICAS_OBSERVABILIDADE.md](METRICAS_OBSERVABILIDADE.md), [MOBILE_FUTURE.md](MOBILE_FUTURE.md).

---

## 1. Sumário executivo

O YBY SEED v1 permanece **CLI no PC**. Wearable (LilyGO **T-Watch S3 Plus**) e Android entram **depois**, com:

1. **Gateway no PC Hub** como autoridade (roteamento, IA, aprovação humana, política de rede).
2. **Relógio** só telemetria, UI mínima, comandos locais (voz/gesto → evento, não LLM no relógio).
3. **Rede privada** (Tailscale no PC + telefone opcional); **sem VPN no ESP32-S3**.
4. **Métricas e fichas de investigação** antes de otimizar energia ou UI.

Evitar programar sem rumo: sequência fixa na seção 8.

---

## 2. Estado atual do projeto (fato)

| Camada | Estado | Repo |
|---|---|---|
| PC Hub + `yby ask` | Feito | `yby-seed` |
| Voz STT/TTS local | Feito (opcional) | `src/voice` |
| Vault + safety | Feito | `memory`, `safety` |
| Agente production-ready | Planejado P0 | [ROADMAP.md](../../ROADMAP.md) |
| Gateway MQTT/HTTP | Legado, loopback | `src/gateway` |
| Firmware T-Watch Plus | Fora da árvore | FRANK_ZER0 / YBY |
| LangGraph/MQTT orquestração | Separado | `yby-core` (D7) |

`docs/AUTO_EVOLUTION.md` descreve **visão histórica** (PostgreSQL + Learning Agent) — **não** é o caminho do `ask`. Auto-melhoria **realista no v1:** evals, CI, `ruff`/`pytest`, vault de decisões, métricas do roadmap.

---

## 3. Arquitetura recomendada

```text
[T-Watch S3 Plus]          [Xiaomi 12 opcional]              [PC Hub yby-seed]
  sensores / LVGL               BLE / notif                       Ollama 3B
  fila offline                  gateway leve (futuro)             agente + safety
        │                              │                              │
        └──────── MQTT/TLS ou WSS ─────┴──── Tailscale LAN ──────────┘
                              (broker local ou bridge no hub)
```

- **IA:** só no PC (e nuvem sob D12). Relógio nunca chama OpenRouter direto.
- **Ações físicas:** intent versionado → hub valida → firmware executa allowlist.
- **Streaming:** STT no hub; respostas curtas no relógio; TTS opcional no PC ou Piper pipeline futuro.

---

## 4. Gateway — onde e como

| Opção | Usar | Evitar |
|---|---|---|
| **PC Hub (principal)** | MQTT broker local Mosquitto **ou** bridge para `src/gateway`; normalização JSON/CBOR | Expor broker na internet |
| **Xiaomi 12** | BLE provisioning, notificação, cache curto offline | LLM pesado em background (HyperOS mata) |
| **Raspberry / edge box** | Só se PC não puder ficar ligado | Duplicar lógica de agente |

### Protocolos (prioridade)

| Prioridade | Protocolo | Uso |
|---|---|---|
| P0 | **JSON** + schema versionado | Debug, MVP gateway |
| P1 | **CBOR** ou MessagePack | Telemetria compacta |
| P2 | **Protobuf** | Contrato estável em produção |
| — | Fila offline + **idempotência** (IDs de evento) | Wearable sem Wi-Fi constante |
| — | Retries + timeout por classe de mensagem | Não bloquear UI |

Padrões inspirados em OSS (MIT/Apache): bounded agent loop [Yo](https://github.com/SeansGravy/Yo), citações [Qavrn](https://github.com/mussussu/Qavrn) — ver seção 7.

---

## 5. Rede privada (Tailscale / WireGuard)

| Tema | Recomendação YBY |
|---|---|
| **ESP32-S3** | **Não** Tailscale no chip — usar MQTT/TLS até o hub |
| **PC Hub** | Tailscale **subnet router** opcional para LAN doméstica; ACLs mínimas |
| **Android** | App Tailscale oficial; cuidado com Doze |
| **Containers** | Tailscale sidecar ou host network — documentar antes de deploy |
| **Userspace WireGuard** | Termux possível; custo de bateria — **usar depois** |
| **Exit node** | Evitar para wearable; aumenta superfície |
| **Rotação de chaves / tags** | Política quando hub expuser APIs |
| **Observabilidade** | Logs de conexão + latência; não logar payload sensível |

Investigar cada mudança com [FICHA_INVESTIGACAO.md](FICHA_INVESTIGACAO.md).

---

## 6. Firmware, energia, rádio, UI (hipóteses a validar)

Tudo abaixo é **planejamento até medição** (não datasheet).

### Energia

Separar sempre: **módulo ESP32** vs **placa completa** (display, PMIC, GPS, áudio).

Modos a benchmarkar na **S3 Plus** real: active, modem-sleep, light/deep sleep, wake sources, backlight, brownout recovery.

### Wi-Fi + BLE

Coexistência IDF; prioridade de rádio; provisioning BLE → Wi-Fi STA. Issues comunitárias sobre `stop_scan` e heap — confirmar com IDF advisory + teste em [FICHA_INVESTIGACAO.md](FICHA_INVESTIGACAO.md).

### ESP-IDF / FreeRTOS

- Alvo: versão IDF **suportada por [LilyGoLib](https://github.com/Xinyuan-LilyGO/LilyGoLib)** para **T-Watch S3 Plus** (MIT).
- Dual-core: UI em task dedicada; afiniade para I/O; stack watermark obrigatório.
- OTA: partições + rollback; Secure Boot / flash encryption como fase segurança.

### LVGL

- Branch oficial LilyGO ainda referencia **lvgl v7** em docs antigos — **confirmar** versão no quick start Plus antes de codificar.
- Buffers parciais + PSRAM; medir FPS/flush (ver [METRICAS_OBSERVABILIDADE.md](METRICAS_OBSERVABILIDADE.md)).
- Menu: **poucos níveis**, atalhos por voz no hub; microgestos = eventos discretos, não gestos complexos.

### GPIO / hardware

Antes de qualquer pinout: preencher tabela produto = **T-Watch S3 Plus**, revisão PCB, flash, PSRAM. Fonte: LilyGoLib + esquemático da revisão **medida**, não T-Watch 2019.

---

## 7. Projetos OSS — usar / adaptar / evitar

| Projeto | Licença | Classificação | Componente útil | Risco histórico comum | Mitigação YBY |
|---|---|---|---|---|---|
| [LilyGoLib](https://github.com/Xinyuan-LilyGO/LilyGoLib) | MIT | **Usar depois** | Board init Plus | Variante errada | Checklist hardware |
| [Yo](https://github.com/SeansGravy/Yo) | Apache-2.0 | **Adaptar** | Loop bounded + citações | Escopo fechado | Modelo fase B |
| [Qavrn](https://github.com/mussussu/Qavrn) | MIT | **Adaptar** | RAG local + fontes | Desktop pesado | Vault + `recall` |
| [Loco-RAG](https://github.com/ROHITCRAFTSYT/Loco-RAG) | MIT | **Usar depois** | LanceDB/Chroma swap | Agent sem HITL | `safety` |
| [ESPHome MQTT TLS](https://esphome.io/components/mqtt/) | MIT/GPL C++ | **Evitar merge** | Padrão TLS PEM | GPLv3 runtime | Só ideias de config |
| [velijv T-Watch ESPHome](https://github.com/velijv/LILYGO-T-Watch-S3-ESPHome) | CC BY-NC-ND | **Evitar** | — | Licença | Não copiar |
| **yby-seed** `src/gateway` | MIT | **Adaptar** | Token loopback | MQTT trust broker | D10 + rede |
| **omi** (fork org) | (ver upstream) | **Usar depois** | Wearable voice produto | Outro escopo | Estudar padrões, D7 |

**Hugging Face:** modelos `qwen2.5-coder:3b` via Ollama já decididos (D4); não puxar 7B no hub 4GB.

---

## 8. Menu, navegação e “auto-evolução”

### Navegação (produto)

| Superfície | Funções (máx. recomendado no MVP wearable) |
|---|---|
| **PC** | CLI `yby.py` → modo agente futuro; vault; `listen` |
| **Relógio** | 1) status 2) último alerta 3) confirmar/recusar 4) atalho voz (wake) 5) métricas vitais |
| **Voz** | Comandos curtos → hub; confirmação para escrita/ação |
| **Microgestos** | 2–3 gestos = eventos (`confirm`, `back`, `voice`) — calibrar em hardware |

Não montar “menu com muitas funções” no firmware antes do agente P0 no PC validar fluxos.

### Auto-evolução (realista)

| Ferramenta | O quê faz | Onde |
|---|---|---|
| **Evals + regressão** | Prompt/modelo/tool não pioram | CI fase C roadmap |
| **`make check`** | Lint + testes | Hoje |
| **Vault de decisões** | `note` com ADR curto | `src/memory` |
| **Ficha investigação** | Não repetir bugs | [FICHA_INVESTIGACAO.md](FICHA_INVESTIGACAO.md) |
| **Auto-limpeza** | Scripts allowlisted, confirmação | `safety` + skills dry-run |

Não ativar PostgreSQL/Learning Agent legado sem ADR explícito.

---

## 9. Plano de execução (ordem obrigatória)

| # | Entrega | Repo | Depende de |
|---|---|---|---|
| 1 | Fase P checklist ([PHASE-P.md](../PHASE-P.md)) | yby-seed | D9 |
| 2 | **P0** Agente loop + schemas | yby-seed | ROADMAP |
| 3 | PRD wearable fase D (8 estados UI definidos) | yby-seed doc | #2 |
| 4 | Spike LilyGoLib “hello LVGL + heap log” | FRANK_ZER0 | #3 |
| 5 | Broker MQTT TLS local + auth | hub / yby-core | #2 |
| 6 | Telemetria unidirecional + métricas | firmware + [METRICAS](METRICAS_OBSERVABILIDADE.md) | #4–5 |
| 7 | Android gateway leve (opcional) | YBY mobile | #6 |
| 8 | Tailscale ACL documentada | ops | #5 |

**Parar** se P0 agente não passar evals — não abrir firmware pesado.

---

## 10. Itens não decidíveis sem hardware na mão

- Revisão PCB exata da unidade YBY-WATCH-001
- Autonomia real (mAh × perfil de uso)
- IDF/LVGL pinados para Plus
- Coexistência BLE+Wi-Fi no layout de antena da Plus
- Oito estados visuais do avatar (definir com design, não no seed)

---

## 11. Próximo passo imediato (yby-seed)

Abrir issue **P0: Agente mínimo com loop controlado** — copiar critérios do [ROADMAP.md](../../ROADMAP.md). Este plano **não** substitui essa issue.