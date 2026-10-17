# Política de execução — YBY SEED

## Estado padrão

Execução de comandos no sistema hospedeiro está **desligada por padrão**.

O YBY SEED pode planejar comandos, mas não pode executá-los sem aprovação explícita.

## Quando habilitado

A execução deve seguir estas regras:

- Allow-list de comandos permitidos.
- Bloqueio de comandos destrutivos, como `rm -rf`, `mkfs`, `dd`, `shutdown` e similares.
- Timeout obrigatório.
- Bloqueio de acesso à rede por padrão.
- Execução apenas dentro do workspace autorizado.
- Captura de saída, erro e código de retorno.
- Registro completo na auditoria.

## Sandbox

Na fase futura de escala, comandos devem ser executados em container Docker com:

- Sistema de arquivos isolado.
- Rede desabilitada ou restrita.
- Limites de CPU e memória.
- Usuário sem privilégios.
- Volume somente com o workspace do projeto.

## Proibições

O agente não pode:

- Executar código fora do workspace.
- Acessar arquivos do usuário sem permissão.
- Instalar pacotes sem aprovação.
- Modificar configuração do sistema.
- Enviar dados para fora sem autorização.
- Executar comandos em cadeia sem que cada comando seja auditado.
