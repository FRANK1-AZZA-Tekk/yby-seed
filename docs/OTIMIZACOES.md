# Otimizações e gargalos

## GTX 1650 (4 GB VRAM)

- Usar modelos 1B–3B.
- Um modelo por vez (`OLLAMA_MAX_LOADED_MODELS=1`).
- `OLLAMA_KEEP_ALIVE=0` para liberar VRAM.
- Verificar com `ollama ps` se está 100% GPU.

## Qdrant

- Limitar a 1 GB de RAM no Docker Compose.
- Volume persistente em `./data/qdrant`.

## FastAPI

- Validar entrada e saída com Pydantic.
- Timeout de 30s no LiteLLM.
- Fallback para OpenRouter.

## Automações

- Sempre dry-run primeiro.
- Execução só após confirmação do usuário.

## Docker

- Portas apenas em 127.0.0.1.
- Limites de memória por serviço.
- Subir um serviço por vez.
