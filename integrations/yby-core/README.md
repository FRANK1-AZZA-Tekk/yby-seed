# YBY Core

YBY Core é o orquestrador unificado do ecossistema YBY.

Ele conecta IA local, nuvem, ferramentas de desenvolvimento, MQTT, memória vetorial e firmware ESP32 em um único fluxo controlado por LangGraph.

## Arquitetura

```text
Usuário / Wearable / Dashboard
            ↓
        FastAPI
            ↓
      YBY Core
LangGraph + Pydantic AI
            ↓
      MCP Tool Router
 ┌──────────┼──────────┐
 │          │          │
Ollama     Qdrant    OpenRouter
PlatformIO PostgreSQL Gemini
Docker     MQTT      Perplexity
```

## Requisitos

- Python 3.11+
- Ollama rodando em `http://localhost:11434`
- Qdrant opcional
- Mosquitto opcional
- PlatformIO opcional

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Teste

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Leia o README e explique a arquitetura."}'
```

## Segurança

- Acesso a arquivos restrito à pasta `~/yby`.
- Portas locais apenas.
- Dados sensíveis devem usar Ollama local.
- Ações destrutivas exigem aprovação humana.
