# Decisões — YBY SEED

## D1 — PC-first

A fase atual foca exclusivamente no PC Hub. Mobile e ESP32 ficam para fases posteriores.

## D2 — Documentação antes de código

Inventário real de repositórios e arquitetura por domínios antes de qualquer código novo.

## D3 — Local-first

Ollama local primeiro; OpenRouter apenas quando houver ganho real de qualidade, pesquisa ou capacidade.

## D4 — Hardware alvo

Perfil inicial: GTX 1650 com 4 GB de VRAM. Um modelo local por vez.

O sistema deve usar perfis de hardware em config.yaml, começando por:

- leve: CPU ou GPU com pouca VRAM.
- medio: 4–8 GB de VRAM.
- forte: 12 GB ou mais de VRAM.

## D5 — MVP sem Docker no núcleo

O núcleo do YBY SEED deve funcionar sem containers. Docker entra apenas quando houver necessidade real de isolamento de execução.

## D6 — Automações seguras

Toda skill começa em dry-run e só executa após confirmação explícita do usuário.

## D7 — Consolidação de repositórios

Materiais de YBY, YBY Zero e outros projetos são revisados e unificados no YBY SEED quando fizer sentido técnico.

## D8 — Sem Mem0 no MVP

Mem0 não será usado no MVP porque pode enviar conteúdo do usuário para provedores externos por padrão.

A memória inicial será local, usando SQLite com FTS5. Mem0 só poderá retornar em fase futura, configurado com LLM e embeddings locais.

## D9 — Permissões em três níveis

1. Leitura: permitida dentro do escopo autorizado.
2. Escrita: permitida somente dentro do workspace do projeto, com confirmação inicial por projeto.
3. Execução, acesso fora do workspace ou rede: exige aprovação por ação.

## D10 — Controle de custo obrigatório

Toda chamada a modelo na nuvem deve ter estimativa de custo antes da execução.

O sistema deve respeitar teto por pedido e teto diário. Ao atingir o limite, o roteador deve usar modelo local e registrar o motivo.

## D11 — Execução desligada por padrão

Execução de comandos no sistema hospedeiro fica desligada por padrão.

Se habilitada, deve usar allow-list, timeout, bloqueio de rede e confirmação por ação. Sandbox com Docker é uma evolução futura.

## D12 — Orquestrador simples primeiro

O MVP usa uma máquina de estados em Python puro, com contratos Pydantic.

LangGraph ou Agno só entram quando houver múltiplos fluxos ramificados e necessidade real de retomada de estado.

## D13 — Idioma

Interface, documentação, prompts e mensagens de usuário em português do Brasil.

Código, identificadores, nomes de arquivos e variáveis em inglês.
