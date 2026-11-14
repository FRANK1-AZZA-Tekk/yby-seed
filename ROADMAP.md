# Roadmap — YBY SEED

Estado alinhado ao checklist em [docs/REPOS.md](docs/REPOS.md) e às decisões [D1–D11](DECISIONS.md) (com [D12–D13](DECISIONS.md) para economia e voz em nuvem). Roadmap histórico (MQTT/wearable): [docs/ROADMAP.md](docs/ROADMAP.md) — **não** substitui as fases abaixo.

| Fase | Descrição | Status |
|---|---|---|
| 0 | Consolidação: escopo PC Hub, docs, separação de repos | Feito |
| 1 | Núcleo local (`yby.py` + Ollama + nuvem sob demanda) | Feito |
| 1b | Porta + execução (`safety` / `actions`) + vault | Feito |
| 1c | Voz local (Whisper + Piper) | Feito |
| 2 | Qualidade contínua (Ruff + Pytest no CI) | Feito |
| **P** | **Plataforma** — hub sempre ligado (D9): serviço, boot, sync Syncthing | Em andamento (spec pronta; implementação pendente) |
| 3+ | Skills dry-run, agentes no caminho do `ask`, gateway exposto | Depois |
| Futuro | Mobile / ESP32 | Depois |

## Escopo

- **v1 agora:** `engine`, `safety`, `actions`, `memory`, `voice`, `platform`, `security/ast_guard`, testes — ver [src/README.md](src/README.md).
- **Não fazer:** absorver YBY / yby-core / FRANK_* neste repo; programar em forks ([docs/REPOS.md](docs/REPOS.md)).
- **Fora do v1:** mobile e firmware ([docs/archive/FORA-DO-V1.md](docs/archive/FORA-DO-V1.md)).
- **No disco, fora do `ask` hoje:** `src/agents/`, `src/rag/`, `src/gateway/`, [skills/](skills/) — evolução via fases 3+ e trilha abaixo, sem quebrar o núcleo.

---

## AI Agents Developer Track

Trilha prática para levar o YBY SEED de **CLI local confiável** a **agentes production-ready no PC Hub**, respeitando local-first (D3, D4, D12), porta de comandos (D10), dry-run de skills (D6) e separação de repositórios (D7). Ordem recomendada: concluir estabilização da **fase P** em paralelo às fases A–B; fases C–D assumem fase P aceita ([docs/PHASE-P.md](docs/PHASE-P.md)).

### Fase A — Fundamentos operacionais

| Campo | Conteúdo |
|---|---|
| **Objetivo** | Dominar o stack operacional e produzir um assistente mínimo com saída estruturada validada, usando o mesmo Ollama/`qwen2.5-coder:3b` (D4) e padrões do repo. |
| **Duração estimada** | 2–3 semanas (tempo parcial) |
| **Pré-requisitos** | [docs/DEV.md](docs/DEV.md), ambiente com Ollama, `pytest` verde no clone |
| **Tópicos essenciais** | Python intermediário (funções, classes, typing, `async`, exceções, módulos, [tests/](tests/)); Git/GitHub, terminal Linux, venv; REST, JSON, HTTP, erros e auth (padrão do [gateway](src/gateway/) em loopback + `GATEWAY_TOKEN` quando usado); LLM (tokens, context window, temperatura, structured outputs, custo/latência — ver [MODEL_CARD.md](MODEL_CARD.md), [docs/PLANEJAMENTO-CUSTOS-IA.md](docs/PLANEJAMENTO-CUSTOS-IA.md)); prompt engineering (system, few-shot, templates, JSON Schema). |
| **Entregável obrigatório** | Assistente mínimo (script ou comando isolado **fora** do fluxo `ask` até revisão): recebe tarefa → chama **uma** API/ferramenta allowlisted (ex.: HTTP local ou função Python pura) → retorna JSON validado por schema (sem shell livre). |
| **Critérios de conclusão** | Schema validado em falha e sucesso; nenhum segredo no código; teste `pytest` cobrindo happy path + erro de validação; documentação de 1 página no vault via `note` opcional. |
| **Métricas de sucesso** | 100% das respostas do entregável passam validação de schema; latência medida anotada; zero chamadas de nuvem se não configurada (D12). |
| **Riscos e salvaguardas** | Execução acidental de shell → usar só `gate`/`run` e allowlist ([config/safety-allowlist.txt](config/safety-allowlist.txt)); vazar chave → só `.env`; confiar no LLM → validar saída sempre. |
| **Relação YBY** | Base para entender [src/engine](src/engine) (`ask`, cache, [routing](src/engine/routing.py)), CLI [yby.py](yby.py) e cultura de testes do CI. |

