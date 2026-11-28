# Contrato: log de auditoria

Cobre FR-009 e FR-011, as regras S2 e S4 e as premissas PA-1, PA-2 e PA-3 do [plano](../plan.md).

## Premissas

- **PA-1 (somente acréscimo)**: nenhum comando, inclusive `remover_tudo`, altera ou apaga registros existentes. A porta expõe apenas `append` para o log.
- **PA-2 (recusa com tipo próprio)**: toda recusa tem `tipo = "recusa"` e `motivo`. Nunca é gravada como `execucao`, `sem_efeito` nem `falha`.
- **PA-3 (unidade = tentativa)**: cada tentativa que chega ao domínio gera exatamente um registro. A mesma intenção repetida gera um registro por tentativa.

## Esquema (fechado)

| Campo | Tipo | Obrigatório | Valores ou regra |
|---|---|---|---|
| `seq` | inteiro | sim | Atribuído pela porta; começa em 1; contínuo; nunca reutilizado |
| `ts` | texto | sim | Instante UTC ISO 8601 com milissegundos |
| `tentativa` | texto | sim | UUID gerado no toque que passou pela fila |
| `acao` | enumeração | sim | `consentir`, `criar`, `marcar`, `desmarcar`, `concluir`, `reabrir`, `remover_os`, `remover_tudo`, `exportar` |
| `tipo` | enumeração | sim | `execucao`, `sem_efeito`, `recusa`, `falha` |
| `categoria` | enumeração | sim | `consentimento`, `dados_os`, `exportacao` |
| `osId` | texto ou nulo | sim | UUID da OS; nulo em `consentir`, `remover_tudo`, `exportar` |
| `itemId` | texto ou nulo | sim | Só em `marcar` e `desmarcar` |
| `pendentes` | lista de identificadores de item | não | Só em `concluir` com pendências; nunca texto de item |
| `contagem` | inteiro ou nulo | não | Número de OS em `remover_tudo` e `exportar` |
| `motivo` | enumeração ou nulo | sim | Obrigatório em `recusa`, `sem_efeito` e `falha`; nulo em `execucao` |
| `versaoApp` | texto | sim | Versão do app |

Enumeração de `motivo`:
- `recusa`: `usuario_cancelou`, `estado_invalido`.
- `sem_efeito`: `ja_marcado`, `ja_desmarcado`, `ja_concluida`, `ja_aberta`, `os_ja_existe`, `os_inexistente`, `sem_os`.
- `falha`: `erro_gravacao`, `cota_excedida`, `verificacao_falhou`, `revisao_divergente`.

Chaves fora do esquema são rejeitadas por `audit.js`. Texto livre não é aceito em nenhum campo.

## Invariantes

1. **Efeito com registro**: `execucao` só existe se o efeito foi gravado na mesma transação. Sem registro, sem efeito.
2. **Falha de registro bloqueia**: se o registro não grava, o efeito é cancelado e o usuário vê o erro.
3. **Sequência contínua**: `seq` de 1 a N sem buracos. Na reserva, a verificação ao carregar confere a continuidade.
4. **Remoção em massa preserva o log**: após `remover_tudo`, o log contém todos os registros anteriores mais o do próprio `remover_tudo`.
5. **Sem dado sensível**: nenhum título, cliente, local, telefone, observação ou texto de item aparece em qualquer campo (S4).
6. **Registro `falha`**: gravado em transação própria só de auditoria, no melhor esforço. Se também falhar, o usuário vê o erro e nada é gravado.
7. **Exceção declarada**: a recusa do consentimento inicial não é gravada (D-2 e SC-006).

## Exemplos

```json
{ "seq": 12, "ts": "2026-11-28T10:15:03.120Z", "tentativa": "5b0f0c9a-...", "acao": "concluir", "tipo": "execucao", "categoria": "dados_os", "osId": "a1d3...", "itemId": null, "pendentes": ["a1d3...:4", "a1d3...:7"], "contagem": null, "motivo": null, "versaoApp": "1" }
```

```json
{ "seq": 13, "ts": "2026-11-28T10:15:41.007Z", "tentativa": "c77e...", "acao": "remover_tudo", "tipo": "recusa", "categoria": "dados_os", "osId": null, "itemId": null, "contagem": 8, "motivo": "usuario_cancelou", "versaoApp": "1" }
```

```json
{ "seq": 14, "ts": "2026-11-28T10:16:09.554Z", "tentativa": "02ac...", "acao": "marcar", "tipo": "sem_efeito", "categoria": "dados_os", "osId": "a1d3...", "itemId": "a1d3...:2", "contagem": null, "motivo": "ja_marcado", "versaoApp": "1" }
```

## Como validar

- Teste de lógica: conjunto de entradas com texto sensível conhecido; nenhum campo do registro contém esses textos.
- Teste de lógica: `remover_tudo` mantém todos os registros anteriores.
- Teste de lógica: cada tentativa, inclusive repetida, produz um registro.
- Roteiro em aparelho: contar tentativas executadas e comparar com a contagem da tela de auditoria.
