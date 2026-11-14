# Notas por pilar — YBY SEED (v1)

Snapshot de análise em **2026-11-11** (owner Alisson). Base: `main` + PRs abertos. Decisões vigentes: [DECISIONS.md](../DECISIONS.md) (D1–D11).

## Readiness geral

| Área | Estado |
|---|---|
| Núcleo CLI (`ask` / `run` / `gate` / `note` / `recall` / `listen`) | **pronto no código** |
| Docs de mapa/dev lean | **parcial** — PR [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37) |
| Deploy hub sempre ligado (D9) | **não iniciado** (próximo foco) |
| Integração entre camadas (`ask`↔memória, `ask`↔ações) | **não iniciado** (proposital) |

Ordem sugerida a partir daqui: **(1)** mergear [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37) → **(2)** Plataforma D9 no hub → **(3)** smoke real Ollama+vault+voz no servidor → **(4)** só então skills/integrações leves.

### Não fazer

- Mergear [#35](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/35) (absorção YBY / yby-core / FRANK) — conflita com D7 clarificado.
- Programar features YBY em forks (`langgraph`, `llama.cpp`, …).
- Trazer modelos **7B** (D4 / GTX 1650 4 GB).
- Tratar `src/agents`, `src/rag`, `src/gateway` como caminho do `ask`.
- Confiar em [#28](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/28) (conflitos; trabalho já supersedido em `main`).
- Docker no núcleo (D5); UI / MQTT / LangGraph no v1 imediato.

### PRs (status observado)

| PR | Estado | Nota |
|---|---|---|
| [#36](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/36) Voice | **MERGED** | Whisper + Piper em `main` |
| [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37) docs org | **OPEN** | mapa/DEV/checklist; mergear |
| [#35](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/35) consolidação | **OPEN** | **não mergear** |
| [#28](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/28) recovery | **OPEN / CONFLICTING** | ignorar / fechar |

---

## 1. Purpose — exocórtex pessoal / PC Hub

**Estado:** feito (decisão + escopo).

**Evidência:** D1/D9; README posiciona o seed como hub local-first; mobile/firmware fora (`docs/archive/FORA-DO-V1.md`).

**Funciona:** narrativa e fronteira v1 claras no código ativo (`yby.py` → camadas).

**Lacunas:** `ARCHITECTURE.md` na raiz ainda descreve pipeline RouterAgent (legado); `ROADMAP.md` em `main` ainda lista fases antigas (Qdrant/Postgres) — corrigidos no [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37).

**Próximos passos:**

1. Mergear [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37).
2. Manter Purpose como âncora: qualquer feature nova passa no teste “serve o hub no servidor de casa?”.
3. Não reabrir mobile/ESP no seed.

**Deps:** nenhuma de código; guia D1–D11.

---

## 2. Engine — híbrido Ollama / Grok

**Estado:** feito (#30).

**Evidência:** `src/engine/` (`hybrid.py`, `routing.py`, `providers.py`, `config.py`); CLI `yby ask`; testes `tests/test_engine.py`, `tests/test_ask_cli.py`; D3/D4.

**Funciona:** local-first `qwen2.5-coder:3b`; nuvem por `--heavy` / frases / tamanho / complexidade; degradação explícita se Ollama cair sem chave; system prompt sem tools/shell.

**Lacunas:** `ask` não lê vault nem dispara `actions`; LiteLLM na raiz é legado/opcional (motor fala direto com providers); smoke no hub real ainda depende de Ollama+chave no `.env`.

**Próximos passos:**

1. No hub: `ollama pull qwen2.5-coder:3b` + `yby ask` smoke.
2. Preencher `YBY_CLOUD_API_KEY` / `XAI_API_KEY` só se quiser fallback Grok.
3. Ajustar limiares `YBY_HEAVY_*` com uso real (não antecipar).
4. Não ligar agents/RAG ao `ask` ainda.

**Deps:** Plataforma (Ollama no ar); nuvem opcional.

---

## 3. Safety — allowlist gate

**Estado:** feito (#31).

**Evidência:** `src/safety/policy.py`; `config/safety-allowlist.txt`; CLI `gate`; D10. Decide `run` / `ask` / `refuse` — **não executa**.

**Funciona:** read-only + git + scripts em pastas do projeto; confirmação s/n; refuse de padrões destrutivos; AST guard paralelo em `src/security/ast_guard.py` (código gerado / agentes).

**Lacunas:** allowlist ainda enxuta; glue de shell (`&&`, `|`) sempre pede confirmação; `ask` não passa pela safety (proposital — não executa shell).

**Próximos passos:**

1. Expandir `[read]` só com comandos realmente usados no hub.
2. Manter `gate` como diagnóstico; execução só via `run`.
3. Revisar `[refuse]` após primeiros usos reais.
4. Não afrouxar confirmação para “conveniência”.

**Deps:** Actions consome a decisão; Engine independente.

---

## 4. Actions — run após o gate

**Estado:** feito (#34).

**Evidência:** `src/actions/runner.py`; CLI `yby run`; testes `tests/test_actions.py`; D10.

**Funciona:** subprocess só após `run` ou `ask`+sim; timeout; `refuse` nunca chega ao shell.

**Lacunas:** sem dry-run de skills no caminho ativo (D6 ainda aspiracional para skills); sem fila/serviço; cwd = raiz do projeto.

**Próximos passos:**

1. Smoke no hub: `yby run "ls"`, `yby run "rm …"` (deve ask/refuse).
2. Documentar timeout padrão (30s) no DEV quando [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37) mergear.
3. Skills dry-run só depois da plataforma estável.
4. Não deixar o LLM chamar `run` automaticamente.

**Deps:** Safety obrigatória; Purpose (confirmação humana).

---

## 5. Memory — Obsidian + índice + Syncthing

**Estado:** parcial.

**Evidência:** `src/memory/vault.py`; CLI `note` / `recall`; D8; `docs/MEMORY.md`. Índice local hash-bag (64-d) em `.yby/index.json` — **não** embeddings de modelo. Syncthing **fora** do repo (só sincroniza a pasta).

**Funciona:** CRUD Markdown sob `YBY_VAULT_PATH`; recall por similaridade lexical simples; path traversal bloqueado.

**Lacunas:** `ask` não grava/lê vault; Syncthing não configurado no código; índice frágil para recall semântico; vault vazio sem `YBY_VAULT_PATH`.

**Próximos passos:**

1. Definir pasta do vault no hub + Syncthing pasta↔pasta.
2. Smoke `note` / `recall` com `YBY_VAULT_PATH`.
3. Só depois: opcional “`ask` sugere nota” (ainda sem auto-write).
4. Não introduzir Qdrant/Postgres no v1.

**Deps:** Plataforma (pasta + Syncthing); Engine só se/quando integrar recall no prompt.

---

## 6. Voice — Whisper + Piper

**Estado:** feito (#36, merged em `main`).

**Evidência:** `src/voice/` (`session`, `stt`, `tts`, `mic`, `config`); `requirements-voice.txt`; CLI `listen` / `ask --voice`; D11; testes `tests/test_voice.py`.

**Funciona:** push-to-talk (grava até Enter) → STT → HybridEngine → TTS; deps opcionais com degradação clara; Whisper `base` CPU/`int8` por padrão.

**Lacunas:** precisa mic + Piper binário + `YBY_PIPER_MODEL` no hub; sem wake-word / streaming; TTS opcional (pode cair em texto).

**Próximos passos:**

1. Instalar `requirements-voice.txt` + Piper no hub.
2. Smoke `yby listen` com Ollama no ar.
3. Avaliar `YBY_WHISPER_MODEL=small` só se qualidade exigir.
4. Não puxar stack de voz do YBY wearable.

**Deps:** Engine; Plataforma (áudio no servidor).

---

## 7. Platform — servidor doméstico always-on

**Estado:** não iniciado (decisão feita; deploy não).

**Evidência:** D9; hardware em `HARDWARE_SPEC.md` (Ryzen 5 / 16 GB / GTX 1650); `docs/PC_DEPLOYMENT.md` é guia histórico/Docker-heavy — **não** é o caminho lean do núcleo (D5).

**Funciona:** nada de serviço/systemd/boot no repo ainda; núcleo roda como CLI.

**Lacunas:** sem unit systemd / script de boot; sem checklist enxuto “Ollama + vault + Syncthing + yby”; docs de deploy misturam Docker/NVIDIA toolkit.

**Próximos passos:**

1. Checklist mínimo no hub: Ubuntu + Ollama + venv + `.env` + vault path.
2. Syncthing da pasta do vault.
3. (Opcional) unit systemd só se quiser daemon — não obrigatório para CLI.
4. Evitar Compose/Qdrant/Postgres nesta fase.

**Deps:** Purpose; desbloqueia smoke real de Engine/Memory/Voice.

---

## Fora do v1 (breve)

| Tema | Estado | Nota |
|---|---|---|
| Interface além da voz | não iniciado | Sem web/TUI no caminho ativo; FRANK UI fora |
| Integrations (gateway/MQTT) | no disco, fora do `ask` | `src/gateway` loopback + token; não expandir agora |
| Agents / RAG stubs | no disco, fora do `ask` | `src/agents`, `src/rag`, `src/core` — não reescrever sem decisão |
| Outros repos | separados | YBY, yby-core, FRANK_* — **não absorver** ([#35](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/35)) |

---

## Incerteza

- Smoke real no hardware do dono (Ollama GPU, mic, Piper, Syncthing) **não** foi executado nesta análise — só leitura de código/docs/PRs.
- Conteúdo exato do [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37) após rebase com Voice: ROADMAP do branch docs ainda podia dizer Voice “aberto”; em `main` Voice já está merged.
- D7 em `main` lista inventário separado, mas a frase anti-absorção explícita está no [#37](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/37) — tratar como vigente pela intenção do owner.
