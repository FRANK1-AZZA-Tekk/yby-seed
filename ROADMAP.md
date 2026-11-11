# Roadmap — YBY SEED

Estado alinhado ao checklist em [docs/REPOS.md](docs/REPOS.md) e às decisões D1–D11.

| Fase | Descrição | Status |
|---|---|---|
| 0 | Consolidação: escopo PC Hub, docs, separação de repos | Em andamento (docs); código irmão **não** entra no seed |
| 1 | Núcleo local (`yby.py` + Ollama + nuvem sob demanda) | Feito (`src/engine`) |
| 1b | Porta + execução (`safety` / `actions`) + vault | Feito |
| 1c | Voz local (Whisper + Piper) | Aberto — PR #36 |
| 2 | Qualidade contínua (Ruff + Pytest no CI) | Feito no essencial |
| **P** | **Plataforma** — hub sempre ligado (D9): serviço, boot, sync Syncthing | **Próximo** |
| 3+ | Skills dry-run, agentes no caminho do `ask`, gateway exposto | Depois da plataforma estável |
| Futuro | Mobile / ESP32 | Fora do v1 — código saiu da árvore |

## Escopo

- **v1 agora:** `engine`, `safety`, `actions`, `memory`, `security/ast_guard`, testes; voz quando #36 mergear.
- **Não fazer:** absorver YBY / yby-core / FRANK_* neste repo; programar em forks.
- **Fora do v1:** mobile e firmware ([docs/archive/FORA-DO-V1.md](docs/archive/FORA-DO-V1.md)).
