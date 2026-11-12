# Decisões — YBY SEED

Decisões do dono em **2026-11-11** substituem a redação anterior quando o assunto é o mesmo. O texto antigo fica registrado na própria decisão.

## D1 — PC-first

A fase atual foca exclusivamente no PC Hub. Mobile e ESP32 ficam fora do v1; o código saiu da árvore e permanece no histórico do git.

A plataforma desse PC Hub está em D9: servidor doméstico sempre ligado.

## D2 — Documentação antes de código

Inventário real de repositórios e arquitetura por domínios antes de qualquer código novo.

## D3 — Local-first, nuvem sob demanda (2026-11-11; nota OpenRouter 2026-11-11)

Ollama local primeiro. A nuvem entra quando a heurística de complexidade ou tamanho dispara, ou quando a pessoa pede (`--heavy`, frases como "pensa mais").

O provedor de nuvem é compatível com a API da OpenAI e configurável por URL, modelo e chave. Destino de nuvem padrão: **OpenRouter com modelo free** (`openrouter/free`). Se OpenRouter falhar ou não houver chave, fallback para **Grok (xAI)**. Chaves só no `.env` do servidor.

Nota do dono (aprovado): OpenRouter free é o alvo de nuvem padrão; Grok é o fallback.

Substitui a redação intermediária em que Grok era o destino automático e OpenRouter só configuração alternativa. Também substitui a redação antiga "Ollama local primeiro; OpenRouter apenas como fallback."

## D4 — Modelo local (2026-11-11)

Padrão local e único modelo local: `qwen2.5-coder:3b`, o vencedor dos benchmarks yby-seed-local. Cabe na GTX 1650 de 4 GB. Modelos 7B não entram no v1.

Substitui `llama3.2:3b` e as recomendações antigas de Qwen 7B no **CLI**.

**Nota D12 (2026-11-12):** o alias LiteLLM `yby-local` no stack Docker (`src/yby_seed`) usa `qwen2.5-coder:7b-instruct-q3_K_M` com `num_ctx: 4096` e semáforo VRAM — não contradiz o 3B do `ask`, são **entradas diferentes**.

## D12 — Exocórtex CLI e dual stack (2026-11-12)

- **CLI v1:** `yby skill` / `ask --skill` → `SkillManager` → dry-run → confirmação → `src/actions` (allowlist) → ledger JSONL `data/exocortex_ledger.jsonl`.
- **API Vibe Coding:** `src/yby_seed` (agentes, sandbox, export) — não substitui o CLI; ponte opcional `GET /v1/seed/exocortex/recent`.
- **`process-manager/`:** prototipo não canônico até redesign com allowlist.

## D5 — MVP sem Docker no núcleo

O núcleo (`yby.py` + o motor de `ask`) funciona sem containers. Serviços entram em fases posteriores.

## D6 — Automações seguras

Toda skill começa em dry-run e só executa após confirmação do usuário.

Para comandos de terminal, D10 é a regra vigente: a allowlist roda direto; o resto ainda pede confirmação.

## D7 — Consolidação de repositórios

Materiais de YBY, YBY Zero e outros projetos são revisados e unificados no YBY SEED quando fizer sentido técnico.

Em 2026-11-11 o inventário ficou assim: o v1 programa-se neste repositório. YBY (wearable), yby-core (LangGraph), FRANK_ZER0 (TypeScript, Android, ESP32) e FRANK_ZERO (sem código) permanecem separados. Forks de terceiros não são copiados. O mapa está em `docs/REPOS.md`.

**Clarificação (organização):** “consolidar” = inventário, docs e fronteiras claras — **não** copiar árvores de YBY / yby-core / FRANK para dentro do seed. PRs que absorvem esses produtos no `yby-seed` vão contra este escopo.

## D8 — Memória (2026-11-11)

A memória da pessoa é um vault Obsidian em Markdown, com índice vetorial por cima. O vault sincroniza com o servidor de casa via Syncthing.

`src/memory` lê e grava essa pasta (`YBY_VAULT_PATH`, comandos `note` e `recall`). O `ask` ainda não grava nota sozinho. O Syncthing não é implementado aqui: ele só sincroniza a pasta.

## D9 — Plataforma (2026-11-11)

O YBY SEED roda num servidor doméstico sempre ligado. Esse servidor é o PC Hub.

