# Auditoria SQLite — versão 1

## Estado

Storage isolado. Não integrado ao comando `ask` nesta etapa.
Importar os módulos não cria banco ou diretório.

## Dados permitidos

Identificador aleatório, horários UTC em milissegundos, duração,
backend, modelo solicitado, status e código de saída.

Não registrar prompts, respostas, hashes de conteúdo, mensagens
brutas de erro, cabeçalhos HTTP ou metadados JSON livres.

O backend `ollama` não comprova execução no próprio computador.

## Inicialização

Exige aprovação humana e diretório existente privado.
No Linux, usar diretório do próprio usuário sem acesso de grupo
ou outros; o banco novo é criado com permissão 0600.

`initialize_database()` cria exclusivamente arquivo novo.
`open_existing_database()` não cria banco ausente.
Arquivo parcial após falha de inicialização não é removido
automaticamente: inspecionar e recuperar manualmente.

## Retenção

Política proposta: 30 dias. A limpeza não é executada
automaticamente nesta versão e exige ação explícita e autorizada.

Registros antigos em `started` não são considerados ativos:
significam "sem conclusão registrada".

## Limitações

- `DELETE` não garante apagamento físico imediato de páginas
  livres, WAL ou backups.
- SQLite comum não é criptografado; permissões de arquivo não
  protegem contra processo comprometido com o mesmo usuário.
- Este banco fornece histórico operacional; não é auditoria
  inviolável.
- WAL permite melhor concorrência de leitura, mas continua com
  um único escritor por vez.
