---
name: "yby-os-checklist"
description: "Guia a implementação em camadas da especificação de ordens de serviço com checklist offline (FR-001 a FR-014, decisões D-1 a D-7) em conformidade com a constituição 1.1.0 do YBY SEED."
compatibility: "YBY SEED — Constituição 1.1.0 (.specify/memory/constitution.md) e Spec 001 (specs/001-os-checklist-offline/spec.md)"
metadata:
  author: "yby-seed"
  constitution_version: "1.1.0"
  spec: "specs/001-os-checklist-offline/spec.md"
  layer: "camada-6"
---

## Objetivo

Guiar o planejamento, a implementação em camadas pequenas e a revisão da funcionalidade de **ordens de serviço (OS) com checklist 100% offline** descrita em `specs/001-os-checklist-offline/spec.md`, assegurando aderência integral aos 14 requisitos funcionais (`FR-001` a `FR-014`), às 7 decisões aprovadas (`D-1` a `D-7`), à filosofia **Function over Form** e à constituição `1.1.0` em `.specify/memory/constitution.md` (Princípios `I`–`VI` e regras `S1`–`S4`).

## Contexto

Use esta skill quando:

- Elaborar plano técnico, lista de tarefas, código ou testes para qualquer camada da feature `001-os-checklist-offline`.
- Revisar diffs ou critérios de aceite ligados a persistência offline, idempotência, auditoria local, confirmação humana, bloqueio de segunda aba ou validação móvel (`A-Chrome` e `I-Safari`).
- Verificar se uma decisão de implementação respeita as premissas `D-1` a `D-7` e a trava de escopo do MVP (Princípio `V`).

Não use esta skill para:

- Adicionar recursos bloqueados pelo Princípio `V` e por `FR-013`/`D-6`: login em nuvem, sincronização remota, multi-aba avançada, importação de dados, voz, wearables, visão computacional, mesh, IoT ou firmware.
- Reescrever ou apagar módulos existentes fora do escopo da feature (como `src/yby_machine/`, que serve apenas como referência de contexto).

## Passos

1. **Validar contrato antes de editar**
   - Ler `.specify/memory/constitution.md` (`1.1.0`) e `specs/001-os-checklist-offline/spec.md`.
   - Confirmar qual camada única está autorizada (Princípio `VI`) e obter confirmação explícita do mantenedor antes de escrever arquivos ou instalar dependências (`S1`).
   - Preferir biblioteca padrão e recursos nativos do navegador; qualquer nova dependência exige aprovação explícita e justificativa técnica.

2. **Garantir execução 100% offline e zero tráfego externo (`FR-001`, `FR-002`, `FR-010`, Princípio `II`)**
   - Assegurar que, após a primeira carga, criar, abrir, preencher, concluir, reabrir, exportar e remover uma OS funcionem com a rede desligada.
   - Impedir qualquer requisição de saída com dados do usuário e qualquer fallback silencioso para a nuvem (`S1`, `S2`).
   - Garantir abertura pela tela inicial e recarga offline tanto em Android/Chrome (`A-Chrome`) quanto em iPhone/Safari (`I-Safari`).

3. **Implementar durabilidade explícita e fallback (`FR-003`, `FR-004`, `FR-008`, `D-4`, Princípio `III`)**
   - Persistir cada OS como unidade completa e atômica no armazenamento local principal (IndexedDB).
   - Quando IndexedDB estiver indisponível (por exemplo, modo privado restrito), ativar o fallback documentado em `localStorage` (`D-4`), sem nova dependência, exibindo aviso visível de que o fallback está ativo.
   - Proibir confirmação otimista: mostrar estado intermediário ("salvando") e somente exibir "salvo" após gravação concluída e confirmada por releitura real do dado gravado.
   - Em falha de gravação ou cota esgotada, exibir erro claro, nunca mostrar "salvo" e manter o estado anterior íntegro (nunca parcial após fechamento abrupto ou perda de rede).

