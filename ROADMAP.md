# Roadmap — YBY SEED

Estado alinhado ao checklist em [docs/REPOS.md](docs/REPOS.md) e às decisões D1–D11.

| Fase | Descrição | Status |
|---|---|---|
| 0 | Consolidação: escopo PC Hub, docs, separação de repos | Feito |
| 1 | Núcleo local (`yby.py` + Ollama + nuvem sob demanda) | Feito |
| 1b | Porta + execução (`safety` / `actions`) + vault | Feito |
| 1c | Voz local (Whisper + Piper) | Feito |
| 2 | Qualidade contínua (Ruff + Pytest no CI) | Feito |
| **P** | **Plataforma** — hub sempre ligado (D9): serviço, boot, sync Syncthing | Em andamento (spec pronta; implementação pendente) |
| 3+ | Skills dry-run, agentes no caminho do `ask`, gateway exposto | Depois |
| Futuro | Mobile / ESP32 | Depois |

## Escopo

- **v1 agora:** `engine`, `safety`, `actions`, `memory`, `voice`, `platform`, `security/ast_guard`, testes.
- **Não fazer:** absorver YBY / yby-core / FRANK_* neste repo; programar em forks.
- **Fora do v1:** mobile e firmware ([docs/archive/FORA-DO-V1.md](docs/archive/FORA-DO-V1.md)).
