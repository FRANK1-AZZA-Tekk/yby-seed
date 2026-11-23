# YBY SEED — Claude Code

Sessão: Sonnet. Consultor: Opus (`claude --model sonnet --advisor opus`).
Subagentes Haiku só-leitura: `search`, `grep`, `docs` (um por vez).
Instruções gerais: [AGENTS.md](AGENTS.md). Local-first: D4 / D12. Núcleo: [docs/DEV.md](docs/DEV.md).

## Três portões do consultor

Consulte o Opus só nestes momentos:

1. Antes de travar o plano (arquivos-alvo, critério de aceite, testes).
2. Quando o mesmo erro aparece duas vezes — pare; não repita o mesmo patch.
3. Antes de declarar concluído, e só depois de `make doctor`, `make lint` e `make test`.

Fora disso, Sonnet edita. Escolha de caminho, ferramenta e retry não sobe de modelo.

## Forks rápidos (não é JEV)

JEV não existe no Claude Code. Não instale `jev-router` nem chame rede para micro-decisões.
O análogo no produto é `decide_route` em `src/engine/routing.py` e a porta em `src/safety`.
Esta configuração **não** altera o motor do `ask`.
