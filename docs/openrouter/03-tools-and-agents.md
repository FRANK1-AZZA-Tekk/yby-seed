# 03 — Ferramentas e agentes

## Tool calling não é execução

O modelo retorna uma solicitação estruturada de ferramenta. O backend YBY verifica a allowlist, autenticação, tipos, intervalos, estado atual, consentimento e necessidade de confirmação. Só então um executor controlado realiza a operação. Respostas de ferramenta são dados não confiáveis e não podem sobrescrever instruções/políticas.

## Classes de ferramenta

- **Read-only:** consulta de status, telemetria e documentos locais.
- **Proposta:** prepara uma mudança sem aplicá-la.
- **Escrita reversível:** exige validação de estado, limite e confirmação conforme política.
- **Destrutiva, financeira ou segurança-crítica:** desabilitada por padrão; exige política explícita e confirmação forte.

Não documentar ferramentas como reais até que código e schema existentes no repositório confirmem seu nome e assinatura. O benchmark de tool calling precisa apontar a versão dos contratos usados; exemplos não são interfaces implementadas.

## Avaliação

Medir: decisão de chamar/abster-se, seleção da ferramenta, correção tipada dos argumentos, schema válido, sucesso de execução mockada, conclusão da tarefa, chamadas extras, recuperação de erros, chamadas inseguras, confirmação respeitada, custo e latência.

Hard gates YBY: zero ação não autorizada, zero ferramenta fora da allowlist e zero efeito físico nos benchmarks. Testar prompt injection em resultados de ferramentas, ambiguidade, erros, timeout, retry e idempotência.

## Server tools

Ferramentas fornecidas pelo serviço podem executar pesquisa web/fetch ou outras operações no lado do servidor. Elas são distintas das ferramentas locais YBY. Revisar implicações de dados, custo, fontes, logs e disponibilidade antes de permitir. ZDR de inferência não deve ser presumido como cobertura automática de ferramentas/plugins.

## Saída estruturada

Usar schema estrito quando o endpoint/modelo suportar; ainda assim, validar localmente. Em erro de parse ou schema, não executar ação. Limitar tamanho e enumerações; preferir identificadores internos a nomes livres.

## Fontes

- [API reference e parâmetros](https://openrouter.ai/docs/api_reference/overview)
- [Server tools](https://openrouter.ai/docs/guides/features/server-tools)
- [Tool calling](https://openrouter.ai/docs/guides/features/tool-calling)
