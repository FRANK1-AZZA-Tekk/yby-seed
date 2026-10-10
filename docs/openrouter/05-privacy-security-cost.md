# 05 — Privacidade, segurança e custo

## Privacidade

Políticas de retenção e uso diferem por provedor. `data_collection: "deny"` e ZDR são controles de roteamento sujeitos a disponibilidade e elegibilidade; não significam que a inferência ocorre localmente. Preferências ZDR não devem ser assumidas para plugins/server tools. Se dado não pode sair do dispositivo, bloquear nuvem no Policy Engine YBY.

Aplicar minimização e sanitização local antes da chamada: remover credenciais, identificadores e campos não necessários. Nunca enviar tokens, chaves, conteúdo de memória inteiro ou telemetria contínua sem necessidade. Registrar categoria e decisão de privacidade, não o conteúdo bruto por padrão.

## Chaves e guardrails

- Segredos fora do Git, firmware e frontend; usar secret manager ou ambiente do backend.
- Chaves distintas para dev/test/prod e, se suportado, por módulo/ambiente.
- Menor privilégio e limite de gasto por chave/guardrail.
- Allowlist de modelos/provedores por finalidade.
- Rotação e revogação; alertar sobre uso anormal.
- Não considerar guardrail como substituto das verificações locais.

## Custo e limites

Estimar custo antes da chamada quando possível e impor teto duro por tarefa, dia e mês. Registrar tokens, modelo efetivo, custo retornado quando disponível, retries, cache e custo por tarefa concluída. Tratar erro de saldo/rate limit separadamente de indisponibilidade. O custo de multimodalidade/ferramentas pode não ser representado apenas pelos tokens de texto.

## Cache

Distinguir:

- **Prompt/prefix caching:** pode reduzir custo/latência de prefixos repetidos conforme provedor/modelo.
- **Response caching:** resposta completa para pedido idêntico, com regras/TTL específicas.

Não armazenar respostas sensíveis sem política de retenção, isolamento de usuário e invalidação. Cache pode servir estado desatualizado; usar apenas para tarefas idempotentes adequadas e controlar chave/TTL.

## Observabilidade

Ledger local mínimo: request_id, módulo, tarefa, categoria de sensibilidade, decisão de rota, perfil, modelo/provedor solicitado e efetivo, status, latência/TTFT, tokens, custo, cache, fallback, schema e motivo de bloqueio. Redigir conteúdo sensível. Confrontar ledger com Activity/analytics do serviço.

## Fontes

- [Provider logging](https://openrouter.ai/docs/guides/privacy/provider-logging)
- [ZDR](https://openrouter.ai/docs/guides/features/zdr)
- [Data collection](https://openrouter.ai/docs/guides/privacy/data-collection)
- [Guardrails](https://openrouter.ai/docs/guides/features/guardrails)
- [Response caching](https://openrouter.ai/docs/guides/features/response-caching)
- [Activity](https://openrouter.ai/docs/guides/features/activity)
- [Authentication](https://openrouter.ai/docs/api_reference/authentication)
- [Credits and limits](https://openrouter.ai/docs/api_reference/limits)