### Fase B — Agente funcional

| Campo | Conteúdo |
|---|---|
| **Objetivo** | Agente de pesquisa/documentos com tool calling, memória e RAG local, com aprovação humana antes de escrita ou execução. |
| **Duração estimada** | 4–6 semanas |
| **Pré-requisitos** | Fase A concluída; vault configurado ([docs/MEMORY.md](docs/MEMORY.md)); leitura de [src/agents/README.md](src/agents/README.md) e testes em [tests/test_agents*.py](tests/). |
| **Tópicos essenciais** | Tool/function calling, schemas e validação de args; ReAct, decomposição, retries; memória curta/longa (histórico, resumo, vault); RAG (chunking, embeddings, metadados, avaliação — [docs/ARCHITECTURE_RAG.md](docs/ARCHITECTURE_RAG.md), [src/rag/](src/rag/), Qdrant opcional em [docker-compose.yml](docker-compose.yml)); grafos de estado (referência **yby-core** em repositório separado — D7; ou loop próprio inspirado em stubs em `src/agents/`); human-in-the-loop (D6, D10: `safety` decide, `actions` executa). |
| **Entregável obrigatório** | Agente de pesquisa: consulta **fontes permitidas** (vault + paths allowlisted), produz resposta com **citações**, persiste rascunho no vault, e só grava/executa após confirmação explícita (mesmo padrão `ask` → sim/não do terminal). |
| **Critérios de conclusão** | Cada afirmação factual tem fonte rastreável; escrita bloqueada sem aprovação; eval manual em ≥10 perguntas documentado; `pytest` relevante verde (`test_vault`, `test_rag`, agentes se tocados). |
| **Métricas de sucesso** | Taxa de citação correta ≥80% no conjunto de eval manual; 0 execuções `actions` sem passar por `safety`; recall do vault utilizável em ≥70% dos casos de “lembrar nota”. |
| **Riscos e salvaguardas** | RAG sem metadados → exigir chunk + metadado obrigatório; alucinação → citação ou abstinência; escrita no vault → tratar como ação sensível (D10). |
| **Relação YBY** | [src/memory](src/memory) (`note`/`recall`), [src/safety](src/safety) + [src/actions](src/actions), skills em [skills/](skills/) (dry-run D6), planejamento legado em `src/agents/`. |

### Fase C — Produção segura

