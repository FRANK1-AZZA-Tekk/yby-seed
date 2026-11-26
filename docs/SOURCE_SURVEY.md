# Levantamento rastreável de referências (benchmark YBY)

**Meta:** 300 fontes úteis · **Não concluído** · Registro canônico único (não duplicar em `FICHA_INVESTIGACAO.md`, que é wearable).

**Níveis:** `D0` descoberta (metadados) · `L1` leitura (doc/issue) · `L2` código/teste examinado.

**Rodada 1:** 2026-11-24 · `main` base `d098334…`
**Rodada 2:** 2026-11-24 · `main` base `7c6ef5b403ed19593583b88dcfe34aca58c9a924` (spike `format` no planner).
**Rodada 3:** 2026-11-26 · `main` base `a3a93aa6398f22d1217e33194bcd141f85275285` (YBY Glass G0, [YBY_GLASS_SPEC.md](YBY_GLASS_SPEC.md)).

## Contagens acumuladas (sem duplicatas)

| Rodada | D0 | L1 | L2 | Novas |
|--------|----|----|-----|-------|
| 1 | 1 | 4 | 5 | **10** |
| 2 | 0 | 2 | 3 | **5** |
| 3 | 0 | 4 | 1 | **5** |
| **Total novas** | **1** | **10** | **9** | **20** |

**Acumulado útil:** **20/300** entradas novas (rodadas 1–2 incluem inspeções internas YBY; rodada 3 só externas) + 3 referências prévias reutilizadas (não recontadas). Reutilizadas na rodada 2: **SRC-001**, **SRC-006**, **SRC-007** (sem recontagem). **Meta não concluída.**

**Rodada 2 — externas vs internas:** fontes **externas** novas = **2** (SRC-011, SRC-012); **inspeções código/teste YBY** = **3** (SRC-013–015). O total **5** da rodada 2 soma ambos — não confundir com “5 fontes externas”.

## Referências prévias (reutilizadas, sessão anterior)

| ID | URL | Nível já atingido | Nota |
|----|-----|------------------|------|
| SRC-PRIOR-01 | https://platform.openai.com/docs/api-reference/chat/create | L1 | Contrato `usage` OpenAI-compat |
| SRC-PRIOR-02 | https://openrouter.ai/docs/api-reference/overview | L1 | `prompt_tokens` / `completion_tokens` |
| SRC-PRIOR-03 | https://github.com/BerriAI/litellm (`litellm/types/utils.py` `Usage`) | L2 | Pydantic opcional + detalhes; licença MIT |

## Entradas — rodada 1

| ID | URL / arquivo | Origem | Versão / data | Nível | Evidência útil | Licença | Decisão YBY |
|----|---------------|--------|---------------|-------|----------------|---------|-------------|
| SRC-001 | https://ollama.com/blog/structured-outputs | Doc oficial Ollama | 2024-12-06 | L1 | `format` JSON Schema em `/api/chat`; Pydantic `model_json_schema()` + `model_validate_json` | — | **Comparar** com `OllamaJsonPlanner` (só prompt; `complete` via `/api/generate` sem `format`) |
| SRC-002 | https://platform.openai.com/docs/guides/structured-outputs | Doc oficial OpenAI | consulta 2026-11-24 | L1 | `response_format` / parse tipado; reforça validar após geração | — | Nuvem YBY não usa planner JSON; referência de padrão, não gap imediato no `ask` |
| SRC-003 | https://docs.pydantic.dev/latest/errors/validation_errors/ | Doc Pydantic | latest (2026-11-24) | L1 | Erros estruturados por `loc`; alinhado a `format_validation_error` | MIT (lib) | **Já adotado** em `ToolRegistry.run` |
| SRC-004 | https://owasp.org/www-project-top-10-for-large-language-model-applications/ | OWASP GenAI | portal 2026-11-24 | D0 | Aponta para LLM Top 10; **hipótese** supply-chain/tools até leitura LLM07 | — | Sem mudança só com D0 |
| SRC-005 | `langgraph/libs/prebuilt/tests/test_tool_node_validation_error_filtering.py` | GitHub LangGraph | main (workspace) | L2 | Filtra erros Pydantic para args controlados pelo LLM | MIT | P0 YBY sem injetados; padrão útil se tools ganharem contexto injetado |
| SRC-006 | `src/agent_loop/schemas.py` | Código YBY | `main` @ d098334 | L2 | `parse_planner_step`: fence + `json.loads` + `model_validate`; sem JSON Schema no Ollama | — | Lacuna **testes** de falhas de parse, não ausência de parser |
| SRC-007 | `src/agent_loop/planner.py` | Código YBY | idem | L2 | `OllamaJsonPlanner.plan` → `complete` → `parse_planner_step` | — | Não usa `format` Ollama (ver SRC-001) |
| SRC-008 | `tests/test_agent_loop.py` | Testes YBY | idem | L2 | Cobre tools, timeout, abort, max_steps; **não** cobre JSON planner inválido | — | Gap de cobertura confirmado |
| SRC-009 | `src/agent_loop/loop.py` | Código YBY | idem | L2 | `planner_error` em `ValueError`/`JSONDecodeError`/`ValidationError` | — | Comportamento existe; falta teste |
| SRC-010 | `src/security/cloud_sanitizer.py` | Código YBY | idem | L1 | PII/path redact antes da nuvem; local-first no egress | — | **Já no runtime**; benchmark registra como referência interna |

