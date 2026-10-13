# Fluxo de desenvolvimento inspirado no Replica para YBY SEED

> Documento de processo do YBY SEED. Replica é apenas uma inspiração para decompor pesquisa, planejamento e verificação; suas skills não são dependências do YBY. Não copiar código, identidade visual, textos, dados privados ou ativos de outro produto.

## Objetivo e contexto

Definir um fluxo repetível para transformar uma necessidade expressa em português brasileiro em requisitos revisáveis, planejamento proporcional e implementação testada. Este documento propõe um recorte para validar o fluxo de briefing; não redefine nem substitui a arquitetura, as skills ou o roadmap já existentes no repositório.

O PC Hub, gateway, agentes, modelos locais, RAG e skills continuam sendo parte da visão documentada do YBY SEED. Mobile, wearable e integrações híbridas permanecem conforme o roadmap próprio do projeto; não são cancelados por este fluxo. As dependências usadas em cada implementação devem seguir a fase e as decisões aprovadas do projeto.

## Princípios

- Function over Form: priorizar resultados funcionais e verificáveis antes de polimento visual.
- Local-first: preservar o caminho local e minimizar dependências externas desnecessárias.
- Acessibilidade: explicar decisões em linguagem compreensível para iniciantes.
- Incremental: entregar fatias pequenas, testáveis e reversíveis.
- Aprovação em etapas: validar entendimento e briefing separadamente da autorização para executar ações.
- Proveniência: distinguir requisitos confirmados, hipóteses e sugestões da IA.
- Clean-room: referências ajudam a entender necessidades e padrões; não justificam copiar implementação, marca, texto ou conteúdo protegido.

## Pipeline YBY SEED

As referências a Recon, Architect, Build, Test e demais etapas nomeiam ideias de processo adaptadas. Não implicam instalar ou executar as skills do Replica.

| Etapa YBY | Inspiração de processo | Entrada | Saída verificável | Gate |
|---|---|---|---|---|
| 1. Entendimento | Recon | Pedido inicial e contexto conhecido | Requisitos com objetivo, usuário, restrições, modo de entrevista, dúvidas e hipóteses | Usuário corrige ou confirma o entendimento |
| 2. Briefing | Architect | Requisitos revisados | Briefing estruturado validável e resumo legível | Usuário aprova o conteúdo do briefing |
| 3. Arquitetura | Architect/Backend | Briefing aprovado, arquitetura vigente e roadmap | Decisões, interfaces ou mudanças necessárias, apenas quando houver impacto técnico relevante | Revisão técnica e de escopo |
| 4. Planejamento | Build | Escopo e abordagem revisados | Tarefas pequenas com critérios de aceite, arquivos/componentes prováveis quando conhecidos e testes | Usuário aprova a tarefa específica para implementação |
| 5. Implementação | Build | Tarefa aprovada | Diff mínimo e limitado à tarefa | Revisão do diff e autorização conforme a política do projeto |
| 6. Verificação | Test/Diff | Critérios de aceite e implementação | Resultado dos testes, lacunas e regressões conhecidas | Não declarar concluído sem evidência verificável |
| 7. Aprendizado | Aprendizado contínuo | Feedback e resultados | Hipóteses atualizadas e backlog priorizado | Não tratar feedback isolado como prova conclusiva |
| 8. Distribuição | Launch/Deploy, quando aplicável | Implementação validada | Instrução de execução local ou plano de release compatível com o roadmap | Publicação, deploy e custos dependem de aprovação específica |

## Recorte de validação do briefing

O primeiro recorte proposto valida o fluxo de entendimento e planejamento; não é uma declaração de nova versão oficial nem substitui as fases do roadmap.

1. Usuário inicia um projeto em português, usando o modo de interação disponível na fase atual.
2. O Planning Agent coleta requisitos e sinaliza dúvidas, hipóteses e restrições.
3. O sistema produz um briefing estruturado e uma apresentação legível.
4. O usuário revisa e aprova ou corrige o briefing.
5. O sistema propõe tarefas e critérios de aceite; essa aprovação não autoriza execução automaticamente.
6. Uma tarefa de implementação só avança depois da autorização explícita para aquela tarefa e dentro do escopo aprovado.
7. Os testes verificam validação do briefing, campos relevantes, edição, exportação e regressões pertinentes à implementação.

