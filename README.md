# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA.

## Status

Fase atual: **Fase 0 — Consolidação**. O foco é o PC (Ubuntu 26.04 LTS); mobile e ESP32 ficam para fases futuras.

A branch `fix/issue-18-honest-cli` contém um protótipo de CLI, não o sistema completo. O fluxo `ask` usa LangGraph com resposta simulada por padrão; Ollama é opcional e só é acessado se já estiver disponível localmente. Node-RED e MQTT não são iniciados. O PR #23 ainda requer validação de CI e revisão de segurança antes de merge.

## Início rápido

Execute na raiz do repositório:

```bash
make setup
make install-dev
.venv/bin/python -m src.main status
.venv/bin/python -m src.main ask "olá"
.venv/bin/python -m src.main test
```

`make setup` instala as dependências de `requirements.txt`; `make install-dev` instala pytest e outras ferramentas. O modo `mock` responde com `[mock] Resposta para: ...`: demonstra o fluxo, mas não responde com IA.

## Perguntas e documentos

```bash
.venv/bin/python -m src.main ask "olá"
.venv/bin/python -m src.main ask --cite "arquitetura do YBY"
.venv/bin/python -m src.main ask --remember "Minha preferência é local-first"
.venv/bin/python -m src.main ask --memory-dir .yby "qual é minha preferência?"
```

| Opção | Comportamento atual |
|---|---|
| Sem opções | Grafo LangGraph `route` → `respond`, com provedor `mock` por padrão. |
| `--cite` | Busca lexical em Markdown de `docs/` e `README.md`, incluindo referências `arquivo:linha` para os trechos recuperados. Não verifica se a resposta é sustentada por eles. |
| `--remember` | Grava pergunta e resposta em `.yby/memory.jsonl`. |
| `--memory-dir DIRETÓRIO` | Lê e grava em `DIRETÓRIO/memory.jsonl`. |

A memória é consultada automaticamente, mesmo sem `--remember`; esta opção controla apenas a gravação. `memory:N` é uma posição entre os resultados daquela consulta, não um identificador estável. O arquivo JSONL local não é criptografado: não armazene segredos ou dados sensíveis. Respostas simuladas também podem ser gravadas, portanto não trate memórias como fatos verificados.

Para usar o provedor opcional Ollama, que deve estar instalado, em execução e com o modelo disponível:

```bash
YBY_LLM_PROVIDER=ollama YBY_LLM_MODEL=llama3.2:3b .venv/bin/python -m src.main ask "olá"
```

O comando não instala nem inicia Ollama. `--cite` não usa Qdrant, embeddings ou RAGFlow; as fontes listadas mostram o que foi recuperado, não comprovam a resposta gerada.

## Skills e diagnóstico

```bash
.venv/bin/python -m src.main skills list
.venv/bin/python -m src.main skills run echo --arg 'message=olá'
.venv/bin/python -m src.main skills run read_doc --arg name=PLANO-PC-FIRST
.venv/bin/python -m src.main skills run write_note --arg title=exemplo --arg content=olá --yes
```

`read_doc` lê apenas nomes simples de documentos Markdown em `docs/`; não lê arquivos arbitrários nem `README.md` na raiz. `write_note` grava em `.yby/notes/` apenas com `--yes`, que é uma autorização explícita na própria linha de comando — não um diálogo interativo. Não há sandbox ou política completa de permissões e auditoria; não exponha essas skills a entradas não confiáveis.

`status` mostra a versão do Python, a presença de pytest, Ollama e Docker no ambiente e se a porta local 6333 aceita conexão. Porta aberta não prova que o serviço seja Qdrant; o comando não inicia nada.

## Outros comandos

| Comando | O que faz hoje |
|---|---|
| `.venv/bin/python -m src.main test` | Executa pytest em `tests/` e propaga o código de saída. |
| `.venv/bin/python -m src.main run` | Não implementado; retorna código 1. |
| `.venv/bin/python -m src.main setup` | Não implementado; retorna código 1. |
| `make setup` | Cria `.venv` e instala dependências Python; não baixa modelos. |
| `make install-dev` | Instala dependências de desenvolvimento. |
| `make test` | Executa a suíte pytest instalada na `.venv`. |
| `make lint` | Verifica erros básicos com flake8. |
| `make format` | Formata com black. |
| `make run` | Inicia apenas Qdrant via Docker Compose em `127.0.0.1:6333`, se Docker estiver disponível. |
| `make stop` / `make logs` | Para o Compose / mostra seus logs. |

## Estrutura

```text
src/       → núcleo YBY
skills/    → automações
tests/     → testes
scripts/   → utilitários
docs/      → planos e decisões
examples/  → exemplos (pós-MVP)
grafana/   → observabilidade (pós-MVP)
firmware/  → futuro (ESP32)
```

## Documentação

- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
- [Plano PC-first](docs/PLANO-PC-FIRST.md)
- [Otimizações](docs/OTIMIZACOES.md)
- [Plano de reuso](docs/ARCHITECTURE-REUSE.md)
