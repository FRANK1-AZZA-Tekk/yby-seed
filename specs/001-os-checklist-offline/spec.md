# Feature Specification: Ordens de serviço com checklist offline

**Feature Branch**: `cursor/spec-ordens-servico-offline-e5da`

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "Ordens de serviço com checklist offline: criar, abrir, preencher e concluir uma OS com checklist 100% offline, com persistência durável, idempotência, auditoria local e confirmação humana, validada em Android/Chrome e iPhone/Safari. Requisitos R-01 a R-14 e decisões D-1 a D-4 aprovadas pelo mantenedor."

## Premissas Fixadas (decisões aprovadas pelo mantenedor)

Estas quatro decisões foram propostas e aprovadas antes desta spec e valem para todos os requisitos abaixo. Alterá-las exige nova aprovação.

- **D-1. Leitura crítica (R-09)**: leitura crítica é toda exportação ou compartilhamento de dados de uma OS para fora do app (arquivo baixado, texto copiado ou compartilhamento do sistema). Abrir e visualizar a OS dentro do app não é leitura crítica. Toda leitura crítica gera registro de auditoria e exige confirmação com resumo.
- **D-2. Escopo aprovado de S1 (R-12)**: o escopo aprovado é a gravação de dados de OS no armazenamento local do aparelho (IndexedDB, com fallback em `localStorage`), sem envio à nuvem. O app pede essa confirmação uma única vez, na primeira execução, informando o que grava e onde. Depois disso, criar, marcar e concluir não pedem nova confirmação. Exportação e remoção em massa exigem confirmação explícita com resumo. Sem a confirmação inicial, o app não grava nada.
- **D-3. Comportamento multi-aba (R-13)**: a segunda aba aberta é bloqueada com aviso claro de que o app já está aberto em outra aba. Não há modo somente leitura nem sincronização entre abas.
- **D-4. Fallback de armazenamento (R-03)**: `localStorage` é o fallback documentado quando IndexedDB não está disponível, sem nova dependência. O usuário é avisado de que o fallback está ativo. No fallback, cada gravação é um único registro completo, relido para confirmar antes de mostrar "salvo", e erro de cota é mostrado ao usuário.

## User Scenarios & Testing *(mandatory)*

Nos cenários abaixo, **A-Chrome** é um aparelho Android com Chrome e **I-Safari** é um iPhone com Safari. Todo cenário de aceite vale nos dois ambientes.

### User Story 1 - Executar uma ordem de serviço do início ao fim sem rede (Priority: P1)

O técnico de campo cria uma OS, abre, preenche o checklist e conclui a OS com o aparelho sem rede, e depois consegue reabrir o app e ver o que fez.

**Why this priority**: é o valor central do MVP; sem isso o produto não serve em campo.

**Independent Test**: com a rede desligada após a primeira carga, criar, preencher e concluir uma OS e recarregar o app; tudo continua disponível.

**Acceptance Scenarios**:

1. **Given** o app já foi carregado uma vez e a rede está desligada, **When** o técnico cria uma OS, marca todos os itens e a conclui, **Then** a OS aparece como concluída e nenhuma requisição de rede é feita.
2. **Given** a rede está desligada, **When** o técnico recarrega ou reabre o app pela tela inicial, **Then** o app abre e lista as OS existentes.

---

### User Story 2 - Nunca perder nem mostrar como salvo o que não foi salvo (Priority: P1)

O técnico só vê "salvo" depois que o dado realmente persistiu no aparelho, e nenhuma interrupção deixa a OS corrompida.

**Why this priority**: a confiança nos dados é a razão de existir do produto (Princípio III e IV).

**Independent Test**: forçar falha de gravação e interromper o app no meio de uma gravação; verificar mensagens e integridade.

**Acceptance Scenarios**:

