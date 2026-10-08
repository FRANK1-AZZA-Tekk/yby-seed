# YBY SEED - Programação em Linguagem Natural 🌱

> **Transforme comandos de voz em automações Python** - sem precisar saber programar.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Ubuntu 26.04](https://img.shields.io/badge/Ubuntu-26.04-orange.svg)](https://ubuntu.com/download/desktop)
[![Skills Validated](https://img.shields.io/badge/skills-5%20validated-brightgreen)](skills/VERSIONING.md)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/releases)

![YBY SEED Demo](https://via.placeholder.com/800x400.png?text=YBY+SEED+Demo+-+Voz+para+C%C3%B3digo)

---

## 🎯 O Que É Isso?

**YBY SEED** é um assistente de IA que **ouve você falar** e **cria automações Python automaticamente**.

### Exemplos Reais:

| Você Fala | YBY SEED Cria |
|---|---|
| _"Me avise se chover amanhã"_ | Script que consulta API do clima e envia notificação |
| _"Conte meus passos e meta 10.000"_ | Monitor de passos com alerta ao atingir meta |
| _"Backup dos meus PDFs todo dia"_ | Script que compacta e salva PDFs automaticamente |

**Não precisa saber Python.** Só falar em português natural.

---

## 🚀 Comece Agora (5 Minutos)

### Pré-requisitos

- ✅ Ubuntu 26.04 (ou Windows com WSL2)
- ✅ 16GB RAM
- ✅ NVIDIA GTX 1650 (ou superior) com 4GB VRAM
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
│   ├── core/              # Lógica central (NL2Code, RAG, etc.)
│   ├── agents/            # Agentes de IA (Planning, Execution, etc.)
│   ├── utils/             # Funções utilitárias
│   └── main.py            # Ponto de entrada
│
├── tests/                 # Testes automatizados
│   ├── test_core.py
│   ├── test_agents.py
│   └── test_utils.py
│
├── docs/                  # Documentação completa
│   ├── tutorials/         # Tutoriais passo a passo
│   ├── architecture/      # Arquitetura do sistema
│   └── api/               # Referência de API
│
├── skills/                # Agent Skills (oficiais e comunidade)
│   ├── backup-automation/ # Skill de backup automático
│   ├── api-integration/   # Skill de integração com APIs
│   ├── data-processing/   # Skill de processamento de dados
│   ├── notification-system/ # Skill de notificações
│   └── file-operations/   # Skill de operações com arquivos
│
├── examples/              # Exemplos prontos
│   ├── 01_weather_alert.py
│   ├── 02_steps_tracker.py
│   └── 03_backup_automation.py
│
└── scripts/               # Scripts de setup/deploy
    ├── setup.sh
    └── deploy.sh
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
**Versão:** 1.0.0
