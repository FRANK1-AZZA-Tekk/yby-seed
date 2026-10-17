# Política de memória — YBY SEED

## Decisão do MVP

A memória do YBY SEED será local.

No MVP, usar:

- SQLite como banco.
- FTS5 para busca textual.
- Histórico auditável.
- Resumo rolante para conversas longas.

## Mem0

Mem0 não deve ser usado no MVP.

Motivo: configurações padrão podem enviar conteúdo do usuário para provedores externos, conflitando com o princípio de privacidade por padrão.

Mem0 só poderá ser reintroduzido se:

- O LLM usado pela memória for local.
- Os embeddings forem locais.
- O vector store for local.
- Nenhum dado pessoal sair do dispositivo sem autorização explícita.
- Toda chamada externa for auditada.

## Dados sensíveis

Antes de enviar qualquer contexto para nuvem, o sistema deve detectar e avisar sobre:

- CPF.
- E-mail.
- Telefone.
- Senhas ou tokens.
- Endereços.
- Dados financeiros.
- Informações médicas.

O envio só ocorre após confirmação explícita do usuário.

## Direitos do usuário

O usuário deve poder:

- Ver o que está memorizado.
- Buscar memórias.
- Corrigir memórias.
- Apagar memórias específicas.
- Apagar toda a memória local.
- Exportar a memória em formato legível.
