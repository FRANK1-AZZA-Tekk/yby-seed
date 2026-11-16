# Memória

A memória do YBY é uma pasta de notas Markdown, no formato de um vault Obsidian.

- `YBY_VAULT_PATH` aponta para essa pasta.
- `python yby.py note "titulo" "texto"` grava a nota (atualiza o índice).
- `python yby.py recall "consulta"` busca no índice local (`.yby/index.json`).
- `python yby.py recall --fresh "consulta"` / `python yby.py reindex` — reconcilia disco→índice por **content-hash** (não mtime); remove órfãos após Syncthing/edições externas.
- Preferências (lote 20): `python yby.py prefs list|get|set` em `.yby/prefs.json`.
  - Livres: `locale`, `reply_style` (`short`|`teach`).
  - Exigem `--consent`: `share_notes_with_cloud`, `remember_failures`, `allow_web_search`.
  - `allow_web_search=1` autoriza `yby research` sem `--consent` one-shot (ainda HTTP fake).
  - Sem Vector DB novo; sem FTS; `ask` ainda não grava nota automaticamente.
- O Syncthing sincroniza a pasta com o servidor de casa. O YBY só lê e grava arquivos; não implementa o Syncthing. Após sync externo, rode `reindex` ou `recall --fresh`.
- Exemplos sem segredos: [syncthing/vault-folder.example.yaml](syncthing/vault-folder.example.yaml) e [examples/syncthing/](../examples/syncthing/).

## Registro de decisões de execução

- D12 define economia de execução: local primeiro, nuvem apenas sob demanda e limites mensais de Cursor e OpenRouter.
- D13 registra que voz em nuvem via Grok/xAI é opcional e futura; a voz local continua sendo o padrão.
