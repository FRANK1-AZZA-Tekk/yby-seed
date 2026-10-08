# Melhores Práticas de Segurança - YBY SEED

> **Última atualização:** 2026-10-08  
> **Status:** Crítico para produção

---

## 🚨 Riscos Identificados

### 1. Execução de Código Gerado por IA

**Risco:** Código malicioso ou buggy pode:
- Acessar arquivos sensíveis do sistema
- Executar comandos shell perigosos (`rm -rf /`, `chmod 777`)
- Vazar credenciais e dados pessoais
- Causar DoS (consumo infinito de CPU/memória)

**Solução:** SandboxExecutor com isolamento [1213][1215]

```python
from src.security.sandbox_executor import SandboxExecutor

sandbox = SandboxExecutor(
    timeout=5,
    memory_limit_mb=128,
    cpu_limit=1,
    network_enabled=False
)

result = sandbox.execute(generated_code)

if not result["success"]:
    print(f"❌ Código rejeitado: {result['error']}")
```

---

### 2. Vazamento de Dados para APIs Externas

**Risco:** Enviar PRDs para OpenRouter pode vazar:
- Paths de arquivos locais (`/home/usuario/...`)
- Emails, telefones, CPF/CNPJ
- Chaves de API e tokens
- Estrutura de diretórios do projeto

**Solução:** OpenRouterSanitizer com redaction [1212][1219]

```python
from src.security.openrouter_sanitizer import OpenRouterSanitizer

sanitizer = OpenRouterSanitizer()

# Antes de enviar para OpenRouter
sanitized_prd = sanitizer.sanitize(prd_text)

# Valida antes de enviar
validation = sanitizer.validate_before_send(sanitized_prd)

if not validation["is_safe"]:
    print(f"⚠️  Dados sensíveis detectados: {validation['remaining_sensitive']}")
else:
    # Envia para OpenRouter
    response = openrouter_api.chat(sanitized_prd)
```

---

### 3. Auto-evolução sem Validação

**Risco:** Sistema pode "otimizar" para métricas erradas:
- Specification gaming (otimizar métrica, não objetivo real) [1207]
- Regressões não detectadas
- Loops infinitos de "melhoria" [1205]

**Solução:** Golden Set + Avaliador Fixo [1202][1203]

```python
from src.evaluation.golden_set import GoldenSet

golden = GoldenSet()

# Avalia agente
evaluation = golden.evaluate(agent_function, task_id="medium_01")

if evaluation["score"] < 0.8:
    print("⚠️  Agente regrediu, não aplicar melhoria")
else:
    print("✅ Agente melhorou, aplicar mudança")
```

---

### 4. Cursor Pro sem Isolamento

**Risco:** Implementação em camadas pode quebrar o projeto:
- Conflitos de merge
- Vazamento de segredos em commits
- Alterações não revisadas

**Solução:** Branch por camada + Revisão obrigatória [1209][1211]

```bash
# Camada 1: Setup
git checkout -b feature/layer-1-setup
cursor implement "setup do projeto"
git commit -m "feat: layer 1 setup"
git push origin feature/layer-1-setup
# Cria PR → Revisão humana → Merge

# Camada 2: Estrutura
git checkout -b feature/layer-2-structure
cursor implement "estrutura de arquivos"
git commit -m "feat: layer 2 structure"
git push origin feature/layer-2-structure
# Cria PR → Revisão humana → Merge
```

---

## ✅ Checklist de Segurança

### Antes de Executar Código Gerado

- [ ] Código passou por validação AST (Syntax + Imports perigosos)
- [ ] SandboxExecutor configurado com limites (timeout, memória, CPU)
- [ ] Rede desabilitada (network_enabled=False)
- [ ] Sistema de arquivos isolado (temp directory)
- [ ] Logs de execução salvos para auditoria

### Antes de Enviar para APIs Externas

- [ ] OpenRouterSanitizer aplicado
- [ ] Validação confirmou 0 dados sensíveis restantes
- [ ] Chave de API com limite de uso e expiração [1212]
- [ ] Proxy local configurado (não chamar API diretamente do client) [1219]

### Antes de Aplicar Auto-melhoria

- [ ] Golden Set rodou em todas as 15 tarefas
- [ ] Task completion rate >= 90%
- [ ] Human override rate <= 10%
- [ ] Máximo 3 iterações de melhoria (circuit breaker) [1205]
- [ ] Avaliador externo fixo validou melhoria

### Antes de Merge de Cursor Pro

- [ ] Branch isolado (feature/layer-X)
- [ ] PR criado com descrição clara
- [ ] Scan de segredos passou (gitleaks, trufflehog)
- [ ] Pelo menos 1 revisão humana aprovou
- [ ] CI/CD passou (testes, lint, type check)

---

## 📊 Métricas de Segurança

| Métrica | Alvo | Como Medir |
|---|---|---|
| **Código inseguro bloqueado** | 100% | % de códigos rejeitados pelo SandboxExecutor |
| **Dados sensíveis vazados** | 0 | Contagem de vazamentos detectados |
| **Auto-melhorias regredidas** | <5% | % de melhorias que pioram Golden Set |
| **Segredos em commits** | 0 | Scan com gitleaks/trufflehog |
| **PRs sem revisão** | 0 | % de merges sem aprovação humana |

---

## 🛡️ Ferramentas Recomendadas

### Sandbox/Isolamento

- **sandbox-executor** (PyPI, 2025) - Isolamento local [1213]
- **SafeRun** (PyPI, 2025) - AST + chroot + seccomp [1215]
- **gVisor** (produção) - Interceptação de syscalls [1224]
- **Firecracker microVMs** (produção) - Isolamento hardware [1224]

### Scan de Segredos

- **gitleaks** - Scan de repositório Git
- **trufflehog** - Scan de commits
- **Akeyless** (Cursor extension) - Scan em tempo real [1211]

### Validação de Código

- **AST parser** (Python stdlib) - Validação estática
- **bandit** - Scan de segurança Python
- **safety** - Scan de dependências vulneráveis

---

## 🆘 Incident Response

### Se Código Malicioso Escapar

1. **Isolar sistema:** Desligar containers, revogar tokens
2. **Auditar logs:** Verificar quais arquivos foram acessados
3. **Rotacionar credenciais:** Trocar todas as chaves de API
4. **Reportar:** Criar issue no GitHub com detalhes
5. **Corrigir:** Reforçar sandbox com novas regras

### Se Dados Vazarem para OpenRouter

1. **Revogar chave:** Invalidar API key no OpenRouter [1212]
2. **Criar nova chave:** Com limites mais restritos
3. **Auditar PRDs:** Verificar quais dados foram enviados
4. **Reforçar sanitização:** Adicionar novos padrões ao OpenRouterSanitizer
5. **Notificar:** Se dados pessoais vazaram, seguir LGPD

---

**Segurança é prioridade máxima no YBY SEED.** 🛡️

Nenhuma funcionalidade deve ser implementada sem passar por validação de segurança.
