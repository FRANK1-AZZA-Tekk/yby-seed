# YBY SEED — instruções do agente

Python CLI (`yby`). Núcleo atual: `src/engine`, `src/safety`, `src/actions`, `src/memory`, `src/voice` e a plataforma.
O restante em `src/` é legado: não apagar, reescrever nem expandir sem pedido explícito.

## Como trabalhar
- Ler só os arquivos citados no pedido, e `docs/DEV.md` se o caminho estiver ambíguo.
  Não varrer `docs/` nem o legado por padrão.
- Mudar o mínimo. Não refatorar, não adicionar dependências, não fazer merge.
- No fim: `make doctor`, `make lint` e `make test` (ou `make check`). Não vigiar o CI do GitHub.
- Responder com resumo e lista de arquivos; não despejar arquivos inteiros.

## Convenções
- Seguir o estilo do código tocado. O Ruff é a fonte de estilo (não repetir guia aqui).

## Harness engineering

Antes de iniciar uma tarefa não trivial, o agente deve tratar o pedido como um contrato verificável.

1. Leia `CONTRACT.md` antes de agir.
2. Consulte apenas os documentos necessários para a tarefa atual.
3. Registre progresso, decisões, bloqueios e evidências em `PROGRESS.md`.
4. Execute os sensores definidos no contrato antes de declarar conclusão.
5. Nunca altere arquivos fora do escopo definido no contrato.
6. Em caso de dúvida arquitetural, de segurança ou de hardware, pare e peça decisão humana.

### Mapa de documentos

| Área | Arquivo / pasta | Quando consultar |
|---|---|---|
| Contrato da tarefa | `CONTRACT.md` | Sempre, antes de iniciar |
| Estado do trabalho | `PROGRESS.md` | Antes de começar e após cada etapa |
| Estado estruturado | `config/agent/state.json` | Ao validar escopo, sensores e limites |
| Arquitetura geral | `ARCHITECTURE.md` | Ao criar ou alterar módulos |
| Núcleo YBY | `docs/YBY_CORE.md` | Ao mexer em orquestração, agentes ou fluxo |
| Roadmap | `ROADMAP.md` | Ao definir prioridade ou escopo |
| Decisões | `DECISIONS.md` | Antes de mudar arquitetura |
| Segurança | `SECURITY.md` | Ao lidar com chaves, rede, permissões ou dados |
| Hardware | `HARDWARE_SPEC.md` | Ao alterar firmware, sensores ou wearable |
| Testes | `tests/` | Ao implementar ou corrigir código |
| Scripts | `scripts/` | Ao usar automações existentes |
| Skills | `skills/` | Ao criar ou alterar habilidades do agente |

### Regras de firmware e hardware

- Não modifique pinos, periféricos, OTA, BLE, Wi-Fi ou MQTT sem validação humana.
- Não execute comandos de flash, erase, upload ou reset sem aprovação.
- Não altere configurações de energia sem medir impacto.
- Mantenha firmware e documentação sincronizados.

### Regras de IA

- Não envie segredos, chaves, dados pessoais ou conteúdo sensível para provedores externos.
- Prefira modelo local primeiro quando a tarefa permitir.
- Use fallback de nuvem apenas quando necessário e autorizado.
- Não permita que a IA acesse diretamente GPIO, sensores ou atuadores sem camada de controle.

### Fluxo padrão

```text
CONTRACT.md
   ↓
ler apenas documentos relevantes
   ↓
planejar em passos pequenos
   ↓
implementar
   ↓
executar sensores
   ↓
atualizar PROGRESS.md
   ↓
commit
   ↓
relatório final
```

### Definição de falha

A tarefa é considerada falha se o agente:

- Alterar arquivos fora do escopo.
- Pular sensores obrigatórios.
- Declarar conclusão sem evidência verificável.
- Repetir o mesmo erro duas vezes sem nova informação.
- Atingir limite de tempo, custo ou tentativas.
- Executar ação irreversível sem aprovação humana.
