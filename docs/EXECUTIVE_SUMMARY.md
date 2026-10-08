# 📋 Resumo Executivo - YBY SEED

## O Que É

O **YBY SEED** é uma plataforma de **Natural Language Programming** que permite que não-programadores criem automações de software através de comandos de voz ou texto em linguagem natural.

## Problema que Resolve

- **Barreira técnica:** Automações industriais e educacionais exigem conhecimento de programação.
- **Custo de desenvolvimento:** Contratar desenvolvedores para automações simples é caro.
- **Manutenção complexa:** Sistemas de automação tradicionais são difíceis de modificar.

## Solução

O usuário fala: _"Crie um alerta se meu batimento passar de 120"_

O sistema:
1. Processa o comando com LLM local (Qwen2.5-Coder-3B)
2. Gera código Python automaticamente
3. Valida a segurança do código
4. Registra e executa a automação
5. Gerencia o ciclo de vida (atualizar, pausar, deletar)

## Arquitetura em 1 Minuto

```
Usuário (voz/texto)
    ↓
LLM Local (Qwen2.5-Coder-3B na GTX 1650)
    ↓
Código Python gerado
    ↓
Sandbox de segurança (linter + resource limits)
    ↓
Execução como subprocesso
    ↓
Automação ativa (ex.: monitora MQTT e alerta se BPM > 120)
```

## Diferenciais

| Característica | YBY SEED | Alternativas |
|---|---|---|
| **Local-first** | ✅ Roda 100% local, fallback para nuvem | ❌ Nuvem obrigatória |
| **Open-source** | ✅ MIT License | ⚠️ Muitos são proprietários |
| **NL2Code** | ✅ Gera Python executável | ⚠️ Apenas blocos visuais |
| **Sandbox** | ✅ Linter + limites de recursos | ❌ Execução sem restrições |
| **Hardware acessível** | ✅ GTX 1650 (4GB VRAM) | ❌ Requer H100/A100 |

## Stack Tecnológico

- **LLM:** Qwen2.5-Coder-3B-Instruct (84% HumanEval, 2.5GB VRAM)
- **Gateway:** LiteLLM Proxy (roteamento Ollama → Groq → OpenRouter)
- **Orquestração:** Node-RED + MQTT (Mosquitto)
- **Sandbox:** subprocess + resource module (Python nativo)
- **Registry:** SQLite (metadados de automações)

## Casos de Uso

### Educacional
- _"Crie um quiz de matemática que me avisa se errar 3 seguidas"_
- _"Monitore meu tempo de estudo e sugira pausas a cada 50min"_

### Industrial
- _"Alerte se a temperatura do motor passar de 80°C"_
- _"Registre consumo de energia e gere relatório diário"_

### Saúde
- _"Monitore batimento e alerte se ficar acima de 120 por 5min"_
- _"Conte passos e avise se não atingir 10.000 até 20h"_

## Roadmap (11 Semanas)

| Fase | Duração | Entrega |
|---|---|---|
| 1 | 2 semanas | MQTT funcional entre wearable, mobile e servidor |
| 2 | 2 semanas | Ollama respondendo via Node-RED |
| 3 | 2 semanas | Fallback automático local→nuvem |
| 4 | 2 semanas | CRUD de automações via linguagem natural |
| 5 | 3 semanas | Sistema production-ready |

## Equipe Necessária

- **1 Engenheiro de ML:** Otimização de modelos, quantização
- **1 Engenheiro Backend:** Docker, MQTT, Node-RED
- **1 Engenheiro Embarcado:** Firmware ESP32, OTA
- **1 Designer de UX:** Interface TUI (Textual)

## Custo Estimado (Mensal)

| Item | Custo |
|---|---|
| **Hardware (servidor)** | R$ 3.000 (one-time) |
| **Groq API** | $0-50 (free tier generoso) |
| **OpenRouter** | $0-20 (pay-per-use) |
| **Tailscale** | $0 (free para 3 usuários) |
| **Total** | ~R$ 350/mês (após hardware) |

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| **LLM gera código buggy** | Alto | Linter estático + sandbox com limites |
| **GTX 1650 não aguenta** | Médio | Fallback automático para Groq/OpenRouter |
| **MIUI mata Termux** | Alto | Wake lock + supervisor + notificação persistente |
| **Wearable descarrega rápido** | Médio | Deep Sleep + wake-up a cada 5min |

## Próximos Passos Imediatos

1. ✅ Repositório GitHub criado: https://github.com/FRANK1-AZZA-Tekk/yby-seed
2. ⏳ Configurar ambiente Docker no Ubuntu
3. ⏳ Comprar componentes (LilyGO T-Watch S3 Plus)
4. ⏳ Configurar Termux no Xiaomi 12
5. ⏳ Implementar Fase 1 (MQTT básico)

---

**YBY SEED** - _Function Over Form_ 🚀

**Contato:** Alisson De Faria - alissonfaria4@gmail.com
