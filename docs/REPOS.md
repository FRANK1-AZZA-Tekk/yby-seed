# Onde programar

O código do **v1 (PC Hub)** fica neste repositório, `yby-seed`. Os outros repositórios do dono continuam **separados**. Forks de terceiros não entram aqui. Não copie segredos (`.env`, chaves) para o git.

Guia prático de comandos e pastas: [DEV.md](DEV.md).

## Checklist de camadas (v1)

| Camada | Pasta / entrada | Estado |
|---|---|---|
| CLI | `yby.py` → `src/main.py` | feito |
| Motor `ask` | `src/engine` | feito (#30) |
| Porta de segurança | `src/safety` | feito (#31) |
| Auditoria / AST / vault | `src/security`, `src/memory`, … | feito (#33) |
| Execução | `src/actions` | feito (#34) |
| Memória (vault) | `src/memory` | feito |
| Guarda AST | `src/security/ast_guard.py` | feito |
| Voz (STT/TTS) | `src/voice` | feito (#36) |
| **Plataforma** | servidor de casa sempre ligado (D9) | **próximo** — deploy/serviço no hub, não merge de outros repos |
| Agentes / RAG / gateway | `src/agents`, `src/rag`, `src/gateway`, … | no disco; **fora** do caminho do `ask` |

Caminho ativo hoje:

```text
yby.py → engine | safety → actions | memory | voice | security/ast_guard
```

## Neste repositório

| Pasta | Papel |
|---|---|
| `src/engine` | `ask`: Ollama local e fallback de nuvem |
| `src/safety` | decide run, ask ou refuse; não executa |
| `src/actions` | executa shell só depois da porta permitir |
| `src/memory` | notas Markdown do vault |
| `src/voice` | STT/TTS opcional (`listen` / `ask --voice`) |
| `src/security/ast_guard.py` | bloqueia código gerado perigoso |
| `tests/` | suíte que o CI roda |
| `config/safety-allowlist.txt` | allowlist da porta |
| `litellm_config.yaml` | config LiteLLM **canônica** na raiz (ver [DEV.md](DEV.md)) |

O resto de `src/` existe e ainda não entra no `ask`. Mobile e firmware saíram da árvore; ver [archive/FORA-DO-V1.md](archive/FORA-DO-V1.md). Mapa interno: [src/README.md](../src/README.md).

## Repositórios do dono, separados

**Não absorva** o código desses repos neste seed (nem “consolide” copiando YBY / yby-core / FRANK para cá). Integração futura, se houver, é por API/processo ou decisão explícita — não por dump de árvore.

| Repositório | O que é | Por que não mescla no seed |
|---|---|---|
| [YBY](https://github.com/FRANK1-AZZA-Tekk/YBY) | YBY ZERO: PC + celular + fone + relógio | O v1 é só o PC Hub; o pacote wearable fica lá. |
| [yby-core](https://github.com/FRANK1-AZZA-Tekk/yby-core) | Orquestrador FastAPI + LangGraph, MQTT, PlatformIO | Outro processo; o `ask` não chama isso. |
| [FRANK_ZER0](https://github.com/FRANK1-AZZA-Tekk/FRANK_ZER0) | Protótipo 2026 (TS / Android / ESP) | UI e hardware fora do v1. |
| [FRANK_ZERO](https://github.com/FRANK1-AZZA-Tekk/FRANK_ZERO) | README de uma linha | Sem código para trazer. |

## Forks

`langgraph`, `litellm`, `llama.cpp`, `whisper.cpp`, `omi` e os demais forks sob a org são **upstream de terceiros**. Dependência, quando existir, fica no `requirements`. **Não programe features do YBY nesses forks** e não copie o código deles para cá.
