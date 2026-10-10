# 06 — Plano de benchmark OpenRouter para YBY

## Objetivo

Decidir por evidência quais recursos/modelos entram no MVP comparando Ollama local e candidatos OpenRouter. Não eleger vencedor geral por ranking público: medir em tarefas YBY e por perfil.

## Grupos

- Comandos curtos/triagem.
- Automação e telemetria.
- Conhecimento/RAG.
- Código/firmware.
- Tool calling.
- Multimodalidade e server tools somente em fases posteriores.

## Protocolo

1. Fixar dataset, instruções, contexto, schema e parâmetros.
2. Usar dados sintéticos/não sensíveis; ferramentas sempre mockadas.
3. Repetir cada caso pelo menos três vezes e distinguir cache hit/miss.
4. Consultar e registrar snapshot do catálogo, preço, data, ID, parâmetros e endpoints elegíveis.
5. Comparar modelos locais e cloud com orçamento/timeout equivalentes por classe.
6. Testar falha de provedor/modelo, timeout, `429`, `5xx`, saldo e saída/schema inválidos.
7. Não acionar hardware nem ferramentas de escrita reais.

## Métricas

- Qualidade: acerto, completude, groundedness e aderência ao schema.
- Latência: TTFT e total P50/P90.
- Custo: por chamada e por tarefa concluída.
- Tool use: decisão, seleção, argumentos, execução mockada, passos, chamadas extras.
- Robustez: sucesso sob erro, fallback, circuito aberto e modo offline.
- Segurança: vazamento, ação proibida, confirmação e abstenção segura.

## Gates de aprovação

- Zero ação não autorizada e zero chamada fora da allowlist.
- Schema válido em todos os resultados aceitos para execução.
- Respeito a limite de custo e política de dados.
- Ganho mensurável em qualidade, capacidade ou latência que justifique custo e exposição.
- Fallback local/degradado comprovado.

## Manifesto de resultado

Para cada execução, guardar: case_id, data, modelo/provider efetivo, parâmetros, versão do prompt/schema, resultado, nota, TTFT/total, tokens, custo, cache, fallback e validação de segurança. Não incluir segredos ou dados pessoais.

## Decisão final por capacidade

Marcar `adotar`, `testar depois` ou `não adotar`, com motivo, responsável, data e critérios de reavaliação. Reexecutar benchmark quando o ID do modelo, preço, endpoint ou política mudar significativamente.
