# YBY SEED — prontidão para o ecossistema (Lote 28)

Auditoria factual do núcleo ativo. **Não** declara o SEED “pronto para produção”.

Evidência desta revisão: `ruff check src tests` ok; `pytest -q` → **309 passed, 14 skipped**; smokes CLI (`gate`, `ask --explain`, `brief`→`plan` incompleto exit 1, `scaffold test-generated` bloqueado). Branch: lotes 13–24 + 28 + Grok off + cloud default-off.

## Vocabulário

| Termo | Significado aqui |
|---|---|
| **Pronto** | Código no caminho ativo; CLI exposta; comportamento alinhado à doc ativa |
| **Testado** | Coberto por `pytest` (e/ou smoke CLI reproduzível neste ambiente) |
| **Validado** | Exercitado de ponta a ponta com Ollama/nuvem reais + aceitação humana no hub — **não** afirmado nesta revisão |

## Mapa do fluxo criação → execução

```text
ask [--explain] ──(manual)──► brief* ──► plan from-brief ──► scaffold propose
                                                      │              │
                                                      │              ▼
                                                      │         validate (estático)
                                                      │              │
                                                      │              ▼
                                                      │         apply (escreve disco)
                                                      ▼
                                              (sem plan execute)
run/gate ◄── política D10 ──► actions   ← ortogonal ao plano
scaffold test-generated → BLOQUEADO (sem sandbox OS)
```

| Etapa | Pronto | Testado | Validado | Limite |
|---|---|---|---|---|
| Conversa `ask` / `--explain` | sim | sim | não (rede/Ollama real fora do CI) | não grava vault; não abre brief |
| Porta `gate` / `run` | sim | sim | parcial (integração tmp) | paths `[read]` sem sandbox |
| Brief → proposta | sim | sim | não | ≠ autorização |
| Plano verificável | sim | sim | não | ≠ execução |
| Scaffold + manifesto | sim | sim | não | só Python CLI; sem install |
| Validação estática | sim | sim | não | não roda pytest do gerado |
| Execução de gerado / plano | **não** | bloqueio testado | — | sem isolamento OS |

## Capacidades prontas (núcleo)

- HybridEngine local-first; OpenRouter primário; confirm TTY default-deny no CLI; secret gate hard-block; usage JSONL metadados.
- D10: `decide` → `run`/`ask`/`refuse`; executor `shell=False` + argv/workdir.
- Vault Markdown + índice hash 64-d; `note`/`recall`.
- Voz opcional; hub keepalive.
- Criação: `brief` → `plan` → `scaffold` → `validate`/`apply`/`revert`.
- Backup local: `yby backup create/list/restore` (vault + logs redigidos; restore em pasta alvo).
- Obs local: `yby usage` / `usage tail` (JSONL + teto mensal; sem Datadog).
- Execução: timeout com teto, truncagem de stdout/stderr, recusa sob `.yby/artifacts-manifest.json`.
- Cursor fake: `yby cursor-fake simulate` dry-run de plano `validated` (sem MCP / sem escrita).
- Aprendizado diário: `yby learn log/report` (JSONL local; sem auto-merge em `docs/LEARNING.md`).
- Prefs no vault: `yby prefs` (consentimento para chaves sensíveis; sem Vector DB).
- Pesquisa consentida: `yby research` (gate + HTTP fake; sem busca real).

## Lacunas críticas (antes de ser “cérebro” do ecossistema)

1. **Sem sandbox OS** — limites de timeout/saída e bloqueio sob scaffold (lote 24); ainda sem isolamento de SO completo.
2. ~~**Consentimento de nuvem** default-off~~ — `YBY_CLOUD_MODE` padrão `local_only` + enum estrito; library `confirm_fn=None` ainda auto-aprova quando mode=`ask`.
3. ~~**Grok** wiring morto~~ — **removido** (lote Grok off): destino único `YBY_CLOUD_*`.
4. ~~**Backup vault**~~ — `yby backup` local (tar.gz + retenção); checklist Fase P Fase 5 ainda exige exercício no hub real.
5. ~~**Observabilidade CLI**~~ — `yby usage` / `usage tail` sobre JSONL local (sem Datadog).
6. **Memória**: prefs+consentimento feitos (lote 20); ainda sem FTS, sem reindex CLI; `ask` não grava nota.
7. **ask ↛ brief** — fluxo de criação é manual, não conversacional contínuo.
8. **Legado** `agents/`/`rag/`/`gateway/` ainda no disco — risco de confundir com o caminho ativo.

## Riscos residuais

- Paths allowlisted leem qualquer arquivo acessível ao usuário.
- Secret gate: gaps Bearer/`Authorization` e JSON sem prefixo conhecido.
- Heurística “fora de escopo” do plano é por tokens — falsos positivos/negativos.
- Syncthing é processo externo; índice do vault pode ficar stale se arquivos mudam fora do `note`.
- Docs históricos (`OBSERVABILITY`, `AUTO_EVOLUTION`) podem parecer produto.

## Próximos portões (ordem sugerida)

1. ~~**Grok off**~~ — feito.
2. ~~**Consentimento nuvem default-off**~~ — feito (`local_only` + validação).
3. ~~**Backup local**~~ — feito (`yby backup`; restore em pasta alvo).
4. ~~**Obs CLI**~~ — feito (`yby usage`).
5. ~~**Sandbox / bloquear** execução ampliada~~ — lote 24 (limites) + 17 (gerado); sandbox OS completo ainda fora.
6. ~~**Cursor fake**~~ — feito (lote 18 dry-run); MCP/Cursor real ainda fora.
7. Contratos de dispositivos / wearable (lote 27) quando fizer sentido.

## O que esta revisão NÃO afirma

- Que o hub doméstico está operacional 24/7.
- Que Ollama/OpenRouter foram validados ao vivo nesta auditoria.
- Que o SEED está pronto para produção ou para comandar hardware.
