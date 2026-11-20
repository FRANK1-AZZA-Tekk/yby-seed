# YBY assist (PR1 — texto)

Sessão conversacional em PT-BR para **ferramentas cadastradas** do PC Ubuntu.
Não substitui o `ask`. Sem nuvem, sem shell livre, sem voz neste PR.

## Setup

```bash
cp config/assist.example.json ~/.config/yby-seed/assist.json
# ajuste apps, search_roots e routines
export YBY_ASSIST_CONFIG=~/.config/yby-seed/assist.json
export YBY_VAULT_PATH=~/Obsidian/Vault   # se for usar vault.search
python yby.py assist
```

## O que é teste automatizado vs manual

| Automatizado (`make test`) | Manual no Ubuntu |
|---|---|
| Planner/launcher/relógio simulados | Apps reais (Obsidian, etc.) |
| Pastas temporárias + symlinks | Suas `search_roots` |
| Ollama mockado / down | Ollama real + alias sem Ollama |
| Sem desktop | Confirmação TTY real de lembretes |

## Demo rápida (manual)

1. `python yby.py assist` → `ajuda`
2. Digite exatamente `modo estudo` (alias) — deve abrir o app cadastrado e buscar no vault **mesmo se o Ollama estiver parado**.
3. `acha relatorio` (com arquivos nas roots) → escolha `o segundo` (seleciona, **não abre**).
4. Peça um lembrete → confira a prévia → `n` cancela; ou confirme com os dados exatos.
5. `status` → disco + Ollama; erros aparecem separados.

## Limites (honestos)

- Lembretes **só** avisam com a sessão `assist` aberta (sem daemon).
- Rotinas **não** podem chamar outras rotinas.
- Alias é **exato** (casefold); frases parecidas não autorizam.
- Voz / Sentinela / OpenRouter / Cursor-como-tool: fora deste PR.
