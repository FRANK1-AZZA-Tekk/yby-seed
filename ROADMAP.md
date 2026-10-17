# Roadmap — YBY SEED

## Princípio

Cada fase só é considerada concluída quando seu critério de saída for testável e verificável.

## Fases

| Fase | Entregável | Critério de saída | Status |
|---|---|---|---|
| F0 — Fundação | Repositório organizado, configuração, SQLite, auditoria e CLI yby ask | yby ask "oi" responde via Ollama e registra evento completo | Em andamento |
| F1 — Cérebro | Classificador de intenção, roteador LiteLLM e controle de custo | Acurácia igual ou superior a 85% em dataset de 60 pedidos PT-BR; teto diário bloqueia nuvem corretamente | Pendente |
| F2 — Conversa útil | Memória SQLite + FTS5, entrevistador e plano aprovável | Pedido vago gera no máximo 3 perguntas e resulta em plano em PT-BR | Pendente |
| F3 — Construtor | Desenvolvedor, ferramentas de arquivo, workspace isolado e Git | Pedido cria projeto somente dentro de workspaces/<slug>/; escrita externa é bloqueada | Pendente |
| F4 — Painel | FastAPI, HTMX e SSE | Uso diário por 7 dias sem necessidade de terminal | Pendente |
| F5 — Escala | LiteLLM Proxy, PostgreSQL, Revisor, Pesquisador e sandbox Docker | Multi-projeto, custo por projeto e execução isolada | Futuro |
| F6 — Borda | MQTT/HTTP, ESP32-S3 e voz | Comando por voz chega ao backend e retorna resposta | Futuro |

## MVP

O MVP é concluído no fim da F4.

Antes disso, o projeto é protótipo. Depois disso, torna-se produto pessoal utilizável.

## Fora do MVP

Não implementar agora:

- Nove agentes.
- Mem0.
- Supabase ou PostgreSQL.
- LiteLLM Proxy.
- Docker no fluxo principal.
- Voz.
- MQTT.
- BLE.
- ESP32-S3.
- Visão computacional.
- Autenticação multiusuário.

## Ordem de módulos

1. Configuração, banco e auditoria.
2. Roteador com provider fake para testes sem custo.
3. Classificador com dataset rotulado.
4. Orquestrador como máquina de estados.
5. Memória SQLite + FTS5.
6. Entrevistador e arquiteto.
7. Ferramentas de arquivo e criação de projeto.
8. Interface web.
