# Política de custo — YBY SEED

## Objetivo

Evitar que um pedido, loop de agente ou erro de configuração consuma créditos de API sem controle.

## Regras

- Modelos locais via Ollama são preferenciais.
- Modelos na nuvem são usados apenas quando houver ganho real de qualidade, pesquisa profunda, código complexo ou contexto longo.
- Antes de chamar a nuvem, o sistema calcula uma estimativa de custo.
- O sistema possui:
  - Teto de custo por pedido.
  - Teto de custo diário.
  - Registro de custo por modelo, agente e pedido.
- Se a estimativa ultrapassar o teto por pedido ou o gasto diário restante, o sistema usa fallback local.
- O motivo da escolha — inclusive a decisão de não usar nuvem — deve ser registrado na auditoria.

## Fórmula base

`custo_estimado = soma(tokens_entrada * preco_entrada + tokens_saida * preco_saida) + custo_de_ferramentas`

## Modo economia

O modo economia deve:

- Forçar uso exclusivo de modelos locais.
- Bloquear chamadas à nuvem.
- Bloquear ferramentas que gerem custo.
- Registrar cada bloqueio como evento.

## Auditoria

Cada chamada deve registrar:

- Pedido.
- Agente.
- Modelo.
- Tokens de entrada e saída.
- Custo estimado.
- Custo real, quando disponível.
- Motivo da escolha.
- Se houve fallback local.
