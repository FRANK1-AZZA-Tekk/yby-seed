# Relatório de auditoria geral — YBY SEED

**Data:** 2026-11-23  
**Repositório:** `yby-seed` (branch auditada: `main` @ pull 2026-11-23)  
**Escopo:** leitura de `src/`, `tests/`, `config/`, `deploy/`, `scripts/`, `docs/`, raiz; execução de `pytest` e cobertura. **Nenhum código de produção foi alterado nesta entrega.**

**Comandos executados**

| Comando | Resultado |
|--------|-----------|
| `PYTHONPATH=. python3 -m pytest -rs -q` | **324 passed**, **14 skipped** (12,68s) |
| `PYTHONPATH=. python3 -m pytest --cov=src --cov-report=term-missing -q` | **81%** linhas cobertas (`TOTAL 4094 stmts, 782 miss`) |
| Grep: `except:` | 0 ocorrências em `src/` |
| Grep: `shell=True` | 0 ocorrências |
| `make lint` (ambiente local) | Falhou: `ruff` ausente no `.venv` (ambiente incompleto; CI usa dev deps) |

Artefatos: `/opt/cursor/artifacts/pytest-full.txt`, `pytest-cov.txt`, `pytest-skips.txt`.

---

## 1. Sumário executivo — top 5 riscos

1. **Gateway IoT legado não persiste telemetria:** `process_batch` chama `db_client.insert(...)` sem `await` em função síncrona — corrotinas nunca executam (`src/gateway/fastapi_mqtt_bridge.py:234`).
2. **Integração MQTT ↔ asyncio incorreta:** callback Paho (thread) usa `asyncio.Queue.put_nowait` sem `loop.call_soon_threadsafe` — risco de corrida/perda silenciosa (`src/gateway/mqtt_listener.py:139-140`).
3. **MQTT sem TLS no código:** clientes usam TCP plano na porta 1883; documentação exige TLS na LAN, mas não há `tls_set` / `use_tls` (`src/iot/client.py:63`, `src/gateway/mqtt_listener.py:72-75`).
4. **Superfície de visão sem autenticação:** servidor FUSION expõe `POST /v1/chat/completions` sem token (default `127.0.0.1`, mas arriscado se `FUSION_SERVER_HOST=0.0.0.0`) (`src/vision/fusion/server.py:80-151`).
5. **Sandbox herda `os.environ` completo:** subprocesso do `SandboxExecutor` recebe cópia integral do ambiente, inclusive chaves — diverge de `scrubbed_env()` em `src/actions/runner.py` (`src/security/sandbox_executor.py:95-107`).

**Pontos positivos verificados:** D12 respeitado em `HybridEngine._after_local_failure` (`src/engine/hybrid.py:129-146`); CLI liga confirmação de nuvem via `build_engine()` (`src/main.py:367-373`); log de nuvem bloqueia campos sensíveis (`src/engine/cloud_usage_log.py:50-52`, permissão `0o600` em `57-67`); `subprocess` do runner usa `shell=False` (`src/actions/runner.py:140-147`); gateway HTTP protege rotas de dados com `GATEWAY_TOKEN` (`src/gateway/fastapi_mqtt_bridge.py:54-57`, `89`).

---

## 2. Tabela de achados por severidade

| ID | Sev. | Área | Resumo |
|----|------|------|--------|
| A01 | ~~**Crítico**~~ **Corrigido** (PR-CRIT-1) | gateway | `insert` assíncrono chamado sem `await` |
| A02 | ~~**Crítico**~~ **Corrigido** (PR-CRIT-2) | gateway | `asyncio.Queue` manipulada de thread MQTT |
| A03 | **Alto** | security | Sandbox propaga secrets via `os.environ.copy()` |
| A04 | **Alto** | iot/gateway | MQTT sem TLS/autenticação transporte |
| A05 | **Alto** | vision | API de inferência sem auth |
| A06 | **Alto** | gateway | Embeddings dummy (vetores nulos) |
| A07 | **Alto** | gateway | WebSocket e worker competem pela mesma fila |
| A08 | **Médio** | engine | `HybridEngine` confirma nuvem automaticamente se `confirm_fn=None` |
| A09 | **Médio** | gateway | `HTTPException(detail=str(e))` vaza stack interno |
| A10 | **Médio** | core | `MemoryAllocator.install()` executa `sudo apt` e altera `~/.bashrc` |
| A11 | **Médio** | testes | 14 testes skipped (gateway, RAG, agentes legado) |
| A12 | **Médio** | cobertura | 17+ módulos `src/` com **0%** cobertura na suíte |
| A13 | **Médio** | vision | `FUSION_QUANTIZATION` padrão `none` vs D14 (4bit / VRAM) |
| A14 | **Baixo** | gateway | `datetime.utcnow()` (deprecado) em metadados |
| A15 | **Baixo** | ops | `logging.basicConfig` repetido em vários módulos legado |
| A16 | **Baixo** | docs/código | Módulos `evaluation/` e `monitoring/` duplicam conceito de dashboard |

