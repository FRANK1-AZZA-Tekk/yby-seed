# Revisão crítica da proposta v4.0

Data: 2026-10-15
Status: recomendações para implementação; não representa código validado nem benchmark executado.

## Escopo

Este documento registra correções à proposta v4.0. Em conflito, privacidade e orçamento prevalecem. O escopo atual permanece em [MVP](MVP.md).

## Melhorias aceitas

- Banco determinístico de 30 perguntas em YAML.
- Resumos por bloco com referência aos IDs originais.
- Um modelo local de geração por vez.
- Embeddings em CPU.
- Host nativo como caminho principal.
- TTFT como métrica interativa.
- LiteLLM in-process como candidato.
- Reconciliação de custo como auditoria.

## Correções obrigatórias

### Benchmark

O benchmark deve medir TTFT, tempo total, tokens/s, pico de VRAM e camadas realmente offloaded. Deve usar stream, relógio monotônico, repetições fria e quente, timeout, erro explícito e saída JSONL. Não deve baixar modelos automaticamente. `num_gpu=99` não prova offload integral.

### LangGraph

O checkpointer deve permanecer aberto durante o ciclo de vida da aplicação. Execução deve ser serializada por `thread_id`. Cada resposta deve ser persistida antes da confirmação ao usuário. Nós com efeito colateral exigem idempotência. Thread com interrupt pendente deve exigir `/resume`.

### Idempotência e cobrança

Hash de prompt é cache, não garantia de cobrança única. Usar `operation_id`, `request_fingerprint` e `attempt_id`. Estados: `reserved`, `in_flight`, `succeeded`, `failed`, `uncertain`. Reservar orçamento em transação antes do envio. Timeout após envio permanece `uncertain` e não faz retry automático.

### Ledger e fuso

Usar UTC para timestamps e `America/Sao_Paulo` para janelas locais. Limite do provedor em UTC e limite local são políticas independentes. Reconciliação detecta desvio, mas não atribui custo individual com certeza nem autoriza ultrapassar teto.

### Memória e privacidade

Vetor e metadados exigem chave de ligação explícita, digest, dimensão e métrica. Dimensões de embedding não são intercambiáveis. Regex não prova ausência de dado sensível. Política de egress deve bloquear nuvem em modo privado, falha de política ou conteúdo restrito.

### Aprovações e arquivos

Aprovação deve ser vinculada a hash do payload, destino, revisão e validade. Alteração de conteúdo invalida aprovação. Escrita aprovada deve ser atômica e registrada com hash. `Path.resolve()` não elimina corrida por symlink.

### Backup

Não copiar apenas o arquivo SQLite com WAL ativo. Usar API de backup, incluir checkpoints e testar restauração.

## Plano incremental

- P0: benchmark e testes do Gatekeeper.
- P1: YAML da entrevista e persistência por resposta.
- P2: ledger transacional com reservas.
- P3: correção da integração LangGraph.
- P4: política de egress e testes de privacidade.

## Testes adicionais

- V4-01: concorrência não ultrapassa saldo reservado.
- V4-02: timeout faturado permanece `uncertain`.
- V4-03: cache não duplica custo nem vaza resultado entre projetos.
- V4-04: reinício após cada resposta retoma sem perda.
- V4-05: alteração de artefato invalida aprovação.
- V4-06: backup restaurado recupera app e checkpoint coerentes.
- V4-07: conteúdo privado não aparece no payload de nuvem.
- V4-08: reconexão SSE não duplica execução.
- V4-09: dimensão incompatível é rejeitada.
- V4-10: benchmark falha claramente com modelo ausente.
