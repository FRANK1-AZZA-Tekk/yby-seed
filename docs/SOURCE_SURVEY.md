# Levantamento rastreável de referências (benchmark YBY)

**Meta:** 300 fontes úteis · **Não concluído** · Registro canônico único (não duplicar em `FICHA_INVESTIGACAO.md`, que é wearable).

**Níveis:** `D0` descoberta (metadados) · `L1` leitura (doc/issue) · `L2` código/teste examinado.

**Rodada 1:** 2026-11-24 · `main` base `d098334175287f38639a2d7237c77cf90566ef2c`.

## Contagens (somente entradas **novas** desta rodada)

| Nível | Novas nesta rodada |
|-------|-------------------|
| D0 | 1 |
| L1 | 4 |
| L2 | 5 |
| **Total novas** | **10** |

**Acumulado útil:** 10 novas + 3 referências prévias reutilizadas (não recontadas).

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

*Próxima rodada:* aprofundar OWASP LLM07 (L1) e doc `api/chat` vs `api/generate` Ollama; meta acumulada 20/300.