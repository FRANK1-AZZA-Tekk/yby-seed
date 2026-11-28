---
name: "yby-audit-s1-s4"
description: "Guia a auditoria objetiva de conformidade de planos, diffs, ferramentas e PRs contra as regras S1–S4 da constituição 1.1.0 do YBY SEED."
compatibility: "YBY SEED — Constituição 1.1.0 (.specify/memory/constitution.md) e DECISIONS.md (D3, D12)"
metadata:
  author: "yby-seed"
  constitution_version: "1.1.0"
  spec: "specs/001-os-checklist-offline/spec.md"
  layer: "camada-6"
---

## Objetivo

Conduzir auditorias determinísticas e rastreáveis de conformidade contra as regras **S1**, **S2**, **S3** e **S4** da constituição `1.1.0` em `.specify/memory/constitution.md`, aplicando a filosofia **Function over Form** (bloqueios objetivos baseados em evidência, sem burocracia superficial) e garantindo alinhamento às decisões `D3` e `D12` de `DECISIONS.md` e, quando aplicável, à especificação `specs/001-os-checklist-offline/spec.md`.

## Contexto

Use esta skill quando:

- Revisar um plano, especificação, diff local, pull request, prompt de agente ou nova ferramenta antes da execução ou integração.
- Validar camadas da feature `001-os-checklist-offline` quanto a confirmação humana (`FR-012`, `D-1`, `D-2`, `D-5`, `D-7`), auditoria local (`FR-009`), ausência de envio/fallback para nuvem (`FR-010`), proteção de dados sensíveis (`FR-011`) e bloqueio de firmware no MVP (`FR-013`).
- Auditar alterações no roteamento entre modelo local e nuvem (`src/engine/routing.py` ou módulos equivalentes) quanto a `D3`, `D12` e `S2`.

Regras inegociáveis da constituição `1.1.0` aplicadas em toda auditoria:

- **Confirmação humana**: resposta explícita do mantenedor, na sessão atual, a uma pergunta que descreve a ação; silêncio, aprovação anterior ou instrução genérica não valem.
- **Registro de auditoria**: uma linha por evento, em arquivo local somente de acréscimo, com data e hora em UTC, nunca contendo valores de segredo.

## Passos

1. **Delimitar o alvo da auditoria**
   - Identificar os arquivos, diffs, comandos, prompts ou fluxos de rede sob revisão.
   - Carregar `.specify/memory/constitution.md` (`1.1.0`) e, quando o alvo envolver ordens de serviço offline, `specs/001-os-checklist-offline/spec.md`.

2. **Auditar S1 — Confirmação antes de escrever ou enviar**
   - Verificar todas as operações que criam, alteram ou apagam arquivos fora do escopo já aprovado, instalam dependências, executam comandos que gravam ou enviam dados pela rede.
   - Confirmar que o pedido de aprovação apresenta os caminhos afetados ou destino remoto e o resumo do conteúdo (tamanho ou diff).
   - Confirmar que, na ausência de confirmação explícita na sessão atual, a ação é recusada sem gravar nem enviar nada, mantendo apenas leitura e simulação (`dry-run`).
   - Confirmar que a auditoria registra ação, caminho ou destino, confirmação recebida (`sim` ou `não`) e identificador da camada.
   - Em `001-os-checklist-offline`: confirmar consentimento inicial único (`D-2`) e confirmação com resumo para exportação/compartilhamento (`D-1`), conclusão com pendências (`D-5`), remoção de uma OS (`D-7`) e remoção em massa (`FR-012`).

3. **Auditar S2 — Auditoria de roteamento e de execução**
   - Verificar se toda decisão de roteamento (local vs. nuvem, conforme `D3` e `D12`) e toda execução de ferramenta ou comando grava registro append-only em UTC **antes** da execução.
   - Confirmar a presença dos campos obrigatórios: decisão (`local` ou `nuvem`), modelo, motivo (custo, latência, sensibilidade ou flag explícita como `--heavy`), ferramenta, argumentos com segredos mascarados e resultado (`sucesso`, `falha` ou `recusa`).
   - Confirmar que toda rota para a nuvem passa por confirmação `S1` e que **não existe fallback silencioso para a nuvem** quando o caminho local falha.
   - Confirmar o comportamento fail-closed: se o registro de auditoria não puder ser gravado, a execução ou o roteamento é recusado (`S2`, `FR-009`).

4. **Auditar S3 — Firmware somente em dispositivo cadastrado**
   - Verificar se há qualquer tentativa de gravar, fazer flash ou atualizar firmware em hardware.
   - Se o projeto ainda estiver no escopo do MVP (Princípio `V` e `FR-013`), **bloquear** qualquer habilitação de firmware no MVP.
   - Para propostas ou fluxos futuros (pós-MVP), confirmar que exigem dispositivo previamente cadastrado e validado pelo usuário, proíbem cadastro automático por inferência, exigem confirmação por gravação (identificador cadastrado, versão atual e versão de destino) e registram auditoria com identificador, versão antes/depois, hash do artefato, confirmação e resultado.

