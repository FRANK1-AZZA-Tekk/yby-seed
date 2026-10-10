# 01 — Plataforma e API

## O que é

OpenRouter é um gateway/API unificada para inferência em vários modelos e provedores. O benefício arquitetural é trocar modelos e provedores por configuração, mantendo uma integração do lado do cliente. Isso não torna os modelos equivalentes: parâmetros, modalidades, limites, preços e comportamento variam.

## Conceitos que não devem ser confundidos

- **Modelo:** identificador lógico no catálogo, com modalidades e parâmetros declarados.
- **Provedor/endpoint:** infraestrutura concreta que serve aquele modelo.
- **Roteador:** política que escolhe endpoint/provedor e, opcionalmente, alternativas de modelo.
- **YBY Router:** componente local que decide se a nuvem pode ser usada, qual perfil aplica e se a saída pode ser aceita.

## Integração

A API de chat é compatível com o formato OpenAI em muitos usos. SDKs podem apontar para o endpoint OpenRouter; também é possível chamar REST diretamente. O YBY deve encapsular o acesso em um provider próprio, sem espalhar SDK ou chaves pelo firmware, aplicativo e agentes.

Cabeçalhos de atribuição podem identificar a aplicação, mas não substituem autenticação, orçamento nem auditoria local. Guardar chaves em secret manager/variáveis de ambiente do backend; nunca embutir chave OpenRouter no ESP32, T-Watch, frontend ou repositório.

## Catálogo dinâmico

Antes de configurar um modelo, consultar API/página de modelos e verificar:

- ID exato e disponibilidade.
- Modalidades de entrada e saída necessárias.
- Parâmetros suportados, incluindo tools e resposta estruturada.
- Contexto e limites de saída.
- Preço atual, endpoints/provedores disponíveis e política de dados.
- Datas/versões e eventuais variantes.

Não congelar nomes de modelos de conversas ou posts como verdade permanente. Manter IDs e políticas numa configuração versionada; registrar snapshot do catálogo/data usada no benchmark.

## Contrato interno sugerido

O provider YBY deve devolver um resultado normalizado, sem expor detalhes do SDK ao restante do sistema:

```json
{
  "ok": true,
  "provider": "openrouter",
  "model_requested": "catalog-id",
  "model_used": "returned-model-id",
  "content": null,
  "tool_calls": [],
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "cost_usd": null,
  "latency_ms": 0,
  "request_id": "opaque-id",
  "error": null
}
```

Valores não retornados pela API devem permanecer `null`, não ser inventados. Validar todas as saídas localmente.

## Fontes

- [Quickstart](https://openrouter.ai/docs/quickstart)
- [API reference](https://openrouter.ai/docs/api_reference/overview)
- [Listagem de modelos e propriedades](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)
- [Catálogo](https://openrouter.ai/models)
