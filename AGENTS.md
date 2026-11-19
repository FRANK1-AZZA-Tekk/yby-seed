# YBY SEED — instruções do agente

Python CLI (`yby`). Núcleo atual: `src/engine`, `src/safety`, `src/actions`, `src/memory`, `src/voice` e a plataforma.
O restante em `src/` é legado: não apagar, reescrever nem expandir sem pedido explícito.

## Como trabalhar
- Ler só os arquivos citados no pedido, e `docs/DEV.md` se o caminho estiver ambíguo.
  Não varrer `docs/` nem o legado por padrão.
- Mudar o mínimo. Não refatorar, não adicionar dependências, não fazer merge.
- No fim: `make doctor`, `make lint` e `make test` (ou `make check`). Não vigiar o CI do GitHub.
- Responder com resumo e lista de arquivos; não despejar arquivos inteiros.

## Três paradas (sem advisor)
No Cursor não há Opus consultor. Pare e valide nestes momentos:
1. Antes de travar o plano (arquivos-alvo, aceite, testes).
2. Quando o mesmo erro aparece duas vezes — não repita o mesmo patch.
3. Antes de declarar concluído: rode `make doctor`, `make lint` e `make test`.
Árvore Claude Code (Sonnet + Haiku + Opus): [CLAUDE.md](CLAUDE.md) e [docs/DEV.md](docs/DEV.md).

## Convenções
- Seguir o estilo do código tocado. O Ruff é a fonte de estilo (não repetir guia aqui).
