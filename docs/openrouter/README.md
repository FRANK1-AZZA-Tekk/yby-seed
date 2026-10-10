# OpenRouter no YBY SEED

Dossiê vivo para estudar, validar e decidir como usar o OpenRouter no YBY. O serviço deve ser tratado como uma camada opcional de inferência e ferramentas remotas; política, autorização, memória privada, validação e execução permanecem sob controle local do YBY.

## Princípios YBY

- Local-first para memória privada, classificação de sensibilidade, políticas e execução de ações.
- Nuvem apenas quando houver benefício medido e permitido por consentimento/política.
- Nenhum modelo executa diretamente ações de hardware, destrutivas ou financeiras.
- Modelos, preços, capacidades e limites são dinâmicos: consultar o catálogo antes de cada benchmark/release.
- Cada decisão de rota, incluindo bloqueios e bypass local, deve ser auditável localmente.

## Trilha do dossiê

1. [Plataforma e API](01-platform-and-api.md)
2. [Roteamento e resiliência](02-routing-and-resilience.md)
3. [Ferramentas e agentes](03-tools-and-agents.md)
4. [Multimodalidade e RAG](04-multimodal-and-rag.md)
5. [Privacidade, segurança e custo](05-privacy-security-cost.md)
6. [Plano de benchmark YBY](06-yby-benchmark-plan.md)

## Status de validação

| Tema | Status | Próxima evidência necessária |
|---|---|---|
| API e catálogo | Em estudo | Smoke test com IDs obtidos do catálogo ao vivo |
| Roteamento/fallback | Em estudo | Testes simulados de provedor, modelo, timeout e custo |
| Tool calling | Não validado no YBY | Contratos reais de ferramentas e runner mockado |
| Multimodalidade/RAG | Não validado no YBY | Casos controlados e comparação com alternativas locais |
| Privacidade/guardrails | A validar na conta | Revisão das configurações e políticas de cada endpoint |
| Custos/observabilidade | A validar | Conciliação do ledger local com Activity/usage |

## Fontes oficiais para manter atualizadas

- [Documentação OpenRouter](https://openrouter.ai/docs)
- [Catálogo de modelos](https://openrouter.ai/models)
- [API de listagem de modelos](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)
- [Roteamento de provedores](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Fallbacks de modelos](https://openrouter.ai/docs/guides/routing/model-fallbacks)
- [Privacidade e retenção por provedor](https://openrouter.ai/docs/guides/privacy/provider-logging)
- [ZDR](https://openrouter.ai/docs/guides/features/zdr)

## Como atualizar

Ao testar um recurso, registrar data, endpoint/API, modelo e provedor efetivos, parâmetros, modalidade, custo, latência, resultados, limitações e decisão (`adotar`, `testar depois`, `não adotar`). Não registrar segredos, prompts privados ou dados pessoais nos documentos do repositório.