1. **Given** a gravação falha, **When** o técnico tenta salvar, **Then** o app mostra erro claro e nunca mostra "salvo".
2. **Given** o navegador é fechado de forma abrupta no meio de uma gravação, **When** o app é reaberto, **Then** a OS está no estado anterior completo ou no novo completo, nunca parcial.

---

### User Story 3 - Repetir uma ação não duplica nem corrompe (Priority: P2)

Duplo toque, recarga no meio, reabertura e conclusão repetida não geram OS duplicadas, itens duplicados ou estados diferentes.

**Why this priority**: toque repetido é comum em campo; duplicidade quebra a confiança nos registros.

**Independent Test**: repetir cada ação várias vezes, com e sem recarga, e conferir a contagem de registros e o estado final.

**Acceptance Scenarios**:

1. **Given** o técnico toca duas vezes em "Criar", **When** a criação termina, **Then** existe uma única OS.
2. **Given** uma OS concluída, **When** o técnico a conclui de novo, **Then** o estado e o instante de conclusão não mudam.

---

### User Story 4 - Auditoria, confirmação e privacidade locais (Priority: P2)

Toda escrita e toda leitura crítica ficam registradas localmente; a gravação inicial, a exportação e a remoção em massa exigem confirmação; nenhum dado sai do aparelho.

**Why this priority**: cumpre as regras S1, S2 e S4 da constituição 1.1.0.

**Independent Test**: executar o fluxo completo, comparar ações com registros e inspecionar a rede.

**Acceptance Scenarios**:

1. **Given** a primeira execução, **When** o técnico recusa a confirmação inicial, **Then** nada é gravado.
2. **Given** o fluxo completo executado, **When** a auditoria é conferida, **Then** há um registro por ação e nenhum registro contém valores de campos sensíveis.

---

### User Story 5 - Limites de escopo e validação em aparelhos reais (Priority: P3)

A primeira versão não oferece nuvem, sincronização, multi-aba avançada, voz, wearable nem firmware, e é validada em Android/Chrome e iPhone/Safari.

**Why this priority**: mantém o MVP pequeno e fecha o ciclo de validação (Princípio V).

**Independent Test**: abrir duas abas e executar o roteiro manual nos dois aparelhos.

**Acceptance Scenarios**:

1. **Given** o app aberto em uma aba, **When** uma segunda aba é aberta, **Then** ela é bloqueada com aviso claro e nenhum dado é corrompido.
2. **Given** o roteiro de validação, **When** é executado nos dois aparelhos, **Then** o resultado de cada requisito fica registrado.

---

### Edge Cases

- Armazenamento cheio ou bloqueado (modo privado, cota esgotada): erro claro, nenhum "salvo", nenhum registro parcial.
- Registro de auditoria não pode ser gravado: a ação é recusada (S2).
- Armazenamento principal indisponível: fallback ativo com aviso ao usuário (D-4).
- Safari no iPhone pode apagar dados de sites sem uso por um período: o app informa isso e o roteiro de validação cobre o caso.
- Duas abas abertas ao mesmo tempo: a segunda é bloqueada com aviso (D-3).
- Fechamento abrupto do navegador ou perda de rede durante uma gravação: estado anterior ou novo completo, nunca parcial.
- Toque repetido, recarga durante a criação ou reenvio de uma ação: no máximo um efeito.
- Recusa da confirmação inicial de gravação: o app não grava nem cria OS.

## Requirements *(mandatory)*

Cada requisito abaixo corresponde a um item R-xx levantado na Camada 3 (FR-001 corresponde a R-01, e assim por diante). Cada um traz regra aplicável, critério de aceite verificável e cenário de teste em A-Chrome e I-Safari.

### Functional Requirements

- **FR-001 (R-01)**: O sistema DEVE permitir criar, abrir, preencher e concluir uma OS com checklist inteiramente offline, sem nenhuma requisição de rede em todo o fluxo.
  - **Regra aplicável**: Princípio II; S4.
  - **Critério de aceite**: fluxo completo concluído com rede desligada; zero requisições de saída no log de rede; nenhum recurso externo no carregamento.
  - **A-Chrome**: carregar o app com rede, ativar modo avião, criar uma OS, marcar todos os itens e concluir.
  - **I-Safari**: o mesmo roteiro, com modo avião ativado.

