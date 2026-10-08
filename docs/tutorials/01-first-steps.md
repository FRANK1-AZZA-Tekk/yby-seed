# Primeiros Passos com YBY SEED

> **Tempo estimado:** 15 minutos  
> **Nível:** Iniciante absoluto

---

## 🎯 O Que Você Vai Aprender

Neste tutorial, você vai:

1. Entender o que é o YBY SEED
2. Ver exemplos reais de automações
3. Configurar seu primeiro ambiente
4. Criar sua primeira automação por voz

---

## 🤔 O Que É YBY SEED?

**YBY SEED** é um sistema de **programação por voz** que transforma comandos em português natural em **código Python executável**.

### Analogia Simples

Pense no YBY SEED como um **tradutor**:

- **Você fala:** "Me avise se vai chover amanhã"
- **YBY SEED traduz:** Script Python que consulta API do clima + envia notificação

### Por Que Isso É Importante?

No Brasil, **menos de 1% da população sabe programar**. Isso significa que milhões de pessoas têm **ideias incríveis** mas não conseguem **transformar em software**.

O YBY SEED **democratiza a programação**, permitindo que qualquer pessoa crie automações sem precisar aprender sintaxe de programação.

---

## 📋 Pré-requisitos

Antes de começar, você precisa de:

### Hardware

| Componente | Mínimo | Recomendado |
|---|---|---|
| **CPU** | 4 cores | 6+ cores (Ryzen 5 ou superior) |
| **RAM** | 8GB | 16GB |
| **GPU** | 4GB VRAM (GTX 1650) | 8GB+ VRAM (RTX 3060) |
| **Storage** | 50GB livre | 100GB+ SSD |

### Software

- ✅ Ubuntu 26.04 (ou Windows com WSL2)
- ✅ Docker instalado
- ✅ Microfone funcional

### Conhecimentos

- ✅ Saber usar terminal básico (cd, ls, mkdir)
- ✅ Noções de arquivos e pastas
- ❌ **NÃO precisa saber Python**
- ❌ **NÃO precisa saber programação**

---

## 🚀 Instalação Passo a Passo

### Passo 1: Clone o Repositório

```bash
# Abra o terminal
git clone https://github.com/FRANK1-AZZA-Tekk/yby-seed.git
cd yby-seed
```

### Passo 2: Execute o Setup Automático

```bash
# Isso vai:
# - Criar ambiente virtual Python
# - Instalar dependências
# - Baixar modelos de IA
# - Configurar Docker
make setup
```

**O que acontece aqui:**

1. `make setup` lê o arquivo `Makefile`
2. Executa comandos em sequência:
   - Cria `.venv` (ambiente virtual)
   - Instala packages do `requirements.txt`
   - Baixa modelos Ollama (Llama 3.2 3B, Qwen2.5-Coder 3B)
   - Verifica Docker

**Tempo estimado:** 5-10 minutos (depende da internet)

### Passo 3: Teste a Instalação

```bash
# Verifica se tudo está funcionando
make test
```

**Saída esperada:**

```
🧪 Rodando testes...
✅ Testes concluídos!
```

### Passo 4: Inicie o Sistema

```bash
# Inicia todos os serviços (Ollama, Node-RED, MQTT)
make run
```

**Saída esperada:**

```
🚀 Iniciando YBY SEED...
✅ Serviços iniciados!

📌 Acesse:
   - Node-RED: http://localhost:1880
   - Ollama: http://localhost:11434
```

---

## 🎤 Seu Primeiro Comando de Voz

Agora vem a parte mágica! Vamos criar uma automação **falando em português**.

### Exemplo 1: Alerta de Chuva

**Comando de voz:**

> "Crie um script que me avise se vai chover amanhã em São Paulo"

**O que o YBY SEED faz:**

1. **Transcreve** sua voz para texto
2. **Analisa** a intenção (alerta de chuva)
3. **Gera** código Python usando:
   - API do OpenWeatherMap (previsão do tempo)
   - Sistema de notificações do Ubuntu
4. **Salva** o script em `examples/weather_alert.py`

**Código gerado:**

```python
#!/usr/bin/env python3
"""Alerta de Chuva - Gerado por YBY SEED"""

import requests
from datetime import datetime, timedelta

def get_weather_tomorrow(city="Sao Paulo"):
    """Consulta previsão do tempo para amanhã"""
    url = "http://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": "SUA_API_KEY", "units": "metric"}
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Filtra dados para amanhã
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    
    for item in data["list"]:
        if item["dt_txt"].startswith(tomorrow_str):
            return item
    
    return None

# Verifica se vai chover
weather = get_weather_tomorrow()
if weather and "rain" in weather["weather"][0]["description"].lower():
    print("☔ Vai chover amanhã! Leve um guarda-chuva.")
else:
    print("☀️  Tempo seco amanhã.")
```

### Como Executar o Script

```bash
# Navegue até a pasta de exemplos
cd examples

# Execute o script
python weather_alert.py
```

---

## 📚 Próximos Passos

Agora que você configurou o YBY SEED, continue aprendendo:

1. **[Sua Primeira Automação](02-first-automation.md)** - Crie um monitor de passos em 10 minutos
2. **[Comandos de Voz](03-voice-commands.md)** - Configure microfone e fale com o sistema
3. **[Personalizando Modelos](04-custom-models.md)** - Troque Llama 3.2 por Qwen2.5

---

## 🆘 Problemas Comuns

### Erro: "make: command not found"

**Solução:**

```bash
sudo apt install make -y
```

### Erro: "Docker not found"

**Solução:**

```bash
# Instale Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

### Erro: "Model not found"

**Solução:**

```bash
# Baixe modelos manualmente
ollama pull llama3.2:3b-instruct-q4_K_M
ollama pull qwen2.5-coder:3b-instruct-q4_K_M
```

---

## 📞 Precisa de Ajuda?

- **GitHub Issues:** [Abra uma issue](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues)
- **Discord:** [Entre no servidor](https://discord.gg/yby-seed)
- **Email:** alissonfaria4@gmail.com

---

**Parabéns!** Você completou o primeiro passo. 🎉

**Próximo tutorial:** [Sua Primeira Automação](02-first-automation.md)
