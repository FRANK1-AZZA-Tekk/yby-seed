# YBY SEED Skills

> **Skills** são instruções especializadas que ensinam o agente a realizar tarefas específicas.

---

## 📚 O Que É uma Skill?

Uma skill é um **diretório** contendo:

- `SKILL.md` (obrigatório) - Instruções em Markdown com YAML frontmatter
- `scripts/` (opcional) - Código executável (Python, Bash)
- `references/` (opcional) - Documentação de referência
- `assets/` (opcional) - Templates, schemas, arquivos estáticos

---

## 🎯 Estrutura de uma Skill

```
skill-name/
├── SKILL.md              # Obrigatório: metadados + instruções
├── scripts/              # Opcional: código executável
│   ├── process_data.py
│   └── validate.sh
├── references/           # Opcional: documentação
│   └── api-guide.md
└── assets/               # Opcional: templates
    └── report-template.md
```

---

## 📋 SKILL.md - Anatomia

### YAML Frontmatter (Obrigatório)

```yaml
---
name: skill-name
description: Descrição clara do que a skill faz e quando usar
compatibility: ubuntu, python-3.11+
license: MIT
---
```

### Corpo do SKILL.md (Recomendado)

```
## Quando Usar

Descreva quando esta skill deve ser ativada.

## Instruções Passo a Passo

1. Primeiro passo
2. Segundo passo
3. Terceiro passo

## Exemplos

### Exemplo 1: Uso básico

Input: ...
Output: ...

### Exemplo 2: Caso complexo

Input: ...
Output: ...

## Edge Cases

- Caso especial 1
- Caso especial 2

## Referências

- [Link para documentação](url)
- [API reference](url)
```

---

## 🛠️ Skills Oficiais

| Skill | Descrição | Complexidade |
|---|---|---|
| **[backup-automation](skills/backup-automation/)** | Backup automático de arquivos e pastas | Fácil |
| **[api-integration](skills/api-integration/)** | Integração com APIs REST | Médio |
| **[data-processing](skills/data-processing/)** | Processamento de dados (CSV, JSON, etc.) | Médio |
| **[notification-system](skills/notification-system/)** | Sistema de notificações (email, Telegram, etc.) | Médio |
| **[file-operations](skills/file-operations/)** | Operações com arquivos (ler, escrever, mover) | Fácil |

---

## 🚀 Como Usar Skills

### 1. Discovery (Automático)

O agente descobre skills disponíveis no diretório `skills/`.

### 2. Activation (Automático)

Quando o comando do usuário corresponde à `description` de uma skill, ela é ativada.

### 3. Execution (Automático)

O agente segue as instruções do `SKILL.md` para executar a tarefa.

---

## 📚 Criando Sua Própria Skill

### Passo 1: Criar Diretório

```bash
mkdir skills/minha-skill
```

### Passo 2: Criar SKILL.md

```bash
touch skills/minha-skill/SKILL.md
```

### Passo 3: Adicionar Frontmatter

```yaml
---
name: minha-skill
description: Descrição clara do que faz
---
```

### Passo 4: Adicionar Instruções

```markdown
## Quando Usar

Use esta skill quando...

## Instruções

1. ...
2. ...
```

### Passo 5: Testar

```bash
python src/skills/skill_manager.py test minha-skill
```

---

## 🔒 Segurança

- ✅ Skills são **somente leitura** por padrão
- ✅ Scripts em `scripts/` rodam em **sandbox**
- ✅ Validação de segurança antes de executar

---

## 📊 Métricas

| Métrica | Alvo |
|---|---|
| **Skills implementadas** | 10+ |
| **Skills da comunidade** | 20+ |
| **Documentação** | 100% |

---

**Contribua com suas skills!** 🚀