- **FR-002 (R-02)**: O sistema DEVE iniciar sem rede depois da primeira carga, com tudo o que precisa disponível no aparelho.
  - **Regra aplicável**: Princípio II.
  - **Critério de aceite**: com a rede cortada, a recarga abre o app e lista as OS existentes.
  - **A-Chrome**: carregar online, cortar a rede, recarregar e reabrir pela tela inicial; conferir a lista.
  - **I-Safari**: o mesmo roteiro, incluindo a abertura pelo ícone na tela inicial.

- **FR-003 (R-03)**: O sistema DEVE persistir os dados de forma durável e local, com gravação por unidade completa. Com o armazenamento principal indisponível, DEVE usar o fallback documentado em D-4, com aviso ao usuário.
  - **Regra aplicável**: Princípio III; D-4.
  - **Critério de aceite**: após fechar e reabrir, todos os dados gravados estão presentes e íntegros; falha de gravação não deixa registro parcial; com o fallback ativo, o aviso é exibido.
  - **A-Chrome**: criar OS, fechar a aba, reabrir; repetir após encerrar o Chrome pelo seletor de apps; repetir com o armazenamento principal indisponível.
  - **I-Safari**: o mesmo roteiro no Safari, incluindo modo de navegação privada para exercitar o fallback.

- **FR-004 (R-04)**: O sistema DEVE mostrar confirmação visual de "salvo" somente depois da persistência real, confirmada por releitura do dado gravado.
  - **Regra aplicável**: Princípio III.
  - **Critério de aceite**: com falha de gravação simulada, nenhuma mensagem de sucesso aparece e o erro é claro; com gravação atrasada, o app mostra estado de "salvando" e só depois "salvo".
  - **A-Chrome**: forçar cota cheia ou bloqueio de armazenamento e verificar ausência de "salvo"; no caminho feliz, verificar a ordem das mensagens.
  - **I-Safari**: o mesmo roteiro.

- **FR-005 (R-05)**: O sistema DEVE tornar a criação de OS idempotente: cada intenção de criar produz no máximo uma OS, com identidade estável.
  - **Regra aplicável**: Princípio IV.
  - **Critério de aceite**: dois toques rápidos em "Criar" resultam em uma única OS; recarregar durante a criação resulta em zero ou uma OS, nunca duas.
  - **A-Chrome**: duplo toque rápido; recarregar logo após tocar em "Criar"; contar os registros.
  - **I-Safari**: o mesmo roteiro.

- **FR-006 (R-06)**: O sistema DEVE tornar a marcação de itens idempotente: marcar e desmarcar definem um estado e repetir a mesma operação não altera o resultado nem duplica itens.
  - **Regra aplicável**: Princípio IV.
  - **Critério de aceite**: aplicar a mesma marcação N vezes deixa o estado igual ao da primeira; o checklist nunca tem itens duplicados.
  - **A-Chrome**: tocar repetidamente no mesmo item, recarregando entre os toques; conferir estado e contagem.
  - **I-Safari**: o mesmo roteiro.

- **FR-007 (R-07)**: O sistema DEVE tornar a reabertura e a conclusão idempotentes: reabrir uma OS não cria nova OS nem altera dados; concluir uma OS já concluída não tem efeito e não gera erro.
  - **Regra aplicável**: Princípio IV.
  - **Critério de aceite**: reabrir três vezes mantém um único registro com o mesmo conteúdo; concluir duas vezes mantém um único estado "concluída" e um único instante de conclusão.
  - **A-Chrome**: concluir, reabrir, concluir de novo; conferir registro e instante.
  - **I-Safari**: o mesmo roteiro.

