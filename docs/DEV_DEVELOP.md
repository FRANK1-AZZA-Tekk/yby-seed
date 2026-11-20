# Develop (piloto multi-camada)

Fluxo local: **Ollama → Markdown → Cursor CLI** em worktree. Sem OpenRouter neste PR.
Os planos são gravados em `~/.local/state/yby-seed/develop/plans/` (mesmo contrato do [painel](PAINEL.md)).

## Comandos

```bash
python yby.py develop plan "adicione X em duas camadas"
python yby.py develop export <plan_id> --layer L1
python yby.py develop send <plan_id> --layer L1 --dry-run
python yby.py develop send <plan_id> --layer L1    # TTY + confirm
python yby.py develop accept <plan_id> --layer L1
python yby.py develop reject <plan_id> --layer L1
python yby.py develop show <plan_id>
```

`YBY_DEVELOP_ROOT` sobrescreve a pasta de estado. `YBY_CURSOR_BIN` força o binário.

## Demo duas camadas

1. Plano com L1 e L2 (`L2.depends_on=["L1"]`), ambas `preparada`.
2. `send L1` → `enviada` (exit 0 do Cursor **≠** aceita).
3. `send L2` **bloqueado** enquanto L1 não for `aceita`.
4. `accept L1` → libera `send L2`.
5. `reject L1` ou falha de envio → L2 permanece bloqueada.

## Simulado vs Cursor real

| CI / testes | Máquina com Cursor |
|---|---|
| `ScriptedDevelopPlanner` + fake bin | `agent` / `cursor-agent` / `cursor` no PATH |
| dry-run / `run_fn` mock | worktree em `~/.cache/yby/develop/wt/` |

Nunca aplica `optional_patch` no SEED; sem push/merge/PR automático.
