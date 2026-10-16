# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)

PC Hub local-first para automações e IA.

## Status

Fase atual: **Fase 1 — Núcleo local**. Foco exclusivo no PC. Mobile, wearables e integrações externas ficam para fases futuras.

## O que é

YBY SEED é um hub central no PC que:

- Conversa localmente via Ollama.
- Aplica regras determinísticas de segurança e roteamento.
- Organiza e busca documentos localmente (planejado).
- Usa nuvem apenas como fallback controlado (planejado; não conectado ao `ask`).

## Estado implementado

- CLI Click com `health` e `ask`.
- Reconhecimento determinístico de comandos.
- Geração via Ollama, com erros tipados no caminho principal.
- Storage SQLite isolado.
- Política de transporte restrita a loopback, sem proxies e sem redirecionamentos.
- Router determinístico de rota única (`local_ollama`) e flags `--offline`/`--private` no `ask`.
- Auditoria opt-in de metadados no `ask` (`--audit`); `--private` nunca persiste.

Fluxo executável atual:

```text
Usuário → comandos → Gatekeeper → Router → verificações do Ollama → geração → resposta
```

## Fluxo alvo do MVP

```text
Usuário → Gatekeeper → Router → Ollama → resposta → SQLite
```

Modos offline/privado e auditoria opt-in estão disponíveis no `ask`.
Consulta e rotação da auditoria ficam para fases posteriores.

Não há fallback de nuvem conectado ao `ask`.

O escopo atual está definido em [docs/MVP.md](docs/MVP.md).

O MVP roda nativamente no host. **Docker é opcional** e não faz parte do caminho principal nesta fase.

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3:4b
python -m src.main --help
python -m src.main health
python -m src.main ask "Explique o que é local-first."
python -m src.main ask --offline --private "Explique o que é local-first."
python -m src.main ask --audit "Explique o que é local-first."
```

O modelo final deve ser validado com benchmark de tokens/s, VRAM e RAM antes de ser fixado.

## Estrutura

```text
src/       → núcleo YBY
skills/    → automações
tests/     → testes
scripts/   → utilitários
docs/      → blueprint, MVP e decisões
examples/  → exemplos (pós-MVP)
grafana/   → observabilidade (pós-MVP)
firmware/  → futuro (ESP32)
```

## Documentação

- [Blueprint Técnico v3.1](docs/BLUEPRINT_YBY_SEED_v3.1.md)
- [MVP](docs/MVP.md)
- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
- [Política de transporte](docs/TRANSPORT_POLICY.md)
- [Plano PC-first](docs/PLANO-PC-FIRST.md)
- [Otimizações](docs/OTIMIZACOES.md)
