# Segurança técnica — YBY SEED

Notas de implementação. Para reportar vulnerabilidades, use [SECURITY.md](../SECURITY.md) na raiz.

## Limitação conhecida do AST guard

O `validate_code_ast` é análise estática. Não detecta ofuscação
em runtime, como `chr()` montando string e depois `exec()`.
Para defesa em profundidade, o executor (`sandbox_executor.py`) deve
também restringir `exec`/`eval` no namespace real, não só na AST.

## Log / registro local de uso de nuvem

**Especificação alvo (issue #42):** [CLOUD_USAGE_SPEC.md](./CLOUD_USAGE_SPEC.md)
(SQLite registry, orçamento diário+mensal, confirmação, sanitização, migração JSONL).

### Baseline atual (JSONL)

Arquivo: `logs/cloud_usage.jsonl` (`YBY_CLOUD_LOG_PATH`), permissão **0600**.

### O que entra (metadados)

- Timestamp, provedor, modelo, finalidade (`purpose`)
- Estimativa de tokens de entrada/saída
- Resultado do evento (`cloud_requested`, `cloud_confirmed`, `cloud_completed`, etc.)

### O que NÃO entra

- Texto do prompt ou da resposta
- Conteúdo do vault ou áudio
- Chaves de API (`YBY_CLOUD_API_KEY`, `OPENROUTER_API_KEY`, etc.)

O arquivo fica fora do git (`logs/` no `.gitignore`).

### Evolução (spec)

- Store primário: SQLite local (`YBY_CLOUD_DB_PATH`, default `logs/cloud_usage.sqlite3`)
- Campos adicionais: custo estimado, status, session/task id, `prompt_hash` / refs sem segredos
- Authz: vault/refs só com `YBY_CLOUD_ALLOW_VAULT=1`; sem grant → `cloud_blocked_authz` (sem HTTP)
- Redaction (`YBY_CLOUD_SANITIZE=1`) antes do egress
- Mirror JSONL off por padrão (`YBY_CLOUD_JSONL_MIRROR=0`); retenção via `CloudUsageRegistry.prune` / `yby cloud prune`
- Relatório local: `yby cloud report` (metadados/orçamento; sem prompts)
- Modo `local_only` e offline continuam sem chamada de nuvem
- Sem fallback automático OpenRouter↔Grok (D12)
- D11 (voz local) permanece o padrão
- Exception de budget **não** bypassa authz deny nem `local_only`