## Achados úteis (rodada 1, máx. 3)

1. **Planner local sem structured output nativo:** `OllamaJsonPlanner` depende de instrução em texto + `parse_planner_step` (`SRC-006`/`007`), enquanto Ollama documenta `format` com JSON Schema (`SRC-001`). YBY `OllamaProvider` usa `/api/generate` sem campo `format` — divergência de mecanismo, não ausência de rota/max_tokens/reported.
2. **Falhas de JSON do planner pouco testadas:** `ControlledAgentLoop` já retorna `planner_error` para parse inválido (`SRC-009`), mas `tests/test_agent_loop.py` não exercita `parse_planner_step` com JSON quebrado, ação desconhecida ou fence com conteúdo inválido (`SRC-008`).
3. **Histórico do planner sem teto como nuvem:** `history_text = json.dumps(list(history))` cresce a cada iteração (`SRC-007`); `trim_context` aplica-se ao egress cloud, não ao loop agente — risco de contexto local longo dentro de `max_iterations` (confirmado no código, não corrigido nesta rodada).

## Recomendação única (tarefa pequena)

**Tarefa:** adicionar testes offline de falha de parse do planner em `tests/test_agent_loop.py` (ou arquivo irmão), sem alterar runtime.

| Campo | Conteúdo |
|-------|----------|
| Evidência | `SRC-008` + `SRC-009` + ausência de asserts para `parse_planner_step` inválido |
| Arquivos prováveis | `tests/test_agent_loop.py`, opcionalmente imports de `parse_planner_step` |
| Risco | Baixo; só testes |
| Aceite | `pytest` verifica: string sem `{` → `ValueError`; JSON inválido → `JSONDecodeError`; `action` desconhecida → `ValueError`; mock planner que levanta esses erros → `AgentRunResult.status == "error"` e passo `planner_error` |
| **Status** | **Atendida** — `tests/test_agent_loop.py` (parse direto + `OllamaJsonPlanner` + fake `complete`) |

**Não recomendado nesta rodada:** ligar `format` Ollama ao planner sem spike em `/api/generate` + `qwen2.5-coder:3b` (hipótese de compatibilidade, SRC-001).

---

## Entradas — rodada 2 (planner / `format` Ollama)

| ID | URL / arquivo | Origem | Versão / data | Nível | Evidência útil | Licença | Decisão YBY |
|----|---------------|--------|---------------|-------|----------------|---------|-------------|
| SRC-011 | https://github.com/ollama/ollama/blob/main/docs/api.md | Doc oficial Ollama | `main` (lido 2026-11-24) | L1 | **`POST /api/generate`**: `format` = string `"json"` **ou** objeto JSON Schema; exemplos de structured outputs e JSON mode na mesma rota que YBY já usa | MIT (Ollama) | Corrige hipótese da rodada 1: não é só `/api/chat` |
| SRC-012 | https://github.com/ollama/ollama/releases/tag/v0.5.4 | GitHub releases | v0.5.4 · 2024-12-17 | L1 | Release próximo ao blog structured outputs; menciona correção com `format: null` | — | **Não** inferir versão instalada no PC Hub (`GET /api/version` pendente) |
| SRC-013 | `src/engine/providers.py` (`build_ollama_generate_payload`, `OllamaProvider.complete`) | Código YBY | `main` @ a6f6aa0+ | L2 | `ollama_format` kw-only opcional; chave `format` só quando não `None` | — | **Implementado** (opt-in planner) |
| SRC-014 | `src/main.py` (`yby agent --local`) | Código YBY | idem | L2 | Único uso de `OllamaJsonPlanner` + `OllamaProvider`; `HybridEngine`/`ask` não passam por aqui | — | Dá para restringir `format` ao planner |
| SRC-015 | `tests/test_providers.py` | Testes YBY | idem | L2 | Asserções do corpo `/api/generate`; base para testar `format` opcional offline | — | Aceite offline sem inferência |

