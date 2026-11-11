# Aprendizados do YBY SEED

Registro de uso real, falhas e aprendizados práticos.

## 2026-11-11 — Primeiro uso real

- Testado: `python yby.py ask "explique uma lista em Python"`
- Resultado: exit code 1; nenhum texto de resposta. Mensagem no stderr: Ollama indisponível em `http://127.0.0.1:11434` (connection refused). Sem `YBY_CLOUD_API_KEY`, o motor não usou nuvem.
- Observações: Teste feito sem nuvem (política local-first). A degradação do `HybridEngine` foi explícita e previsível. Próximo passo: repetir no PC Hub com Ollama e modelo `qwen2.5-coder:3b` via `yby hub`.

## Checklist de validação no PC Hub

- [ ] Ollama ativo e modelo `qwen2.5-coder:3b` disponível.
- [ ] `yby ask "explique uma lista em Python"` retorna resposta.
- [ ] `yby ask --heavy "pergunta complexa"` pede confirmação para nuvem.
- [ ] `yby listen` grava, transcreve e fala a resposta.
- [ ] `yby note "título" "texto"` grava no vault.
- [ ] `yby recall "consulta"` busca no vault.
- [ ] `yby run "ls"` executa comando seguro da allowlist.
- [ ] `yby run "rm -rf /"` é recusado pela porta de segurança.
- [ ] Serviço systemd ativo após reboot.
- [ ] Log local registra falha do Ollama quando está off.

## Próximos testes planejados

- [ ] `yby ask` com pergunta simples em português.
- [ ] `yby ask --heavy` com pergunta complexa.
- [ ] `yby listen` com voz local.
- [ ] `yby note` e `yby recall` com vault.
- [ ] `yby run` com comando seguro da allowlist.
