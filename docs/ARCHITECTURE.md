# Arquitetura YBY SEED

> **Visão técnica completa** do sistema YBY SEED

---

## 🎯 Visão Geral

YBY SEED é um sistema de **programação em linguagem natural** (NL2Code) que transforma comandos em português em **código Python executável**.

### Princípios de Design

1. **Local-First:** Tudo roda localmente (Ollama, SQLite, Node-RED)
2. **Function Over Form:** Performance > estética
3. **Zero Trust:** Validação rigorosa de código gerado
4. **Progressive Disclosure:** Complexidade revelada gradualmente

---

## 🏗️ Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE INTERFACE                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Voice UI  │  │   Text UI   │  │   Node-RED  │         │
│  │  (Whisper)  │  │  (Textual)  │  │   (Flows)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  CAMADA DE ORQUESTRAÇÃO                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Router    │  │  Planning   │  │  Execution  │         │
│  │   Agent     │  │   Agent     │  │   Agent     │         │
│  │  (3B LLM)   │  │  (3B LLM)   │  │  (7B LLM)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE MEMÓRIA                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   SQLite    │  │   RAG       │  │   Cache     │         │
│  │   (FTS5)    │  │   (AST)     │  │   (Redis)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE INFRA                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Ollama    │  │   Docker    │  │   MQTT      │         │
│  │  (LLMs)     │  │  (Services) │  │  (Broker)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 Agentes de IA

### 1. Router Agent (3B LLM)

**Função:** Classifica intenção do usuário e roteia para agente correto.

**Modelo:** Llama 3.2 3B (Q4_K_M)

**Exemplo:**

```python
# Input: "Crie um script de backup"
# Output: {"agent": "execution", "intent": "backup_automation"}
```

**Latência:** < 100ms (100% em VRAM)

---

### 2. Planning Agent (3B LLM)

**Função:** Entrevista o usuário, coleta requisitos, gera PRD.

**Modelo:** Qwen2.5-Coder 3B (Q4_K_M)

**Modos:**

| Modo | Perguntas | Validação | Output |
|---|---|---|---|
| **Basic** | 1-2 | Automática | Script simples |
| **Junior** | 3-5 | Semi-automática | Script + docs |
| **Pro** | 10-15 | Manual (usuário aprova) | PRD + código |

**Exemplo:**

```python
# Input: "Quero um backup automático"
# Pergunta: "Qual pasta quer fazer backup?"
# Resposta: "/home/usuario/Documentos"
# Output: PRD.md com requisitos
```

**Latência:** < 500ms (100% em VRAM)

---

### 3. Execution Agent (7B LLM)

**Função:** Gera código Python baseado no PRD.

**Modelo:** Qwen2.5-Coder 7B (Q4_K_M, offloading parcial)

**Exemplo:**

```python
# Input: PRD.md (backup de PDFs)
# Output: backup_automation.py
```

**Latência:** 2-5s (offloading para RAM)

---

### 4. Validation Agent (Regras + 3B LLM)

**Função:** Valida código gerado (segurança, sintaxe, lógica).

**Checklist:**

- ✅ Sintaxe Python válida
- ✅ Sem chamadas de rede não autorizadas
- ✅ Sem acesso a arquivos sensíveis
- ✅ Tratamento de erros adequado

**Exemplo:**

```python
# Código gerado:
import os
os.system("rm -rf /")  # ❌ Bloqueado!

# Validação:
if "rm -rf" in code:
    raise SecurityError("Comando destrutivo detectado")
```

---

### 5. Learning Agent (Offline)

**Função:** Aprende com erros e feedback do usuário.

**Mecanismo:**

1. Usuário reporta erro
2. Learning Agent analisa log
3. Atualiza RAG com correção
4. Próxima geração evita mesmo erro

**Exemplo:**

```python
# Erro reportado:
"Script falhou: API key inválida"

# Aprendizado:
RAG atualiza chunk:
"Sempre valide API key antes de usar"
```

---

## 🗄️ Memória e RAG

### SQLite + FTS5

**Por que SQLite?**

- ✅ Leve (< 1MB RAM)
- ✅ Full-text search nativo (FTS5)
- ✅ Zero dependências externas
- ✅ ACID compliance

**Schema:**