| Campo | Conteúdo |
|---|---|
| **Objetivo** | Agente rodando no PC Hub com MCP (servidor próprio), guardrails, observabilidade, evals, deploy opcional e controle de custo — ainda local-first. |
| **Duração estimada** | 6–8 semanas |
| **Pré-requisitos** | Fase B; fase **P** estável ([docs/PHASE-P-CHECKLIST.md](docs/PHASE-P-CHECKLIST.md)); leitura de [SECURITY.md](SECURITY.md), [src/security/ast_guard.py](src/security/ast_guard.py). |
| **Tópicos essenciais** | MCP (hosts, clients, servers, tools, auth — **implementação nova** no seed, alinhada a necessidade YBY); MCP server YBY para capacidade concreta (ex.: leitura de vault, automações em `skills/`, hub/Ollama health — sem shell amplo); segurança (least privilege, allowlist, sandbox, prompt injection, secrets, audit); observabilidade ([docs/OBSERVABILITY.md](docs/OBSERVABILITY.md), logs de nuvem D12); evals (datasets, regressão, testes em [tests/](tests/)); deploy ([src/gateway/](src/gateway/), Docker opcional, Postgres/Redis **fases futuras** em [ARCHITECTURE.md](ARCHITECTURE.md)); roteamento/custo ([litellm_config.yaml](litellm_config.yaml), [tests/test_budget.py](tests/test_budget.py)). |
| **Entregável obrigatório** | Agente “production-ready **local**”: MCP server versionado, tracing/log estruturado de tool calls, suite de evals reprodutível, guardrails (AST + allowlist + confirmação), empacotamento Docker **opcional** (núcleo continua sem Docker — D5). |
| **Critérios de conclusão** | MCP server com escopo fechado documentado; evals rodam no CI ou script documentado; gateway só em `127.0.0.1` se ativo; custo/latência registrados por tarefa; nenhuma regressão em `ruff` + `pytest` do v1. |
| **Métricas de sucesso** | Ver tabela [Métricas de agente](#métricas-de-agente); bloqueio documentado quando guardrail dispara; custo por tarefa dentro de tetos D12. |
| **Riscos e salvaguardas** | MCP com privilégio alto → uma capability por server; dados sensíveis → local por padrão; demo exposta → sem bind público; LiteLLM → budget em config, chaves só em `.env`. |
| **Relação YBY** | [src/platform](src/platform) (hub), gateway/token, `ast_guard`, LiteLLM como proxy **opcional**, testes `test_gateway_auth`, `test_ast_guard`, `test_cloud_usage_log`. |

### Fase D — Especialização YBY

| Campo | Conteúdo |
|---|---|
| **Objetivo** | Definir o primeiro agente de produto YBY (automação pessoal / wearable futuro) sem implementar mobile/ESP32 no v1. |
| **Duração estimada** | 3–4 semanas (especificação + POC mínima) |
| **Pré-requisitos** | Fase C; agente único confiável; D7 e [docs/future/](docs/future/) lidos. |
| **Tópicos essenciais** | Multi-agentes **somente** se um agente instrumentado não bastar; multimodal (voz [src/voice](src/voice), documentos vault, sensores **futuro**); roteamento híbrido local/nuvem por privacidade/latência/custo ([src/engine](src/engine), D3/D12); integração futura ESP32/wearables via repos [YBY](https://github.com/FRANK1-AZZA-Tekk/YBY) / [FRANK_ZER0](https://github.com/FRANK1-AZZA-Tekk/FRANK_ZER0) — não neste repo; privacidade por design (vault local vs contexto enviado à nuvem). |
| **Entregável obrigatório** | **Especificação de produto** (PRD curto): persona, fluxos, tools permitidas, política de aprovação, métricas-alvo, riscos; POC opcional só com componentes já no seed (voz + memória + gate). |
| **Critérios de conclusão** | PRD revisável; nenhum requisito que force mobile/firmware no v1; roteamento documentado (local vs `--heavy` / explícito); evals e limites de iteração definidos. |
| **Métricas de sucesso** | Metas numéricas copiadas da tabela de métricas; cenários de privacidade classificados (dado nunca sai / pode sair com consentimento). |
| **Riscos e salvaguardas** | Multi-agente prematuro → veto explícito no PRD; wearable → apenas interface futura; voz em nuvem → só D13, não v1. |
| **Relação YBY** | Visão [README.md](README.md), [HARDWARE_SPEC.md](HARDWARE_SPEC.md), [MODEL_CARD.md](MODEL_CARD.md); orquestração externa permanece em **yby-core**. |

---

## Princípios de agentes YBY

1. **Function over form:** utilidade real, simplicidade e confiabilidade acima de demos chamativas.
2. **Local-first por padrão;** nuvem só quando necessário ou autorizado (D3, D12).
3. **Menor privilégio** em todas as ferramentas (D10, allowlist).
4. **Nenhuma ação destrutiva, financeira, envio de mensagem ou alteração de sistema** sem aprovação humana explícita (D6, D10).
5. **Toda ferramenta** com contrato claro, validação de entrada, limite de escopo e log de auditoria.
6. **Autonomia é meio;** o objetivo é execução confiável.
7. **Todo agente** precisa de evals, tracing, limite de iteração e capacidade de abortar.
8. **Multi-agentes** só quando um agente único bem instrumentado não resolver (D7: não duplicar yby-core sem necessidade).
9. **Custo, latência e privacidade** são critérios de arquitetura, não otimizações tardias.

---

## Métricas de agente

| Métrica | Definição operacional | Onde instrumentar (alvo) |
|---|---|---|
| Taxa de conclusão da tarefa | % tarefas marcadas “concluída” no eval set | `tests/`, dataset de eval (fase C) |
| Precisão na seleção de ferramenta | % passos com tool correta vs gold | logs de tool call / eval trajetória |
| Taxa de alucinação / não fundamentada | % respostas sem citação ou fonte quando exigido | eval manual + LLM-as-judge (revisão humana final) |
| Número médio de passos por tarefa | média de iterações tool+LLM | tracing |
| Latência ponta a ponta | tempo usuário → resposta final | engine/gateway; ver [MODEL_CARD.md](MODEL_CARD.md) |
| Custo por tarefa concluída | tokens/$ por tarefa (nuvem) | [tests/test_cloud_usage_log.py](tests/test_cloud_usage_log.py), D12 |
| Taxa de falha recuperada por retry | % falhas resolvidas em retry permitido | engine / agent loop |
| Taxa de bloqueio por guardrail | % tentativas barradas (AST, safety, schema) | `ast_guard`, `safety` |
| Taxa de aprovação humana necessária | % ações que exigiram sim/não | `safety` + métricas CLI |
| Regressões pós-mudança | % evals que pioram após prompt/modelo/tool | CI eval job (fase C) |
| Satisfação / correção humana | % respostas editadas ou rejeitadas pelo usuário | feedback no vault ou log opcional |

---

## Anti-patterns

- Criar multi-agentes antes de validar um agente único instrumentado.
- Dar acesso amplo a arquivos, rede, shell, e-mail ou dispositivos (viola D10).
- Tratar o LLM como fonte de verdade sem validação ou citação.
- Usar RAG sem metadados, chunking adequado e avaliação ([docs/ARCHITECTURE_RAG.md](docs/ARCHITECTURE_RAG.md)).
- Deixar segurança para depois (AST, gate, token do gateway).
- Medir apenas “a resposta parece boa”.
- Construir autonomia sem limites, logs ou botão de parada.
- Acumular frameworks sem necessidade (D5: núcleo sem Docker).
- Enviar dados sensíveis à nuvem sem necessidade ou consentimento (D12).
- Confundir demo com produto production-ready (fase P + evals + guardrails).

---

## Backlog priorizado

Itens são **issues futuras** no sentido de planejamento; não implicam código neste PR. Prioridade: **P0** essencial próximo MVP agente → **P3** futuro YBY.

### P0 — essencial para o próximo MVP agente

| Título | Objetivo | Critério de aceite | Dependências | Risco de segurança |
|---|---|---|---|---|
| Agente mínimo com loop controlado | Loop LLM + tools com teto de iterações e abort | Max N passos; abort limpa estado; teste automatizado | Fase A; `src/agents/` ou módulo novo fora do `ask` | Médio: loop sem teto |
| Contratos de tools e schemas | JSON Schema por tool, validação antes de executar | Falha de arg não chama `actions` | P0 loop | Alto sem validação |
| Memória de sessão e resumo | Histórico + resumo para caber no contexto | Resumo reprodutível; vault intacto | [src/memory](src/memory) | Baixo |
| Integrar trajetória ao `ask` (3+) | Entrada única CLI para modo agente opt-in | `ask` default inalterado; flag/documentação | P0, [docs/REPOS.md](docs/REPOS.md) | Médio |

### P1 — importante para produção

| Título | Objetivo | Critério de aceite | Dependências | Risco |
|---|---|---|---|---|
| RAG local com metadados | Busca vault + docs com chunk + metadado | Precisão medida em eval ≥ baseline | [src/rag](src/rag), Qdrant opcional | Médio: vazamento de paths |
| MCP server automação local | Expor capacidade YBY (vault read, skill dry-run) via MCP | Escopo fechado; auth documentada | Fase C | Alto se overprivileged |
| Guardrails e aprovação humana | Unificar AST + safety + confirmação em fluxo agente | Escrita/execução sempre gated | D10, `ast_guard` | Alto |
| Dataset de evals e regressão | Conjunto fixo de tarefas + trajetórias gold | CI ou `make test` estendido documentado | `tests/` | Baixo |
| Tracing e custo por execução | Log estruturado por tarefa (local/nuvem) | Campos D12 preenchidos | engine, [litellm_config.yaml](litellm_config.yaml) | Médio: logs com PII |
| Política de permissões por ferramenta | Matriz tool → run/ask/refuse | Doc + testes | `safety`, allowlist | Alto |

### P2 — melhoria e escalabilidade

| Título | Objetivo | Critério de aceite | Dependências | Risco |
|---|---|---|---|---|
| Roteamento local/nuvem por tarefa | Política além de heurística atual | Testes em [tests/test_engine.py](tests/test_engine.py) | [routing.py](src/engine/routing.py) | Médio: nuvem involuntária |
| Skills dry-run no caminho do agente | Ativar [skills/](skills/) só após confirmação | D6 respeitado em 100% dos casos | P0, skills README | Médio |
| Gateway FastAPI endurecido | API agente só loopback | `test_gateway_auth` verde | [src/gateway](src/gateway) | Alto se exposto |
| Cache e paralelismo seguro de tools | Reduzir latência sem race em `actions` | Testes de concorrência documentados | engine | Médio |
| Estabilizar fase P | Hub systemd + Syncthing + backup vault | [PHASE-P](docs/PHASE-P.md) checklist 8/8 | D9 | Médio: perda de vault |

### P3 — futuro e especialização YBY

| Título | Objetivo | Critério de aceite | Dependências | Risco |
|---|---|---|---|---|
| Especificação agente wearable/automação pessoal | PRD fase D | Aprovado sem escopo mobile no v1 | Fase D | Baixo |
| Documentar arquitetura de agentes no ARCHITECTURE.md | **Proposta** futura, sem alterar D1–D11 | Seção marcada “proposta”; link para este roadmap | Aprovação explícita | Baixo |
| Ponte read-only com yby-core | Avaliar LangGraph/MQTT sem merge | ADR curto em DECISIONS ou doc | D7, repo externo | Alto se merge |
| Multimodal voz+agente | `listen` aciona loop agente local | Sem D13; deps voice opcionais | [src/voice](src/voice) | Médio |
| Integração ESP32/wearable | Só após v1 PC estável | Nenhum firmware neste repo | [FORA-DO-V1](docs/archive/FORA-DO-V1.md) | Alto |

---

## Relação com fases 3+ e Futuro

- **Fase 3+** (tabela inicial): skills dry-run, agentes no caminho do `ask`, gateway exposto → cobertos pelo backlog P0–P2 e fases B–C desta trilha.
- **Futuro (mobile/ESP32):** permanece fora do v1; fase D produz especificação e interfaces, não firmware neste repositório.

## Referências rápidas

- Arquitetura atual: [ARCHITECTURE.md](ARCHITECTURE.md) · Decisões: [DECISIONS.md](DECISIONS.md) · Dev: [docs/DEV.md](docs/DEV.md) · Plataforma: [docs/PLATFORM.md](docs/PLATFORM.md) · Segurança de comandos: D10 + [src/safety](src/safety)