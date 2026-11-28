# Contrato: comandos do usuário

Cada comando passa pela fila única do coordenador, é decidido por `domain.js` e deixa exatamente um registro por tentativa (PA-3). Detalhes de registro em [audit-log.md](audit-log.md).

## Comandos

| Comando | Entrada | Confirmação (S1) | Pré-condição | Efeito em sucesso |
|---|---|---|---|---|
| `consentir` | aceite | Única, antes de qualquer gravação (D-2) | Sem consentimento prévio | Grava consentimento, backend e registro `consentir` |
| `criar` | `id` (da intenção), título, cliente, local, telefone, observações, itens | Não | `id` inexistente; dados válidos | Cria OS `aberta` |
| `definirItem` | `osId`, `itemId`, `marcado` | Não | OS `aberta`; item existente | Define o estado do item |
| `concluir` | `osId` | Alerta com pendentes se houver itens desmarcados (D-5) | OS `aberta` | `concluida` ou `concluida_pendencias` |
| `reabrir` | `osId` | Não | OS concluída | `aberta` |
| `removerOs` | `osId` | Por ação, com título e número de itens (D-7) | OS existente | Remove a OS |
| `removerTudo` | nenhuma | Por ação, com número de OS e itens | Existe ao menos uma OS | Remove todas as OS; o log permanece |
| `exportar` | nenhuma | Por ação, com número de OS e itens (D-1) | Existe ao menos uma OS | Entrega o JSON ao navegador depois do registro |

## Resultado de cada tentativa

| Situação | `tipo` do registro | `motivo` | Efeito |
|---|---|---|---|
| Comando válido e aplicado | `execucao` | nulo | Sim |
| Comando já satisfeito (repetição) | `sem_efeito` | `ja_marcado`, `ja_desmarcado`, `ja_concluida`, `ja_aberta`, `os_ja_existe`, `os_inexistente`, `sem_os` | Nenhum |
| Usuário cancelou a confirmação | `recusa` | `usuario_cancelou` | Nenhum |
| Comando incompatível com o estado | `recusa` | `estado_invalido` | Nenhum |
| Falha técnica na gravação | `falha` | `erro_gravacao`, `cota_excedida`, `verificacao_falhou`, `revisao_divergente` | Nenhum |

Exceção: a recusa do consentimento inicial não gera registro (nada pode ser gravado antes do aceite).

## Estados que a UI mostra

| Estado | Quando | Regra |
|---|---|---|
| `salvando` | Do toque até a releitura | Controles do item desabilitados; novo toque não vira tentativa |
| `salvo` | Só depois de commit e releitura iguais | Nunca antes |
| `erro` | Qualquer erro tipado | Mensagem clara e sem dado sensível; estado anterior preservado |

## Casos de borda cobertos pelos comandos

- Duplo toque em criar: uma OS; o segundo toque, se virar tentativa, é `sem_efeito` com `os_ja_existe`.
- Marcar o mesmo item várias vezes: estado igual; repetições são `sem_efeito`.
- Concluir duas vezes: instante de conclusão da primeira é mantido.
- Remover OS já removida: `sem_efeito` com `os_inexistente`.
- Remover tudo sem OS: `sem_efeito` com `sem_os`.
- Recarregar durante criar: zero ou uma OS.
- Segunda aba: bloqueada, sem comandos de escrita (D-3).
- Importação: não existe comando (D-6).