Operação: unit systemd de usuário (`scripts/yby-hub.service` + `scripts/install-hub-service.sh`) mantém um keepalive fino (`python -m src.platform.hub` / `yby hub`) que só checa o Ollama — **não** sobe o gateway MQTT. Vault via Syncthing (`examples/syncthing/`, `docs/syncthing/`). Cache de respostas e limite de contexto antes da nuvem. Detalhe: [docs/PLATFORM.md](docs/PLATFORM.md).

## D10 — Segurança de comandos (2026-11-11)

A allowlist cobre comandos somente leitura (`ls`, `cat`, `df`, estado do sistema e equivalentes), comandos `git` e scripts dentro da pasta do YBY. Qualquer outro comando pede sim ou não no terminal. Padrões destrutivos óbvios são recusados.

O módulo `src/safety` classifica o comando em run, ask ou refuse e faz a pergunta no terminal. Ele não executa o comando. O `ask` também não executa shell.

A camada `src/actions` é quem executa: só chama o subprocesso depois de `run`, ou de `ask` com sim. `refuse` nunca chega ao shell. O CLI é `python yby.py run "..."`. `gate` continua só decidindo.

## D11 — Voz local (2026-11-11)

STT com **faster-whisper** (padrão `base` em CPU/`int8`; `small` via `YBY_WHISPER_MODEL`). TTS com **Piper** (binário + `.onnx` em `YBY_PIPER_MODEL`). Cabe no servidor de casa (GTX 1650 4 GB / CPU).

CLI: `python yby.py listen` ou `python yby.py ask --voice` — grava até Enter, transcreve, chama o HybridEngine e fala a resposta. Dependências em `requirements-voice.txt` (opcionais). Sem elas, o texto (`yby ask "..."`) continua funcionando e a voz avisa com mensagem clara.

## Auditoria de 2026-11-11

- O GovernanceAgent usa uma guarda AST (`src/security/ast_guard.py`), a mesma do sandbox. As regexes antigas não bloqueavam nada.
- O gateway HTTP escuta em `127.0.0.1` por padrão (`FASTAPI_HOST`) e exige `GATEWAY_TOKEN` nas rotas de dados. `/health` fica aberto.
- A URL do Postgres vem de `YBY_DATABASE_URL`. Não há senha no código.
- O workflow da Strix foi removido: o instalador retornava 404 e não havia chave.
- O CI é `ruff` e `pytest` em push e pull request.
- `src/mobile` e `firmware/` saíram da árvore. O histórico do git guarda os arquivos. Ver `docs/archive/FORA-DO-V1.md`.

## D12 — Economia de execução (2026-11-11)

Prioridade: reduzir custo de tokens e créditos, sem reduzir a qualidade mínima necessária.

Tetos operacionais:
- Cursor Premium: R$ 100 por mês.
- OpenRouter: R$ 50 por mês.

Regras:
- O caminho padrão é local: Ollama, `qwen2.5-coder:3b`, testes e ferramentas locais.
- Nuvem só entra quando a tarefa exigir capacidade indisponível localmente ou quando o usuário autorizar explicitamente.
- OpenRouter é alternativa manual/configurável, não fallback automático.
- Grok/xAI pode ser o destino de nuvem configurado; OpenRouter permanece opcional.
- Cursor executa tarefas com escopo fechado: arquivos-alvo, critério de aceite, diff mínimo e testes.
- Evitar exploração ampla do repositório, refatoração não solicitada, documentação nova sem aprovação e subagentes paralelos.
- Modelos locais de 7B ou maiores não entram no v1, salvo decisão explícita do dono.
- Antes de usar nuvem, o sistema deve informar o motivo e, quando possível, o custo estimado.
- Toda execução de nuvem deve registrar modelo, finalidade, tokens estimados e resultado no log local.

Interpretação:
- “máximo: local apenas” proíbe chamadas de nuvem.
- “pode usar OpenRouter se travar” permite nuvem apenas após falha local documentada.
- Sem instrução explícita, usar o caminho local primeiro.

## D13 — Voz em nuvem opcional (futura)

A voz local permanece como padrão, conforme D11: faster-whisper + Piper.

A integração Grok Voice/xAI é opcional e futura. Ela não substitui D11 e não entra no v1.

Quando for avaliada, ela deve:
- exigir autorização explícita do usuário;
- nunca enviar áudio sem confirmação;
- operar apenas como rota alternativa;
- registrar sessões, tokens e custo;
- manter o modo local funcional sem internet;
- entrar somente após a fase P — PC Hub sempre ligado — estiver estável.
