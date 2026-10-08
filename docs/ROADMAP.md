# Roadmap do YBY SEED

## Fase 1 — Fundação de Comunicação (MVP MQTT)
**Objetivo:** Estabelecer comunicação nervosa central entre os 3 nós.

### Tarefas
- [ ] Deploy do Mosquitto em Docker (sem persistência, sem autenticação para MVP)
- [ ] Configurar LilyGO T-Watch para publicar `yby/wearable/status` via Wi-Fi
- [ ] Configurar Termux (Xiaomi 12) com script `paho-mqtt` para áudio/texto
- [ ] Node-RED básico para logar mensagens MQTT em arquivo

### Critério de Sucesso
- Mensagem publicada no wearable chega ao nó móvel em **<200ms**.

### Duração Estimada
- **2 semanas**

---

## Fase 2 — Orquestração Básica (Node-RED + Ollama)
**Objetivo:** Roteamento de mensagens e primeiro LLM local.

### Tarefas
- [ ] Node-RED com fluxo: `MQTT → HTTP (Ollama) → MQTT`
- [ ] Ollama rodando Qwen2.5-Coder-3B-Instruct Q4_K_M
- [ ] Teste de latência ponta a ponta (wearable → Ollama → mobile)

### Critério de Sucesso
- Resposta do Ollama em **<5s** para prompts simples (<100 tokens).

### Duração Estimada
- **2 semanas**

---

## Fase 3 — Gateway Híbrido (LiteLLM + Fallback)
**Objetivo:** Roteamento inteligente local→nuvem.

### Tarefas
- [ ] Deploy do LiteLLM Proxy com Ollama + Groq + OpenRouter
- [ ] Node-RED atualizado para chamar LiteLLM
- [ ] Configurar fallback: Ollama (3s timeout) → Groq → OpenRouter
- [ ] Logging de custos e latência por requisição

### Critério de Sucesso
- Fallback automático em **<1s** se Ollama exceder timeout.

### Duração Estimada
- **2 semanas**

---

## Fase 4 — Natural Language Programming (smolagents + Registry)
**Objetivo:** Usuário cria automações via linguagem natural.

### Tarefas
- [ ] Integração do smolagents como container Python separado
- [ ] Node-RED com fluxo: `MQTT (prompt) → smolagents → Executa → MQTT`
- [ ] Registry SQLite para CRUD de automações
- [ ] Interface TUI com Textual para monitoramento
- [ ] Documentação de 5 automações de exemplo

### Critério de Sucesso
- Usuário descreve automação em linguagem natural e ela executa em **<10s**.

### Duração Estimada
- **2 semanas**

---

## Fase 5 — Segurança e Produção
**Objetivo:** Blindagem do sistema para uso real.

### Tarefas
- [ ] Autenticação MQTT (senha + VLAN isolada)
- [ ] OTA para firmware do T-Watch
- [ ] Testes automatizados (pytest, PlatformIO)
- [ ] Monitoramento com Prometheus + Grafana

### Critério de Sucesso
- Sistema opera por **7 dias** sem intervenção manual.

### Duração Estimada
- **3 semanas**

---

## Cronograma Total

| Fase | Duração | Marco |
|---|---|---|
| Fase 1 | 2 semanas | MQTT funcional entre 3 nós |
| Fase 2 | 2 semanas | Ollama respondendo via Node-RED |
| Fase 3 | 2 semanas | Fallback local→nuvem automático |
| Fase 4 | 2 semanas | NL2Code com CRUD de automações |
| Fase 5 | 3 semanas | Sistema production-ready |
| **Total** | **11 semanas** | MVP completo |

---

**Princípio:** _Function Over Form_ 🚀
