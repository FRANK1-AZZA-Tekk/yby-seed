# Contrato: porta de armazenamento

Implementações: `storage/idb.js` (principal) e `storage/ls.js` (reserva, D-4). A porta falsa dos testes cumpre o mesmo contrato com injeção de falha.

## Operações

| Operação | Entrada | Saída | Regras |
|---|---|---|---|
| `carregar()` | nenhuma | `{ rev, consent, os, audit }` | Só leitura. Valida o formato (ver [data-model](../data-model.md)). Estado inválido gera `EstadoInvalido` e impede a escrita |
| `commit(tx)` | `{ revEsperada, gravarOs?, removerOs?, removerTodas?, consent?, audit }` | `{ revNova, seq }` | Atômico. `audit` é obrigatório. Recusa se `revEsperada` diferir da guardada |
| `reler(seq, ids)` | número do registro e identificadores de OS | `{ audit, os }` | Leitura independente da transação de escrita, para comparar |

`audit` é o único acréscimo ao log. A porta não expõe `put`, `delete` nem limpeza do log (PA-1). `removerTodas` apaga só as OS.

## Garantias

1. **Tudo ou nada**: o efeito sobre OS, o consentimento e o registro de auditoria vão juntos ou nenhum vai.
2. **Sequência**: `seq` é atribuída dentro da transação como último `seq` mais 1.
3. **Revisão**: `rev` soma 1 a cada commit bem-sucedido.
4. **Releitura**: o coordenador compara o que `reler` devolve com o que pretendia gravar. Qualquer diferença gera `VerificacaoFalhou` e o app não mostra "salvo".
5. **Sem escrita antes do consentimento**: `carregar()` e a sonda não gravam. `commit` sem `consent` aceito é recusado.

## Erros tipados

| Erro | Quando | Resultado para o usuário |
|---|---|---|
| `Indisponivel` | Backend não abre | Reserva com aviso, ou parada se também indisponível |
| `CotaExcedida` | Cota cheia (`QuotaExceededError`) | Erro claro; nada é dado como salvo; registro `falha` no melhor esforço |
| `RevisaoDivergente` | `revEsperada` diferente | Erro visível; recarregar estado |
| `VerificacaoFalhou` | Releitura difere do gravado | Erro visível; nada é dado como salvo |
| `EstadoInvalido` | Formato inválido ao carregar | App não escreve; mensagem para exportar ou contatar o mantenedor |
| `ErroGravacao` | Qualquer outra falha na gravação | Erro visível; registro `falha` no melhor esforço |

## Detalhes por backend

- **IndexedDB**: uma transação `readwrite` sobre `os`, `audit` e `meta`; a sequência e a revisão são lidas e gravadas na mesma transação. A releitura é uma transação `readonly` separada.
- **Reserva**: leitura da chave, aplicação em memória, uma chamada `setItem`, depois `getItem` e comparação. Antes do `setItem`, confere o tamanho para avisar a 80% da cota estimada.
- **Sonda**: IndexedDB aberto com aborto em `onupgradeneeded` quando a versão antiga é 0 (não cria banco); reserva só com `getItem`.

## Testes do contrato (a rodar nos dois backends)

- Commit feliz grava e relê igual.
- Falha injetada no meio do commit deixa o estado anterior completo.
- Commit com revisão errada é recusado.
- Cota simulada gera `CotaExcedida` e não altera o estado.
- `removerTodas` mantém todos os registros de auditoria.
- Duas tentativas seguidas com a mesma identidade de OS geram uma OS.
