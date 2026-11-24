# Desenvolvimento — YBY SEED

Como rodar e onde tocar código no v1 (PC Hub). Decisões vigentes: [DECISIONS.md](../DECISIONS.md). Mapa de repos: [REPOS.md](REPOS.md).

## Setup

```bash
make setup                            # venv + requirements + requirements-dev
# ou:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff, pytest
ollama pull qwen2.5-coder:3b
cp .env.example .env                  # preencha chaves só no .env local
```

Nunca commite `.env` nem chaves. O template é `.env.example` (`.env` já está no `.gitignore`).

### OpenRouter (somente no seu `.env`)

1. `cp .env.example .env` na raiz do repositório.
2. Defina **uma** das chaves lidas por `EngineConfig.from_env()` (`src/engine/config.py`):
   - `YBY_CLOUD_API_KEY=…`, ou
   - `OPENROUTER_API_KEY=…` (usada se `YBY_CLOUD_API_KEY` estiver vazia).
3. Opcional: `YBY_CLOUD_MODEL` (padrão `openrouter/free`) e `YBY_CLOUD_BASE_URL` (padrão `https://openrouter.ai/api/v1`).
4. Gate de nuvem: `YBY_CLOUD_REQUIRE_CONFIRM=1` (padrão), `YBY_CLOUD_MODE` diferente de `local_only`, TTY ou `YBY_CLOUD_ALLOW_NO_TTY=1` conforme política em `docs/CLOUD_USAGE_SPEC.md`.
5. O `ask` carrega o `.env` via `load_dotenv(override=False)` dentro de `EngineConfig.from_env()` — variáveis já exportadas no shell têm precedência.

Nuvem continua **somente** com roteamento pesado / `--heavy` (D12); falha local do Ollama não sobe para OpenRouter automaticamente.

Depois do setup: `make doctor` (ambiente) e `make test` (pytest).

### Smokes de aceite (somente no PC Hub)

Executar **depois** de `make check` verde local. Não colar chaves no terminal compartilhado nem no chat.

**Ollama (local real)**

| Item | Detalhe |
|------|---------|
| Pré-requisitos | Ollama no ar; `ollama pull qwen2.5-coder:3b` (ou `YBY_LOCAL_MODEL`); `.env` opcional para URLs/modelo |
| Comando | `python yby.py ask "Em uma frase: o que é uma lista ligada?"` |
| Sucesso | `exit 0`; stderr `modelo: local <modelo>`; stdout com texto gerado |
| **Não** é sucesso | `exit 1` com aviso D12 (“Nuvem não é acionada automaticamente…”) — só prova falha controlada sem Ollama |

**OpenRouter (nuvem real; exige sua aprovação e TTY)**

| Item | Detalhe |
|------|---------|
| Pré-requisitos | Chave só no `.env` (`YBY_CLOUD_API_KEY` ou `OPENROUTER_API_KEY`); `YBY_CLOUD_MODE` ≠ `local_only`; terminal interativo; confirmar `s` no gate |
| Comando | `YBY_CACHE_PATH=memory python yby.py ask --heavy "Responda apenas com a palavra OK."` |
| Sucesso (CLI) | `exit 0`; stderr `modelo: cloud <modelo>` com motivo contendo `heavy_flag`; stdout coerente; **sem** “Respondi com o modelo local …” |
| Sucesso (log) | Última sequência em `logs/cloud_usage.jsonl`: `cloud_requested` → `cloud_confirmed` → `cloud_completed` com `provider` `openrouter` ou `cloud` — **não** `cache` sozinho |
| Corroborar custo | Painel OpenRouter (atividade da chave); **não** use `input_tokens_estimate`/`output_tokens_estimate` do JSONL como fatura (heurística `len/4`) |
| Tokens reportados | Em `cloud_completed` de chamada HTTP fresca, campos opcionais `input_tokens_reported` / `output_tokens_reported` vêm do `usage` da API quando presente; ausência ou valor inválido **não** vira zero. Orçamento local (`CloudBudget`) continua somando só `*_estimate`. |
| Limites | `YBY_CLOUD_MAX_OUTPUT_TOKENS` → campo `max_tokens` no POST (teto de saída). Distinto de `YBY_CLOUD_CONTEXT_MAX_CHARS` (entrada) e de `YBY_CLOUD_*_TOKEN_LIMIT` (orçamento local) |

### Previsão de rota (offline, antes dos smokes)

Usa a mesma regra que o `ask` (`decide_route` + `YBY_HEAVY_*` via `EngineConfig.from_env()`). Não chama Ollama, cache, gate nem nuvem.

