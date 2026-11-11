# Degradação segura

Estados:

- `FULL_LOCAL`: PC local completo.
- `MOBILE_LOCAL`: celular e comandos reduzidos.
- `DETERMINISTIC_ONLY`: regras locais.
- `WATCH_SAFE_MODE`: status, vibração e confirmação.
- `LOCKED_SAFE_STATE`: diagnóstico sem ações externas.

Cada provider deve ter timeout, contador de falhas, circuit breaker, teste de saúde e fallback explícito.
