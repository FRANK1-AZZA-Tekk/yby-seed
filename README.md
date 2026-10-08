# YBY SEED - Programação em Linguagem Natural 🌱

> **Transforme comandos de voz em automações Python** - sem precisar saber programar.
> **Foco atual: PC Hub (Ubuntu + GTX 1650)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Ubuntu 26.04](https://img.shields.io/badge/Ubuntu-26.04-orange.svg)](https://ubuntu.com/download/desktop)
[![Skills Validated](https://img.shields.io/badge/skills-5%20validated-brightgreen)](skills/VERSIONING.md)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/releases)

---

## 🎯 O Que É Isso?

**YBY SEED** é um assistente de IA que **ouve você falar** e **cria automações Python automaticamente**.

### Exemplos Reais:

| Você Fala | YBY SEED Cria |
|---|---|
| _"Me avise se chover amanhã"_ | Script que consulta API do clima e envia notificação |
| _"Backup dos meus PDFs todo dia"_ | Script que compacta e salva PDFs automaticamente |
| _"Monitore CPU e RAM do PC"_ | Script que coleta métricas e publica em dashboard |

**Não precisa saber Python.** Só falar em português natural.

---

## 🚀 Comece Agora (5 Minutos)

### Pré-requisitos

- ✅ Ubuntu 26.04 (ou Windows com WSL2)
- ✅ **NVIDIA GTX 1650 (ou superior) com 4GB VRAM**
- ✅ **16GB RAM**
- ✅ Docker instalado

### Instalação Rápida

```bash
# 1. Clone o repositório
git clone https://github.com/FRANK1-AZZA-Tekk/yby-seed.git
cd yby-seed

# 2. Execute o setup automático
make setup

# 3. Teste a instalação
make test

# 4. Inicie o sistema
make run
```

**Pronto!** Acesse http://localhost:1880 (Node-RED) e comece a criar automações.

---

## 🏗️ Arquitetura Atual (PC Hub)

```
[Usuário] → [FastAPI Gateway] → [Agentes de IA] → [Skills] → [Node-RED] → [Ação]
                ↓                      ↓               ↓          ↓
          [MQTT Broker]        [Ollama LLM]   [Backup,     [Dashboard,
          [LanceDB RAG]        [PostgreSQL]   Notification] Notificações]
```

### Componentes:

| Componente | Tecnologia | Função |
|------------|------------|--------|
| **Gateway** | FastAPI + MQTT | Recebe comandos, gerencia filas |
| **Agentes** | 5 agentes (Router, Planning, Execution, Validation, Learning) | Orquestração |
| **LLMs** | Ollama (Llama 3.2 3B, Qwen2.5 7B) | NL2Code |
| **RAG** | LanceDB + AST Chunking | Recuperação de contexto |
| **Skills** | Backup, Notification, Hardware Monitor | Automações prontas |
| **Dashboard** | Grafana + Prometheus | Monitoring em tempo real |

---

## 📚 Tutoriais Passo a Passo

### Para Iniciantes Absolutos

1. **[Primeiros Passos](docs/tutorials/01-first-steps.md)** - O que é YBY SEED, como funciona
2. **[Sua Primeira Automação](docs/tutorials/02-first-automation.md)** - Crie um alerta de chuva em 10 minutos
3. **[Comandos de Voz](docs/tutorials/03-voice-commands.md)** - Configure microfone e fale com o sistema

### Para Usuários Intermediários

4. **[Personalizando Modelos](docs/tutorials/04-custom-models.md)** - Troque Llama 3.2 por Qwen2.5
5. **[Integrações com APIs](docs/tutorials/05-api-integrations.md)** - Conecte Google Drive, Telegram, etc.

### Para Avançados

6. **[Criando Novos Agentes](docs/tutorials/06-custom-agents.md)** - Adicione seus próprios agentes de IA
7. **[Deploy em Produção](docs/tutorials/07-production-deploy.md)** - Coloque o sistema para rodar 24/7

---

## 🛠️ Comandos Úteis (Makefile)

```bash
# Veja todos os comandos disponíveis
make help

# Instale dependências
make setup

# Rode testes
make test

# Inicie o sistema
make run

# Pare o sistema
make stop

# Limpe arquivos temporários
make clean

# Gere documentação
make docs
```

---

## 📁 Estrutura do Projeto

```
yby-seed/
├── README.md              # Este arquivo (você está aqui)
├── Makefile               # Comandos úteis (make setup, make test)
├── requirements.txt       # Dependências Python
├── docker-compose.yml     # Configuração Docker (Ollama, Node-RED, etc.)
│
├── src/                   # Código principal
│   ├── gateway/           # FastAPI + MQTT + LanceDB
│   ├── agents/            # Agentes de IA (Router, Planning, etc.)
│   ├── rag/               # RAG otimizado (AST Chunking, Pruning)
│   ├── core/              # Lógica central (KV cache, GPU offload)
│   └── monitoring/        # Métricas (Grafana, Prometheus)
│
├── tests/                 # Testes automatizados
│   ├── test_gateway.py
│   ├── test_rag.py
│   └── test_agents.py
│
├── docs/                  # Documentação completa
│   ├── architecture/      # Arquitetura do sistema
│   ├── ai/                # Sistema de IA (RAG, modelos)
│   ├── tutorials/         # Tutoriais passo a passo
│   └── future/            # Futuro: Mobile + ESP32
│
├── skills/                # Agent Skills (oficiais e comunidade)
│   ├── backup-automation/ # Skill de backup automático
│   ├── notification-system/ # Skill de notificações
│   └── hardware-monitor/  # Skill de monitoramento de hardware
│
└── examples/              # Exemplos prontos
    ├── 01_weather_alert.py
    ├── 02_backup_automation.py
    └── 03_hardware_monitor.py
```

---

## 🤔 Perguntas Frequentes (FAQ)

### Preciso saber programar?

**Não!** O YBY SEED foi feito exatamente para quem **não sabe programar**. Você fala em português natural e o sistema cria o código Python automaticamente.

### Funciona no Windows?

**Sim!** Use WSL2 (Windows Subsystem for Linux) com Ubuntu 26.04. Siga o guia [Instalação no Windows](docs/tutorials/install-windows.md).

### Quanto de VRAM preciso?

**Mínimo:** 4GB (GTX 1650)  
**Recomendado:** 8GB (RTX 3060 ou superior)

Com 4GB, o sistema roda modelos 3B rapidamente. Modelos 7B+ usam offloading para RAM (mais lento).

### Posso usar sem internet?

**Sim!** Ollama roda modelos localmente. Só precisa de internet para baixar os modelos na primeira vez.

### Como contribuo?

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes. Comece com issues marcadas como ["good first issue"](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

---

## 🚀 Roadmap

### **Fase 1 (Atual): PC Hub 100%** ✅

- ✅ Gateway FastAPI + MQTT
- ✅ 5 agentes de IA (Router, Planning, Execution, Validation, Learning)
- ✅ RAG otimizado (AST Chunking, Context Pruning)
- ✅ Skills (Backup, Notification, Hardware Monitor)
- ✅ Auto-Evolução (Bayesian Teaching, Auto-Cleanup, Auto-Improvement)
- ✅ Testes automatizados + Grafana Dashboard

### **Fase 2 (Futuro): Mobile (Android)**

- ⏸️ Gateway MQTT no Termux (Xiaomi 12)
- ⏸️ OpenCL na GPU Adreno 730
- ⏸️ Injeção ADB (HyperOS 3.0)
- ⏸️ Termux:API (sensores, notificações)

### **Fase 3 (Futuro): Wearable (ESP32-S3)**

- ⏸️ Firmware LilyGO T-Watch S3 Plus
- ⏸️ MQTT+TLS (MQTTS)
- ⏸️ Deep Sleep + sensores (batimentos, SpO2, passos)

---

## 🙏 Agradecimentos

- **Ollama Team** - Motor de inferência local
- **Node-RED** - Orquestração de fluxos
- **Hugging Face** - Modelos open-source
- **Comunidade Python Brasil** - Suporte e inspiração

---

## 📄 Licença

MIT License - ver [LICENSE](LICENSE)

---

## 📞 Contato

- **Email:** alissonfaria4@gmail.com
- **GitHub:** [@FRANK1-AZZA-Tekk](https://github.com/FRANK1-AZZA-Tekk)
- **Discord:** [Entre no servidor](https://discord.gg/yby-seed)

---

**YBY SEED** - _Function Over Form_ 🚀

**Última atualização:** 2026-10-08  
**Versão:** 1.0.0 (PC Hub)
