# YBY SEED - Natural Language Programming

> **Exocórtex de IA distribuído, open-source e local-first** para automações educacionais e industriais.

## 🎯 Visão Geral

O YBY SEED permite que **não-programadores** construam ferramentas de software e automações através de **linguagem natural**. O sistema traduz comandos como _"Crie um alerta se meu batimento passar de 120"_ em scripts Python executáveis, gerenciados automaticamente.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    YBY ECOSYSTEM                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Wearable    │    │  Nó Móvel    │    │  Servidor    │  │
│  │ LilyGO T-    │───▶│  Xiaomi 12   │───▶│   Ubuntu     │  │
│  │ Watch S3+    │◀───│  Termux      │◀───│  Docker      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         └───────────────────┼───────────────────┘           │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │  MQTT Broker    │                      │
│                    │  (Mosquitto)    │                      │
│                    └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

## 🧠 Stack Tecnológico

| Componente | Tecnologia | Função |
|---|---|---|
| **LLM Local** | Qwen2.5-Coder-3B-Instruct (Q4_K_M) | Gera código Python a partir de linguagem natural |
| **Gateway LLM** | LiteLLM Proxy | Roteamento híbrido (local → nuvem) com fallback |
| **Orquestrador** | Node-RED | Fluxos de automação e integração MQTT |
| **Broker MQTT** | Eclipse Mosquitto | Comunicação nervosa central entre nós |
| **Sandbox** | subprocess + resource limits | Execução segura de código gerado |
| **Registry** | SQLite | Metadados de automações ativas |
| **Interface** | Textual (TUI) | Terminal de monitoramento de status |

## 📦 Nós do Sistema

### 1. **Servidor Local (Ubuntu)**
- **Hardware:** Ryzen 5 4600G, 16GB RAM, GTX 1650 (4GB VRAM)
- **Serviços Docker:** Mosquitto, Node-RED, Ollama, LiteLLM, Process Manager
- **Função:** Orquestração pesada, LLM local, registry de automações

### 2. **Nó Móvel (Edge)**
- **Hardware:** Xiaomi 12 (Termux sem root)
- **Software:** Python + paho-mqtt + Silero VAD + ffmpeg
- **Função:** Captura de áudio, STT local, notificações push

### 3. **Wearable**
- **Hardware:** LilyGO T-Watch S3 Plus (ESP32-S3)
- **Software:** Arduino + PubSubClient + ArduinoOTA
- **Função:** Sensores corporais (BPM, passos), alertas discretos

## 🚀 Funcionalidades

### Natural Language Programming
- ✅ **Criar:** _"Crie um alerta se meu batimento passar de 120"_
- ✅ **Ler:** _"Quais alertas tenho ativos?"_
- ✅ **Atualizar:** _"Mude o alerta de batimento para 140"_
- ✅ **Deletar:** _"Desligue o alerta de batimento"_

### Automações Exemplo
```python
# Exemplo 1: Alerta de batimento cardíaco
if bpm > 120:
    mqtt_publish("yby/mobile/alert", {"message": "BPM elevado!"})

# Exemplo 2: Meta de passos diários
if steps < 5000 and hour == 20:
    mqtt_publish("yby/mobile/alert", {"message": "Meta de passos não atingida"})
```

## 🛡️ Segurança

- **MQTT:** Autenticação por senha + rede Wi-Fi isolada (VLAN)
- **Sandbox:** Linter estático + limites de CPU/RAM (resource module)
- **OTA:** Atualização de firmware over-the-air com senha
- **Tailscale:** WireGuard para comunicação segura nó móvel ↔ servidor

## 📋 Roadmap

- [x] **Fase 1:** Fundação MQTT (wearable ↔ mobile ↔ servidor)
- [ ] **Fase 2:** Ollama + Qwen2.5-Coder (NL2Code local)
- [ ] **Fase 3:** LiteLLM Proxy (fallback para nuvem)
- [ ] **Fase 4:** Interface TUI (Textual) + Registry SQLite

## 📄 Licença

MIT License - ver [LICENSE](LICENSE)

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

**YBY SEED** - _Function Over Form_ 🚀
