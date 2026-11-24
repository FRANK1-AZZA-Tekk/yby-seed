# YBY SEED — instruções do agente

Python CLI (`yby`). Mapa de módulos: [src/README.md](src/README.md) (caminho do `ask` vs fora do fluxo). Não apagar, reescrever nem expandir módulos fora do escopo sem pedido explícito.

## Como trabalhar

- Comece pelos arquivos citados na tarefa; leia `docs/DEV.md` se o caminho estiver ambíguo. Abra testes, interfaces, imports e chamadores diretamente relacionados quando precisar implementar ou validar. Não varrer `docs/`, módulos fora do fluxo atual nem o repositório inteiro sem justificativa; peça orientação se o contexto necessário ultrapassar materialmente o escopo autorizado.
- Mudança mínima. Não refatorar nem fazer merge sem pedido. Dependências novas só com aprovação explícita; necessidade técnica não equivale a autorização. Antes de propor uma dependência, explique por que a biblioteca padrão e as dependências já no projeto não bastam.
- Documentação: atualize só o que a mudança afeta diretamente (ou diga por que não mudou). Não criar documentos extensos nem reorganizar documentação fora do escopo.
- No fim: `make doctor`, `make lint` e `make test` (ou `make check`). Não vigiar o CI do GitHub.
- Responder com resumo e lista de arquivos; não despejar arquivos inteiros.

## Autorização

- Autorização para editar não autoriza commit, push, abertura de PR, merge, publicação nem deploy. Cada ação exige aprovação explícita; operações destrutivas exigem aprovação específica.

## Fluxo Cursor

Leitura mínima, diff mínimo, dependências, gates locais e publicação: **Como trabalhar**, **Autorização** e `.cursor/rules/yby.mdc`. Planejamento com aceite e testes: **yby.mdc** (*Antes de editar*).

- **Rodada:** uma tarefa completa por vez, com escopo e aceite explícitos; não encadear a próxima tarefa sem pedido.
- **Testes:** cobrir comportamento e falhas relevantes; não enfraquecer testes nem relaxar asserts só para passar. Gates: testes direcionados à mudança e `make doctor` / `make lint` / `make test` (ou `make check`) conforme **Como trabalhar**.
- **Preservação:** manter stash, branches e WIP de outras tarefas intactos; não aplicar nem remover stash sem instrução; não expor segredos (ver **yby.mdc** — Segurança).
- **Git e CI:** commit, push e PR só com autorização; merge só com aprovação explícita e requisitos do repositório cumpridos no **SHA atual** do head — não reutilizar veredito de commit anterior. Consulta pontual ao CI; não vigiar continuamente.
- **Bloqueio:** relatar fatos concretos (comando, saída, SHA, check, conflito); não repetir intenção sem evidência nova.
- **Encerramento:** resumo curto com `RESULTADO`, `ALTERAÇÕES`, `VALIDAÇÃO`, `GIT`, `PENDÊNCIA` (somente o que impede concluir).

## Runtime YBY vs desenvolvimento no Cursor

- **Runtime YBY** (`yby ask`, `run`, roteamento em `src/engine`): local-first (D12), modelo padrão e roteamento conforme `docs/DEV.md` e decisões vigentes; execução de comandos via `src/safety`; sem fallback automático para nuvem nem mudança de permissões por inferência.
- **Desenvolvimento no Cursor**: estas regras não escolhem o modelo da sessão do agente. O terminal do Cursor não passa automaticamente por `src/safety`. Não alterar provedores, modelos ou cobrança; não afirmar uso de Ollama sem evidência de execução. Sandbox e aprovação humana aplicam-se a código arbitrário gerado pelo YBY, não às verificações locais `make *`.

## Convenções

- Seguir o estilo do código tocado. O Ruff é a fonte de estilo (não repetir guia aqui).

Complementos no Cursor: `.cursor/rules/yby.mdc` (escopo e segurança) e `yby-economy.mdc` (economia de recursos).
