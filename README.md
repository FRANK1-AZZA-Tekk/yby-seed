# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main)

**YBY SEED** é o núcleo local-first do ecossistema YBY: um hub no PC para IA local, automações seguras e organização de documentos.

## Status

**Fase 0 — Consolidação / Camada 1 concluída parcialmente.**

O foco atual é o PC com Ubuntu 26.04 LTS. Mobile, wearable e ESP32 permanecem em fases futuras.

| Área | Estado |
|---|---|
| CLI local-first | ✅ Implementado |
| Diagnóstico de ambiente e Ollama | ✅ Implementado |
| Execução de testes via CLI | ✅ Implementado |
| Pipeline de briefing revisável | 🚧 Planejado |
| Skills de automação | 🚧 Planejado |
| RAG funcional | 🚧 Planejado |
| Gateway de telemetria seguro | 🚧 Planejado |
| Execução segura de código gerado | 🚧 Planejado |
| Mobile, voz e wearable | ⏳ Futuro |
| ESP32 / firmware | ⏳ Futuro |

## O que é

O YBY SEED será um hub central capaz de:

- Conversar localmente via Ollama.
- Executar automações seguras, com autorização explícita.
- Organizar e buscar documentos locais.
- Usar nuvem apenas como fallback controlado.

O princípio é **function over form**: primeiro fazer o núcleo funcionar de forma honesta e útil; depois expandir interface, hardware e integrações.

## Comandos

### Usando o Makefile

```bash
make help
make setup
make doctor
make test
make run
make clean
```

| Comando | Função |
|---|---|
| `make setup` | Cria o ambiente virtual, instala dependências e valida o ambiente local. |
| `make doctor` | Diagnostica Python, dependências, estrutura do projeto e Ollama. |
| `make test` | Executa a suíte de testes com pytest e propaga falhas reais. |
| `make run` | Inicia o núcleo local em modo de diagnóstico/inicialização. |
| `make lint` | Verifica erros críticos de sintaxe e imports com flake8. |
| `make format` | Formata o código com black. |
| `make clean` | Remove caches e artefatos temporários. |

### Usando o CLI diretamente

```bash
python src/main.py doctor
python src/main.py setup
python src/main.py test
python src/main.py run
```

## Requisitos

- Python 3.11 ou superior.
- [Ollama](https://ollama.com/) instalado e em execução.
- Dependências Python declaradas em `requirements.txt`.

O MVP atual **não exige Docker**.

## Início rápido

```bash
make setup
make doctor
make test
make run
```

Se o Ollama não estiver acessível, `make setup` e `make run` falharão com uma mensagem clara, em vez de reportar sucesso falso.

## Arquitetura mínima

```text
Usuário → CLI (src/main.py) → validação de ambiente → Ollama
                              ↘ futura integração: RouterAgent → Briefing → Skills
```

A Camada 1 entrega a base de inicialização e diagnóstico. A próxima etapa é integrar o pipeline mínimo de briefing revisável:

```text
Pedido em português → entrevista mínima → briefing/PRD → revisão → exportação Markdown/JSON
```

Nenhuma execução automática de código, ação externa ou ação destrutiva ocorrerá sem autorização explícita.

## Estrutura

```text
src/       → núcleo YBY e CLI
tests/     → testes automatizados
skills/    → automações futuras
scripts/   → utilitários
docs/      → planos e decisões
examples/  → exemplos futuros
grafana/   → observabilidade futura
firmware/  → ESP32, fase futura
```

## Segurança

- O YBY SEED é local-first: dados e processamento permanecem no PC sempre que possível.
- Código gerado por IA não é executado automaticamente.
- Ações externas, destrutivas, privilegiadas ou com custo exigirão autorização específica.
- Localização, métricas de saúde e documentos pessoais devem ser tratados como dados sensíveis.

## Documentação

- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
- [Plano PC-first](docs/PLANO-PC-FIRST.md)
- [Otimizações](docs/OTIMIZACOES.md)

## Contribuir

1. Crie uma branch descritiva.
2. Execute `make doctor` e `make test` antes de abrir um PR.
3. Não use `|| true` para esconder falhas de teste ou setup.
4. Documente qualquer serviço, permissão ou dependência nova.