5. **Auditar S4 — Dados sensíveis permanecem locais**
   - Inspecionar código, testes, logs, auditoria, prompts, commits, PRs e payloads de rede em busca de chaves de API, credenciais, tokens, segredos ou dados pessoais (em `001-os-checklist-offline`: cliente, endereço, telefone e observações — `FR-011`).
   - Confirmar que nenhum segredo existe no repositório ou no pacote entregue e que padrões de segredo são removidos ou mascarados antes de sair da máquina.
   - Confirmar que a auditoria registra apenas categoria do dado e destino (ou identificador da OS), nunca o valor sensível.
   - Caso exista envio excepcional à nuvem sem alternativa local, exigir confirmação `S1` com lista explícita do que será enviado; sem confirmação, recusar.

6. **Emitir parecer estruturado**
   - Classificar cada regra (`S1`, `S2`, `S3`, `S4`) como `CONFORME`, `NÃO APLICÁVEL` (com justificativa factual) ou `VIOLAÇÃO`.
   - Emitir veredito final `APROVADO` somente se houver zero violações; qualquer violação resulta em `BLOQUEADO`, listando exatamente o arquivo/fluxo afetado e a correção mínima necessária.

## Critérios de aceite

- As quatro regras (`S1`, `S2`, `S3` e `S4`) foram avaliadas explicitamente com evidência concreta (arquivo, símbolo, comando ou fluxo inspecionado).
- Nenhuma confirmação tácita, anterior ou genérica foi aceita como válida para `S1`.
- Nenhum fallback silencioso para nuvem e nenhuma execução sem registro prévio append-only em UTC passaram sem bloqueio (`S2`).
- Qualquer tentativa de habilitar firmware no MVP ou gravar fora de dispositivo cadastrado foi bloqueada (`S3` e Princípio `V`).
- Nenhum valor de segredo ou dado pessoal apareceu no relatório de auditoria, nos logs ou nos arquivos aprovados (`S4`).
- O parecer termina com veredito claro (`APROVADO` ou `BLOQUEADO`) e ações objetivas de correção quando bloqueado.

## Exemplos

### Exemplo 1: Auditoria com veredito `BLOQUEADO` (violações em `S2` e `S4`)

**Alvo**: diff propondo cliente HTTP que envia texto de observações da OS para API de nuvem quando o modelo local retorna timeout, registrando o payload completo em `audit.log`.

- **S1**: `VIOLAÇÃO` — inicia envio de dados do usuário à nuvem sem solicitar confirmação explícita com destino e lista de campos.
- **S2**: `VIOLAÇÃO` — implementa fallback silencioso para a nuvem em erro local (viola `S2` e `D12`) e grava o log apenas após a chamada, ignorando falha de escrita do log.
- **S3**: `NÃO APLICÁVEL` — nenhuma operação de firmware ou hardware no diff.
- **S4**: `VIOLAÇÃO` — envia campo `observacoes` da OS para destino remoto sem necessidade nem confirmação, e grava o valor bruto no log de auditoria em vez da categoria do dado.
- **Veredito**: `BLOQUEADO`.
- **Correção mínima**: remover o fallback silencioso para a nuvem, manter dados de OS estritamente locais (`FR-010`, `FR-011`), gravar a auditoria append-only em UTC antes da ação (recusando se falhar) e registrar apenas `data_category` e `os_id`, nunca valores sensíveis.

### Exemplo 2: Auditoria com veredito `APROVADO` (camada de `001-os-checklist-offline`)

**Alvo**: camada de exportação de OS em arquivo JSON local (leitura crítica `D-1`) e remoção unitária (`D-7`).

- **S1**: `CONFORME` — exportação exibe resumo (identificador da OS, título e destino local de download) e aguarda confirmação explícita; remoção unitária exibe título e contagem de itens; cancelar preserva todos os dados.
- **S2**: `CONFORME` — ambas as ações gravam 1 linha UTC append-only na auditoria local antes de executar (`os.export` e `os.delete`); teste unitário comprova que erro na escrita do log impede a ação; zero chamadas de rede.
- **S3**: `NÃO APLICÁVEL` — escopo restrito à aplicação offline de OS; nenhuma funcionalidade de firmware presente (respeita Princípio `V` e `FR-013`).
- **S4**: `CONFORME` — nenhum segredo no diff; registros de auditoria contêm apenas `ts`, `action`, `os_id`, `data_category`, `confirmed` e `result`, sem nome do cliente, endereço, telefone ou observações.
- **Veredito**: `APROVADO`.
