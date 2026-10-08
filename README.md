# YBY SEED - Natural Language Programming

> **Exocórtex de IA distribuído, open-source e local-first** para automações educacionais e industriais.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI/CD](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://frank1-azza-tekk.github.io/yby-seed/)
[![Model Card](https://img.shields.io/badge/model-card-HuggingFace-orange)](MODEL_CARD.md)
[![Citation](https://zenodo.org/badge/DOI/10.0000/zenodo.yby-seed-2026.svg)](https://doi.org/10.0000/zenodo.yby-seed-2026)

[![GitHub stars](https://img.shields.io/github/stars/FRANK1-AZZA-Tekk/yby-seed?style=social)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/FRANK1-AZZA-Tekk/yby-seed?style=social)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/network)
[![GitHub issues](https://img.shields.io/github/issues/FRANK1-AZZA-Tekk/yby-seed)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues)

---

## 🚀 Quick Start (15 minutos)

### Pré-requisitos

- Docker + Docker Compose
- Python 3.10+
- (Opcional) VS Code + Dev Containers extension

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/FRANK1-AZZA-Tekk/yby-seed.git
cd yby-seed

# 2. Configure variáveis de ambiente
cp .env.example .env
nano .env  # Preencha GROQ_API_KEY e OPENROUTER_API_KEY

# 3. Execute setup
make setup

# 4. Teste a instalação
make test
```

### Primeiro Comando

```bash
# Publique um prompt NL2Code
mosquitto_pub -t "yby/user/prompt" -m "Crie um alerta se BPM > 120"

# Ouça a resposta
mosquitto_sub -t "yby/agent/response" -v
```

---

## 📚 Documentação

- **[📖 Getting Started](docs/getting-started/installation.md)** - Instalação detalhada
- **[🏗️ Architecture](docs/architecture/overview.md)** - Diagramas e componentes
- **[🛠️ Development](docs/development/setup.md)** - Setup para contribuidores
- **[📡 API Reference](docs/api/mqtt-topics.md)** - Tópicos MQTT e endpoints
- **[💡 Examples](docs/examples/bpm-alert.md)** - Automações prontas
- **[🎓 Model Card](MODEL_CARD.md)** - Detalhes do modelo, avaliação, limitações

---

## 🏗️ Arquitetura

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Wearable    │    │  Nó Móvel    │    │  Servidor    │
│ LilyGO T-    │───▶│  Xiaomi 12   │───▶│   Ubuntu     │
│ Watch S3+    │◀───│  Termux      │◀───│  Docker      │
└──────────────┘    └──────────────┘    └──────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                    ┌────────▼────────┐
                    │  MQTT Broker    │
                    │  (Mosquitto)    │
                    └─────────────────┘
```

### Stack Tecnológico

| Componente | Tecnologia | Função |
|---|---|---|
| **LLM Local** | Qwen2.5-Coder-3B-Instruct (Q4_K_M) | Gera código Python via NL |
| **Gateway LLM** | LiteLLM Proxy | Roteamento Ollama → Groq → OpenRouter |
| **Orquestrador** | Node-RED | Fluxos MQTT + automações |
| **Broker MQTT** | Eclipse Mosquitto | Comunicação nervosa central |
| **Sandbox** | subprocess + resource limits | Execução segura de código |
| **Registry** | SQLite | Metadados de automações |
| **Interface** | Textual (TUI) | Monitoramento em terminal |

---

## 🎯 Casos de Uso

### Educacional
- _"Crie um quiz de matemática que me avisa se errar 3 seguidas"_
- _"Monitore meu tempo de estudo e sugira pausas a cada 50min"_

### Industrial
- _"Alerte se a temperatura do motor passar de 80°C"_
- _"Registre consumo de energia e gere relatório diário"_

### Saúde
- _"Monitore batimento e alerte se ficar acima de 120 por 5min"_
- _"Conte passos e avise se não atingir 10.000 até 20h"_

---

## 🧪 Testes

```bash
# Todos os testes
make test

# Apenas wearable (PlatformIO + Wokwi)
make test-wearable

# Apenas servidor (Pytest)
make test-server

# Com coverage
cd tests && pytest --cov=server --cov-report=html
```

### CI/CD

GitHub Actions roda automaticamente:
- ✅ Testes Python (pytest + coverage)
- ✅ Testes ESP32 (PlatformIO Native)
- ✅ Build Docker images
- ✅ Deploy documentação (MkDocs)

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Veja:

1. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Como contribuir
2. **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** - Código de conduta
3. **[SECURITY.md](SECURITY.md)** - Política de segurança
4. **[Good First Issues](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** - Issues para iniciantes

### Áreas que Precisam de Ajuda

- [ ] Testes E2E (wearable → mobile → server)
- [ ] Traduções (espanhol, francês)
- [ ] Otimização de energia (ESP32, BLE)
- [ ] UI/UX (interface TUI mais amigável)
- [ ] Papers acadêmicos (escrita, submissão)

---

## 📄 Licença

MIT License - ver [LICENSE](LICENSE)

---

## 📚 Como Citar

Se usar YBY SEED em pesquisa acadêmica, cite:

```bibtex
@software{yby-seed,
  author = {Alisson De Faria},
  title = {YBY SEED: Natural Language Programming for Educational and Industrial Automations},
  year = {2026},
  url = {https://github.com/FRANK1-AZZA-Tekk/yby-seed},
  version = {1.0.0},
  doi = {10.0000/zenodo.yby-seed-2026}
}
```

**DOI:** [10.0000/zenodo.yby-seed-2026](https://doi.org/10.0000/zenodo.yby-seed-2026) (pendente de registro no Zenodo)

---

## 🙏 Agradecimentos

- **Qwen Team** (Qwen2.5-Coder-3B)
- **Hugging Face** (infraestrutura de model cards)
- **PlatformIO** (desenvolvimento ESP32)
- **Node-RED** (orquestração de fluxos)
- **Eclipse Mosquitto** (broker MQTT)

---

## 📞 Contato

- **Email:** alissonfaria4@gmail.com
- **GitHub:** [@FRANK1-AZZA-Tekk](https://github.com/FRANK1-AZZA-Tekk)
- **LinkedIn:** [Alisson De Faria](https://linkedin.com/in/alissonfaria)

---

**YBY SEED** - _Function Over Form_ 🚀

**Última atualização:** 2026-10-08  
**Versão:** 1.0.0
