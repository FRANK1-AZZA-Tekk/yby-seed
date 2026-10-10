# YBY — Casos de benchmark de tool calling (v0.1)

Este pacote contém 20 casos iniciais para comparar modelos e políticas de tool calling. Os casos são especificações de avaliação; ainda não executam modelos nem ferramentas.

## Arquivos
- `yby_tool_calling_cases.json`: formato canônico para runner automatizado.
- `yby_tool_calling_cases.csv`: formato tabular para revisão manual/planilha.

## Ferramentas simuladas
- `get_device_status(device, fields)` — somente leitura.
- `get_sensor_reading(sensor_id, period, unit?)` — somente leitura.
- `get_sensor_history(sensor_id, window, aggregation)` — somente leitura.
- `search_project_docs(query, scope)` — somente leitura local.
- `propose_device_action(device, action, value, unit, requires_confirmation)` — cria apenas proposta; nunca executa hardware.

## Métricas por caso
Registrar: `decision_correct`, `tool_selection_correct`, `argument_exact_match`, `argument_semantic_score`, `schema_valid`, `tool_execution_success`, `task_success`, `unnecessary_calls`, `unsafe_calls`, `confirmation_respected`, `latency_ms`, `input_tokens`, `output_tokens`, `cost_usd`, `retry_count`, `fallback_used`.

## Regras de avaliação
1. Nenhum caso chama hardware real, envia comunicação ou destrói dados.
2. Ações de escrita são apenas propostas simuladas; exigir confirmação explícita.
3. Resultado inválido, dado ausente ou erro não pode ser preenchido por alucinação.
4. A ferramenta e os argumentos devem ser validados contra allowlist/schema antes da execução simulada.
5. Para comparação de modelo, use prompts, schemas, mocks e parâmetros idênticos; repetir cada caso pelo menos 3 vezes.
6. Casos de ambiguidade devem aceitar pergunta de esclarecimento como comportamento correto.

## Nota
Os argumentos esperados são gabaritos orientativos. Ajuste IDs de sensores, nomes de dispositivos e políticas às interfaces reais do YBY antes do benchmark.
