# YBY Machine (Spec-First)

Gera um **micro-app offline** (PWA) a partir de um pedido em português. O modelo só monta a **especificação** (`YBYSpec`); o HTML/CSS/JS vem de templates fixos — nunca de LLM.

## O que cada arquivo faz

| Arquivo | Função |
|---|---|
| `spec.py` | Modelo da especificação (nome, campos BR, Pix, WhatsApp, status de pagamento). |
| `translator.py` | Converte o pedido em `YBYSpec` via Ollama local (`format=json`). Se falhar, usa fallback. **Não** chama nuvem sozinho. |
| `fallback.py` | Spec mínima por palavras-chave (encomenda, oficina, estoque). |
| `compiler.py` | Monta o PWA (HTML + CSS + JS + manifest + service worker). |
| `http.py` | API fina: `POST /api/machine/generate` com `{"prompt": "..."}`. |
| `__init__.py` | Exporta `YBYSpec`, `compile_pwa`, `prompt_to_spec`. |

## Como gerar e abrir no navegador

No PC (com o venv do projeto):

```bash
# 1) Gerar os arquivos (sem Ollama: usa fallback por palavras-chave se o modelo falhar)
PYTHONPATH=. .venv/bin/python yby.py machine "App de encomendas com Pix e WhatsApp" -o /tmp/yby-encomendas

# 2) Servir a pasta (obrigatório para o service worker)
cd /tmp/yby-encomendas
python3 -m http.server 8765 --bind 127.0.0.1

# 3) Abrir no navegador
# http://127.0.0.1:8765/
```

Dica: abrir o `index.html` direto do disco (file://) pode bloquear o service worker; use o `http.server` local.

API (opcional):

```bash
PYTHONPATH=. .venv/bin/uvicorn src.yby_machine.http:app --port 8090
# POST http://127.0.0.1:8090/api/machine/generate  {"prompt":"..."}
```
