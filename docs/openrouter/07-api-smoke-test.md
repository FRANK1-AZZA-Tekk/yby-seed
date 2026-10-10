# Procedimento de smoke test da API OpenRouter

## Objetivo e limites

Validar conectividade, autenticação, catálogo e uma conclusão sintética de baixo custo. Rodar somente com chave de teste guardada em secret manager/variável de ambiente no backend local. Não passar chave em conversa, código-fonte, logs, firmware, frontend ou repositório. Usar payload sintético; não incluir dados pessoais, RAG privado, imagem, áudio, ferramentas ou ação de dispositivo.

## Etapa 0 — Pré-requisitos

- Criar chave de teste com limite de gasto baixo.
- Usar ambiente local protegido; configurar `OPENROUTER_API_KEY` fora do repositório.
- Confirmar que cobrança e limites estão entendidos.
- Registrar data, versão do cliente e ID escolhido.

Se não houver chave disponibilizada com segurança, executar apenas o GET público do catálogo, sem alegar validação de autenticação ou geração.

## Etapa 1 — Catálogo público

```bash
curl --fail-with-body --silent --show-error \\
  https://openrouter.ai/api/v1/models \\
  -o /tmp/openrouter-models.json
```

Validar status HTTP, JSON e presença de lista `data`. Selecionar um ID real do catálogo que aceite chat e os parâmetros usados no smoke test. Não confiar em IDs copiados de documentação antiga.

## Etapa 2 — Verificação da chave

O endpoint de chave retorna estado/limites associados à chave autenticada, conforme documentação vigente. Consultar somente de um ambiente seguro; filtrar/redigir a saída e não armazenar o bearer token.

```bash
curl --fail-with-body --silent --show-error \\
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \\
  https://openrouter.ai/api/v1/key
```

Não usar a chave de produção para o smoke test. Não imprimir chave ou headers nos logs.

## Etapa 3 — Geração mínima

Primeiro consultar preço e capacidade do modelo. Configurar `max_tokens` baixo e, quando suportado, `provider.max_price`. Fazer uma única requisição sintética sem tools.

```bash
curl --fail-with-body --silent --show-error \\
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \\
  -H "Content-Type: application/json" \\
  -H "HTTP-Referer: https://yby.local" \\
  -H "X-OpenRouter-Title: YBY-API-Smoke-Test" \\
  https://openrouter.ai/api/v1/chat/completions \\
  -d '{
    "model": "REPLACE_WITH_VERIFIED_MODEL_ID",
    "messages": [{"role":"user","content":"Responda somente: YBY-API-OK"}],
    "max_tokens": 12,
    "temperature": 0,
    "stream": false
  }'
```

O placeholder de modelo deve ser substituído por um ID verificado no catálogo. Não executar o exemplo sem configurar uma chave de teste e confirmar preço/limite.

## Etapa 4 — Critérios de sucesso

- HTTP 2xx e corpo JSON parseável.
- `choices[0].message` presente e conteúdo não vazio.
- Campo de modelo efetivamente usado registrado.
- Uso/tokens e custo registrados quando retornados; campos ausentes ficam `null`.
- Latência medida no cliente.
- Nenhum segredo ou payload privado nos logs.

## Tratamento de falhas

- `401/403`: verificar chave, escopo e status; não repetir em loop.
- `402`: parar; verificar saldo e limite da chave antes de qualquer nova tentativa.
- `429`: respeitar `Retry-After` se enviado, reduzir frequência; não fazer retry imediato em loop.
- `5xx`/timeout: registrar request id/status; uma repetição controlada no máximo para o smoke test.
- `400`: revisar ID, parâmetros e formato; não remover restrições de privacidade/custo para “fazer passar”.

## Registro do resultado

Registrar apenas: data/hora, endpoint, status HTTP, modelo pedido/efetivo, latência, tokens, custo, request id e resultado pass/fail. Não registrar prompt completo, chave, bearer header ou dados pessoais.

## Validação em camadas

Um GET público bem-sucedido valida apenas acesso ao catálogo público. Só o `GET /key` valida a autenticação da chave; só uma conclusão com credencial valida o caminho de inferência e cobrança. Não afirmar que tool calling, multimodalidade, ZDR ou fallbacks foram testados pelo smoke test básico.
