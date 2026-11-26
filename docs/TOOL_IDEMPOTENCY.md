# Idempotência de tools com efeito externo — YBY SEED

**Documento canônico.** Contrato que toda tool com `risk` `write`, `external` ou `privileged` deve cumprir antes de entrar no `yby agent`. Referência executável: [`src/agent_loop/idempotency.py`](../src/agent_loop/idempotency.py), coberta por [`tests/test_tool_idempotency.py`](../tests/test_tool_idempotency.py).

**Estado:** só contrato. Nenhuma tool mutável existe; o módulo **não** está ligado ao `ToolRegistry` e não muda o comportamento atual. Política de ações, D12, route, cache e orçamento ficam como estão.

## Ficha de admissão ([LAYER_ADMISSION.md](LAYER_ADMISSION.md))

| Pergunta | Resposta |
|---|---|
| Qual problema real resolve? | A aprovação é de uso único (`AuthorizedCall`), mas não impede repetir o efeito se o processo cair depois da ação e o estado for retomado |
| Qual é o menor escopo? | Este contrato + módulo puro em memória + testes offline |
| Como será validado? | `tests/test_tool_idempotency.py` e `make check` |
| O que fica fora? | Persistência do registro, integração com `ToolRegistry`, qualquer tool mutável real |
| Quem decide? | O dono do repositório |
| Quando será removida ou arquivada? | Se a primeira tool mutável adotar outro contrato aprovado, este é arquivado |

## Identificadores

- `action_id` é o id da tool na [política de ações](../config/agent-policy.yaml) (ex.: `vault_search`). Não muda.
- `operation_id` identifica **uma operação**: `sha256("v1" ␀ action_id ␀ alvo ␀ argumentos_canônicos)` em hexadecimal (64 caracteres). É o "id estável" de cada chamada com efeito.
- A versão (`v1`) entra no hash; mudar a normalização exige nova versão.

## Normalização de argumentos

- Usa os argumentos **já validados** pelo modelo pydantic da tool (`model_dump(mode="json")`).
- JSON com chaves ordenadas, separadores compactos e strings em Unicode NFC.
- Ordem de chaves não importa. Ordem de listas importa, exceto nos campos de topo que a tool declarar como `unordered` (conjuntos).
- Rejeita NaN/Infinity, chaves não textuais, chaves que colidem após NFC e tipos fora de JSON.

## Alvo

Texto explícito e não vazio do recurso afetado (caminho no vault, destinatário, URL), fornecido pela tool. Entra no hash; não é normalizado além de NFC.

## Estados e janela

| Estado | Significado | Bloqueia repetir? |
|---|---|---|
| `pending` | Registro criado antes do efeito | Sim, sempre |
| `succeeded` | Tool devolveu `Outcome("succeeded")` | Sim, dentro da janela |
| `failed` | Tool devolveu `Outcome("failed", código)` | Sim, dentro da janela |
| `unknown` | Exceção, retorno ambíguo ou queda | Sim, até resolução humana |

- Janela padrão: 24 h (`DEFAULT_WINDOW_SECONDS`). Após a janela, `succeeded`/`failed` deixam de bloquear e uma nova chamada idêntica vira nova operação, que ainda passa por aprovação.
- Após reinício, todo `pending` vira `unknown` (`recover()`).
- Só decisão humana tira uma operação de `unknown` (`resolve_unknown`).

## Regras

1. **Consulta antes de repetir:** o registro é consultado antes de qualquer execução; havendo registro que bloqueia, nada executa e o registro é devolvido (`OperationExists`).
2. **Registro do resultado:** `pending` é gravado **antes** do efeito; o resultado final só por `Outcome` explícito.
3. **Proibido inferir sucesso:** `None`, `True`, `dict`, texto ou qualquer retorno que não seja `Outcome` vira `unknown`. Exceção vira `unknown`, não `failed`.
4. **Proibido retry automático:** o efeito roda no máximo uma vez por operação, inclusive após `failed`. Nova tentativa exige nova decisão humana.
5. **Política:** tool que exige idempotência nunca é `autonomous` (a política já recusa `autonomous` fora de `risk: read`); sem entrada na política, cai em `manual`.

## Retenção e privacidade

- O registro guarda só `operation_id`, `action_id`, estado, horários e um `error_code` curto (`[a-z][a-z0-9_]*`).
- Nunca guarda argumentos, alvo em claro, saída da tool, prompts ou segredos.
- Retenção mínima: a janela; `unknown` fica até ser resolvido.

## Antes da primeira tool mutável

- Ficha de admissão própria.
- Registro persistente (fora deste contrato) com as mesmas regras, sobrevivendo a reinício.
- Integração no `ToolRegistry`: `authorize` → `operation_id` → consulta → `pending` → efeito → `Outcome`.
