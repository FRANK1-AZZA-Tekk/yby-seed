# Planejamento de Custos de IA — YBY SEED

> Estratégia para maximizar o crédito do OpenRouter (meta: US$ 10/mês) combinando Ollama local, modelos gratuitos, modelos econômicos e Claude Sonnet apenas para tarefas críticas.

## Princípio central

**Function over Form:** o modelo mais caro só entra quando o mais barato não resolve. O Ollama local absorve o volume; o OpenRouter fica para qualidade de fronteira sob demanda.

## Pirâmide de roteamento

| Nível | Ferramenta/Modelo | Custo | Papel no SEED |
|---|---|---|---|
| 1 — Volume | Ollama local (3–8B) | US$ 0 | Classificação de intenção, rascunhos, chat rápido, privacidade |
| 2 — Grátis | Modelos `:free` (Nemotron, Llama 3.3, Qwen3 Coder) | US$ 0 | Prototipagem, testes, tarefas secundárias |
| 3 — Econômico | Hermes 4 70B, DeepSeek V3.1, Llama 3.3 70B | US$ 0,10–0,40/M tokens | Debate do crew, pesquisa, specs, código médio |
| 4 — Premium | Claude Sonnet | US$ 2–10/M tokens | Implementação crítica, debug difícil, revisão final |

### Preços de referência (OpenRouter, out/2026)

- Hermes 4 70B: US$ 0,13/M input · US$ 0,40/M output
- DeepSeek V3.1: US$ 0,25/M input · US$ 0,95/M output
- Llama 3.3 70B: US$ 0,10/M input · US$ 0,32/M output
- Qwen3 Coder 480B: US$ 0,30/M input · US$ 1,00/M output
- Claude Sonnet: US$ 2,00/M input · US$ 10,00/M output

## Modelos gratuitos (multiplicador principal)

- O OpenRouter mantém 20+ modelos com custo zero de token (Nemotron 3 Ultra, Llama 3.3 70B, Qwen3 Coder, GPT-OSS 120B etc.).
- **Comprar US$ 10 em créditos uma única vez eleva o limite de modelos grátis de 50 para 1.000 requisições/dia — permanentemente**, mesmo após o saldo zerar.
- Usos ideais do tier gratuito: testes de prompt, protótipos de agente, classificação, resumos, embeddings.

## Prompt caching (economia de 60–80%)

- Em modelos suportados, a releitura de contexto em cache custa 0,25x–0,50x do preço normal.
- Estruturar prompts com o **prefixo estável primeiro** (system prompt, regras do crew, documentação) para maximizar cache hits.
- O OpenRouter usa roteamento sticky para preservar o cache entre requisições da mesma sessão.
- **Atenção:** BYOK desativa o caching do OpenRouter — permanecer no crédito nativo.

## Disciplina de contexto

Sessões com mais de 200K tokens de contexto respondem por ~56% do custo total em agentes de código.

- `/clear` após cada tarefa concluída.
- CLAUDE.md enxuto, com globs cirúrgicos (regras amplas são carregadas em toda sessão).
- Uma tarefa = uma sessão: três sessões de 60K tokens custam ~7x menos que uma de 400K.
- Resumir o estado do projeto em ~500 tokens ao encerrar cada sessão e abrir a próxima com esse resumo.

## Configuração LiteLLM (roteamento automático)

```yaml
model_list:
  - model_name: yby-fast        # 90% das chamadas
    litellm_params:
      model: openrouter/meta-llama/llama-3.3-70b-instruct
  - model_name: yby-smart       # tarefas médias
    litellm_params:
      model: openrouter/deepseek/deepseek-chat-v3.1
  - model_name: yby-critical    # apenas o essencial
    litellm_params:
      model: openrouter/anthropic/claude-sonnet-4.5
```

- Fallback: Hermes/DeepSeek primeiro; Sonnet apenas se falhar.
- `max_budget` diário na LiteLLM + alerta em 80% do crédito no OpenRouter.

## Compra inteligente de crédito

- Comprar US$ 10 de uma vez (nunca US$ 5): destrava o free tier de 1.000 req/dia e dilui a taxa de 5,5%.
- Recarregar em lotes de US$ 25+ quando necessário.
- Comparar provedores do mesmo modelo (Llama 3.3 70B varia de US$ 0,10 a US$ 1,00/M conforme o provedor).
- Monitorar descontos de 50–80% na página de modelos.

## Blueprint de US$ 10/mês

| Alocação | Valor | Render estimado |
|---|---|---|
| Compra inicial (destrava free tier) | US$ 10 | 1.000 req/dia grátis + crédito |
| Hermes 4 70B (crew/debate) | ~US$ 3 | ~15–20M tokens = mês inteiro de crew |
| DeepSeek V3.1 (código médio) | ~US$ 4 | ~4–5M tokens = dezenas de tarefas |
| Claude Sonnet (crítico) | ~US$ 3 | ~6–10 sessões cirúrgicas |

## Decisões de stack relacionadas

- **Cursor Pro (US$ 20/mês)**: editor principal, já inclui pool de créditos de modelos de fronteira.
- **OpenRouter (pay-per-token)**: Claude Code via OpenRouter + Hermes + modelos variados, sem assinatura fixa.
- **Claude Pro (US$ 20/mês)**: alternativa apenas se o uso intenso diário justificar cota fixa em vez de crédito flexível.
- **Não assinar os três**: estoura o orçamento de US$ 30/mês.

## Próximos passos

1. Configurar `litellm_config.yaml` com os 4 níveis, fallback e budget diário.
2. Mapear os modelos `:free` atuais por agente do crew (pesquisador, revisor, implementador).
3. Criar protocolo de sessão econômica (template de CLAUDE.md + estrutura de prompt otimizada para cache).