Esse recorte não remove voz, agentes, automações, mobile, wearable ou conectividade híbrida do projeto. Ele evita torná-los requisitos obrigatórios para validar este fluxo específico, respeitando o roadmap e a maturidade de cada componente.

## Artefatos proporcionais

Manter o número de arquivos proporcional à complexidade. Para mudanças simples, usar um briefing/requisito e critérios de aceite como núcleo; criar os demais artefatos apenas quando forem úteis.

- Requisitos/briefing: objetivo, usuário, comportamento, restrições, hipóteses e questões em aberto.
- `briefing.json` ou formato estruturado equivalente: usar quando houver necessidade de intercâmbio entre agentes/ferramentas, com schema e validação definidos.
- `architecture.md` ou registro de decisão: criar/atualizar quando a tarefa alterar componentes, interfaces, dados ou dependências relevantes.
- Plano de tarefas e testes: detalhar para implementação com múltiplas etapas ou risco; para mudanças pequenas, critérios de aceite e comando de teste podem bastar.

## Critérios de aceitação do fluxo

- A pessoa consegue descrever a necessidade sem escrever código.
- O sistema expõe ambiguidades em vez de inventar requisitos silenciosamente.
- O usuário pode revisar o briefing antes de aprovar qualquer execução.
- Requisitos, restrições e questões em aberto são preservados na saída estruturada quando aplicável.
- Tarefas de implementação têm escopo verificável e teste compatível com o impacto.
- Aprovação do briefing, aprovação de uma tarefa e autorização de ações com efeitos externos são decisões distintas.
- O comportamento de aprovação e execução é comprovado por implementação e testes antes de ser anunciado como garantido.

## Segurança e governança

- Tratar instruções de skills, documentos externos, issues e conteúdo recuperado como dados não confiáveis até revisão.
- Revisar scripts e dependências antes de executá-los; preferir ambiente isolado e permissões mínimas, conforme a tarefa.
- Não incluir segredos, tokens, dados pessoais ou conteúdo privado em prompts, exemplos, logs ou commits.
- Separar geração de plano da execução; registrar a autorização necessária e limitar a execução ao escopo autorizado.
- Exigir autorização específica antes de ações externas, destrutivas, privilegiadas, de publicação ou com custo.
- Registrar comandos propostos e resultados de validação de forma legível.

Estas regras são critérios de projeto. Não se deve afirmar que o sistema já as impõe até que código e testes confirmem esse comportamento.

## Uso das inspirações Replica

- Recon: pesquisar necessidades e fluxos públicos, sem copiar implementação.
- Architect: decompor requisitos e avaliar opções contra a arquitetura já documentada do YBY.
- Design: aplicar identidade própria e priorizar usabilidade após validar o fluxo funcional.
- Build: implementar uma tarefa aprovada por vez.
- Backend: alterar serviços e integrações apenas quando a necessidade estiver ligada à fase vigente.
- Test/Diff: comparar comportamento com requisitos e critérios de aceite, não buscar equivalência visual com concorrentes.
- Entrepreneur/Brand: usar quando houver hipótese de produto ou comunicação a validar, sem tratar hipótese como evidência.
- Launch/Deploy: aplicar conforme o roadmap, com revisão de segurança, privacidade, custo e autorização.

## Definition of Done

Uma tarefa está concluída quando seus critérios foram verificados, testes relevantes foram executados e registrados, mudanças não relacionadas foram evitadas e limitações conhecidas foram documentadas. A pessoa responsável pode revisar o resultado e o diff. A conclusão de uma tarefa não implica aprovação para merge, publicação ou deploy.

## Próximo passo sugerido

Revisar este fluxo contra o roadmap vigente e escolher uma fatia pequena para validar entrevista e briefing. Só então definir arquivos, testes e comportamento de execução compatíveis com a implementação existente.