- **FR-008 (R-08)**: O sistema DEVE manter a OS íntegra diante de fechamento abrupto do navegador e perda total de rede no meio de uma gravação: o estado é o anterior ou o novo, nunca corrompido.
  - **Regra aplicável**: Princípios III e IV.
  - **Critério de aceite**: após interrupção simulada, a OS abre sem erro e o checklist mostra o estado anterior completo ou o novo completo.
  - **A-Chrome**: marcar um item e encerrar o Chrome logo em seguida; cortar a rede e fechar; reabrir e validar a integridade.
  - **I-Safari**: o mesmo roteiro, encerrando o Safari pelo seletor de apps.

- **FR-009 (R-09)**: O sistema DEVE registrar em auditoria local, somente de acréscimo, toda escrita (criar, marcar, concluir, reabrir, remoção em massa) e toda leitura crítica (exportação ou compartilhamento, conforme D-1). Cada registro é uma linha por evento, em UTC, sem valores sensíveis. Falha ao gravar o registro DEVE impedir a ação.
  - **Regra aplicável**: S2; D-1.
  - **Critério de aceite**: cada ação do fluxo de FR-001 gera exatamente um registro; repetir uma ação idempotente registra a tentativa sem duplicar o dado; falha de gravação do registro recusa a ação.
  - **A-Chrome**: executar o fluxo completo e comparar a contagem de ações com a de registros; simular falha de gravação do registro.
  - **I-Safari**: o mesmo roteiro.

- **FR-010 (R-10)**: O sistema NÃO DEVE enviar dados do usuário a nenhum destino remoto nem fazer fallback silencioso para a nuvem. Qualquer rota para a nuvem que venha a existir exige confirmação e registro.
  - **Regra aplicável**: S1; S2.
  - **Critério de aceite**: inspeção de rede e do código mostra zero chamadas de saída com dados; nenhuma rota de nuvem habilitada por padrão.
  - **A-Chrome**: executar o fluxo completo com um proxy que registra requisições; o resultado esperado é nenhuma.
  - **I-Safari**: o mesmo roteiro, com proxy na rede do aparelho.

- **FR-011 (R-11)**: O sistema DEVE manter os dados sensíveis (cliente, endereço, telefone, observações) somente no aparelho. Nenhum segredo, chave ou credencial pode existir no repositório, no pacote entregue ou nos registros de auditoria.
  - **Regra aplicável**: S4.
  - **Critério de aceite**: varredura de segredos limpa; registros de auditoria sem valores de campos sensíveis (apenas categoria e identificador); nenhum dado do usuário em URL, console ou cache compartilhado.
  - **A-Chrome**: preencher uma OS com dados fictícios sensíveis; inspecionar armazenamento, auditoria e rede; confirmar que só o armazenamento local contém o dado.
  - **I-Safari**: o mesmo roteiro.

- **FR-012 (R-12)**: O sistema DEVE pedir confirmação humana na primeira execução, informando o que será gravado e onde (D-2), e DEVE exigir confirmação explícita com resumo para exportação e remoção em massa. Sem a confirmação inicial, o app não grava nada.
  - **Regra aplicável**: S1; D-2.
  - **Critério de aceite**: recusar a confirmação inicial deixa o armazenamento vazio; exportar ou remover em massa sem confirmar não executa e a recusa é registrada.
  - **A-Chrome**: recusar na primeira execução e verificar que nada foi gravado; aceitar e seguir; tentar remover tudo e cancelar, conferindo que os dados permanecem.
  - **I-Safari**: o mesmo roteiro.

- **FR-013 (R-13)**: O sistema NÃO DEVE incluir login em nuvem, sincronização remota, multi-aba avançada, voz, wearables nem firmware. A segunda aba aberta DEVE ser bloqueada com aviso claro (D-3).
  - **Regra aplicável**: Princípio V; S3; D-3.
  - **Critério de aceite**: a spec e a interface não contêm esses recursos; nenhuma dependência os habilita; a segunda aba mostra o aviso e não grava nem corrompe dados.
  - **A-Chrome**: abrir duas abas, conferir o bloqueio e a integridade dos dados da primeira.
  - **I-Safari**: o mesmo roteiro.

