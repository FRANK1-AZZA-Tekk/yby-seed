# Roadmap — YBY SEED

| Fase | Descrição | Status |
|---|---|---|
| 0 | Consolidação de repositórios | Em andamento |
| 1 | Núcleo local (CLI + Ollama) | Pendente |
| 2 | Qualidade (Pytest, Ruff, Black, mypy) | Pendente |
| 3 | RouterAgent | Pendente |
| 4 | Primeira skill (dry-run) | Pendente |
| 5 | Memória (SQLite + sqlite-vec; LanceDB se necessário) | Pendente |
| 6 | Serviço (FastAPI) | Pendente |
| 7 | Persistência (histórico local; Redis só se faltar) | Pendente |
| 8 | Interface web mínima | Pendente |
| 9 | Mobile (Tailscale + Termux) | Pendente |

## Escopo por fase

- **MVP (fases 0–4):** src, tests, skills, scripts, docs — sem Docker.
- **Pós-MVP (fases 5–8):** memória, FastAPI, interface.
- **Futuro (fase 9+):** Tailscale, Termux, firmware/ESP32.

## Fase 0 — checklist

- [x] Inventário dos repositórios irmãos (`docs/REPO_MAP.md`)
- [x] Absorver YBY ZERO (eventos, privacidade, degradação, roteamento)
- [x] Absorver yby-core (orquestrador local-first + espelho LangGraph)
- [x] Absorver benchmarks de `yby-seed-local`
- [x] Arquivar blueprint FRANK_ZER0 como legado (sem UI neon no núcleo)
- [x] READMEs ponte nos repositórios satélite
