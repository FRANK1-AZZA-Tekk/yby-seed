# Política de orçamento — YBY SEED

## Princípio

O controle de custo usa barreiras independentes. O ledger local é a fonte operacional; a reconciliação do provedor é auditoria, não autorização para ultrapassar limite.

## Limites

- Teto mensal local: US$ 10,00.
- Teto diário local: US$ 0,35, como trava contra loops.
- Limite no provedor: configurado separadamente, em UTC.
- Ambos os limites são verificados antes de cada chamada de nuvem.
- O limite mensal prevalece sobre projeções baseadas no limite diário.

## Fusos

- Timestamps internos: UTC.
- Janela local: America/Sao_Paulo.
- Janela do provedor: UTC.
- São políticas independentes; uma não compensa a outra.

## Ciclo de chamada

1. Calcular custo estimado.
2. Verificar saldo disponível, incluindo reservas pendentes.
3. Reservar custo em transação.
4. Registrar operação como `in_flight`.
5. Chamar o provedor.
6. Atualizar para `succeeded`, `failed` ou `uncertain`.
7. Conciliar custo real quando houver identificador consultável.

## Estados

- `reserved`: orçamento reservado.
- `in_flight`: chamada enviada.
- `succeeded`: resposta recebida e custo conhecido.
- `failed`: falha antes do envio ou sem cobrança confirmada.
- `uncertain`: timeout ou falha após envio; pode ter gerado cobrança.

## Regras de retry

- `failed` antes do envio pode ser repetido.
- `uncertain` nunca é repetido automaticamente.
- Cache válido registra custo incremental zero e referência à operação original.
- Cache não é garantia de cobrança única; é otimização.
- Reconciliação não autoriza retry automático nem ultrapassar teto.

## Privacidade

- Modo offline ou privado bloqueia nuvem.
- Falha na detecção de sensibilidade bloqueia nuvem.
- Conteúdo `estritamente_local` bloqueia nuvem.
- Detecção por regex é camada adicional, não garantia.
