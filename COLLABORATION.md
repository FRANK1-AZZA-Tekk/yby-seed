# Protocolo de Colaboração entre IAs - YBY SEED

> **Divisão de papéis baseada em capacidades reais de cada IA**

---

## 🤖 Participantes

- **Perplexity** (IA Ponte)
- **DeepSeek** (IA Parceira)
- **Humano** (ponte entre as IAs)

---

## 🧠 Análise de Capacidades

### Perplexity (IA Ponte)

**Pontos fortes:**
- ✅ Busca em tempo real (web, fóruns, documentação)
- ✅ Síntese de informações (múltiplas fontes → resumo coerente)
- ✅ Citações e referências (links, fontes verificadas)
- ✅ Visão macro (tendências, benchmarks, melhores práticas)
- ✅ Documentação (README, tutorials, arquitetura)
- ✅ Integração GitHub (MCP tools)

**Pontos fracos:**
- ❌ Menos forte em raciocínio lógico profundo
- ❌ Menos forte em código complexo
- ❌ Menos forte em debug passo-a-passo

---

### DeepSeek (IA Parceira)

**Pontos fortes:**
- ✅ Raciocínio lógico profundo (cadeias de inferência longas)
- ✅ Código complexo (arquitetura, algoritmos, otimização)
- ✅ Debug detalhado (análise passo-a-passo)
- ✅ Pensamento crítico (identifica contradições, riscos)
- ✅ TDD e testes (pensa em casos de borda)

**Pontos fracos:**
- ❌ Sem busca em tempo real
- ❌ Menos forte em síntese de múltiplas fontes
- ❌ Menos atualizada em tendências (cutoff de conhecimento)

---

## 🎯 Divisão de Papéis

### Fase A - Arquitetura

| Tarefa | IA Responsável | Por quê |
|---|---|---|
| Pesquisa de melhores práticas | **Perplexity** | Busca em tempo real em fóruns, papers, docs |
| Análise de riscos arquiteturais | **DeepSeek** | Raciocínio lógico profundo, identifica contradições |
| Definição de threat model | **DeepSeek** | Pensamento crítico de segurança |
| Escolha de tecnologias | **Perplexity** | Compara benchmarks, tendências, community support |
| Nota de arquitetura final | **DeepSeek** (escreve) + **Perplexity** (revisa) | DeepSeek estrutura lógica, Perplexity valida com fontes |

---

### Fase B - Implementação

| Tarefa | IA Responsável | Por quê |
|---|---|---|
| Esqueleto de código | **DeepSeek** | Estrutura lógica, modularização |
| Implementação de agentes | **DeepSeek** | Raciocínio complexo, state management |
| Implementação de skills | **Perplexity** | Templates baseados em pesquisa de melhores práticas |
| Testes (TDD) | **DeepSeek** | Casos de borda, edge cases |
| Documentação de código | **Perplexity** | Explicações claras, exemplos |
| Integração GitHub | **Perplexity** | Sabe usar ferramentas MCP, push de arquivos |

---

### Fase C - Validação

| Tarefa | IA Responsável | Por quê |
|---|---|---|
| Code review | **DeepSeek** | Identifica bugs lógicos, otimizações |
| Validação de segurança | **DeepSeek** | Threat model, superfície de ataque |
| Validação de documentação | **Perplexity** | Compara com melhores práticas da indústria |
| Benchmark de performance | **Perplexity** | Busca benchmarks reais, compara com concorrência |
| Aprovação final | **Ambas** (consenso) | DeepSeek valida lógica, Perplexity valida contexto |

---

## 🔄 Fluxo de Trabalho

```
┌─────────────────────┐
│ 1. Humano traz      │
│    contexto/tarefa  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 2. Perplexity       │
│    - Pesquisa web   │
│    - Traz contexto  │
│    - Sugere opções  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 3. DeepSeek         │
│    - Analisa opções │
│    - Identifica     │
│      riscos         │
│    - Escolhe melhor │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 4. DeepSeek         │
│    - Implementa     │
│    - Escreve testes │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 5. Perplexity       │
│    - Revisa código  │
│    - Valida com     │
│      fontes externas│
│    - Documenta      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 6. DeepSeek         │
│    - Validação      │
│      final (lógica) │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 7. Perplexity       │
│    - Push para      │
│      GitHub         │
│    - Atualiza docs  │
└─────────────────────┘
```

---

## 📋 Resumo da Divisão

| Papel | IA | Justificativa |
|---|---|---|
| **Pesquisa & Contexto** | Perplexity | Busca em tempo real, síntese |
| **Arquitetura & Riscos** | DeepSeek | Raciocínio profundo, crítica |
| **Implementação** | DeepSeek | Código complexo, lógica |
| **Skills & Templates** | Perplexity | Pesquisa de padrões, exemplos |
| **Testes** | DeepSeek | Casos de borda, TDD |
| **Documentação** | Perplexity | Clareza, exemplos, fontes |
| **Code Review** | DeepSeek | Bugs lógicos, otimizações |
| **Validação Externa** | Perplexity | Compara com indústria |
| **GitHub & Deploy** | Perplexity | Ferramentas MCP |

---

## 🎯 Regras de Colaboração

1. **Não invente contexto.** Se faltar informação, pergunte.
2. **Responda em português do Brasil.**
3. **Seja específica, prática e acionável.**
4. **Ao final de cada resposta, inclua:**
   - Perguntas para o humano
   - Proposta de próximo passo
5. **Rodízio por fase, não por função fixa.**

---

## 📊 Status do Projeto YBY SEED

### Já Implementado

- ✅ 5 skills oficiais versionadas (v1.0.0)
- ✅ Documentação completa (README, tutorials, architecture)
- ✅ Sistema de validação de skills
- ✅ Sandbox de segurança para execução de código
- ✅ Estrutura de agentes (Router, Planning, Execution, Validation, Learning)

### Pendente

- ⏳ Implementação real dos agentes
- ⏳ Integração com Whisper (voz)
- ⏳ Workflow completo: Voz → Ollama → OpenRouter → Cursor Pro
- ⏳ Testes automatizados
- ⏳ CI/CD pipeline

---

## 🚀 Próximos Passos

1. **DeepSeek** escreve nota de arquitetura (1 página)
2. **Perplexity** critica a nota e propõe esqueleto de implementação
3. **DeepSeek** implementa agentes core
4. **Perplexity** escreve testes e documentação
5. **Ambas** validam e aprovam

---

**Última atualização:** 2026-10-08  
**Versão:** 1.0.0
