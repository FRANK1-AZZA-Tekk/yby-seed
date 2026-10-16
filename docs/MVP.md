# MVP — YBY SEED

**Fase atual:** Fase 1 — Núcleo local  
**Fonte da verdade:** [Blueprint Técnico v3.1](BLUEPRINT_YBY_SEED_v3.1.md)

## Objetivo

Entregar um núcleo local-first funcional no PC, capaz de receber um pedido em português, aplicar regras de segurança e roteamento, consultar o Ollama e devolver uma resposta.

## Escopo incluído

- Entrada por texto em português do Brasil.
- Gatekeeper determinístico.
- Router com regras locais.
- Um modelo Ollama 4B.
- Memória local com SQLite e `sqlite-vec`.
- Registro de eventos, rota, latência e custo.
- Modo offline e modo privado.
- CLI e health check.
- Testes das regras críticas.

## Fluxo do MVP

```text
Usuário
  → Gatekeeper
  → Router
  → Ollama local
  → Resposta
  → Registro em SQLite
```

## Fora do escopo

- Entrevista de criação de projetos.
- Council e geração de artefatos.
- Integração com OpenRouter.
- Dashboard web.
- SSE.
- Voz.
- Mobile.
- Wearables.
- Execução automática de código.
- Docker como caminho principal.

## Regras críticas

- Comandos como `parar`, `cancelar` e `modo offline` só são reconhecidos quando a mensagem inteira corresponde ao comando.
- “como faço para parar de fumar” não é comando.
- Dado sensível força rota local.
- Modo offline impede qualquer chamada de nuvem.
- O teto mensal de US$ 10 prevalece sobre o teto diário.

## Critérios de aceite

- `parar` interrompe o fluxo ativo.
- `modo offline` força rota local.
- CPF, chave privada ou token longo força rota local.
- Toda chamada registra modelo, rota, latência e custo.
- O sistema funciona sem Docker.
- Os testes T01 a T04 do blueprint passam.

## Próximo passo

Após o núcleo estável, iniciar a Fase 2: LangGraph, entrevista de 30 perguntas, Council em uma chamada e geração de artefatos para o Cursor Pro.
