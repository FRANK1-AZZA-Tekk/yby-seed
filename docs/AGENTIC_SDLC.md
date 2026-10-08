# Agentic SDLC (Ciclo de Vida Orientado a Agentes)

> **Status:** v1.1.0
> **Última atualização:** 2026-10-08
> **Agentes:** 5 especializados + 3 modos operacionais

## 🧠 Os 5 Agentes do YBY SEED

O YBY SEED não é um monólito — é um **enxame de 5 agentes especializados**:

```
[Planning Agent] → [Execution Agent] → [Validation Agent]
       ↓                  ↓                    ↓
[Governance Agent] ← [Learning Agent] ← [Feedback]
```

---

## 1. Planning Agent (Analista / Entrevistador)

### **Responsabilidade:**
- Coletar requisitos via conversa em linguagem natural
- Fazer perguntas de clarificação (modo Junior/Pro)
- Gerar PRD (Documento de Requisitos de Produto)

### **Modelo:**
- **Llama 3.2 3B** (Q4_K_M, 100% VRAM, 28-100 t/s)
- **Gemma 3 4B** (alternativa)

### **3 Modos de Entrevista:**

| Modo | Duração | Profundidade | Validação |
|------|---------|--------------|------------|
| **Basic** | <1 min | Superficial | Pós-execução |
| **Junior** | 5-15 min | Progressiva | Resumo antes de codar |
| **Pro** | 15-30 min | Exaustiva | PRD obrigatório |

### **Exemplo de Código:**

```python
from src.agents.planning_agent import PlanningAgent

agent = PlanningAgent(model="llama3.2:3b")

# Modo Basic: resposta direta
result = agent.interview("Crie um backup dos meus PDFs", mode="basic")
# → {"intent": "backup_automation", "slots": {...}}

# Modo Junior: entrevista progressiva
result = agent.interview("Quero automatizar meu CRM", mode="junior")
# → Perguntas: "Qual CRM?", "O que automatizar?", "Qual gatilho?"

# Modo Pro: PRD completo
result = agent.interview("Sistema de gestão de estoque", mode="pro")
# → PRD.md com 10+ seções (requisitos, fluxos, exceções)
```

---

## 2. Execution Agent (Desenvolvedor)

### **Responsabilidade:**
- Receber PRD + contexto RAG
- Gerar código Python executável
- Preencher templates de skills

### **Modelo:**
- **Qwen2.5 7B** (Q4_K_M, offloading RAM, 21-62 t/s)
- **Olmo Hybrid 7B** (alternativa, 49% menos tokens)

### **Exemplo de Código:**

```python
from src.agents.execution_agent import ExecutionAgent

agent = ExecutionAgent(model="qwen2.5:7b")

code = agent.generate(
    prd=result.prd,
    context=rag_chunks,
    skill_template="backup-automation"
)
# → Código Python completo com imports, funções, main
```

---

## 3. Validation Agent (Revisor de Qualidade)

### **Responsabilidade:**
- Validar código gerado contra PRD
- Testar casos de borda
- Sugerir melhorias

### **Implementação:**
- **AST validation** (validação sintática)
- **Pattern matching** (regras determinísticas)
- **LLM critique** (Qwen2.5 3B revisa código)

### **Exemplo de Código:**

```python
from src.agents.validation_agent import ValidationAgent

agent = ValidationAgent()

is_valid, errors = agent.validate(
    code=generated_code,
    prd=result.prd
)
# → (True, []) ou (False, ["Erro: função main não encontrada"])
```

---

## 4. Governance Agent (Guardião de Permissões)

### **Responsabilidade:**
- Bloquear código perigoso (rm -rf, DROP TABLE, etc.)
- Validar permissões de API/DB
- Exigir aprovação humana para ações críticas

### **Regras Determinísticas:**

```python
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",          # Delete raiz
    r"DROP\s+TABLE\s+",       # Delete DB
    r"os\.system\s*\(",      # Shell command
    r"subprocess\..*shell\s*=\s*True",  # Shell injection
]
```

### **Exemplo de Código:**

```python
from src.agents.governance_agent import GovernanceAgent

agent = GovernanceAgent()

is_allowed, reason = agent.check(
    code=generated_code,
    action="execute"
)
# → (True, "Aprovado") ou (False, "Código perigoso detectado")
```

---

## 5. Learning Agent (Otimização Contínua)

### **Responsabilidade:**
- Armazenar execuções em PostgreSQL
- Aprender com feedback do usuário
- Sugerir melhorias no sistema

### **Implementação:**
- **PostgreSQL + pgvector** (embeddings de execuções)
- **Bayesian Teaching** (atualização de crenças)

### **Exemplo de Código:**

```python
from src.agents.learning_agent import LearningAgent

agent = LearningAgent()

agent.log_execution(
    intent="backup_automation",
    code=generated_code,
    result=execution_result,
    user_feedback="success"
)

# Aprende com erro:
agent.learn_from_mistake(
    error="Timeout após 30s",
    fix="Aumentar timeout para 60s"
)
```

---

## 🔄 Fluxo Completo por Modo

### **Modo Basic:**

```
Usuário → Planning (superficial) → Execution → Validation (pós) → Execute
```

### **Modo Junior:**

```
Usuário → Planning (5-15 min) → PRD → Execution → Validation (antes) → Governance → Execute
```

### **Modo Pro:**

```
Usuário → Planning (15-30 min) → PRD.md → Validation (PRD) → Execution → Validation (código) → Governance → Execute
```

---

## 📊 Matriz de Agentes

| Agente | Modelo | Latência | Função |
|--------|--------|----------|--------|
| **Planning** | Llama 3.2 3B | <500ms | Entrevista + PRD |
| **Execution** | Qwen2.5 7B | 1-5s | Geração de código |
| **Validation** | AST + 3B | <200ms | Revisão |
| **Governance** | Regras + 3B | <100ms | Segurança |
| **Learning** | PostgreSQL | <50ms | Memória |

---

## 🔗 Referências

- [Agentic SDLC Paper](https://arxiv.org/abs/2401.08779)
- [Bayesian Teaching (Google)](https://research.google/pubs/bayesian-teaching/)
- [PRD Template (GitHub Spark)](https://github.blog/2024-03-15-github-spark-prompt-to-app/)