```sql
-- Tabela de comandos
CREATE TABLE offline_commands (
    id INTEGER PRIMARY KEY,
    command_text TEXT,
    created_at TEXT,
    status TEXT
);

-- FTS5 para busca
CREATE VIRTUAL TABLE commands_fts USING fts5(
    command_text,
    content='offline_commands'
);
```

**Busca:**

```sql
SELECT * FROM commands_fts WHERE commands_fts MATCH 'backup';
-- Retorna comandos relacionados a backup
```

---

### AST Chunking (RAG Otimizado)

**Problema:** Chunking tradicional (por caracteres) quebra contexto semântico.

**Solução:** Chunking baseado em **Árvore de Sintaxe Abstrata (AST)**.

**Como funciona:**

1. Parse do código/documento com Tree-sitter
2. Identifica nós semânticos (funções, classes, métodos)
3. Chunk = nó completo + metadados

**Exemplo:**

```python
# Código:
def calculate_tax(income):
    if income < 1000:
        return 0
    elif income < 5000:
        return income * 0.1
    else:
        return income * 0.2

# AST Chunk:
{
    "type": "function_definition",
    "name": "calculate_tax",
    "code": "def calculate_tax(income): ...",
    "tokens": 45
}
```

**Vantagem:** Recall@5 > 70% (vs 43% com chunking tradicional)

---

## 🔄 Fluxo Completo

### Passo a Passo

1. **Usuário fala:** "Crie um script de backup"

2. **Router Agent:**
   - Classifica: `intent = "backup_automation"`
   - Roteia: `agent = "planning"`

3. **Planning Agent:**
   - Entrevista:
     - "Qual pasta quer backup?"
     - "Com que frequência?"
     - "Para onde salvar backup?"
   - Gera PRD.md

4. **Execution Agent:**
   - Lê PRD.md
   - Recupera chunks RAG (APIs de backup, compressão ZIP)
   - Gera código Python

5. **Validation Agent:**
   - Valida sintaxe
   - Checa segurança
   - Aprova/rejeita

6. **Usuário:**
   - Revisa código
   - Aprova
   - Executa

7. **Learning Agent:**
   - Monitora execução
   - Aprende com erros
   - Atualiza RAG

---

## 📊 Métricas de Performance

| Métrica | Valor | Como Medir |
|---|---|---|
| **Latência Router** | < 100ms | `time router_agent.run()` |
| **Latência Planning** | < 500ms | `time planning_agent.run()` |
| **Latência Execution** | 2-5s | `time execution_agent.run()` |
| **Precisão RAG** | > 70% Recall@5 | `rag_benchmark.evaluate()` |
| **Segurança** | 0 vulnerabilidades críticas | `security_scan.run()` |

---

## 🛡️ Segurança

### Validações

1. **Sintaxe:** `ast.parse(code)` (levanta erro se inválido)
2. **Imports:** Lista branca de módulos permitidos
3. **Chamadas de rede:** Requer aprovação explícita
4. **Acesso a arquivos:** Sandbox em `/tmp/yby_sandbox`

### Exemplo de Validação

```python
import ast

def validate_code(code):
    """Valida código Python"""
    
    # 1. Sintaxe
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Sintaxe inválida: {e}")
    
    # 2. Imports perigosos
    dangerous = ["os.system", "subprocess.call", "eval", "exec"]
    for d in dangerous:
        if d in code:
            raise SecurityError(f"Importe perigoso: {d}")
    
    # 3. Chamadas de rede
    if "requests" in code or "urllib" in code:
        print("⚠️  Código faz chamadas de rede. Aprovar?")
        if not input("[y/N]: ").lower() == "y":
            raise SecurityError("Chamada de rede rejeitada")
    
    return True
```

---

## 📚 Referências

- **Spec-Driven Development:** [SpecMine Paper](https://www.semanticscholar.org/paper/182977bff1f746ed79c185a33412214dc1fcdb7d)
- **NL2Code Survey:** [Beyond NL2Code](https://arxiv.org/abs/2606.15932)
- **Agentes:** [Agents Framework](https://github.com/aiwaves-cn/agents)
- **RAG Otimizado:** [AST Chunking](https://aclanthology.org/2025.ijcnlp-long.184/)

---

**Arquitetura YBY SEED v1.0** - _Function Over Form_ 🚀
