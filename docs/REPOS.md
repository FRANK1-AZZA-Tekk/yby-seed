# Onde programar

O código do v1 fica neste repositório, `yby-seed`. Os outros repositórios do dono continuam separados. Forks de projetos de terceiros não entram aqui.

## Neste repositório

O caminho que o `yby.py` usa hoje:

| Pasta | Papel |
|---|---|
| `src/engine` | `ask`: Ollama local e fallback de nuvem |
| `src/safety` | decide run, ask ou refuse; não executa |
| `src/memory` | notas Markdown do vault |
| `src/security/ast_guard.py` | bloqueia código gerado perigoso |
| `tests/` | suíte que o CI roda |

O resto de `src/` (agentes, RAG, gateway, monitoramento) existe no disco e ainda não entra no `ask`. Mobile e firmware saíram da árvore; ver [archive/FORA-DO-V1.md](archive/FORA-DO-V1.md).

## Repositórios do dono, separados

| Repositório | O que é | Por que não mescla no seed |
|---|---|---|
| [YBY](https://github.com/FRANK1-AZZA-Tekk/YBY) | YBY ZERO: PC + celular + fone + relógio, com eventos, privacidade e voz | O v1 é só o PC Hub. O pacote `src/yby_zero` continua lá. |
| [yby-core](https://github.com/FRANK1-AZZA-Tekk/yby-core) | Orquestrador FastAPI + LangGraph, MQTT e PlatformIO | É outro processo, com firmware e ferramentas que o `ask` não chama. |
| [FRANK_ZER0](https://github.com/FRANK1-AZZA-Tekk/FRANK_ZER0) | Protótipo 2026 em TypeScript, React, Android e ESP32 | Interface e hardware fora do v1. |
| [FRANK_ZERO](https://github.com/FRANK1-AZZA-Tekk/FRANK_ZERO) | README de uma linha | Não há código para trazer. |

## Forks

`langgraph`, `litellm`, `llama.cpp`, `whisper.cpp`, `omi` e os demais forks são upstream. A dependência, quando existir, fica no `requirements`. O código deles não é copiado para cá.
