# Fluxo de solicitação de texto (`yby ask`)

## Objetivo e limites do diagrama

POC visual do fluxo **atual** de entrada de texto e resposta via `python yby.py ask "..."` (sem `--voice`). Cobre CLI → `HybridEngine` → roteamento → Ollama local e caminho de nuvem quando o roteamento pede.

**Fora do escopo deste diagrama (não inspecionados aqui como parte do fluxo):** voz (`--voice`, `listen`), `run`/`gate`/`src/safety`, RAG, gateway, agente P0, proxy LiteLLM, sandbox de código gerado.

**Não confundir:** decisão de **segurança de shell** (`gate`/`run`) com o **ask** (só gera texto; `SYSTEM_PROMPT` proíbe executar comandos no motor).

## Inspeção

| Item | Valor |
|------|--------|
| Branch | `main` |
| Commit-base inspecionado | `7866c227e19c63a11fa3037af8b1c08fef37617a` |
| Diagrama visual | [yby-request-flow.html](./yby-request-flow.html) |

**Alterações locais relevantes (não inspecionadas para o fluxo):** `AGENTS.md`, `.cursor/rules/yby.mdc` e `.cursor/rules/yby-economy.mdc` modificados antes desta tarefa; não fazem parte do runtime do `ask`.

## Componentes e conexões (código)

| # | Componente | Arquivo · símbolo | Conexão comprovada |
|---|------------|-------------------|-------------------|
| 1 | Atalho CLI | `yby.py` → `src.main.cli` | `yby.py` importa e chama `cli()` |
| 2 | Comando `ask` (texto) | `src/main.py` · `ask()` | Junta argumentos; ignora voz se `--voice` (fora deste diagrama) |
| 3 | Montagem do motor | `src/main.py` · `build_engine()` → `engine_from_env()` | `hybrid.py` · `engine_from_env` monta `EngineConfig`, `OllamaProvider`, `CascadingCloudProvider`, cache, `CloudBudget`, `confirm_fn` |
| 4 | Orquestração | `src/engine/hybrid.py` · `HybridEngine.reply()` | Chama roteamento; despacha `_local_first` ou `_cloud_first` |
| 5 | Roteamento | `src/engine/routing.py` · `decide_route()` | Retorna `RouteDecision` `local` ou `cloud` (sinais `YBY_HEAVY_*`, `--heavy`, frases) |
| 6 | Cache de respostas | `src/engine/cache.py` (via `HybridEngine._lookup` / `_store`) | Chave com prompt + model + `SYSTEM_PROMPT` |
| 7 | Provedor local | `src/engine/providers.py` · `OllamaProvider.complete()` | HTTP `POST {ollama}/api/generate` |
| 8 | Falha local sem nuvem auto | `src/engine/hybrid.py` · `_after_local_failure()` | `provider: none` + aviso; **não** chama nuvem (D12) |
| 9 | Pré-nuvem | `hybrid.py` · `_prepare_cloud_prompt()` | `trim_context` + `sanitize_for_cloud` |
| 10 | Porta orçamento / TTY | `src/engine/budget.py` · `CloudBudget.evaluate()`; `hybrid.py` · `_cloud_gate_reply()` | Orçamento/TTY/local_only ou confirmação cancelada devolve `EngineReply` bloqueado; `_cloud_first` chama `_local_after_cloud_block` (degradação local, não é `gate`/`run` de shell) |
| 11 | Nuvem primária | `providers.py` · `CascadingCloudProvider.complete_with_meta()` | Só `primary` (OpenRouter); **sem** failover automático para Grok |
| 12 | Degradação pós-nuvem | `hybrid.py` · `_local_after_cloud_block`, `_local_after_cloud_failure`, `_local_without_cloud_key` | Tentam Ollama local + avisos; falha dupla → `provider: none` |
| 13 | Saída CLI | `src/main.py` · `ask()` | `notice` em stderr; metadados `modelo:` em stderr; texto em stdout; exit `1` se `provider == "none"` |

### Somente em documentação (não verificado linha a linha nesta passagem)

- Tabelas de variáveis `.env` em `docs/DEV.md` espelham nomes usados em `EngineConfig.from_env()` — conferir `src/engine/config.py` ao atualizar.
- Decisões D12/D13 em `docs/DECISIONS.md` — alinhadas aos comentários em `hybrid.py` e `providers.py`.

### Divergências / limitações

- `docs/DEV.md` resume “Ollama → nuvem se pesado”; o código **não** sobe para nuvem após falha Ollama no caminho local (`_after_local_failure`).
- `engine_from_env` instancia provedor fallback Grok no construtor, mas `CascadingCloudProvider` **não** o chama em `complete_with_meta` (comentário issue #42).
- `CloudUsageLog.append` registra eventos de nuvem — presente no código, omitido do SVG para manter o foco no caminho de dados (ver `hybrid._cloud_gate_reply`, `_cloud_call`).
- O SVG prioriza **ramificações** (cache hit, sucesso, falha, degradação); setas verdes/vermelhas são convencão visual, não estados de runtime.

## Fluxo textual resumido

1. Usuário invoca `python yby.py ask "…"` (opcional `--heavy`).
2. `ask()` chama `build_engine().reply(texto, explicit_heavy=heavy)`.
3. `decide_route` classifica **local** (padrão) ou **cloud** (pesado / limites / frases).
4. **Local:** cache hit → `EngineReply` local **sem** Ollama; miss → Ollama → sucesso com `_store` ou `_after_local_failure` (`provider none`, sem nuvem automática).
5. **Cloud:** cache hit → `EngineReply` cloud **sem** HTTP; miss → sem chave → `_local_without_cloud_key`; com chave → `_cloud_gate_reply` (bloqueio orçamento/TTY **ou** confirmação cancelada) → `_local_after_cloud_block`; gate liberado → `_cloud_call` → sucesso cloud ou `_local_after_cloud_failure`. Degradações usam `_reply_from_local` (cache local opcional, Ollama, possível `provider none`).
6. `HybridEngine.reply` devolve `EngineReply`; `main.ask` imprime notice (stderr), testa `provider == none` (exit `1` sem linha modelo) ou imprime modelo (stderr) e texto (stdout), exit `0`. O SVG segue essa ordem.

## Como atualizar

1. Reinspecionar `src/main.py` (`ask`, `build_engine`) e `src/engine/hybrid.py`, `routing.py`, `providers.py`, `budget.py`.
2. Ajustar este Markdown (tabela de símbolos) e o SVG em `yby-request-flow.html`.
3. Atualizar commit-base e branch na seção **Inspeção**.
4. Não incluir fluxos novos (voz, agente, safety) sem evidência explícita no código.