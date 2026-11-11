# Memória

A memória do YBY é uma pasta de notas Markdown, no formato de um vault Obsidian.

- `YBY_VAULT_PATH` aponta para essa pasta.
- `python yby.py note "titulo" "texto"` grava a nota.
- `python yby.py recall "consulta"` busca no índice local (`.yby/index.json`).
- O Syncthing sincroniza a pasta com o servidor de casa. O YBY só lê e grava arquivos; não implementa o Syncthing.

## Registro de decisões de execução

- D12 define economia de execução: local primeiro, nuvem apenas sob demanda e limites mensais de Cursor e OpenRouter.
- D13 registra que voz em nuvem via Grok/xAI é opcional e futura; a voz local continua sendo o padrão.