```bash
python yby.py route "Em uma frase: o que é uma lista?"
# previsão: …
# rota: local
# motivos: pedido dentro do limite local

python yby.py route --heavy "Responda apenas com OK."
# rota: cloud
# motivos: flag --heavy

python yby.py route "Pensa mais sobre recursão"
# rota: cloud
# motivos: frase explícita (lista YBY_HEAVY_PHRASES)  # rótulo fixo; não ecoa a frase nem o pedido
```

Útil para validar `--heavy` e limiares antes do smoke OpenRouter no PC. O comando **não** repete o texto do pedido na saída. Motivos de tamanho/complexidade mostram só contagens; gatilho por frase usa rótulo categórico (a decisão interna permanece igual ao `ask`).

## Comandos CLI

| Comando | O que faz |
|---|---|
| `python yby.py ask "..."` | texto via HybridEngine (Ollama → nuvem se pesado/`--heavy`) |
| `python yby.py run "..."` | porta de segurança → executa se permitido |
| `python yby.py gate "..."` | só decide (run/ask/refuse); não executa |
| `python yby.py route "..."` | previsão local/nuvem + motivos; **não** chama modelo nem rede |
| `python yby.py route --heavy "..."` | mesma regra de rota que `ask --heavy` (só a decisão) |
| `python yby.py note "título" texto da nota...` | grava no vault |
| `python yby.py recall "consulta"` | busca no vault |
| `python yby.py listen` | push-to-talk: Whisper → ask → Piper |
| `python yby.py ask --voice "..."` | mesmo fluxo com prompt opcional |
| `python yby.py hub` | keepalive do hub (Ollama); `--once` para uma checagem |
| `python yby.py agent "..." --script examples/agent_demo_script.json` | loop P0 (demo sem LLM) |
| `python yby.py agent "..." --local` | loop P0 com planner Ollama (só local) |
| `python yby.py evo report --day YYYY-MM-DD` | Evo v0.1: relatório local (offline) |
| `python -m src.evo report --seed-demo --no-ollama` | mesmo fluxo via módulo |

Agente P0 (fora do `ask`; `--local` exige Ollama). Exit: `0` completed, `2` aborted, `1` erro.

**Limite do prompt do planner (`YBY_PLANNER_PROMPT_MAX_CHARS`, padrão 8192):** teto conservador em **caracteres Python** (não tokens) sobre `system` + prompt do `OllamaJsonPlanner`. Abaixo do teto o histórico vai integralmente; acima disso o planner projeta um JSON válido com passos recentes, omissão explícita de passos antigos (`_yby_planner_omitted_steps`) e redução de observações grandes (`…[observação reduzida pelo limite do planner]…`). O histórico em `AgentRunResult` permanece integral. Se tarefa + tools + instruções já excedem o teto, falha com `planner_error` **antes** do HTTP. Distinto de `YBY_CLOUD_CONTEXT_MAX_CHARS` (nuvem/`ask`).

**Timeout de tools (`tool_timeout_seconds`, padrão 30s no `ControlledAgentLoop`):** limita só quanto o loop **espera** pelo retorno da tool em uma thread auxiliar. Em timeout o loop volta com `status=error` **sem** esperar o fim da thread (`shutdown(wait=False)`). Isso **não cancela** o handler Python em execução — efeitos tardios ainda são possíveis se a tool mutar estado ou I/O. Handlers atuais: `echo_json` (puro), `vault_search` (leitura). Use `tool_timeout_seconds=None` para executar na thread principal (sem teto). Sem cancelamento cooperativo nos handlers hoje.

```bash
python yby.py agent "demo P0" --script examples/agent_demo_script.json
python yby.py agent "demo P0" --script examples/agent_demo_script.json --json
```

Voz: `pip install -r requirements-voice.txt`, binário Piper no PATH e `YBY_PIPER_MODEL`. Sem isso, `ask` em texto segue; a voz avisa com mensagem clara.

Hub no boot: `bash scripts/install-hub-service.sh --enable`. Detalhe: [PLATFORM.md](PLATFORM.md).

## Variáveis úteis (`.env`)