**Contagem:** Crítico **2** · Alto **5** · Médio **6** · Baixo **3** → **16 achados** (todos com referência de arquivo:linha abaixo).

---

## 3. Detalhe por achado

### A01 — ~~Crítico~~ Corrigido (PR-CRIT-1) · Gateway não persiste batch

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/fastapi_mqtt_bridge.py` |
| Linhas | 217-234, 159 (`insert` é `async def`) |
| Status | **Corrigido** — `process_batch` é `async` e faz `await db_client.insert`; testes em `tests/gateway/test_process_batch.py`. |
| Descrição | `process_batch` é síncrona e invoca `db_client.insert({...})` sem `await`. Em Python 3.12 isso produz uma corrotina descartada; nenhuma escrita LanceDB ocorre. |
| Impacto | Telemetria wearables aparenta “processar” nos logs, mas dados não chegam ao banco — falha silenciosa em produção. |
| Correção sugerida | Tornar pipeline consistente: `await db_client.insert` no event loop, ou `asyncio.run_coroutine_threadsafe` / fila dedicada com worker async. |
| Esforço | **M** |

### A02 — ~~Crítico~~ Corrigido (PR-CRIT-2) · Thread-safety da fila MQTT

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/mqtt_listener.py` |
| Linhas | 118-140 |
| Status | **Corrigido** — `enqueue_mqtt_payload` + `loop.call_soon_threadsafe`; testes em `tests/gateway/test_mqtt_listener_threadsafe.py`. |
| Descrição | `on_message` (thread do Paho) chama `queue.put_nowait` em `asyncio.Queue` passada por `userdata`. A documentação do asyncio exige uso do loop (`call_soon_threadsafe`) para produtores externos. |
| Impacto | Mensagens perdidas, `RuntimeError` intermitente ou corrupção sob carga — viola backpressure prometido na arquitetura. |
| Correção sugerida | Usar `asyncio.Queue` apenas no loop principal; bridge com `loop.call_soon_threadsafe(queue.put_nowait, data)` ou `janus.Queue`. |
| Esforço | **M** |

### A03 — Alto · Secrets no subprocesso do sandbox

| Campo | Valor |
|-------|--------|
| Arquivo | `src/security/sandbox_executor.py` |
| Linhas | 95-107 |
| Descrição | `env = os.environ.copy()` repassa todas as variáveis ao `python3` filho. O runner de ações usa `scrubbed_env()` (`src/actions/runner.py:172-180`), mas o sandbox não. |
| Impacto | Código gerado (mesmo após AST guard) pode ler `OPENROUTER_API_KEY`, `GATEWAY_TOKEN`, etc. via `os.environ` se escapar restrições. |
| Correção sugerida | Reutilizar `scrubbed_env()` ou whitelist mínima (`PATH`, `HOME`, `TMPDIR`). |
| Esforço | **S** |

### A04 — Alto · MQTT em texto claro

| Campo | Valor |
|-------|--------|
| Arquivo | `src/iot/client.py`, `src/iot/config.py`, `src/gateway/mqtt_listener.py`, `src/gateway/config.py` |
| Linhas | `client.py:63-64`; `config.py:11-12`, `64-65`; `mqtt_listener.py:72-75`; `gateway/config.py:28-29` |
| Descrição | Conexões usam host/porta sem `tls_set` / certificados. Porta 8883 é aceita na config (`tests/iot/test_mqtt_client.py:36-42`) mas ainda sem TLS. `docs/IOT.md` documenta TLS; código não implementa. |
| Impacto | Credenciais e telemetria de saúde/casa expostas na LAN (conflito com D10/D9 e MODEL_CARD). |
| Correção sugerida | `IOT_USE_TLS`, `ca_certs`, integração com Mosquitto local; recusar bind público sem TLS. |
| Esforço | **M** |

### A05 — Alto · Servidor FUSION sem autenticação