### Caminho real YBY (referência cruzada)

`OllamaJsonPlanner.plan` → `TextProvider.complete` → `OllamaProvider` **`POST {base}/api/generate`** (`build_ollama_generate_payload`) → campo `response` (string) → **`parse_planner_step`** → `ToolCallStep` \| `FinishStep` \| `AbortStep` (Pydantic; `action` ∈ `tool|finish|abort`).

**Parser:** cerca markdown opcional; `json.loads` no primeiro `{…}`; validação por modelo Pydantic. Schema Ollama **não substitui** o parser — só reduz JSON malformado.

**`format:"json"` vs JSON Schema (Ollama):**

| `format` | Efeito documentado | Uso planner |
|----------|-------------------|-------------|
| `"json"` | Objeto JSON bem formado; ainda exige instrução no prompt | Menor mudança; `parse_planner_step` inalterado |
| objeto JSON Schema | Saída deve aderir ao schema | Pode espelhar `action` + campos opcionais; `arguments`/`answer` continuam objetos abertos; compatibilidade por modelo **não** documentada para `qwen2.5-coder:3b` |

## Decisão rodada 2 — `format` no `OllamaJsonPlanner`

**Letra: A** — evidência **suficiente** para implementação pequena e **opt-in**, com bloqueio de ativação padrão até smoke no PC Hub.

| Critério | Situação |
|----------|----------|
| `/api/generate` + `format` | Confirmado (SRC-011) |
| Isolar do `ask`/híbrido | Confirmado (SRC-014) |
| Manter `parse_planner_step` + `planner_error` | Obrigatório; sem segunda chamada HTTP |
| Modelo Hub `qwen2.5-coder:3b` + versão Ollama | **Não verificado** nesta VM (bloqueio PC Hub) |

### Implementação (decisão A — concluída no código, smoke Hub pendente)

1. `build_ollama_generate_payload(..., *, ollama_format: str | None = None)` — inclui `format` só se não `None` (fase 1: só string `"json"`).
2. `OllamaProvider.complete(..., *, ollama_format=None)` — repassa ao payload; default preserva `ask`/híbrido.
3. `YBY_PLANNER_OLLAMA_FORMAT=json` → `OllamaJsonPlanner` passa `ollama_format="json"` só em `isinstance(..., OllamaProvider)`; instrução JSON no prompt mantida; JSON Schema **fora** desta rodada.
4. Assinatura `TextProvider` inalterada; fakes legados sem kw extra.

**Arquivos:** `src/engine/providers.py`, `src/agent_loop/planner.py`, `src/agent_loop/planner_env.py`, `tests/test_providers.py`, `tests/test_agent_loop.py`, `docs/DEV.md`.

**Testes offline:** payload sem `format` por default; POST com `format` opt-in; fake legado; env inválido antes de HTTP; uma iteração do planner sem tool em falha HTTP/parse.

**Aceite pós-código (PC Hub, fora desta rodada):** `ollama --version` ou `GET /api/version`; `yby agent --local` com env ativo; taxa de `planner_error` ≤ baseline em N prompts — **não** assumir sucesso só com pytest.

**Bloqueios:** versão Ollama e comportamento de `qwen2.5-coder:3b` com `format` no PC Hub; não declarar 300 fontes concluídas.

### Inspeção interna — timeout de tools (não conta como fonte externa)

| ID | Arquivo | Nível | Evidência | Decisão |
|----|---------|-------|-----------|---------|
| SRC-016 | `src/agent_loop/loop.py` (`_run_tool`) | L2 | `future.result(timeout=…)` + `ThreadPoolExecutor` com `shutdown(wait=True)` no `with` prendia o retorno de `run()` após timeout | **Corrigido:** `shutdown(wait=False)` no timeout; contrato = limite de espera, não cancelamento |
| SRC-017 | `src/agent_loop/planner.py` + `planner_prompt.py` | L2 | Histórico serializado integral no prompt antes da projeção | **Corrigido:** `YBY_PLANNER_PROMPT_MAX_CHARS`; histórico original intacto em `AgentRunResult` |

