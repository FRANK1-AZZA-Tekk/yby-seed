# Arquitetura YBY SEED

> **Status:** v1.0.0  
> **Última atualização:** 2026-10-08  
> **Commit de referência:** HEAD (main)

## 🌐 Visão Geral

O **YBY SEED** opera como o **PC Hub** central dentro do ecossistema YBY (um exocórtex pessoal distribuído). Ele é o motor de inferência pesada e execução de código do sistema, projetado para capacitar não-programadores a construírem automações em linguagem natural (NL2Code). 

O fluxo arquitetural distribui a carga cognitiva em múltiplas pontas:
1. **Edge/Wearable:** LilyGO T-Watch S3 Plus (via Wi-Fi/BLE) capturando voz e intenção bruta.
2. **Mobile Node:** Smartphone processando roteamento BLE e conectividade de borda via Termux.
3. **PC Hub (YBY SEED):** Onde os agentes, modelos LLM locais (Ollama) e serviços de automação (Node-RED) residem.
4. **Cloud Fallback:** Roteamento degradado para APIs externas quando o hardware local atinge o limite.

## 🏗️ Estado Atual do Sistema

- **Agentes Específicos:** 7 agentes independentes implementados em `src/agents/` (Orchestrator, Operator, Builder, Guardian, Archivist, Researcher, Technician).
- **Skills Validadas:** 5 módulos operacionais em `skills/` gerenciados por frontmatter YAML.
- **Isolamento e Execução:** Ambiente de Sandbox nativo utilizando `subprocess.Popen` aliado a regras estritas de `rlimits` e validação AST prévia.
- **Modelos de Linguagem Local:** 
  - Modelos de 3B parâmetros executando inteiramente na VRAM (GPU).
  - Modelos de 7B parâmetros executando com offloading dinâmico na RAM.
- **Roteamento Cloud:** Integração sanitizada (via `openrouter_sanitizer.py`) para chamadas em fallback usando OpenRouter e Groq.
- **Stack de Infraestrutura:** Orquestrada via Docker Compose contendo Ollama, Node-RED, Mosquitto (MQTT), PostgreSQL e Redis.

## 📐 Decisões Arquiteturais e Design Covenants

1. **Local-First Absoluto:** O sistema deve ser integralmente funcional offline por padrão. A nuvem atua estritamente como redundância (fallback).
2. **Democratização (NL2Code):** Foco em processamento de linguagem natural em Português (PT-BR), voltado para a curva de aprendizado de não-programadores e pequenas automações industriais/residenciais.
3. **Function Over Form:** Código, documentação e estrutura de diretórios priorizam utilidade, baixa latência e facilidade de manutenção em vez de complexidade abstrata.
4. **Isolamento Leve:** O uso de `subprocess` + `rlimits` evita o overhead de levantar containers Docker individuais por skill, garantindo execução rápida com threat model assumindo um "usuário confiável".
5. **Restrição de Hardware Alvo:** A arquitetura é construída tendo como teto uma GPU de entrada (GTX 1650 4GB VRAM) e 16GB de RAM, forçando um desenvolvimento hiper-otimizado e acessível.

## 🧪 Hipóteses Operacionais em Teste

- Um modelo de 3B parâmetros alocado em 4GB VRAM entrega tempo de resposta aceitável para interações de voz em tempo real.
- O offloading de RAM para modelos 7B supre a necessidade em tarefas analíticas e geração de código não-críticas onde a latência não é o fator principal.
- A combinação Node-RED + Mosquitto MQTT oferece a espinha dorsal necessária para telemetria IoT sem adicionar complexidade desnecessária ao código Python puro.

## ⚠️ Pendências Críticas (Roadmap v1.1)

- **Cobertura de Testes:** Atualmente sem testes automatizados implementados (`tests/` necessita de mocking e testes unitários das rotas).
- **Especificação de Skills:** Documentar formalmente e fechar o contrato de dados para a estrutura de `SKILL.md`.
- **Pipeline de Voz:** A integração do Whisper para ASR local direto no PC Hub ainda precisa ser conectada ao barramento principal.
- **Telemetria BLE:** Refinar o pipeline de dados em tempo real conectando o Android (Termux) ao PC Hub.

## 🚫 Não-objetivos do MVP (Out of Scope)

- Desenvolvimento de aplicativo mobile nativo (o uso do Termux supre a necessidade no MVP).
- Execução segura de scripts complexos de terceiros não-validados.
- Fine-tuning ou treinamento de modelos (foco em RAG, Prompt Engineering e roteamento).
- UI/UX elaborada para desktop (a interface primária é CLI, logs e os fluxos no Node-RED).
- Isolamento total de rede/Filesystem na execução das automações.

## 🔗 Referências Cruzadas
- [Runtime de Execução](runtime.md)
- [Sistema de Agentes](agents.md)
- [Matriz de Modelos](models.md)
- [Diretrizes de Segurança](security.md)
- [Fluxo de Roteamento de IA](../ai/routing.md)