# Política de permissões — YBY SEED

## Objetivo

Garantir que o YBY SEED seja útil sem colocar arquivos, contas, rede ou sistema do usuário em risco.

## Níveis de permissão

### 1. Leitura

- Leitura de arquivos dentro do workspace autorizado.
- Leitura de configuração do próprio YBY SEED.
- Leitura de memória local.

### 2. Escrita

- Criação e modificação de arquivos somente dentro de workspaces/<slug>/.
- Cada projeto possui workspace isolado.
- O sistema deve criar o workspace com git init.
- Escrita fora do workspace é bloqueada.
- Path traversal, como ../../, deve ser rejeitado.
- Symlinks que apontem para fora do workspace devem ser rejeitados.

### 3. Execução, rede e ações externas

Exigem aprovação por ação:

- Executar comandos no sistema.
- Instalar dependências.
- Acessar internet.
- Enviar mensagens ou e-mails.
- Criar, modificar ou apagar recursos em serviços externos.
- Enviar dados para modelo na nuvem.
- Gastar créditos de API.

## Regras obrigatórias

- Nenhuma ação de nível 3 pode ser executada automaticamente.
- A aprovação deve mostrar descrição em português, escopo exato e expiração.
- Toda permissão concedida ou negada deve gerar evento de auditoria.
- O usuário deve poder revogar permissões a qualquer momento.