4. **Assegurar idempotência obrigatória (`FR-005`, `FR-006`, `FR-007`, `FR-008`, `D-5`, `D-7`, Princípio `IV`)**
   - Atribuir identidade estável a cada OS e a cada item de checklist.
   - Garantir que duplo toque em "Criar" ou recarga durante a criação gere zero ou uma OS, nunca duas (`FR-005`).
   - Tratar marcação/desmarcação de item como definição de estado idempotente, impedindo itens duplicados (`FR-006`).
   - Garantir que reabrir uma OS não duplique registro nem corrompa dados, e que concluir uma OS já concluída (com ou sem pendências) mantenha estado e instante de conclusão inalterados (`FR-007`, `D-5`).
   - Garantir que remover uma OS já removida ou inexistente seja no-op sem erro (`D-7`).

5. **Aplicar confirmações humanas obrigatórias (`S1`, `FR-012`, `D-1`, `D-2`, `D-5`, `D-7`)**
   - Na primeira execução, solicitar consentimento único informando exatamente o que será gravado e onde (`D-2`); enquanto recusado, não gravar nenhum byte de dados de OS.
   - Após o consentimento inicial, não repetir confirmação para criar, marcar ou concluir sem pendências (`D-2`).
   - Exigir confirmação explícita com resumo antes de:
     - Leitura crítica: exportação ou compartilhamento de dados da OS para fora do app (`D-1`).
     - Conclusão com itens pendentes: alerta visual listando os itens pendentes (`D-5`), levando ao estado `"concluída com pendências"`.
     - Remoção de uma única OS: resumo com título e número de itens (`D-7`).
     - Remoção em massa (`FR-012`).
   - Em qualquer recusa, manter os dados intactos e registrar a recusa na auditoria.

6. **Registrar auditoria local append-only e proteger dados sensíveis (`S2`, `S4`, `FR-009`, `FR-011`)**
   - Registrar localmente, em modo somente de acréscimo, 1 linha por evento em UTC para toda escrita (criar, marcar, concluir, reabrir, remoção unitária, remoção em massa) e toda leitura crítica (`D-1`).
   - Gravar o registro de auditoria antes de efetivar a ação; se a gravação do registro falhar, recusar a ação (`S2`, `FR-009`).
   - Na conclusão com pendências (`D-5`), registrar apenas os identificadores dos itens pendentes, nunca o texto do item.
   - Manter dados sensíveis (cliente, endereço, telefone, observações) exclusivamente no armazenamento local do aparelho; nunca gravar valores sensíveis em registros de auditoria, URLs, console, cache compartilhado, repositório ou pacote entregue (`S4`, `FR-011`).

7. **Aplicar bloqueio de segunda aba e trava de escopo (`FR-013`, `D-3`, `D-6`, Princípio `V`, `S3`)**
   - Bloquear qualquer segunda aba aberta com aviso claro de que o app já está aberto em outra aba, sem modo somente leitura nem sincronização entre abas (`D-3`).
   - Não expor nenhuma ação ou leitura de arquivo para importação de dados (`D-6`).
   - Manter fora da interface e das dependências qualquer recurso de nuvem, voz, wearable, visão, mesh, IoT ou firmware (`FR-013`, `S3`).

8. **Testar durabilidade, idempotência e aparelhos reais (`FR-014`, Princípio `VI`)**
   - Para cada camada que persiste dados, incluir testes automatizados de repetição da ação, recarga, falha de gravação e interrupção no meio da escrita.
   - Executar e documentar o roteiro manual em `A-Chrome` (Android/Chrome) e `I-Safari` (iPhone/Safari), tratando e documentando as limitações do Safari (remoção de dados de sites sem uso e instalação na tela inicial).

## Critérios de aceite

