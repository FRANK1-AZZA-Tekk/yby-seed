---
name: api-integration
version: 1.0.0
min_agent_version: 2.0.0
last_updated: 2026-10-08
description: Integra com APIs REST para buscar dados, enviar requisições, processar respostas JSON XML, conectar serviços externos, previsão do tempo, Telegram Bot, GitHub, web scraping
compatibility: ubuntu, python-3.11+, requests, httpx
license: MIT
authors:
  - "Alisson Faria (@FRANK1-AZZA-Tekk)"
keywords:
  - API
  - REST
  - buscar
  - dados
  - enviar
  - requisições
  - JSON
  - XML
  - conectar
  - serviços
  - previsão
  - tempo
  - Telegram
  - GitHub
  - web
  - http
  - requests
  - OpenWeatherMap
  - webhook
changelog:
  - version: 1.0.0
    date: 2026-10-08
    changes:
      - "Versão inicial da skill de integração com APIs"
      - "Suporte a requisições GET, POST, PUT, DELETE"
      - "Autenticação com API key, OAuth, bearer token"
      - "Processamento de respostas JSON e XML"
      - "Tratamento de erros HTTP e timeout"
      - "Exemplos com OpenWeatherMap, Telegram, GitHub"
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Buscar dados de uma API"
- "Enviar dados para uma API"
- "Integrar com [serviço específico]"
- "Consultar previsão do tempo"
- "Enviar mensagem para Telegram/Slack"
- "Buscar repositórios do GitHub"
- "Web scraping de site"

## Instruções Passo a Passo

### 1. Coletar Requisitos

Pergunte ao usuário:

1. **Qual API**? (nome do serviço, URL da API)
2. **Que operação**? (GET, POST, PUT, DELETE)
3. **Autenticação**? (API key, OAuth, token, sem autenticação)
4. **Dados de entrada**? (parâmetros, body da requisição)
5. **Processar resposta**? (salvar JSON, extrair campos específicos)

### 2. Template Base

```python
#!/usr/bin/env python3
"""Integração com API - Gerado por YBY SEED"""

import requests
import json
from pathlib import Path

# Configurações
API_BASE_URL = "https://api.exemplo.com"
API_KEY = "SUA_API_KEY_AQUI"  # Configurar em .env

def fetch_data(endpoint: str, params: dict = None) -> dict:
    """Busca dados da API"""
    
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()

def send_data(endpoint: str, data: dict) -> dict:
    """Envia dados para API"""
    
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    return response.json()

if __name__ == "__main__":
    # Exemplo de uso
    data = fetch_data("users", {"limit": 10})
    print(json.dumps(data, indent=2))
```

### 3. APIs Comuns

#### OpenWeatherMap (Previsão do Tempo)

```python
API_KEY = "SUA_API_KEY"
BASE_URL = "http://api.openweathermap.org/data/2.5"

def get_weather(city: str) -> dict:
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "pt_br"
    }
    
    response = requests.get(f"{BASE_URL}/weather", params=params)
    return response.json()

# Uso
weather = get_weather("Sao Paulo")
print(f"Temperatura: {weather['main']['temp']}°C")
```

#### Telegram Bot (Enviar Mensagem)

```python
BOT_TOKEN = "SEU_BOT_TOKEN"
CHAT_ID = "SEU_CHAT_ID"

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    
    response = requests.post(url, json=data)
    return response.json()

# Uso
send_telegram_message("Olá do YBY SEED!")
```

### 4. Tratamento de Erros

```python
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError

def safe_request(url: str, **kwargs):
    try:
        response = requests.get(url, timeout=10, **kwargs)
        response.raise_for_status()
        return response.json()
    
    except HTTPError as e:
        print(f"❌ Erro HTTP {e.response.status_code}: {e}")
        return None
    
    except Timeout:
        print("⏰ Timeout na requisição")
        return None
    
    except ConnectionError:
        print("🔌 Erro de conexão")
        return None
    
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return None
```

## Exemplos

### Exemplo 1: Buscar Previsão do Tempo

**Input:**

> "Buscar previsão do tempo para São Paulo"

**Output:**

```python
#!/usr/bin/env python3
import requests

API_KEY = "SUA_API_KEY"
city = "Sao Paulo"

url = "http://api.openweathermap.org/data/2.5/weather"
params = {"q": city, "appid": API_KEY, "units": "metric"}

response = requests.get(url, params=params)
data = response.json()

print(f"Temperatura: {data['main']['temp']}°C")
print(f"Descrição: {data['weather'][0]['description']}")
```

### Exemplo 2: Enviar Mensagem Telegram

**Input:**

> "Enviar mensagem para Telegram quando backup terminar"

**Output:**

```python
#!/usr/bin/env python3
import requests

BOT_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"

def notify_backup_complete(backup_name: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": f"✅ Backup concluído: {backup_name}"
    }
    
    requests.post(url, json=data)
```

## Edge Cases

### 1. API Key Inválida

```python
if response.status_code == 401:
    print("❌ API key inválida ou expirada")
    print("💡 Verifique se a chave está correta em .env")
```

### 2. Rate Limiting

```python
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    print(f"⏰ Rate limit atingido, aguarde {retry_after}s")
    time.sleep(retry_after)
```

## Referências

- [requests library](https://docs.python-requests.org/)
- [httpx library](https://www.python-httpx.org/)
- [OpenWeatherMap API](https://openweathermap.org/api)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [GitHub API](https://docs.github.com/en/rest)

## Scripts

- `scripts/test_api.py` - Testa conectividade com API
- `scripts/validate_response.py` - Valida schema da resposta

## Tests

```bash
# Testar skill
python -m pytest tests/skills/test_api_integration.py -v

# Testar API
python scripts/test_api.py https://api.exemplo.com
```
