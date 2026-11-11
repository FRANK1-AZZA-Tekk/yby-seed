# YBY SEED — instruções do agente

Python CLI (`yby`). Núcleo atual: `src/engine`, `src/safety`, `src/actions`, `src/memory`, `src/voice` e a plataforma.
O restante em `src/` é legado: não apagar, reescrever nem expandir sem pedido explícito.

## Como trabalhar
- Ler só os arquivos citados no pedido, e `docs/DEV.md` se o caminho estiver ambíguo.
  Não varrer `docs/` nem o legado por padrão.
- Mudar o mínimo. Não refatorar, não adicionar dependências, não fazer merge.
- No fim: `ruff` e `pytest` uma vez. Não vigiar o CI do GitHub.
- Responder com resumo e lista de arquivos; não despejar arquivos inteiros.

## Convenções
- Seguir o estilo do código tocado. O Ruff é a fonte de estilo (não repetir guia aqui).