- **Offline total (`SC-001`)**: 100% do fluxo criar, abrir, preencher e concluir funciona sem rede e com zero requisições de saída em `A-Chrome` e `I-Safari`.
- **Durabilidade verificada (`SC-002`, `SC-003`)**: em 100% das falhas simuladas de gravação, o usuário vê erro claro e nunca vê "salvo"; após fechamento abrupto ou perda de rede, 0 OS ficam corrompidas e 0 itens ficam em estado parcial; fallback `D-4` exibe aviso quando ativo.
- **Idempotência (`SC-004`)**: duplo toque, recarga, reabertura e conclusão/remoção repetidas resultam em 0 OS duplicadas e 0 itens duplicados.
- **Auditoria e privacidade (`SC-005`, `S2`, `S4`)**: toda escrita e toda leitura crítica geram exatamente 1 registro append-only em UTC; falha de gravação do log bloqueia a ação; 0 registros contêm valores de campos sensíveis ou segredos.
- **Confirmação humana (`SC-006`, `S1`)**: com consentimento inicial recusado, 0 bytes de dados de OS são gravados; exportação, conclusão com pendências, remoção unitária e remoção em massa bloqueiam sem confirmação explícita.
- **Escopo e multi-aba (`FR-013`, `D-3`, `D-6`, `S3`)**: segunda aba bloqueada com aviso; nenhuma ação de importação ou recurso fora do MVP presente.
- **Validação real (`SC-007`, `FR-014`)**: roteiro manual registrado em `A-Chrome` e `I-Safari` cobrindo `FR-001` a `FR-008` e `D-5` a `D-7`, com limitações do Safari documentadas.
- **Qualidade da camada**: em camadas de implementação, `make doctor`, `make lint` e `make test` verdes antes de encerrar a camada.

## Exemplos

### Exemplo 1: Salvamento durável com falha de cota e fallback `localStorage` (`FR-003`, `FR-004`, `D-4`)

**Cenário**: técnico abre o app no Safari em modo restrito onde IndexedDB não está disponível e tenta salvar uma OS com 4 itens.

1. O app detecta indisponibilidade do IndexedDB, ativa o fallback `localStorage` e exibe aviso permanente: `"Armazenamento alternativo (localStorage) ativo neste navegador."`
2. O técnico aceita o consentimento inicial (`D-2`) e aciona "Criar OS". A interface exibe `"Salvando..."` (nunca `"Salvo"` antes da confirmação).
3. Antes da gravação, o evento `os.create` é apensado na auditoria local em UTC contendo apenas `timestamp_utc`, `action`, `os_id`, `result` e `data_category`, sem nome do cliente nem observações.
4. O registro completo da OS é gravado atomicamente e relido para conferência de integridade.
   - Se a releitura confirmar o conteúdo gravado, a UI atualiza para `"Salvo"`.
   - Se ocorrer `QuotaExceededError`, a UI exibe erro explícito (`"Não foi possível salvar: armazenamento local sem espaço."`), não exibe `"Salvo"` e mantém intactas as OS previamente salvas.

### Exemplo 2: Conclusão com pendências (`D-5`) e remoção unitária (`D-7`)

**Cenário**: uma OS (`os-20261128-001`) possui 3 itens (`item-1` marcado; `item-2` e `item-3` pendentes).

1. **Conclusão com pendências**:
   - O técnico toca em "Concluir OS". O app exibe alerta visual listando os 2 itens pendentes e solicita confirmação explícita.
   - Se o técnico recusar, a OS permanece `"aberta"` e a auditoria registra:
     `{"ts":"2026-11-28T10:15:00Z","action":"os.complete","os_id":"os-20261128-001","pending_item_ids":["item-2","item-3"],"confirmed":false,"result":"refused"}`
   - Se o técnico confirmar, a OS muda para `"concluída com pendências"` com `completed_at` fixado e a auditoria registra os IDs `["item-2","item-3"]` (sem o texto descritivo dos itens). Acionar "Concluir OS" novamente não altera o estado nem `completed_at`.
2. **Remoção unitária**:
   - O técnico solicita remover `os-20261128-001`. O app exibe confirmação explícita com resumo (`título` e `3 itens`).
   - Ao cancelar, nada muda e `result:"refused"` é registrado. Ao confirmar, a OS e seus itens são removidos, as demais OS permanecem inalteradas e 1 registro de auditoria (`action:"os.delete"`, sem valores sensíveis) é gravado. Repetir a remoção do mesmo `os_id` não produz erro nem altera dados.
