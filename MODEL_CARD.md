---
license: mit
language:
- python
- en
- pt
tags:
- natural-language-programming
- iot
- esp32
- mqtt
- llm
- automation
- edge-computing
- local-first
pipeline_tag: text-generation
library_name: yby-seed
---

# YBY SEED - Model Card

## 🎯 Model Details

**Model Description:** YBY SEED é uma plataforma de Natural Language Programming que traduz comandos em linguagem natural para automções Python executáveis, orquestrando wearables (ESP32), nós móveis (Termux/Android) e servidores locais (Ubuntu/Linux) via MQTT.

**Developed by:** Alisson De Faria (LINKK TEKK, Jundiaí, Brasil)

**Funded by:** Projeto independente open-source

**Model type:** Sistema multi-agente com LLM (Qwen2.5-Coder-3B-Instruct) + orquestração MQTT + sandbox de execução

**License:** MIT License

**Repository:** https://github.com/FRANK1-AZZA-Tekk/yby-seed

## 📋 Intended Uses

### Primary Use Cases

- **Educacional:** Estudantes e educadores criando automações sem conhecimento de programação
- **Industrial:** Técnicos monitorando equipamentos via comandos de voz
- **Pesquisa:** Laboratórios de sistemas embarcados e IoT distribuindo experimentos reprodutíveis
- **Saúde:** Pacientes monitorando sinais vitais com alertas personalizados

### Out-of-Scope Uses

- **NÃO usar para:** Automações críticas de segurança (médico, industrial de alto risco)
- **NÃO usar para:** Processamento de dados sensíveis sem auditoria humana
- **NÃO usar para:** Sistemas que exigem latência <100ms (o sistema tem latência de 1-5s)

## 🏗️ Architecture

```
Usuário (voz/texto)
    ↓
LLM Local (Qwen2.5-Coder-3B na GTX 1650)
    ↓
Código Python gerado
    ↓
Security Linter (valida padrões perigosos)
    ↓
Sandbox (subprocess + resource limits)
    ↓
Execução como automação persistente
    ↓
Monitoramento via MQTT + TUI
```

## 📊 Evaluation

### NL2Code Accuracy

| Benchmark | Score | Notes |
|---|---|---|
| HumanEval (Qwen2.5-Coder-3B) | 84% | Modelo base |
| NL2Code (YBY SEED, 50 prompts) | 78% | Prompts em português do Brasil |
| Security Linter (100 testes) | 96% | Bloqueio de padrões perigosos |

### Latência

| Operação | Latência Média | Hardware |
|---|---|---|
| NL2Code (local, Ollama) | 3-5s | GTX 1650, 4GB VRAM |
| NL2Code (fallback, Groq) | 0.5-1s | API externa |
| MQTT end-to-end | <200ms | Wi-Fi local |
| OTA (wearable) | 30-60s | Wi-Fi, 400KB firmware |

### Recursos

| Componente | RAM | VRAM | CPU |
|---|---|---|---|
| Ollama + Qwen2.5-Coder-3B | 2GB | 2.5GB | 4 threads |
| Node-RED + Mosquitto | 200MB | - | 1 thread |
| LiteLLM Proxy | 150MB | - | 1 thread |
| Process Manager | 100MB | - | 1 thread |

## 🚀 Limitations

### Técnicas

- **VRAM limitada:** GTX 1650 (4GB) suporta apenas modelos até 3B parâmetros (Q4_K_M)
- **Latência:** 3-5s para NL2Code local (aceitável para automações, não para chat em tempo real)
- **Conectividade:** Wearable depende de Wi-Fi (sem LoRa no MVP)
- **Bateria:** Wearable dura 14-20h com Deep Sleep + wake-up a cada 5min

### de Segurança

- **Sandbox não é perfeita:** Linter estático bloqueia 96% dos padrões perigosos, mas não previne todos os ataques
- **Sem isolamento de rede:** Scripts podem abrir sockets se não bloqueados no linter
- **Dependência de API:** Fallback para Groq/OpenRouter requer internet e chave de API

### Éticas

- **Viés do LLM:** Qwen2.5-Coder treinado em código público (pode reproduzir vieses de gênero, raça, etc.)
- **Privacidade:** Dados de sensores corporais trafegam via MQTT (recomenda-se TLS em produção)
- **Responsabilidade:** Usuário final é responsável por validar automções antes de deploy em produção

## 📈 Training Data

**LLM Base:** Qwen2.5-Coder-3B-Instruct
- **Dataset:** Código Python público (GitHub, StackOverflow, etc.)
- **Linguagens:** Python, JavaScript, Bash
- **Período:** Até 2025
- **Licenças:** Múltiplas (MIT, Apache 2.0, BSD, etc.)

**Fine-tuning (YBY SEED):**
- **Dataset:** 500+ prompts em português do Brasil com automações IoT
- **Exemplos:** "Crie um alerta se BPM > 120", "Monitore passos e avise se < 5000"
- **Validação:** 50 prompts de teste com automações funcionais

## 🛡️ Security & Privacy

### Security Measures

- **Linter estático:** Bloqueia `os.system`, `eval`, `exec`, `subprocess`, etc.
- **Limites de recursos:** 128MB RAM, 30s CPU timeout por script
- **Usuário não-root:** Scripts rodam como `yby-executor` sem acesso a `/`, `/etc`, `/home`
- **MQTT com senha:** Autenticação básica no broker (recomenda-se TLS em produção)

### Privacy Considerations

- **Dados locais:** Tudo roda localmente (Ollama, Mosquitto, Node-RED)
- **Fallback opcional:** Groq/OpenRouter só se usuário configurar chave de API
- **Dados de saúde:** BPM, passos, temperatura são sensíveis - criptografar em produção
- **Tailscale:** Recomenda-se WireGuard para comunicação nó móvel ↔ servidor

## 🔧 Hardware Requirements

### Servidor (Ubuntu)

- **CPU:** Ryzen 5 4600G (6 cores, 12 threads) ou equivalente
- **RAM:** 16GB mínimo
- **GPU:** GTX 1650 (4GB VRAM) ou superior (NVIDIA)
- **Storage:** 50GB SSD (Docker + modelos)

### Wearable

- **Hardware:** LilyGO T-Watch S3 Plus (ESP32-S3, 8MB PSRAM)
- **Conectividade:** Wi-Fi 2.4GHz
- **Bateria:** 400-500mAh (14-20h autonomia)

### Nó Móvel

- **Hardware:** Xiaomi 12 (ou Android com Termux)
- **SO:** Android 12+ (Termux sem root)
- **Conectividade:** Wi-Fi + Bluetooth (opcional)

## 📚 Citation

Se usar YBY SEED em pesquisa, cite:

```bibtex
@software{yby-seed,
  author = {Alisson De Faria},
  title = {YBY SEED: Natural Language Programming for Educational and Industrial Automations},
  year = {2026},
  url = {https://github.com/FRANK1-AZZA-Tekk/yby-seed},
  version = {1.0.0}
}
```

## 🤝 Contributing

Contribuições são bem-vindas! Leia [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes.

## 📄 License

MIT License - ver [LICENSE](LICENSE)

---

**Última atualização:** 2026-10-08  
**Versão:** 1.0.0
