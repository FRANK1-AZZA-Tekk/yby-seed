# YBY SEED — Arquitetura (Foco PC Hub)

> **Status:** v1.0.0 (PC Hub)  
> **Última atualização:** 2026-10-08  
> **Hardware alvo:** Ryzen 5 4600G, GTX 1650 (4GB VRAM), 16GB RAM

## 🌐 Visão Geral

O **YBY SEED** opera como um **PC Hub** centralizado, transformando comandos de voz em automações Python através de uma arquitetura multi-agente otimizada para hardware local (4GB VRAM, 16GB RAM).

### Arquitetura:

```
[Usuário: Voz/Texto] → [FastAPI Gateway] → [Agentes de IA] → [Skills] → [Node-RED] → [Ação]
                            ↓                    ↓              ↓          ↓
                      [MQTT Broker]        [Ollama LLM]   [Backup,    [Dashboard,
                      [LanceDB RAG]        [PostgreSQL]   Notification] Notificações]
```

---

## 🏗️ Estado Atual do Sistema

- **Agentes:** 5 agentes implementados em `src/agents/` (Router, Planning, Execution, Validation, Learning)
- **Skills:** 3 skills validadas em `skills/` (Backup, Notification, Hardware Monitor)
- **Isolamento:** Sandbox via `subprocess.Popen` + `rlimits` + validação AST
- **Modelos:** 
  - 3B parâmetros (Llama 3.2, Qwen2.5-3B) → 100% VRAM (4GB)
  - 7B parâmetros (Qwen2.5-7B) → Offloading RAM (16GB)
- **RAG:** LanceDB com AST Chunking + Context Pruning (70% menos tokens)
- **Stack:** Ollama, Node-RED, Mosquitto, PostgreSQL, Redis (Docker Compose)

---

## 📐 Decisões Arquiteturais

1. **PC Hub 100%:** Foco em estabilidade e performance no PC antes de expandir para mobile/ESP32
2. **Local-First:** Offline por padrão, cloud só como fallback
3. **NL2Code em Português:** Foco em PMEs e não-programadores brasileiros
4. **5 Agentes:** Router, Planning, Execution, Validation, Learning (orquestração modular)
5. **Skills Modulares:** Frontmatter YAML + scripts Python
6. **Hardware Alvo:** GTX 1650 (4GB VRAM) + 16GB RAM — otimizado para custo-benefício

---

## 🧪 Hipóteses Operacionais

- 3B em 4GB VRAM entrega latência <500ms para interações em tempo real
- 7B com offloading RAM é aceitável para geração de código (1-2s)
- AST Chunking + Context Pruning reduz 70% tokens injetados (4000 → 1200)
- Node-RED + Mosquitto atendem automações IoT sem complexidade excessiva

---

## ⚠️ Pendências Críticas (Roadmap v1.1)

- **Cobertura de Testes:** Implementar testes unitários para todos os módulos
- **Skills Schema:** Documentar formalmente estrutura de `SKILL.md`
- **Pipeline de Voz:** Integrar Whisper para ASR local direto no PC Hub
- **Dashboard Grafana:** Configurar painéis de telemetria em tempo real

---

## 🚫 Não-objetivos do MVP (Out of Scope)

- ⏸️ **Mobile (Android/Termux):** Futuro (Fase 2)
- ⏸️ **Wearable (ESP32-S3):** Futuro (Fase 3)
- Execução segura de scripts complexos de terceiros não-validados
- Fine-tuning ou treinamento de modelos (foco em RAG, Prompt Engineering)
- UI/UX elaborada para desktop (interface primária: CLI, logs, Node-RED)
- Isolamento total de rede/Filesystem na execução das automações

---

## 🔗 Referências Cruzadas

- [Runtime de Execução](architecture/runtime.md)
- [Sistema de Agentes](architecture/agents.md)
- [Matriz de Modelos](architecture/models.md)
- [Diretrizes de Segurança](architecture/security.md)
- [RAG Otimizado](ai/rag_optimizer.md)
- [Futuro: Mobile + ESP32](future/README.md)
