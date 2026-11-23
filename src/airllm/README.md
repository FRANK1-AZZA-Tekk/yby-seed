# Parser de JSON do AirLLM

Módulo do YBY SEED que contorna a falta de `response_format` no AirLLM,
extraindo e validando JSON de saídas em texto livre.

## Uso

```python
from src.airllm.parser import parse_json

schema = {"required": ["resumo", "entidades"]}
resultado = parse_json(saida_airllm, schema=schema, retry_fn=chamar_modelo_novamente)
```

## Limitações

- O AirLLM não suporta `response_format` (json_object/json_schema) — retorna 400.
- O parser extrai JSON de texto livre, markdown ou blocos balanceados.
- Use `retry_fn` para pedir ao modelo que corrija a saída em caso de falha.
- Valide sempre o schema antes de gravar no Mem0/Supabase.
