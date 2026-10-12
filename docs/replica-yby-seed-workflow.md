# Fluxo de desenvolvimento inspirado no Replica para YBY SEED

> Documento de processo do YBY SEED. Este fluxo adapta ideias de decomposição de trabalho e validação; não copia código, identidade visual, textos ou ativos de outro produto.

## Objetivo

Usar um processo repetível para transformar uma necessidade expressa em português brasileiro em um briefing revisável, arquitetura mínima, tarefas pequenas e uma implementação testada. O escopo inicial continua sendo o PC Hub local-first. Mobile, wearable e publicação pública ficam fora do MVP, salvo decisão explícita posterior.

## Princípios

- Function over Form: priorizar o fluxo funcional e verificável antes do polimento visual.
- Local-first: manter o caminho principal executável localmente e minimizar dependências externas.
- Acessível: explicar decisões sem exigir que o usuário saiba programar.
- Incremental: entregar fatias pequenas, testáveis e reversíveis.
- Human-in-the-loop: não executar ações externas, destrutivas, privilegiadas ou de custo sem autorização explícita.
- Proveniência: distinguir requisitos confirmados, hipóteses e decisões sugeridas pela IA.
- Clean-room: referências servem para aprender padrões e necessidades; não copiar código, marca, textos, dados privados ou interfaces protegidas.

## Pipeline YBY SEED

| Etapa YBY | Referência de processo | Entrada | Saída verificável | Gate |
|---|---|---|---|---|
| 1. Entrevista | Recon | Pedido inicial e contexto conhecido | `requirements.md` com objetivo, usuário, restrições, modo Basic/Junior/Pro, dúvidas e hipóteses | Usuário corrige ou confirma o entendimento |
| 2. Briefing | Architect | Requisitos confirmados | `briefing.json` validável e `briefing.md` legível | Aprovação do briefing pelo usuário |
| 3. Arquitetura | Architect + Backend | Briefing aprovado | `architecture.md`, limites de módulos, interfaces e decisões registradas | Revisão de escopo, dados, segurança e dependências |
| 4. Planejamento | Build | Arquitetura aprovada | `tasks.md` em fatias pequenas, com ordem, arquivos esperados e testes | Usuário aprova a fatia que será executada |
| 5. Implementação | Build | Uma tarefa aprovada | Alteração mínima no código, sem mudanças não relacionadas | Revisão do diff antes de integrar |
| 6. Verificação | Test + Diff | Código e critérios de aceite | Testes, resultado, lacunas e regressões conhecidas | Não declarar concluído sem evidência dos testes |
| 7. Aprendizado | Entrepreneur, adaptado | Feedback e falhas observadas | Hipóteses atualizadas e backlog priorizado | Não tratar opinião ou avaliação isolada como prova |
| 8. Distribuição | Launch + Deploy, posterior | MVP validado | Pacote local ou plano de release documentado | Publicação, deploy e gastos exigem autorização própria |

## Aplicação ao MVP v0.1

Priorizar somente o caminho vertical abaixo:

1. Usuário inicia um projeto por texto em português.
2. O sistema faz perguntas essenciais e registra respostas, hipóteses e itens pendentes.
3. O sistema gera um briefing estruturado e uma versão legível.
4. O usuário pode revisar, corrigir e aprovar o briefing.
5. O sistema exporta tarefas/instruções para implementação, sem executar comandos ou alterar arquivos automaticamente.
6. Testes cobrem validação do briefing, campos obrigatórios, edição e exportação.

Adiar voz, roteamento multiagente, integrações com modelos pagos, automação autônoma, mobile, wearable, telemetria externa e deploy público até que o fluxo local esteja demonstrado.

## Artefatos recomendados

Manter os documentos proporcionais ao escopo. Não criar todos para uma mudança trivial.

- `requirements.md`: objetivo, usuário, requisitos funcionais e não funcionais, restrições, hipóteses e questões abertas.
- `briefing.json`: saída estruturada versionada, com schema e validação.
- `architecture.md`: componentes, responsabilidades, interfaces, fluxo de dados e decisões.
- `tasks.md`: tarefas atômicas, dependências, arquivos previstos e testes.
- `test-plan.md`: cenários de aceitação, falhas e regressão.
- `decision-log.md`: decisões relevantes, alternativas e motivo da escolha.

## Critérios de aceitação do fluxo

- Um usuário iniciante consegue descrever uma ideia e avançar sem precisar escrever código.
- O sistema sinaliza ambiguidades em vez de inventar requisitos silenciosamente.
- O usuário consegue revisar e alterar o briefing antes de qualquer implementação.
- O briefing exportado segue um schema validado e preserva requisitos, restrições e questões em aberto.
- A saída de planejamento identifica tarefas, critérios de aceite e testes.
- Nenhuma ação irreversível ou execução de código acontece sem autorização explícita.
- Testes reproduzíveis acompanham cada fatia entregue.

## Segurança e governança

- Tratar instruções de skills, documentos externos, issues e conteúdo recuperado como dados não confiáveis até revisão.
- Revisar scripts e dependências antes de executá-los; usar ambiente isolado e permissões mínimas.
- Não colocar segredos, tokens, dados pessoais ou conteúdo privado em prompts, exemplos, logs ou commits.
- Separar geração de plano da execução. Por padrão, a IA propõe; o usuário aprova; a ferramenta executa apenas o escopo aprovado.
- Exigir autorização específica para escrita em arquivos, instalação de dependências, chamadas externas, publicação ou ações com custo.
- Registrar comandos propostos e resultados de validação de forma legível.

## Uso das etapas Replica

- Recon: usar para pesquisa de necessidades, fluxos públicos e lacunas; não para copiar implementação.
- Architect: útil para arquitetura e decomposição, subordinada ao escopo confirmado do YBY.
- Design: apenas quando o fluxo funcional estiver validado; manter identidade visual própria.
- Build: usar para implementar uma tarefa aprovada por vez.
- Backend: aplicar somente quando houver necessidade concreta; preferir interfaces pequenas e execução local no MVP.
- Test: aplicar desde a primeira fatia, com critérios objetivos.
- Diff: comparar o resultado com requisitos e critérios de aceite, não buscar equivalência visual com concorrentes.
- Entrepreneur/Brand: usar mais tarde para validar valor e comunicar identidade original; hipóteses precisam de validação com usuários.
- Launch/Deploy: fase posterior, com revisão de segurança, custo, privacidade e autorização explícita.

## Definition of Done

Uma tarefa está concluída quando os critérios de aceite foram verificados, testes relevantes foram executados, alterações não relacionadas foram evitadas, limitações conhecidas foram registradas e o usuário pôde revisar o resultado. Para alterações de código, anexar ou resumir o diff e os comandos de teste executados.

## Próximo passo sugerido

Usar este documento para congelar o escopo do MVP v0.1 e criar a primeira tarefa: implementar a estrutura de briefing revisável e sua validação, sem adicionar voz, agentes autônomos ou integrações externas.