Scan externo de projetos semelhantes (relato ~40 páginas) **não** foi importado como verificação de código; hipótese cruzada só com inspeção YBY acima.

---

## Entradas — rodada 3 (YBY Glass G0)

Só fontes externas efetivamente lidas. Padrões, não código: nada foi copiado para o YBY.

| ID | URL / arquivo | Origem | Versão / data | Nível | Evidência útil | Licença | Decisão YBY |
|----|---------------|--------|---------------|-------|----------------|---------|-------------|
| SRC-018 | https://github.com/OpenSQZ/OpenGlass (`README.md`) | GitHub OpenSQZ | `main` @ `e022144` (lido 2026-11-26) | L1 | Óculos ESP32-S3 capturam frame + áudio; host próximo roda ASR/VLM/TTS local; logs/replay locais no host | README (§ License) declara Apache-2.0, mas **não há arquivo LICENSE/NOTICE/COPYING** em nenhum caminho da árvore completa de `e022144` (394 entradas, `truncated=false`; `gh api repos/OpenSQZ/OpenGlass/license` → 404; `license: null`); o artigo (SRC-020) cita só "open-source license", sem nomear | Adotar só a divisão sensor ↔ host; **não copiar código**: declaração só no README, sem texto de licença no repo (verificado 2026-11-26) |
| SRC-019 | https://github.com/OpenSQZ/OpenGlass/blob/main/docs/safety_privacy.md | GitHub OpenSQZ | idem | L1 | Local-first "não é garantia formal de privacidade"; minimizar retenção de brutos; nuvem só como opção habilitada explicitamente | idem | Base das regras d) e "sem promessa de privacidade total" da spec |
| SRC-020 | https://arxiv.org/html/2607.03213 | Artigo (ACL 2026 demo) | HTML arXiv (lido integralmente 2026-11-26, incl. limitações, ética e apêndices) | L1 | Captura **sob demanda de um frame** após a consulta; latência decomposta por estágio; abstenção segura e logs auditáveis; redimensionar o frame domina a latência e o TTS local não é gargalo; ética: minimizar retenção e não logar imagem bruta fora de avaliação | — | Captura discreta (1 ativação = 1 captura) e métricas por estágio; números do artigo **não** são metas YBY. PDF ACL = mesma obra, não recontado |
| SRC-021 | https://github.com/Artod/lstk-eye (`README.md`) | GitHub Artod | `main` @ `2da4e02` (lido 2026-11-26) | L1 | Óculos thin client; servidor dono de estado/planejamento; HUD por cenas JSON pequenas; `--profile mock` + simulador de dispositivo | MIT | Adotar padrão thin client + simulador offline |
| SRC-022 | `Artod/lstk-eye` `src/lstk_eye/protocol/messages.py` | GitHub Artod | idem | L2 | Primitivas discriminadas por tipo (`t`), mensagens planas e limitadas para parser embarcado; cena substitui a anterior | MIT | Inspira primitivas discriminadas por `kind` com limites; esquema YBY é próprio (coords normalizadas, sem seta/gyro) |

### Inspeção interna — rodada 3 (não conta como fonte externa)

| Arquivo | Evidência | Decisão |
|---------|-----------|---------|
| `src/agent_loop/tools.py` | `ToolSpec` + `ToolRegistry.run` validam args Pydantic | Tools Glass reutilizam `ToolSpec`; fora de `default_tool_registry` |
| `src/yby/audio/schemas.py` | Contratos T-Watch (D15) já existem | Glass não duplica; spec referencia |
| `src/memory/vault.py` | `Vault.write_note` | Destino futuro da retenção (G2); G0 usa sink em memória |

Descobertas vistas só em resultado de busca (ex.: página "Mentra HUD Constraints" do WeftOS) **não** foram lidas e **não** foram contadas.

---

*Próxima rodada sugerida:* smoke Hub planner+format; OWASP LLM07 (L1); para Glass G3, obter confirmação de licença do OpenGlass (sem arquivo LICENSE no repo) antes de qualquer reuso.