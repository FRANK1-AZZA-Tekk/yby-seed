---
name: api-integration
description: Integra com APIs REST para buscar dados, enviar requisições e processar respostas (JSON, XML)
compatibility: ubuntu, python-3.11+, requests, httpx
license: MIT
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Buscar dados de uma API"
- "Enviar dados para uma API"
- "Integrar com [serviço específico]"
- "Consultar previsão do tempo"
- "Enviar mensagem para Telegram/Slack"

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

#### GitHub API (Buscar Repositórios)

```python
def get_user_repos(username: str) -> list:
    url = f"https://api.github.com/users/{username}/repos"
    
    response = requests.get(url)
    return response.json()

# Uso
repos = get_user_repos("FRANK1-AZZA-Tekk")
for repo in repos:
    print(f"- {repo['name']}: {repo['description']}")
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

### 5. Salvar Resposta JSON

```python
import json
from datetime import datetime

def save_json_response(data: dict, filename: str = None):
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"api_response_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Dados salvos em {filename}")
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

### Exemplo 3: Salvar Dados em JSON

**Input:**

> "Buscar repositórios do GitHub e salvar em JSON"

**Output:**

```python
#!/usr/bin/env python3
import requests
import json

username = "FRANK1-AZZA-Tekk"
url = f"https://api.github.com/users/{username}/repos"

response = requests.get(url)
repos = response.json()

with open("github_repos.json", 'w') as f:
    json.dump(repos, f, indent=2)

print(f"✅ {len(repos)} repositórios salvos")
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

### 3. Timeout

```python
try:
    response = requests.get(url, timeout=5)
except Timeout:
    print("⏰ API não respondeu em 5 segundos")
    print("💡 Verifique conexão ou aumente timeout")
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
