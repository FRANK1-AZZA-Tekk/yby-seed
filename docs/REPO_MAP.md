# Mapa de repositórios — ecossistema YBY

> Fase 0 (consolidação). Hub canônico: **[yby-seed](https://github.com/FRANK1-AZZA-Tekk/yby-seed)**.

## Decisão

Materiais úteis dos repositórios irmãos entram no YBY SEED. Repositórios vazios ou legados passam a apontar para este hub. Não se mantém implementação paralela do mesmo núcleo.

## Papéis

| Repositório | Papel | Destino no SEED | Ação |
|---|---|---|---|
| **yby-seed** | Hub PC local-first (canônico) | — | Continuar aqui |
| **YBY** | Spec YBY ZERO + eventos/privacidade/degradação | `src/yby_zero/`, `docs/yby-zero/`, `docs/CAPACIDADE-HARDWARE.md` | Absorvido; repo vira ponte |
| **yby-core** | Orquestrador LangGraph + chat streaming | `src/orchestrator/`, `src/tools/`, `integrations/yby-core/` | Absorvido; repo vira ponte |
| **yby-seed-local** | Benchmarks Ollama + Open WebUI | `docs/benchmarks/`, `scripts/benchmark_ollama.sh` | Absorvido; repo vira ponte |
| **FRANK_ZER0** | Protótipo V26 (PWA neon, swarm, ESP32) | `docs/legacy/FRANK_BLUEPRINT_2026.md`; firmware futuro | Arquivo de inspiração; não misturar UI no núcleo |
| **FRANK_ZERO** | Stub vazio | — | Ponte para yby-seed |
| **YBY-brasil** | Stub vazio | — | Ponte para yby-seed |
| **YBY-YOU-BY-YOURSELF** | Stub vazio | — | Ponte para yby-seed |

## O que entrou (melhor de cada um)

### De YBY
- Event bus versionado, política P0–P3, roteador de provider, máquina de degradação.
- Spec v0.1 e docs de arquitetura (eventos, privacidade, voz, degradação).
- Matriz de capacidade de hardware e dossiê mestre (legado).

### De yby-core
- Classificação de tarefa e escolha local-first de modelo (`src/orchestrator/`).
- Ferramentas de arquivo com jail em `~/yby` (`src/tools/`).
- Espelho LangGraph + UI de chat streaming em `integrations/yby-core/` e `static/chat.html`.
- Default de modelo alinhado ao benchmark: `qwen2.5-coder:3b`.

### De yby-seed-local
- Script e resultados reais de benchmark na GTX 1650.
- Compose de referência do Open WebUI.

### De FRANK_ZER0
- Blueprint V26 arquivado em `docs/legacy/` (inspiração: proatividade, kill switch, skills).
- **Não** consolidado no núcleo: dashboard cyberpunk, CrewAI swarm cloud-first, Railway/K8s de demo.

## O que fica de fora do núcleo (de propósito)

- Mobile/Termux e firmware ESP32 como runtime (roadmap fase 9+).
- Qdrant/PostgreSQL como padrão (preferência: SQLite + sqlite-vec; ver `docs/CAPACIDADE-HARDWARE.md`).
- UI neon / Zero UI do FRANK até existir interface mínima do SEED.

## Como contribuir a partir daqui

1. Código e docs novos → pull request em **yby-seed**.
2. Issues de produto → **yby-seed**.
3. Repositórios ponte só atualizam o README de redirecionamento.
