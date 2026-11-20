# YBY assist (texto + voz)

Sessão conversacional em PT-BR para **ferramentas cadastradas** do PC Ubuntu.
Não substitui o `ask`. Sem nuvem e sem shell livre.

## Setup

```bash
cp config/assist.example.json ~/.config/yby-seed/assist.json
# ajuste apps, search_roots e routines
export YBY_ASSIST_CONFIG=~/.config/yby-seed/assist.json
export YBY_VAULT_PATH=~/Obsidian/Vault   # se for usar vault.search
python yby.py assist
python yby.py assist --voice   # pressionar para falar (Whisper/Piper locais)
```

## Voz (`assist --voice`)

Pressionar para falar: `record_until_enter` → `transcribe` → **mesma** `AssistSession` / executor / política do texto → `speak`. Não usa `listen_once` (caminho do `ask`/`listen`). Sem gravação contínua, sem nuvem e sem log de áudio.

- Confirmação: a prévia é falada com os dados exatos; `sim` confirma; `cancela` / silêncio / transcrição ambígua não confirmam; mudar a hora gera **outra** prévia.
- Falha de STT: nada executado; dá para continuar por texto no mesmo turno.
- Falha de TTS depois da ação: imprime o estado real e **não** repete a ação.
- Tempos (`stt` / `interpret` / `exec` / `tts`) só no stderr, sem conteúdo da fala.
- Desempenho no PC Hub (primeira vs seguintes vs rotina sem Ollama): **pendente** até haver fone e modelo real — não marcar como aprovado.
- PR futuro (só após medição): se a transcrição dominar, menor correção candidata é manter o `WhisperModel` vivo entre turnos (hoje cada `transcribe_detailed` instancia de novo). Medir antes/depois; **não** mudar modelo/`num_ctx`/aquecimento neste PR.

`listen` e `ask --voice` permanecem no HybridEngine; este modo não os altera.

## Lembretes (cadastro × entrega)

O **assist só cadastra** no mesmo arquivo `assist-reminders.json` (estados `scheduled` | `pending` | `delivered`).
Quem **notifica** é o processo agendado:

```bash
python yby.py reminders once
bash scripts/install-reminders-timer.sh          # só grava units
bash scripts/install-reminders-timer.sh --enable # só se você pedir
```

| Estado | Significado |
|---|---|
| `scheduled` | ainda não venceu (`vence em …` no painel) |
| `pending` | venceu; notificação falhou / desktop ausente / silêncio |
| `delivered` | `notify-send` confirmou — só então marca entregue |

- Horário silencioso opcional: `reminder_quiet_hours` no JSON (`start`/`end` HH:MM).
- PC desligado ou suspenso: nada marca entregue; no boot o timer (`Persistent=true`) reavalia e avisa no máximo uma vez se ainda pendente.
- Queda depois do notify e antes do save: fica `pending`; a passagem seguinte pode avisar de novo.

## O que é teste automatizado vs manual

| Automatizado (`make test`) | Manual no Ubuntu |
|---|---|
| Planner/launcher/relógio/notificador simulados | Apps reais (Obsidian, etc.) |
| Pastas temporárias + symlinks | Suas `search_roots` |
| Ollama mockado / down | Ollama real + alias sem Ollama |
| Entrega via `reminders once` | Timer systemd de usuário + desktop |

## Demo rápida (manual)

1. `python yby.py assist` → `ajuda`
2. Digite exatamente `modo estudo` (alias) — deve abrir o app cadastrado e buscar no vault **mesmo se o Ollama estiver parado**.
3. `acha relatorio` (com arquivos nas roots) → escolha `o segundo` (seleciona, **não abre**).
4. Peça um lembrete → confira a prévia → `n` cancela; ou confirme com os dados exatos.
5. Feche o assist; `python yby.py reminders once` (com DISPLAY) deve notificar o vencido.
6. `status` → disco + Ollama; erros aparecem separados.

## Limites (honestos)

- Rotinas **não** podem chamar outras rotinas.
- Alias é **exato** (casefold); frases parecidas não autorizam.
- Controlo do Sentinela: `sentinel.rules.list|pause|resume` ([SENTINEL.md](SENTINEL.md)).
- OpenRouter / Cursor-como-tool: fora deste PR.
