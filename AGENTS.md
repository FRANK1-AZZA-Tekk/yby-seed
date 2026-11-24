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

## Runtime YBY vs desenvolvimento no Cursor

- **Runtime YBY** (`yby ask`, `run`, roteamento em `src/engine`): local-first (D12), modelo padrão e roteamento conforme `docs/DEV.md` e decisões vigentes; execução de comandos via `src/safety`; sem fallback automático para nuvem nem mudança de permissões por inferência.
- **Desenvolvimento no Cursor**: estas regras não escolhem o modelo da sessão do agente. O terminal do Cursor não passa automaticamente por `src/safety`. Não alterar provedores, modelos ou cobrança; não afirmar uso de Ollama sem evidência de execução. Sandbox e aprovação humana aplicam-se a código arbitrário gerado pelo YBY, não às verificações locais `make *`.

## Convenções

- Seguir o estilo do código tocado. O Ruff é a fonte de estilo (não repetir guia aqui).

Complementos no Cursor: `.cursor/rules/yby.mdc` (escopo e segurança) e `yby-economy.mdc` (economia de recursos).
