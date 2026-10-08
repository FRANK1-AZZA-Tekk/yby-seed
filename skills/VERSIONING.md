# Versionamento de Skills - YBY SEED

> **Política de versionamento** baseada em [Semantic Versioning 2.0.0](https://semver.org/)

---

## 📋 Estrutura de Versão

```
MAJOR.MINOR.PATCH
   │      │     │
   │      │     └─ Backward compatible bug fixes
   │      └─────── Backward compatible new features
   └────────────── Incompatible API changes
```

### Exemplos

- `1.0.0` - Versão inicial
- `1.0.1` - Bug fix (compatível)
- `1.1.0` - Nova feature (compatível)
- `2.0.0` - Breaking change (incompatível)

---

## 📝 Metadados Obrigatórios

Todo `SKILL.md` deve ter:

```yaml
---
name: skill-name
version: 1.0.0          # Obrigatório
min_agent_version: 2.0.0  # Obrigatório
last_updated: 2026-10-08  # Obrigatório
description: ...
compatibility: ...
license: MIT
authors:
  - "Nome (@github)"
keywords:
  - keyword1
  - keyword2
changelog:
  - version: 1.0.0
    date: 2026-10-08
    changes:
      - "Descrição da mudança"
---
```

---

## 🔄 Ciclo de Vida

### 1. **Desenvolvimento** (0.x.x)

- Skills em desenvolvimento ativo
- Pode ter breaking changes
- Não recomendada para produção

### 2. **Estável** (1.x.x+)

- Skills testadas e validadas
- Breaking changes apenas em major versions
- Recomendada para produção

### 3. **Depreciada**

- Skills substituídas por versões mais novas
- Mantidas por 6 meses após depreciação
- Logs avisam sobre uso

---

## 📅 Política de Atualização

### Major Version (1.x.x → 2.0.0)

**Quando:**
- Mudanças incompatíveis com versões anteriores
- Remoção de features públicas
- Mudança de signature de funções

**Ações:**
- Atualizar `min_agent_version`
- Documentar migração em `MIGRATION.md`
- Manter versão antiga por 6 meses

### Minor Version (1.0.x → 1.1.0)

**Quando:**
- Novas features backward compatible
- Novos endpoints ou funções
- Melhorias de performance

**Ações:**
- Atualizar changelog
- Adicionar testes para novas features

### Patch Version (1.0.0 → 1.0.1)

**Quando:**
- Bug fixes backward compatible
- Correções de documentação
- Melhorias de segurança

**Ações:**
- Atualizar changelog
- Adicionar testes regressivos

---

## 🔍 Validação

### Script de Validação

```bash
# Validar todas as skills
python scripts/validate_skills.py

# Validar skill específica
python scripts/validate_skills.py skills/backup-automation
```

### Checks Automáticos

O script valida:

- ✅ Versão no formato `MAJOR.MINOR.PATCH`
- ✅ `min_agent_version` especificado
- ✅ `last_updated` no formato `YYYY-MM-DD`
- ✅ `changelog` com pelo menos uma entrada
- ✅ Versão incrementada desde último commit
- ✅ Changelog descreve mudanças

---

## 📊 Status das Skills

| Skill | Versão | Última Atualização | Status |
|---|---|---|---|
| backup-automation | 1.0.0 | 2026-10-08 | ✅ Estável |
| api-integration | 1.0.0 | 2026-10-08 | ✅ Estável |
| data-processing | 1.0.0 | 2026-10-08 | ✅ Estável |
| notification-system | 1.0.0 | 2026-10-08 | ✅ Estável |
| file-operations | 1.0.0 | 2026-10-08 | ✅ Estável |

---

## 🚀 Como Atualizar Versão

### Passo 1: Determinar Tipo de Mudança

```bash
# É breaking change?
→ MAJOR (2.0.0)

# É nova feature?
→ MINOR (1.1.0)

# É bug fix?
→ PATCH (1.0.1)
```

### Passo 2: Atualizar SKILL.md

```yaml
---
version: 1.1.0  # Incrementa versão
last_updated: 2026-10-09  # Atualiza data
changelog:
  - version: 1.1.0
    date: 2026-10-09
    changes:
      - "Nova feature: suporte a backup incremental"
```

### Passo 3: Rodar Validação

```bash
python scripts/validate_skills.py
```

### Passo 4: Commit

```bash
git add skills/backup-automation/SKILL.md
git commit -m "feat(backup): v1.1.0 - suporte a backup incremental"
```

---

## 📚 Referências

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Anthropic Agent Skills](https://github.com/anthropics/skills)
- [agentskills.io Specification](https://agentskills.io/specification)