- **FR-014 (R-14)**: O sistema DEVE ser validado em aparelhos reais nos dois ambientes, com as limitações do Safari (remoção de dados de sites sem uso, instalação na tela inicial) tratadas e documentadas.
  - **Regra aplicável**: Princípio V.
  - **Critério de aceite**: roteiro manual executado e registrado em A-Chrome e I-Safari, cobrindo FR-001 a FR-008; falhas e limites de armazenamento documentados.
  - **A-Chrome**: executar o roteiro completo e registrar o resultado por requisito.
  - **I-Safari**: executar o roteiro completo, incluindo o caso de dados removidos por inatividade, e registrar o resultado por requisito.

### Key Entities *(include if feature involves data)*

- **Ordem de serviço (OS)**: unidade de trabalho do técnico, com identidade estável, título, dados do cliente e do local, observações livres, estado (aberta ou concluída) e instante de conclusão.
- **Item de checklist**: etapa de uma OS, com descrição e estado (marcado ou não), sempre pertencente a uma única OS.
- **Registro de auditoria**: evento local somente de acréscimo, com instante em UTC, tipo de ação, identificador da OS (quando houver), resultado (sucesso, falha ou recusa) e categoria do dado, sem valores sensíveis.
- **Consentimento de armazenamento**: registro da confirmação inicial de gravação local (D-2), com instante.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% do fluxo criar, preencher e concluir uma OS funciona com a rede desligada, sem nenhuma requisição de saída, nos dois ambientes de teste.
- **SC-002**: em 100% dos casos de falha de gravação simulada, o usuário vê erro claro e nenhuma confirmação de "salvo".
- **SC-003**: em todas as interrupções simuladas (fechamento abrupto, perda de rede), 0 OS ficam corrompidas e 0 itens ficam em estado parcial.
- **SC-004**: em todos os testes de repetição de ação (duplo toque, recarga, reabertura, conclusão repetida), 0 OS e 0 itens duplicados.
- **SC-005**: cada ação de escrita e cada leitura crítica gera exatamente um registro de auditoria, e 0 registros contêm valores de campos sensíveis.
- **SC-006**: com a confirmação inicial recusada, 0 bytes de dados de OS são gravados.
- **SC-007**: o roteiro de validação é executado e registrado nos dois ambientes (A-Chrome e I-Safari) para os requisitos FR-001 a FR-008, e as limitações encontradas ficam documentadas.

## Assumptions

- Esta spec define apenas o que o produto faz; a escolha técnica de armazenamento e a estrutura do app ficam para o plano. As menções a IndexedDB e `localStorage` constam apenas porque fazem parte das decisões D-2 e D-4 aprovadas.
- O usuário é um técnico de campo, único usuário do aparelho, sem conta nem login.
- A OS tem título, dados do cliente e do local, observações livres e uma lista de itens de checklist definida pelo próprio técnico ao criar a OS.
- A conclusão de uma OS exige que todos os itens estejam marcados; reabrir uma OS concluída permite editá-la de novo.
- Exportação e remoção em massa fazem parte desta versão; importação de dados está fora do escopo. Remover uma única OS não faz parte desta versão.
- A auditoria fica no próprio aparelho, é somente de acréscimo e não é enviada para lugar nenhum.
- O app é carregado com rede pelo menos uma vez antes de ser usado offline.
- Ficam fora desta versão, até validação em dispositivos reais: login em nuvem, sincronização remota, multi-aba avançada, voz, wearables, visão, mesh, IoT e firmware (Princípio V e S3).
- O código existente em `src/yby_machine/` é referência de contexto e não define requisitos desta spec.
