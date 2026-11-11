# Memória

A memória do YBY é uma pasta de notas Markdown, no formato de um vault Obsidian.

- `YBY_VAULT_PATH` aponta para essa pasta.
- `python yby.py note "titulo" "texto"` grava a nota.
- `python yby.py recall "consulta"` busca no índice local (`.yby/index.json`).
- O Syncthing sincroniza a pasta com o servidor de casa. O YBY só lê e grava arquivos; não implementa o Syncthing.
- Exemplos sem segredos: [syncthing/vault-folder.example.yaml](syncthing/vault-folder.example.yaml) e [examples/syncthing/](../examples/syncthing/).
