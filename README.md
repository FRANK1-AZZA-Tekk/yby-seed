# YBY SEED

PC Hub local-first para automações e IA pessoal.

## Status real

Fase atual: **F0 — Consolidação e fundação**.

O projeto está em desenvolvimento inicial. Mobile, wearable, ESP32, voz e visão computacional não fazem parte do MVP.

## O que é

O YBY SEED será um hub local no PC que:

- Recebe pedidos em português do Brasil.
- Classifica a intenção do usuário.
- Usa modelos locais via Ollama sempre que possível.
- Usa modelos na nuvem apenas como fallback controlado.
- Registra decisões, custos e ações em auditoria.
- Cria automações e projetos somente em workspaces isolados.

## MVP

O MVP prioriza:

- CLI `yby ask`.
- Classificador de intenção.
- Roteador local/nuvem com LiteLLM.
- Auditoria em SQLite.
- Memória local com SQLite + FTS5.
- Workspace isolado por projeto.
- Painel web simples com FastAPI + HTMX.

O MVP não depende de Docker.

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.2:3b
python src/main.py
```

> Observação: os comandos acima descrevem o fluxo atual do repositório. Recursos ainda não implementados não devem ser considerados disponíveis.

## Estrutura

```text
src/       → núcleo YBY SEED
skills/    → automações
tests/     → testes
scripts/   → utilitários
docs/      → documentação canônica e políticas
examples/  → exemplos
firmware/  → congelado; não faz parte do MVP
```

## Documentação oficial

Consulte [docs/INDEX.md](docs/INDEX.md) para saber qual documento é a fonte da verdade de cada assunto.

## Princípios

- Function over Form.
- Local-first.
- Privacidade por padrão.
- Controle humano antes de ações externas.
- Uma única fonte de verdade por assunto.
- Nenhuma política sem teste que a prove.
