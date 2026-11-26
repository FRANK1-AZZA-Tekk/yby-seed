# YBY Machine (Spec-First)

Gera um **micro-app offline** (PWA) a partir de um pedido em português. O modelo só monta a **especificação** (`YBYSpec`); o HTML/CSS/JS vem de templates fixos — nunca de LLM.

## O que cada arquivo faz

| Arquivo | Função |
|---|---|
| `spec.py` | Modelo da especificação (nome, campos BR, Pix, WhatsApp, status de pagamento) + `yby_spec_json_schema()`. |
| `ports.py` | Contratos (`EmbedderPort`, `SpecStorePort`, `TranslateCachePort`) e modelos de histórico (`AppSummary`, `StoredAppRecord`). |
| `embedder.py` | Embedder padrão determinístico offline (hash/n-gram) + adapter opcional Ollama embeddings. |
| `store.py` | Store padrão em memória com reuso por similaridade cosseno (`>= 0.92`), listagem e busca por `app_id`. |
| `store_pgvector.py` | Adapter opcional Postgres/pgvector (import lazy); se falhar ou sem env, cai em memória. |
| `cache.py` | Cache LRU em memória (`TranslateCachePort`) + wrapper opcional Redis (import lazy). |
| `translator.py` | Converte pedido em `YBYSpec` via Ollama local (`format=json`). LiteLLM só com env explícita (D12). Timeout ou erro cai no fallback. |
| `fallback.py` | Spec mínima por palavras-chave (encomenda, oficina, estoque). |
| `pipeline.py` | Orquestra `reuse (>= 0.92) -> cache -> translate -> fallback -> persist -> compile`. |
| `compiler.py` | Monta o PWA (HTML + CSS + JS + manifest + service worker + CSP, DOM seguro sem `innerHTML`, IndexedDB + fallback `localStorage`). |
| `http.py` | API FastAPI: `POST /api/machine/generate`, `GET /api/machine/apps`, `GET /api/machine/apps/{app_id}`, `GET /api/machine/schema`, `GET /health`. |
| `__init__.py` | Exporta `YBYSpec`, `compile_pwa`, `prompt_to_spec`, `yby_spec_json_schema`, `MachinePipeline`, `PipelineResult`, `InMemorySpecStore`, `OfflineHashEmbedder`. |

## Modo padrão (offline) vs adapters opcionais

Por padrão, o YBY Machine roda **100% offline em memória**, sem Docker, Postgres, Redis ou nuvem:

- Embeddings: `OfflineHashEmbedder` (determinístico por tokens e 3-gramas).
- Histórico e reuso (`>= 0.92`): `InMemorySpecStore`.
- Cache de tradução: `AsyncSpecFingerprintCache`.
- Tradutor: Ollama local (`format=json`) com fallback seguro em `fallback.py`.

Adapters opcionais só ativam quando a variável de ambiente está definida **e** a biblioteca opcional consegue importar; caso contrário, cai no padrão local (D12):

| Variável | Efeito opcional | Fallback padrão |
|---|---|---|
| `YBY_DATABASE_URL` | Ativa `PgVectorSpecStore` (requer `psycopg` + extensão `vector`) | `InMemorySpecStore` |
| `YBY_REDIS_URL` | Ativa `RedisTranslateCache` (requer `redis`) | `AsyncSpecFingerprintCache` |
| `YBY_MACHINE_TRANSLATOR=litellm` | Usa `litellm.completion` (`YBY_MACHINE_LITELLM_MODEL`) | Ollama local -> `fallback.py` |
| `YBY_MACHINE_EMBEDDER=ollama` | Usa `/api/embeddings` no Ollama (`OLLAMA_MODEL_EMBEDDING`) | `OfflineHashEmbedder` |

## Persistência no PWA

Registros ficam em **IndexedDB** (`yby_machine_db_<name>`) com fallback automático em **`localStorage`** (`yby_machine_<name>`). O DOM é montado sem `innerHTML`, com CSP restritiva, botão Pix copia-cola (BR Code prefixo `000201`, sem CRC EMV bancário completo) e link `wa.me` com `noopener noreferrer`.

## Como gerar e abrir no navegador

```bash
# 1) Gerar os arquivos (sem Ollama: usa fallback por palavras-chave se o modelo falhar)
PYTHONPATH=. .venv/bin/python yby.py machine "App de encomendas com Pix e WhatsApp" -o /tmp/yby-encomendas

# 2) Servir a pasta (obrigatório para o service worker)
cd /tmp/yby-encomendas
python3 -m http.server 8765 --bind 127.0.0.1
```

API HTTP:

```bash
PYTHONPATH=. .venv/bin/uvicorn src.yby_machine.http:app --port 8090
# POST http://127.0.0.1:8090/api/machine/generate       {"prompt":"..."}
# GET  http://127.0.0.1:8090/api/machine/apps
# GET  http://127.0.0.1:8090/api/machine/apps/{app_id}
# GET  http://127.0.0.1:8090/api/machine/schema
```
