# 02 — Roteamento e resiliência

## Camadas de decisão

1. Policy Engine local classifica sensibilidade, consentimento, criticidade e custo máximo.
2. Regras determinísticas resolvem ações simples sem LLM.
3. Ollama/local atende dados proibidos para nuvem, modo offline e tarefas onde seja suficiente.
4. OpenRouter é chamado somente se permitido e justificado.
5. YBY valida schema, limites, evidências e permissões antes de usar a saída.

O modelo de decisão pode recomendar uma rota; não pode conceder consentimento nem alterar política.

## Roteamento de provedores

Documentação OpenRouter expõe preferências como ordenação por preço, throughput ou latência, ordem/allowlist/denylist de provedores e requisitos de compatibilidade. Tratar métricas de desempenho como preferência, não SLA: uma preferência de latência/throughput não é garantia de latência máxima ou taxa mínima.

`max_price` é uma barreira de preço para a rota elegível; confirmar o schema e unidades na documentação atual antes de configurar. Se nenhuma rota cumprir as restrições, falhar fechado ou usar rota local, nunca remover limites silenciosamente.

## Fallback em três níveis

- **Nível 1 — provedor:** outro endpoint para o modelo solicitado, respeitando privacidade, parâmetros e preço.
- **Nível 2 — modelo:** lista explícita de modelos funcionalmente equivalentes, ordenada por perfil e submetida às mesmas restrições.
- **Nível 3 — local/degradado:** Ollama; se indisponível, mensagem/ação determinística segura e fila quando aplicável.

Não considerar qualquer resposta de fallback aceitável automaticamente: validar formato, capacidade, privacidade e qualidade mínima. Gravar modelo/provedor efetivos.

## Timeouts e streaming

Separar timeout de conexão, primeiro token (TTFT), intervalo entre chunks e duração total. Calibrar por classe de tarefa com medições P50/P90; cancelar geração quando o cliente abandona a solicitação. Para voz, otimizar TTFT/resposta curta; para relatórios, permitir duração total maior. Não usar um timeout global de poucos segundos para todos os casos.

## Erros e circuit breaker

Classificar pelo menos: autenticação/configuração, saldo/limite, rate limit, indisponibilidade, timeout, parâmetros incompatíveis, schema inválido e moderação. Retries limitados, backoff com jitter e respeito a `Retry-After` quando fornecido. Circuit breaker por perfil/provedor; não repetir erro permanente. Para ações, usar idempotency key e impedir execução duplicada.

## Fontes

- [Provider selection](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Model fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks)
- [Streaming](https://openrouter.ai/docs/api_reference/streaming)
- [Rate limits e créditos](https://openrouter.ai/docs/api_reference/limits)
