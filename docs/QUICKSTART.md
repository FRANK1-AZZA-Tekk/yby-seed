# 🚀 Quick Start - YBY SEED

## Pré-requisitos

- Ubuntu 22.04+ com Docker e Docker Compose
- GPU NVIDIA (GTX 1650 ou superior) com drivers instalados
- 16GB RAM mínimo
- Conta no Groq e OpenRouter (para fallback)

## 1. Clone o Repositório

```bash
git clone https://github.com/FRANK1-AZZA-Tekk/yby-seed.git
cd yby-seed
```

## 2. Configure as Variáveis de Ambiente

```bash
cp .env.example .env
nano .env
```

Preencha:
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
```

## 3. Inicie os Serviços

```bash
docker-compose up -d
```

Verifique o status:
```bash
docker-compose ps
```

## 4. Baixe o Modelo LLM

```bash
docker exec yby-ollama ollama pull qwen2.5-coder:3b-instruct-q4_K_M
```

## 5. Acesse as Interfaces

- **Node-RED:** http://localhost:1880
- **LiteLLM:** http://localhost:4000
- **Mosquitto:** localhost:1883 (MQTT)

## 6. Teste o Sistema

### Via MQTT (mosquitto_pub)
```bash
# Instale o cliente MQTT
sudo apt install mosquitto-clients

# Publique um prompt
mosquitto_pub -t "yby/user/prompt" -m "Crie um alerta se BPM > 120"

# Ouça as respostas
mosquitto_sub -t "yby/agent/response" -v
```

### Via API (LiteLLM)
```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-yby-master-key-2026" \
  -d '{
    "model": "yby-default",
    "messages": [{"role": "user", "content": "Olá!"}]
  }'
```

## 7. Monitore os Logs

```bash
# Ver todos os serviços
docker-compose logs -f

# Apenas o Process Manager
docker-compose logs -f process-manager

# Apenas o Ollama
docker-compose logs -f ollama
```

## 8. Pare os Serviços

```bash
docker-compose down
```

Para remover volumes (reset completo):
```bash
docker-compose down -v
```

---

## Próximos Passos

1. **Configurar Wearable:** Ver `docs/wearable/README.md`
2. **Configurar Nó Móvel:** Ver `docs/mobile/README.md`
3. **Criar Primeira Automação:** Ver `docs/automations/README.md`

## Solução de Problemas

### Ollama não inicia
```bash
# Verifique se os drivers NVIDIA estão instalados
nvidia-smi

# Reinstale o container
docker-compose rm -f ollama
docker-compose up -d ollama
```

### MQTT não conecta
```bash
# Verifique se a porta 1883 está aberta
sudo ufw status
sudo ufw allow 1883
```

### LiteLLM retorna erro 503
```bash
# Verifique se o Ollama está respondendo
curl http://localhost:11434/api/tags

# Se falhar, reinicie o Ollama
docker-compose restart ollama
```

---

**Dúvidas?** Abra uma issue no GitHub.

**Princípio:** _Function Over Form_ 🚀
