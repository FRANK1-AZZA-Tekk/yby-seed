# Aprendizados do YBY SEED

Registro de uso real, falhas e aprendizados práticos.

## 2026-11-11 — Primeiro uso real

- Testado: `python yby.py ask "explique uma lista em Python"`
- Resultado: exit code 1; nenhum texto de resposta. Mensagem no stderr: Ollama indisponível em `http://127.0.0.1:11434` (connection refused). Sem `YBY_CLOUD_API_KEY`, o motor não usou nuvem.
- Observações: Teste feito sem nuvem (política local-first). A degradação do `HybridEngine` foi explícita e previsível. Próximo passo: repetir no PC Hub com Ollama e modelo `qwen2.5-coder:3b` via `yby hub`.

## Checklist de validação no PC Hub

Marcadores: `[x]` concluído no PC Hub; `[~]` verificado noutro ambiente (ver seção abaixo); `[ ]` pendente no PC Hub.

- [~] Ollama ativo e modelo `qwen2.5-coder:3b` disponível (`curl` → connection refused no Cloud Agent; repetir no PC).
- [~] `yby ask "explique uma lista em Python"` retorna resposta (falhou sem Ollama; ~0,14 s até erro).
- [ ] `yby ask --heavy "pergunta complexa"` pede confirmação para nuvem (exige TTY + chave/policy no PC).
- [~] `yby listen` grava, transcreve e fala a resposta (deps de voz ausentes neste ambiente).
- [ ] `yby note "título" "texto"` grava no vault (`YBY_VAULT_PATH` não definido aqui).
- [ ] `yby recall "consulta"` busca no vault (idem).
- [x] `yby run "ls"` executa comando seguro da allowlist (exit 0; ~0,34 s).
- [x] `yby run "rm -rf /"` é recusado pela porta de segurança (`refuse: padrão destrutivo`).
- [ ] Serviço `systemctl --user status yby-hub` ativo após reboot (sem user bus aqui).
- [~] Log local registra falha do Ollama quando está off (`~/.local/state/yby-seed/hub.log` com WARNING no smoke anterior).

## Resultados da validação (2026-11-11)

**Ambiente:** Cloud Agent (`/agent/repos/yby-seed`), não substitui o PC Hub com Ollama + systemd. Issue #42 mergeada em `main`; testes de nuvem não executados (sem HTTP real).

| Comando / checagem | Resultado | Latência / nota |
| --- | --- | --- |
| `curl http://127.0.0.1:11434/api/tags` | Falhou (connection refused) | ~0 ms |
| `yby ask "explique uma lista em Python"` | Exit 1; Ollama off, sem `YBY_CLOUD_API_KEY` | ~0,14 s |
| `yby ask --heavy "pergunta complexa"` | Exit 1; rota heavy sem credencial de nuvem | ~0,20 s |
| `yby listen` | Exit 0 com aviso; falta `sounddevice` / faster-whisper / piper | n/a |
| `yby note` / `yby recall` | Exit 1; `defina YBY_VAULT_PATH` | ~0,34 s |
| `yby run "ls"` | Exit 0; listou o repositório | ~0,34 s |
| `yby run "rm -rf /"` | Exit 1; recusado (`padrão destrutivo`) | ok |
| `systemctl --user status yby-hub` | Falhou (`No medium found`) | n/a no agente |
| `tail hub.log` | WARNINGs de Ollama indisponível (teste hub antigo, porta 9) | — |

### O que funcionou

- Porta de segurança do `run` (allowlist + bloqueio destrutivo).
- `run "ls"` na allowlist.
- Mensagens de degradação explícitas com Ollama off e sem nuvem.

### O que falhou ou ficou pendente

- Ollama / `ask` / confirmação `--heavy` no PC real.
- Vault (`note` / `recall`) com `YBY_VAULT_PATH` configurado no Hub.
- Voz (`listen`) com `requirements-voice.txt` e Piper.
- systemd user `yby-hub` após reboot.
- Fechar issue #42 via `gh` no agente (`Resource not accessible by integration`); no PC: `gh issue close 42 -R FRANK1-AZZA-Tekk/yby-seed`.

### Próximo passo

No **PC Hub**: subir Ollama (`qwen2.5-coder:3b`), `systemctl --user enable --now yby-hub`, exportar `YBY_VAULT_PATH`, repetir o checklist marcando `[x]`; em seguida benchmark de modelos ou aviso de `YBY_CLOUD_WARN_TOKEN_LIMIT` no CLI.

## Próximos testes planejados

- [~] `yby ask` com pergunta simples em português (tentado; falta Ollama no agente).
- [ ] `yby ask --heavy` com pergunta complexa e confirmação s/n no TTY.
- [~] `yby listen` com voz local (só checagem de deps no agente).
- [ ] `yby note` e `yby recall` com vault.
- [x] `yby run` com comando seguro da allowlist.