| Campo | Valor |
|-------|--------|
| Arquivo | `src/vision/fusion/server.py` |
| Linhas | 71-151, 160-162 |
| Descrição | `create_app` não valida token; rotas aceitam upload de imagem e JSON OpenAI-compatível. Host padrão `127.0.0.1` (`160`), mas configurável para `0.0.0.0`. |
| Impacto | Uso não autorizado de GPU/VRAM e exfiltração de imagens se exposto além do loopback (D14). |
| Correção sugerida | Bearer token opcional (espelhar `src/gateway/auth.py`) + testes de rejeição 401. |
| Esforço | **S** |

### A06 — Alto · Embeddings fictícios no gateway

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/fastapi_mqtt_bridge.py` |
| Linhas | 270-278, 231 |
| Descrição | `generate_embedding` retorna `[0.0] * 384` com comentário TODO; busca RAG (`/vectors/search`) opera sobre dados sem significado semântico. |
| Impacto | Decisões baseadas em similaridade vetorial são inválidas; falso positivo de funcionalidade. |
| Correção sugerida | Integrar `OLLAMA_MODEL_EMBEDDING` (`src/gateway/config.py:35-36`) ou desabilitar endpoint até implementação. |
| Esforço | **M** |

### A07 — Alto · Consumidores concorrentes da fila

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/fastapi_mqtt_bridge.py` |
| Linhas | 111-126, 186-195 |
| Descrição | Worker async e WebSocket `/ws/telemetry` fazem `mqtt_queue.get()` na mesma fila — cada mensagem vai só para um consumidor. |
| Impacto | Dashboard em tempo real ou persistência — um dos fluxos fica sistematicamente esvaziado. |
| Correção sugerida | Padrão pub/sub: `asyncio.Queue` por consumidor, ou broadcast após persistência. |
| Esforço | **M** |

### A08 — Médio · Confirmação de nuvem permissiva por default

| Campo | Valor |
|-------|--------|
| Arquivo | `src/engine/hybrid.py` |
| Linhas | 83-85 |
| Descrição | Se `confirm_fn is None`, engine usa `lambda _msg: True` e `has_tty_fn` verdadeiro — contorna `CloudBudget` TTY em integrações que instanciam `HybridEngine` direto (testes fazem isso de propósito). |
| Impacto | Risco de gasto de tokens sem confirmação em scripts/serviços que não usem `build_engine()`. |
| Correção sugerida | Default conservador (`confirm_fn` que retorna `False`) ou obrigar `confirm_fn` em `engine_from_env` quando `require_confirm`. |
| Esforço | **S** |

