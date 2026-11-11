# Segurança técnica — YBY SEED

Notas de implementação. Para reportar vulnerabilidades, use [SECURITY.md](../SECURITY.md) na raiz.

## Limitação conhecida do AST guard

O `validate_code_ast` é análise estática. Não detecta ofuscação
em runtime, como `chr()` montando string e depois `exec()`.
Para defesa em profundidade, o executor (`sandbox_executor.py`) deve
também restringir `exec`/`eval` no namespace real, não só na AST.

## Log local de uso de nuvem (`logs/cloud_usage.jsonl`)

### O que entra (metadados)

- Timestamp, provedor, modelo, finalidade (`purpose`)
- Estimativa de tokens de entrada/saída
- Resultado do evento (`cloud_requested`, `cloud_confirmed`, `cloud_completed`, etc.)

### O que NÃO entra

- Texto do prompt ou da resposta
- Conteúdo do vault ou áudio
- Chaves de API (`YBY_CLOUD_API_KEY`, `OPENROUTER_API_KEY`, etc.)

O arquivo fica fora do git (`logs/` no `.gitignore`) com permissão **0600**.