| Prefixo / chave | Uso |
|---|---|
| `YBY_OLLAMA_*`, `YBY_LOCAL_MODEL` | Ollama do `ask` / hub |
| `YBY_CLOUD_*` / `OPENROUTER_API_KEY` | nuvem primária (OpenRouter free por padrão); só com roteamento pesado/`--heavy` + gate |
| `YBY_GROK_*` / `XAI_API_KEY` | Grok configurável; **não** é chamado automaticamente se OpenRouter falhar (D12, #42) |
| Falha Ollama (caminho local) | **não** dispara nuvem automática (D12 / fase P); ver `HybridEngine._after_local_failure` |
| `YBY_CACHE_*`, `YBY_CACHE_PATH`, `YBY_CLOUD_CONTEXT_MAX_CHARS` | cache TTL (disco em `~/.local/state/yby-seed/response-cache.json`; `YBY_CACHE_PATH=memory` desliga o arquivo) e limite de **entrada** (caracteres) na nuvem |
| `YBY_CLOUD_MAX_OUTPUT_TOKENS` | teto de **saída** na chamada cloud (`max_tokens` no POST; padrão 512). Distinto de orçamento `YBY_CLOUD_*_TOKEN_LIMIT` (contabilidade local) |
| `YBY_OLLAMA_NUM_CTX`, `YBY_OLLAMA_NUM_PREDICT`, `YBY_OLLAMA_THINK` | contexto local (padrão 4096, cabe em 4 GB), teto de tokens (padrão 1024) e thinking do Ollama (padrão omitido no JSON; `sim` envia `think: true`) |
| `YBY_PLANNER_PROMPT_MAX_CHARS` | teto do prompt do planner Ollama (caracteres; padrão 8192; mínimo 256). Só afeta projeção enviada ao modelo — não trunca o resultado do agente. |
| `YBY_PLANNER_OLLAMA_FORMAT` | **experimental, desligado por padrão:** só o planner (`yby agent --local`) envia `format:"json"` no `POST /api/generate` quando o valor é exatamente `json`; ausente/vazio mantém o comportamento anterior; outros valores falham na config antes do HTTP. Não afeta `ask`/híbrido. **Smoke pendente** no PC Hub (versão Ollama + `qwen2.5-coder:3b`). Não ativar em deploy até validar. |
| `YBY_HEAVY_*` | limiares / frases que sobem para nuvem |
| `YBY_VAULT_PATH` | pasta do vault Obsidian; backup: `scripts/backup-vault.sh` ([BACKUP.md](BACKUP.md)) |
| `YBY_VOICE_MAX_SECONDS` | teto da gravação push-to-talk (padrão 120) |
| `YBY_HUB_*` | intervalo/timeout do keepalive |
| `GATEWAY_TOKEN`, `FASTAPI_HOST` | gateway HTTP (fora do caminho do `ask`) |
| `YBY_DATABASE_URL` | Postgres opcional (agentes legados) |

Roteamento do `ask`: `src/engine/routing.py` e `src/engine/config.py`.

## Onde editar

| Objetivo | Pastas |
|---|---|
| Resposta / provedores / roteamento / cache | `src/engine/` |
| Hub keepalive | `src/platform/`, `scripts/install-hub-service.sh` |
| Allowlist e decisão de comando | `src/safety/`, `config/safety-allowlist.txt` |
| Execução após a porta | `src/actions/` |
| Notas / recall | `src/memory/` |
| Código gerado perigoso | `src/security/ast_guard.py` |
| CLI | `src/main.py`, `yby.py` |
| Testes | `tests/` |

**Não mexa** em `src/agents`, `src/rag`, `src/gateway`, `src/core` (legado), etc. a menos que a tarefa seja explicitamente sobre esse módulo. Eles não estão no caminho do `ask`. Ver [src/README.md](../src/README.md).

## LiteLLM (duas configs)

- **Canônica:** `litellm_config.yaml` na raiz (aliases `yby-local`, etc., alinhados a D3/D4).
- **Espelho antigo:** `litellm/config.yaml` — não use como fonte da verdade; preferir a raiz.

O `ask` atual fala com Ollama/nuvem direto via `src/engine`; o proxy LiteLLM é opcional/legado de custo.

## Testes e CI

```bash
make doctor            # Python, arquivos-chave, imports, alvos Make
make lint              # ruff check src tests
make test              # pytest tests -q
make check             # doctor + lint + test
```

O CI em push/`main` e em todo PR roda os mesmos três alvos e falha o check se algum quebrar. Detalhe e Bugbot: [CI.md](CI.md). Não precisa de Docker para o núcleo.

## O que não fazer

- Programar features do YBY em forks (`langgraph`, `llama.cpp`, …).
- Mesclar YBY / yby-core / FRANK_* para dentro deste repo.
- Colocar segredos no repositório.
- Tratar docs longos em `docs/` (arquitetura 7B, mobile, financiamento) como o caminho atual — ver [README do docs](README.md).
