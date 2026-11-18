# Otimizações e gargalos

## Ollama — motor (`yby ask`) e hub (`yby hub`)

### Fixar `num_ctx` (evitar “reload tax”)

Defina **um** valor em `YBY_OLLAMA_NUM_CTX` (ex.: `4096` no Hub, `2048` em laptop 4 GB) e não mude entre pedidos. Cada mudança pode recarregar o modelo e piorar a latência do primeiro token.

### `keep_alive` — dois perfis

| Perfil | `OLLAMA_KEEP_ALIVE` | Quando |
| --- | --- | --- |
| **PC Hub** (systemd `yby-hub`) | `30m` (padrão no `.env.example`) | Serviço ligado; quer modelo quente entre `ask`s |
| **Laptop 4 GB** (GTX 1650) | `0` | Uso pontual; liberar VRAM após cada resposta |

No Hub, o ping `GET /api/tags` só checa processo. Com `YBY_HUB_WARMUP=1` (padrão), após o primeiro `tags` ok o hub faz **um** `POST /api/generate` com `num_predict=1` e o mesmo `num_ctx`/`keep_alive` do motor — reduz `load_duration` no primeiro `yby ask` real.

Variáveis:

- `YBY_OLLAMA_NUM_PREDICT` — teto de tokens gerados nas respostas (opcional; omitir = padrão do Ollama).
- `YBY_HUB_WARMUP=0` — desliga warmup (útil em testes ou máquina muito justa de VRAM).
- `YBY_HUB_WARMUP_NUM_PREDICT=1` — tokens do ping de warmup (não altere `num_ctx` só por isso).

### Medir no PC

Na resposta JSON do Ollama, compare `load_duration` (reload) vs `eval_duration` (geração). Warmup + `keep_alive` alinhados devem manter `load_duration` baixo entre pedidos.

## GTX 1650 (4 GB VRAM)

- Usar modelos 1B–3B.
- Um modelo por vez (`OLLAMA_MAX_LOADED_MODELS=1`).
- `OLLAMA_KEEP_ALIVE=0` para liberar VRAM (perfil laptop — não misture com hub `30m` na mesma máquina sem intenção).
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
