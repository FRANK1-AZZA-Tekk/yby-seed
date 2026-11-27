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

## Fluxo de Desenvolvimento

- Sequência: especificação, plano, tarefas, implementação de uma camada por vez.
- Toda camada que persiste dados tem testes de durabilidade e idempotência: repetição da ação, recarga e interrupção no meio da gravação.
- Diff mínimo, sem refatoração fora do escopo da camada.

## Governança

Esta constituição prevalece sobre outras práticas do projeto. Emendas exigem proposta escrita e aprovação do mantenedor. O versionamento é semântico: MAJOR para remover ou redefinir princípio, MINOR para adicionar ou ampliar princípio ou seção, PATCH para esclarecimentos. Todo plano e todo PR devem verificar conformidade com os princípios acima; desvios precisam de justificativa explícita.

**Version**: 1.0.0 | **Ratified**: 2026-11-27 | **Last Amended**: 2026-11-27
