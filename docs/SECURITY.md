# Segurança técnica — YBY SEED

Notas de implementação. Para reportar vulnerabilidades, use [SECURITY.md](../SECURITY.md) na raiz.

## Limitação conhecida do AST guard

O `validate_code_ast` é análise estática. Não detecta ofuscação
em runtime, como `chr()` montando string e depois `exec()`.
Para defesa em profundidade, o executor (`sandbox.py`) deve
também restringir `exec`/`eval` no namespace real, não só na AST.
