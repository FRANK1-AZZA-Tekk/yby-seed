# Decisões — YBY SEED

Decisões do dono em **2026-11-11** substituem a redação anterior quando o assunto é o mesmo. O texto antigo fica registrado na própria decisão.

## D1 — PC-first

A fase atual foca exclusivamente no PC Hub. Mobile e ESP32 ficam fora do v1; o código saiu da árvore e permanece no histórico do git.

A plataforma desse PC Hub está em D9: servidor doméstico sempre ligado.

## D2 — Documentação antes de código

Inventário real de repositórios e arquitetura por domínios antes de qualquer código novo.

## D3 — Local-first, nuvem sob demanda (2026-11-11)

Ollama local primeiro. A nuvem entra quando a heurística de complexidade ou tamanho dispara, ou quando a pessoa pede (`--heavy`, frases como "pensa mais").

O provedor de nuvem é compatível com a API da OpenAI e configurável por URL, modelo e chave. O padrão é **Grok (xAI)**. **OpenRouter** continua disponível como configuração alternativa, não como destino automático.

Substitui a redação de D3 anterior: "Ollama local primeiro; OpenRouter apenas como fallback."

## D4 — Modelo local (2026-11-11)

Padrão local e único modelo local: `qwen2.5-coder:3b`, o vencedor dos benchmarks yby-seed-local. Cabe na GTX 1650 de 4 GB. Modelos 7B não entram no v1.

Substitui `llama3.2:3b` e as recomendações antigas de Qwen 7B. O alias `yby-local` do LiteLLM aponta para esse modelo.

## D5 — MVP sem Docker no núcleo

O núcleo (`yby.py` + o motor de `ask`) funciona sem containers. Serviços entram em fases posteriores.

## D6 — Automações seguras

Toda skill começa em dry-run e só executa após confirmação do usuário.

Para comandos de terminal, D10 é a regra vigente: a allowlist roda direto; o resto ainda pede confirmação.

## D7 — Consolidação de repositórios

Materiais de YBY, YBY Zero e outros projetos são revisados e unificados no YBY SEED quando fizer sentido técnico.

## D8 — Memória (2026-11-11)

A memória da pessoa é um vault Obsidian em Markdown, com índice vetorial por cima. O vault sincroniza com o servidor de casa via Syncthing.

`src/memory` lê e grava essa pasta (`YBY_VAULT_PATH`, comandos `note` e `recall`). O `ask` ainda não grava nota sozinho. O Syncthing não é implementado aqui: ele só sincroniza a pasta.

## D9 — Plataforma (2026-11-11)

O YBY SEED roda num servidor doméstico sempre ligado. Esse servidor é o PC Hub.

## D10 — Segurança de comandos (2026-11-11)

A allowlist cobre comandos somente leitura (`ls`, `cat`, `df`, estado do sistema e equivalentes), comandos `git` e scripts dentro da pasta do YBY. Qualquer outro comando pede sim ou não no terminal. Padrões destrutivos óbvios são recusados.

O módulo `src/safety` classifica o comando em run, ask ou refuse e faz a pergunta no terminal. Ele não executa o comando. O `ask` também não executa shell.

## Auditoria de 2026-11-11

- O GovernanceAgent usa uma guarda AST (`src/security/ast_guard.py`), a mesma do sandbox. As regexes antigas não bloqueavam nada.
- O gateway HTTP escuta em `127.0.0.1` por padrão (`FASTAPI_HOST`) e exige `GATEWAY_TOKEN` nas rotas de dados. `/health` fica aberto.
- A URL do Postgres vem de `YBY_DATABASE_URL`. Não há senha no código.
- O workflow da Strix foi removido: o instalador retornava 404 e não havia chave.
- O CI é `ruff` e `pytest` em push e pull request.
- `src/mobile` e `firmware/` saíram da árvore. O histórico do git guarda os arquivos. Ver `docs/archive/FORA-DO-V1.md`.