### A09 — Médio · Vazamento de detalhe em erros HTTP

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/fastapi_mqtt_bridge.py` |
| Linhas | 106-108, 159-161, 176-178 |
| Descrição | `raise HTTPException(..., detail=str(e))` propaga mensagens de exceções internas ao cliente. |
| Impacto | Informação de caminhos, drivers LanceDB, etc. |
| Correção sugerida | Mensagem genérica ao cliente + log completo no servidor (D10). |
| Esforço | **S** |

### A10 — Médio · Allocator legado altera sistema

| Campo | Valor |
|-------|--------|
| Arquivo | `src/core/memory_allocator.py` |
| Linhas | 79-86, 106-111 |
| Descrição | `install()` chama `sudo apt install` e `enable()` acrescenta `LD_PRELOAD` em `~/.bashrc` sem confirmação humana (D6/D10). |
| Impacto | Mudança persistente no host se módulo legado for importado/executado. |
| Correção sugerida | Marcar como opt-in CLI, dry-run, ou mover para `scripts/` fora do import path v1. |
| Esforço | **S** |

### A11 — Médio · Lacunas de teste integração

| Campo | Valor |
|-------|--------|
| Arquivo | `tests/test_gateway.py`, `tests/test_rag.py`, `tests/test_agents.py` |
| Linhas | skips em `10-26` (gateway/rag); `28-97` (agentes) |
| Descrição | 14 skips: gateway/RAG “fixtures pendentes”; agentes “não implementado ainda” apesar de código em `src/agents/`. |
| Impacto | Regressões em MQTT/LanceDB/RAG não detectadas no CI. |
| Correção sugerida | Fixtures docker/mock (mosquitto, LanceDB tmp) alinhadas a `tests/iot/test_mqtt_client.py`. |
| Esforço | **L** |

### A12 — Médio · Módulos sem cobertura na suíte atual

| Campo | Valor |
|-------|--------|
| Arquivo | Ver lista abaixo |
| Linhas | — |
| Descrição | `pytest-cov` não reporta estes módulos (0% — não importados em testes): `src/gateway/fastapi_mqtt_bridge.py`, `mqtt_listener.py`, `lancedb_client.py`; `src/rag/*`; `src/monitoring/metrics_dashboard.py`; `src/evaluation/*`; `src/core/auto_cleanup.py`, `auto_improvement.py`, `gpu_offload.py`, `kv_cache_config.py`, `memory_allocator.py`; `src/vision/fusion/server.py`; `src/security/openrouter_sanitizer.py`; `src/skills/skill_manager.py`. |
| Impacto | Código legado/avançado evolui sem rede de segurança. |
| Correção sugerida | Smoke tests import-only + testes de contrato mínimos por PR do plano robustez. |
| Esforço | **L** |

### A13 — Médio · VRAM vs decisão D14

| Campo | Valor |
|-------|--------|
| Arquivo | `src/vision/fusion/config.py`, `DECISIONS.md` D14 |
| Linhas | `config.py:13`, `54-56`; D14 recomenda `4bit` |
| Descrição | Default `DEFAULT_QUANTIZATION = "none"` pode carregar FP16 (~12–16 GB) se operador não setar `FUSION_QUANTIZATION`. |
| Impacto | OOM em GTX 1650 4 GB; contrário ao plano de quantização. |
| Correção sugerida | Default `4bit` com override explícito; alerta em `FusionClient` load. |
| Esforço | **S** |

### A14 — Baixo · Timestamps UTC deprecados

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/mqtt_listener.py`, `fastapi_mqtt_bridge.py` |
| Linhas | `mqtt_listener.py:135`; `fastapi_mqtt_bridge.py:103`, `143` |
| Descrição | Uso de `datetime.utcnow()` (deprecado em 3.12+). |
| Impacto | Avisos futuros; possível confusão de fuso. |
| Correção sugerida | `datetime.now(timezone.utc)`. |
| Esforço | **S** |

### A15 — Baixo · Logging global repetido

| Campo | Valor |
|-------|--------|
| Arquivo | `src/gateway/mqtt_listener.py:29`, `fastapi_mqtt_bridge.py:32`, `lancedb_client.py:26`, `core/memory_allocator.py:26`, etc. |
| Linhas | ver grep `logging.basicConfig` |
| Descrição | Vários módulos legado chamam `basicConfig` na importação — pode sobrescrever configuração do CLI (`src/main.py:49-60` usa loguru). |
| Impacto | Logs inconsistentes em processos que misturam núcleo v1 e gateway. |
| Correção sugerida | Logger por módulo sem `basicConfig` em library code. |
| Esforço | **S** |

### A16 — Baixo · Duplicação evaluation vs monitoring

| Campo | Valor |
|-------|--------|
| Arquivo | `src/evaluation/metrics_dashboard.py`, `src/monitoring/metrics_dashboard.py` |
| Linhas | — (ambos presentes; nenhum importado em testes) |
| Descrição | Dois dashboards de métricas paralelos, fora do núcleo `yby ask`. |
| Impacto | Manutenção duplicada, confusão de qual usar em PR-7. |
| Correção sugerida | Unificar ou arquivar em `docs/future/` com owner único. |
| Esforço | **S** |

---

## 4. Mapa de calor por módulo

Escala: `▁` baixo · `▃` médio · `▅` alto · `█` crítico (percepção auditada: bugs + segurança + performance + testes).

```
Módulo              | Bugs | Seg | Perf | Test | Notas
--------------------|------|-----|------|------|------------------------------
engine/             | ▁    | ▁   | ▁    | ▅    | hybrid 96%; D12 OK
safety/ + actions/  | ▁    | ▁   | ▁    | ▅    | shell=False, scrubbed_env
agent_loop/         | ▁    | ▁   | ▁    | ▅    | timeout ferramentas 30s
memory/ (vault)     | ▁    | ▁   | ▁    | ▅    | núcleo D8
voice/              | ▁    | ▁   | ▃    | ▅    | STT/TTS local D11
security/           | ▁    | ▃   | ▁    | ▃    | sandbox env (A03); ast_guard OK
iot/                | ▁    | ▅   | ▁    | ▃    | sem TLS; testes mock bons
vision/fusion       | ▁    | ▅   | ▃    | ▃    | server sem auth; VRAM default
gateway/            | █    | ▃   | ▃    | ▁    | A01-A02-A06-A07; skips CI
rag/                | ▁    | ▁   | ▃    | ▁    | legado; 3 skips RAG
core/ (legado)      | ▃    | ▃   | ▃    | ▁    | subprocess/sudo; ollama_client 35%
agents/ + skills/   | ▁    | ▁   | ▁    | ▃    | baixa cobertura agentes “legado”
evo/                | ▁    | ▁   | ▁    | ▅    | sanitize secrets; pipeline testado
platform/           | ▁    | ▁   | ▁    | ▅    | hub keepalive D9
evaluation/         | ▁    | ▁   | ▁    | ▁    | sem testes
monitoring/         | ▁    | ▁   | ▁    | ▁    | sem testes
```

---

## 5. Mapa `src/**/*.py` ↔ testes

| Situação | Módulos |
|----------|---------|
| **Bem cobertos (>85%)** | `engine/hybrid`, `routing`, `budget`, `safety/policy`, `gateway/auth`, `iot/handlers`, `iot/mem0_bridge`, `voice/tts`, `agent_loop/*` |
| **Cobertura parcial (40–85%)** | `engine/providers`, `voice/mic`, `core/ollama_client`, `agents/*`, `evo/*`, `main.py` |
| **Sem cobertura na suíte (0%)** | `gateway/{fastapi_mqtt_bridge,mqtt_listener,lancedb_client}`, `rag/*`, `monitoring/*`, `evaluation/*`, `core/{auto_cleanup,gpu_offload,kv_cache_config,memory_allocator,auto_improvement}`, `vision/fusion/server.py`, `security/openrouter_sanitizer.py`, `skills/skill_manager.py` |
| **Testes skipped** | Integração gateway (3), RAG embeddings (3), agentes Router/Learning (8) |

**pytest skips (razões):**

- `tests/test_agents.py` — Router/Planning/Execution/Validation/Learning “não implementado ainda” (8×)
- `tests/test_gateway.py` — depende Ollama/PostgreSQL/MQTT (3×)
- `tests/test_rag.py` — embeddings reais pendentes (3×)

---

## 6. Conformidade com decisões D1–D14 (amostra verificada)

| Decisão | Status | Evidência |
|---------|--------|-----------|
| D3/D12 local-first | **OK** | `hybrid.py:129-146` não escala nuvem após falha Ollama |
| D10 comandos | **OK** | `safety/policy` + `actions/runner` com confirmação e `refuse` |
| D10 sem secrets em log nuvem | **OK** | `cloud_usage_log.py:50-52` |
| D11 voz local | **OK** | `src/voice/*` testado; opcional `requirements-voice.txt` |
| D14 FUSION VRAM | **Parcial** | Código suporta 4bit; default `none` (`fusion/config.py:13`) |
| D9 MQTT hub | **Parcial** | IoT novo em `src/iot/`; gateway legado com bugs A01–A02 |
| D6 dry-run skills | **OK** | `src/skills/dry_run.py` + testes |

---

## 7. Recomendação de ordem de correção (plano robustez)

Alinhado a `docs/ROBUSTNESS-SCAN.md` e `PROGRESS.md`:

| PR | Foco | Priorizar achados |
|----|------|-------------------|
| **PR-A** | `core`, `engine`, `agent_loop` | A08 (defaults cloud), revisar `ollama_client` timeouts/erros |
| **PR-B** | `memory`, `rag` | A11 skips RAG; cobertura `rag/*`; índice vault |
| **PR-C** | `iot` | A04 TLS + testes de reconexão; manter mocks |
| **PR-D** | `voice`, `vision` | A05 auth FUSION; A13 default 4bit; testes `server.py` |
| **PR-E** | `safety`, `security` | **A03** sandbox env; revisar `openrouter_sanitizer` |
| **PR-F** | `gateway`, `monitoring` | **A01, A02, A06, A07, A09**; fixtures gateway; métricas Prometheus |
| **PR-G** | Transversal + `docs/PERFORMANCE.md` | A12 matriz cobertura; A16 unificar dashboards; benchmarks VRAM |

---

## 8. Conclusão

O **núcleo v1** (`engine`, `safety`, `actions`, `memory/vault`, `voice`, `evo`, `agent_loop`) está **relativamente maduro**: 324 testes passando, 81% cobertura agregada, decisões D3/D10/D12 refletidas no código do `ask`.

O **risco concentrado** está no pacote **`gateway/` legado** e na **integração asyncio/MQTT**, com defeitos funcionais críticos (persistência e thread-safety) ainda não cobertos por testes. **IoT novo** (`src/iot/`) está mais alinhado a D9, mas **TLS permanece só na documentação**.

Recomenda-se tratar **PR-F** com urgência antes de qualquer demo wearables, e **PR-E (A03)** antes de expandir execução de código gerado.

---

*Relatório gerado em auditoria read-only. Revisão humana recomendada para priorização de negócio.*