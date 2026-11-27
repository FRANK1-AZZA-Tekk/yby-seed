# YBY SEED Constituição

## Princípios Fundamentais

### I. Function over Form
Confiabilidade, simplicidade e código fácil de auditar vêm antes de abstrações prematuras ou de UI complexa. Uma abstração só entra com pelo menos dois usos reais ou necessidade comprovada. A interface existe para dar acesso à função, não para decorá-la.

### II. Local-first e offline-first
O fluxo principal funciona no PC e em navegadores móveis sem depender de nuvem. A nuvem nunca é requisito do fluxo principal; quando existir, é opcional e explícita (alinhado a D3 e D12 em `DECISIONS.md`).

### III. Durabilidade explícita
Toda ação crítica de salvamento só dá confirmação visual ao usuário depois da persistência local real (gravação concluída e verificável). Confirmação otimista é proibida. Se a gravação falhar, o usuário vê um erro claro e o estado não é apresentado como salvo.

### IV. Idempotência obrigatória
Repetir uma ação, recarregar a página, perder a conexão ou fechar o navegador de forma abrupta nunca duplica registros nem corrompe estado. Todo registro tem identidade estável e a escrita é atômica ou recuperável.

### V. Trava de escopo do MVP
Ficam fora do escopo atual, até validação completa em dispositivos reais (Android/Chrome e iPhone/Safari): sincronização em nuvem, múltiplas abas avançadas, voz, wearables, visão computacional e patches autônomos de IA. A trava vale para novas especificações e features; não apaga nem reescreve módulos já existentes no repositório.

### VI. Entrega em camadas pequenas
Cada tarefa é curta e testável isoladamente. Uma camada por vez: a próxima só começa com aprovação explícita do mantenedor.

## Restrições Técnicas e Qualidade

- Dependências novas só com aprovação explícita, justificando por que a biblioteca padrão e as dependências atuais não bastam.
- Nenhum segredo no repositório; dados do usuário permanecem locais.
- A documentação descreve apenas o que funciona hoje; o futuro é marcado como futuro.
- Uma camada só é concluída com `make doctor`, `make lint` e `make test` verdes.

## Segurança, Auditoria e Confirmação Humana

Estas regras valem para o agente orquestrador e para qualquer ferramenta que ele acione. Confirmação humana é uma resposta explícita do mantenedor, na sessão atual, a uma pergunta que descreve a ação; silêncio, aprovação anterior ou instrução genérica não contam. Registro de auditoria é uma linha por evento, em arquivo local somente de acréscimo, com data e hora em UTC, e nunca contém valores de segredo.

### S1. Confirmação antes de escrever ou enviar
- **Regra**: nenhuma escrita em disco fora do escopo já aprovado, nem envio de dados à nuvem, ocorre sem confirmação explícita.
- **Aplica-se a**: criar, alterar ou apagar arquivos, instalar dependências, executar comandos que gravam e qualquer chamada de rede que leve dados do usuário.
- **Exige confirmação**: o(s) caminho(s) afetado(s) ou o destino remoto, com resumo do conteúdo (tamanho ou diff).
- **Auditoria**: ação, caminho ou destino, confirmação recebida (sim ou não) e identificador da camada.
- **Bloqueio**: sem confirmação, a ação é recusada e nada é gravado ou enviado; leitura e simulação (dry-run) continuam permitidas.

### S2. Auditoria de roteamento e de execução
- **Regra**: toda decisão de roteamento entre modelo local e nuvem, e toda execução de ferramenta, gera registro antes de acontecer.
- **Aplica-se a**: a escolha entre local e nuvem (alinhada a D3 e D12 em `DECISIONS.md`) e a cada chamada de ferramenta ou comando.
- **Exige confirmação**: toda rota para a nuvem, nos termos de S1; rota local não exige.
- **Auditoria**: decisão (local ou nuvem), modelo, motivo (custo, latência, sensibilidade ou flag explícita como `--heavy`), ferramenta, argumentos com segredos mascarados e resultado (sucesso, falha ou recusa).
- **Bloqueio**: se o registro não puder ser gravado, a execução ou o roteamento não acontece; não há fallback silencioso para a nuvem.

### S3. Firmware somente em dispositivo cadastrado
- **Regra**: escrita ou atualização de firmware só ocorre em dispositivo previamente cadastrado e validado pelo usuário.
- **Aplica-se a**: qualquer gravação, flash ou atualização em hardware. Não habilita firmware no MVP: o Princípio V continua valendo e esta regra é pré-condição para quando firmware existir.
- **Exige confirmação**: cada gravação, mostrando o identificador cadastrado do dispositivo, a versão atual e a versão de destino, mesmo para dispositivo já cadastrado.
- **Auditoria**: identificador do dispositivo, versão antes e depois, hash do artefato, confirmação e resultado.
- **Bloqueio**: dispositivo fora do cadastro, não validado ou com identificador que não confere é recusado; não há cadastro automático por inferência.

### S4. Dados sensíveis permanecem locais
- **Regra**: chaves de API, credenciais, tokens, dados pessoais e segredos permanecem locais sempre que possível.
- **Aplica-se a**: prompts, contexto, logs, auditoria, commits, PRs e qualquer payload enviado a modelo em nuvem.
- **Exige confirmação**: envio excepcional de dado sensível à nuvem quando não houver alternativa local, com a lista do que será enviado (S1).
- **Auditoria**: categoria do dado e destino, nunca o valor; segredos aparecem mascarados.
- **Bloqueio**: conteúdo com padrão de segredo é removido ou mascarado antes de sair da máquina; sem confirmação, o envio é recusado. Reforça, sem substituir, "Nenhum segredo no repositório" em Restrições Técnicas e Qualidade.

## Fluxo de Desenvolvimento

- Sequência: especificação, plano, tarefas, implementação de uma camada por vez.
- Toda camada que persiste dados tem testes de durabilidade e idempotência: repetição da ação, recarga e interrupção no meio da gravação.
- Diff mínimo, sem refatoração fora do escopo da camada.

## Governança

Esta constituição prevalece sobre outras práticas do projeto. Emendas exigem proposta escrita e aprovação do mantenedor. O versionamento é semântico: MAJOR para remover ou redefinir princípio, MINOR para adicionar ou ampliar princípio ou seção, PATCH para esclarecimentos. Todo plano e todo PR devem verificar conformidade com os princípios acima; desvios precisam de justificativa explícita.

**Version**: 1.1.0 | **Ratified**: 2026-11-27 | **Last Amended**: 2026-11-27
