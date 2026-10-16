# Política de transporte Ollama — MVP

## Destinos permitidos

- `localhost`, canonicalizado para `127.0.0.1`.
- `127.0.0.1`.
- `::1`, usando URL IPv6 com colchetes.

Outros hosts são rejeitados antes de criar a sessão HTTP.
A porta deve ser um inteiro entre 1 e 65535.

Esta política exclui endpoints LAN e servidores Ollama remotos.

## Requisições

Todas as operações públicas do cliente usam:

- sessão com `trust_env=False`;
- `allow_redirects=False`;
- rejeição explícita de status HTTP 300–399.

Não há repetição automática nem fallback de nuvem.

## CLI

- `ask`: saída 6 para bloqueio de política.
- `health`: saída 1 para bloqueio de política.
- Falha técnica do cliente em `ask` mantém saída 7.

Comandos reconhecidos são tratados antes de validar o endpoint.

## Compatibilidade

`localhost` passa a usar IPv4 explicitamente.
Se o daemon estiver acessível somente em IPv6, configurar `::1`.

`chat` e `pull` mantêm resultados legados para falhas comuns,
mas não engolem erros de política.

## Limites

Esta política restringe apenas os destinos HTTP deste cliente.
Não é um firewall: não impede conexões próprias do daemon Ollama,
não protege contra processo comprometido com o mesmo usuário
e não torna `pull()` uma operação offline.
