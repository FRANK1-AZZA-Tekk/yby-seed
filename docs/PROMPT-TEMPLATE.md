# Modelo de pedido fechado (YBY SEED)

Preencha e cole em uma mensagem só no Grok Bot. Não peça status no meio do trabalho.

## Objetivo
- (1–3 frases: o que entregar e por quê)

## Arquivos prováveis
- (caminhos existentes; o agente não deve varrer o repositório inteiro)

## Passos
1.
2.
3.

## Testes
- Rodar `ruff` e `pytest` uma vez no fim, no ambiente do agente.
- Não vigiar o CI do GitHub. Não repetir a suíte a cada arquivo.

## Pronto quando
- [ ] (critério observável 1)
- [ ] (critério observável 2)
- [ ] PR aberto, sem merge

## Fora do escopo
- (o que não fazer; não refatorar legado; não absorver outros repositórios)

## Regras de custo
- Uma rodada só. Não explorar docs em massa: usar README, docs/DEV.md e este pedido.
- Modelo: Cursor Auto (Cost) ou Composer 2.5; sem Fast, sem janela 500k, sem modelo de terceiros.
- Não fazer merge. Ao terminar, resumir o que mudou (lista de arquivos / diff), sem despejar arquivos inteiros.
