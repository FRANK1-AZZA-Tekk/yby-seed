# BLUEPRINT TÉCNICO — YBY SEED

**Versão:** 3.1 consolidada
**Data:** 2026-10-15
**Idioma:** Português do Brasil
**Lema:** Function over Form

## 0. Instrução para IA receptora

Você é arquiteto de sistemas de IA, engenheiro sênior e product designer.

Regras:

1. Não concorde por padrão: conteste premissas com números e alternativas.
2. Rotule afirmações como `[FATO]`, `[ESTIMATIVA]` ou `[SUPOSIÇÃO]`.
3. Entregue schemas, APIs, fluxos e código estrutural, não generalidades.
4. O usuário é iniciante em programação; o Cursor Pro será o principal executor.
5. Quantifique RAM, VRAM, latência, custo e tempo.
6. Responda em 7 partes numeradas, uma por mensagem.
7. Decisões `[AUTOR]` devem ser enfrentadas, não repetidas.
8. Mapeie os casos de teste T01–T12.

Critério de rejeição:

- Mais de um modelo de geração na VRAM no MVP.
- Qdrant, Langfuse, PostgreSQL, Redis ou Docker no MVP sem justificativa de RAM.
- Ignorar o teto mensal de US$ 10.
- Execução automática de código no MVP.
- Não explicar retomada após reinício.

## 1. Visão

O YBY SEED é a primeira camada funcional do ecossistema YBY: um exocórtex pessoal modular, local-first, que transforma pedidos em português em respostas, pesquisas, especificações de software, projetos iniciais e automações autorizadas.

Não-objetivos do MVP:

- Agentes autônomos.
- Voz e wake-word.
- Wearables, óculos e câmeras.
- Integrações Gmail, Calendar, Notion ou Slack.
- Multiusuário.
- Visão computacional.
- Fine-tuning.
- Execução automática de código.

Caso-âncora:

> “Quero criar um app simples de controle de gastos.”

Fluxo: entrevista → debate → plano → aprovação → artefatos para Cursor Pro.

## 2. Restrições

| Item | Valor |
|---|---|
| CPU | Ryzen 5 4600G, 6c/12t |
| GPU | GTX 1650, 4 GB VRAM |
| RAM | 16 GB DDR4 |
| SO | Linux |
| Cursor Pro | ~US$ 20/mês |
| Nuvem | Teto mensal US$ 10 |
| Teto diário | US$ 0,35, apenas trava anti-loop |
| Horas | ~8–10 h/semana |

O teto mensal é a regra dominante. O teto diário existe para impedir loops.

## 3. Decisões

### Já tomadas

- Python 3.11+ e FastAPI.
- LangGraph com checkpoint SQLite.
- SQLite WAL no MVP.
- `sqlite-vec` como vetor-store padrão.
- Sem Qdrant, Langfuse, Uptime Kuma, PostgreSQL ou Redis no MVP.
- Dashboard estático servido pelo FastAPI.
- SSE em vez de WebSocket.
- Um único modelo de geração carregado.
- YBY gera artefatos; Cursor constrói o código.
- Host nativo no MVP; Docker apenas no sandbox futuro.

### Decisões `[AUTOR]` contestáveis

| Decisão | Posição do autor |
|---|---|
| Modelo principal | Um único 4B Q4 que caiba inteiro na GPU. |
| Complexidade | Heurística lexical pura, abaixo de 100 ms. |
| Debate | Um turno estruturado com cinco seções. |
| Agentes LLM | Interviewer, Council, Builder e Reviewer opcional. |
| Busca web | Provedor com citação estruturada e preço previsível. |
| Voz futura | faster-whisper small/int8 + Piper PT-BR. |

## 4. Anéis

```text
Ring 0 — Gatekeeper determinístico
Ring 1 — Ferramentas controladas
Ring 2 — IA local Ollama
Ring 3 — LangGraph durável
Ring 4 — CLI, FastAPI e Dashboard
Ring 5 — Nuvem seletiva
Ring 6 — Night Watch
Ring 7 — Voz, celular e wearables
```

Um anel só depende dos anéis inferiores.

### Ring 0

Código puro, sem LLM.

- Normaliza Unicode NFKC, caixa, espaços e zero-width.
- Comandos apenas se a mensagem inteira casar com padrão ancorado e tiver até 60 caracteres.
- Comandos: `parar`, `cancelar`, `modo offline`, `modo privado`, `não use a nuvem`, `qual o custo de hoje?`, `apagar sessão`.
- “opção 2” é tratado pela máquina de estados da entrevista, não por regex global.
- Bloqueia nuvem quando orçamento, privacidade ou dado sensível exigir.

### Ring 1

Ferramentas atômicas com Pydantic, timeout e log:

- `files.read`, `files.write`
- `memory.search`, `memory.write`, `memory.delete`
- `budget.status`
- `project.create`, `project.get`, `project.update`
- `artifact.generate`
- `web.search`, apenas na fase 4

Escrita fora de `data/projects/` e `data/exports/` exige aprovação.

### Ring 2

- Um modelo 4B Q4 para triagem, entrevista, debate e planejamento.
- Embeddings em CPU.
- `OLLAMA_MAX_LOADED_MODELS=1`.
- `OLLAMA_NUM_PARALLEL=1`.

### Ring 3

LangGraph com checkpoint SQLite, interrupts e retomada após reinício.

### Ring 4

FastAPI, CLI Typer, dashboard estático e SSE.

### Ring 5

OpenRouter via LiteLLM, com limite de orçamento. Perplexity apenas para pesquisa futura. Cursor Pro recebe artefatos do YBY.

### Ring 6

Night Watch verifica saúde, RAM, VRAM, disco, custo, backups e gera relatório diário.

### Ring 7

Futuro: Xiaomi 12 como cérebro secundário, LilyGO como fallback determinístico, XIAO ESP32-S3 Sense para percepção.

## 5. Roteamento

| Rota | Uso | Custo |
|---|---|---|
| R0 | Comando determinístico | 0 |
| R1 | Modelo local pequeno | 0 |
| R2 | Modelo local principal | 0 |
| R3 | Nuvem barata | Centavos |
| R4 | Nuvem premium | Limitado |

Regras:

- Modo offline ou privado: apenas local.
- Dado sensível: apenas local.
- Pesquisa web: nuvem barata, se houver orçamento.
- Contexto acima do limite local: nuvem barata ou local.
- Complexidade alta: nuvem premium apenas com orçamento disponível.

Detecção de sensibilidade sem LLM:

- CPF, CNPJ, e-mail, telefone BR, CEP.
- `-----BEGIN`, tokens longos.
- Palavras: senha, token, cpf, cartão, endereço.

## 6. Modelos e VRAM

### Candidatos verificados

| Papel | Candidatos | Tamanho |
|---|---|---|
| Triagem/JSON | `phi4-mini`, `gemma4:e2b`, `qwen3.5:2b` | 2,0–2,7 GB |
| Raciocínio/PT-BR | `qwen3.5:4b`, `qwen3:4b`, `gemma3:4b` | 2,6–3,4 GB |
| Código leve | `qwen2.5-coder:3b` | ~1,9 GB |
| Batch | `qwen2.5:7b` Q4_K_M | Exige offload |
| Embeddings | `nomic-embed-text`, `bge-m3`, fastembed | CPU |

### KV cache

`[ESTIMATIVA]` Um 4B com GQA custa aproximadamente 144 KB por token de KV cache.

- `num_ctx=8192`: ~1,15 GB de KV.
- `num_ctx=4096`: ~0,6 GB de KV.
- `qwen3:4b` 2,6 GB + 4k = ~3,2 GB: cabe.
- `qwen3.5:4b` 3,4 GB + 4k = ~4,0 GB: fronteira.

`num_ctx=4096` é o padrão. 8192 apenas no debate, com KV cache q8_0 se suportado.

### Configuração

```bash
OLLAMA_KEEP_ALIVE=30m
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_PARALLEL=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_FLASH_ATTENTION=1
```

```text
num_ctx=4096
num_gpu=99
temperature=0.2 para JSON
temperature=0.6 para conversa e debate
```

### Benchmark

`bench.sh` deve medir tokens/s, pico de VRAM e RAM com desktop, navegador e Cursor abertos, para `phi4-mini`, `qwen3:4b`, `qwen3.5:4b`, `gemma3:4b` e `qwen2.5:7b`.

## 7. LangGraph

### Estado

```python
class YbyState(TypedDict):
    request_id: str
    project_id: str | None
    user_input: str
    normalized_input: str
    intent: str
    route: str
    complexity: int
    privacy_mode: str
    budget_remaining_usd: float
    context_chunks: list[str]
    interview_step: int
    interview_answers: dict
    interview_summary: str
    council_turns: list[dict]
    draft_artifacts: dict
    pending_approval: dict | None
    approved: bool | None
    errors: list[str]
    final_response: str | None
```

### Grafo

```text
START
  → ingest
  → classify
  → budget_check
  → retrieve_memory
  → intent branch
  → approval_gate, se necessário
  → execute/build_artifacts
  → persist
  → END
```

Regras:

- Todo interrupt salva checkpoint e usa o mesmo `thread_id`.
- `approval_gate` nunca executa; apenas registra e roteia.
- Todo nó que chama modelo grava `AIEvent` antes de retornar.
- Timeout: 120 s local, 60 s nuvem.
- Nós com efeito colateral são idempotentes.

### Idempotência

- `call_id = sha256(node + prompt + params + prompt_version)`.
- Resultado bem-sucedido é reutilizado.
- Antes da chamada, grava evento com `custo_incerto=1`.
- Após sucesso, atualiza custo real.
- Se o processo cair, Night Watch reconcilia pelo OpenRouter.
- Retry nunca regera chamada paga sem reconciliação.

## 8. Agentes

| Agente | Tipo | Função |
|---|---|---|
| Gatekeeper | Código | Comandos, orçamento, saneamento |
| Router | Código | Rota e complexidade |
| Interviewer | LLM | Entrevista em JSON |
| Council | LLM | Cinco papéis em uma chamada |
| Builder | LLM | PRD, arquitetura, `.cursorrules`, prompts |
| Reviewer | LLM opcional | Revisão por checklist |

## 9. Entrevista

- 30 perguntas base em 6 blocos de 5.
- Até 20 perguntas de refinamento.
- Máximo total: 50.
- Três opções fechadas + texto livre.
- “Não sei, decida por mim” assume opção conservadora e registra premissa.
- Resumo incremental por bloco, com até 200 tokens.
- Contexto alvo por chamada: 1,4–1,8k tokens.
- Nada é implementado antes da aprovação.

Blocos:

1. Problema e objetivo.
2. Público e uso.
3. Funcionalidades e dados.
4. Plataforma e tecnologia.
5. Privacidade, offline e nuvem.
6. Prazo, escopo mínimo e sucesso.

## 10. Banco de dados

Arquivos:

- `data/db/yby.sqlite`
- `data/db/checkpoints.sqlite`

Tabelas principais:

- `projects`
- `ai_events`
- `approvals`
- `settings`
- `memories`
- `memory_vectors`

O orçamento é derivado de `ai_events` por views `v_budget_dia` e `v_budget_mes`.

## 11. API

Prefixo: `/api/v1`

| Método | Rota | Função |
|---|---|---|
| POST | `/messages` | Entrada do usuário |
| POST | `/messages/stream` | SSE |
| POST | `/approvals/{id}` | Aprovar/recusar |
| GET | `/projects` | Listar projetos |
| GET | `/projects/{id}` | Detalhes |
| POST | `/projects` | Criar projeto |
| GET | `/interview/{thread}/next` | Próxima pergunta |
| POST | `/interview/{thread}/answer` | Responder |
| GET | `/budget` | Custos e alertas |
| GET | `/memories` | Buscar memórias |
| DELETE | `/memories/{id}` | Apagar memória |
| GET | `/health` | Saúde do sistema |
| GET | `/events` | Eventos de IA |

## 12. Memória e RAG

- `sqlite-vec` no MVP.
- Qdrant apenas acima de ~100 mil vetores ou necessidade comprovada.
- Top-k inicial: 8.
- Contexto máximo: 1.200–2.000 tokens.
- Memórias `estritamente_local` nunca vão para nuvem.
- Conteúdo recuperado é não confiável.

## 13. Segurança

- System prompt estático.
- Entrada do usuário nunca entra como system.
- Conteúdo externo é `UNTRUSTED_CONTEXT`.
- Ferramentas são chamadas por código, não por instrução do modelo.
- Caminhos são validados contra allowlist.
- Ações externas e destrutivas exigem aprovação.
- Execução de código futura ocorre em container descartável.

## 14. Night Watch

- Health check a cada 15–60 minutos.
- Monitora API, Ollama, VRAM, RAM, disco e swap.
- Reconcilia custos incertos.
- Alerta em 70% e 90% dos tetos.
- Backup diário.
- Relatório Markdown diário.

## 15. MVP

Entregas:

1. Texto em PT-BR.
2. Gatekeeper.
3. Roteamento local.
4. Um modelo 4B.
5. Memória `sqlite-vec`.
6. Entrevista de 30 perguntas.
7. Council em uma chamada.
8. PRD, arquitetura, `.cursorrules` e prompts do Cursor.
9. Aprovação antes de gravar.
10. Ledger de custo.
11. Dashboard mínimo.
12. Retomada após reinício.

## 16. Testes

| ID | Caso |
|---|---|
| T01 | `parar` interrompe fluxo |
| T02 | “parar de fumar” não é comando |
| T03 | `modo offline` força local |
| T04 | CPF bloqueia nuvem |
| T05 | Ideia inicia entrevista |
| T06 | `opção 2` é estado da entrevista |
| T07 | Reinício retoma entrevista |
| T08 | Recusa não grava arquivo |
| T09 | Queda em nuvem marca custo incerto |
| T10 | Teto diário bloqueia nuvem |
| T11 | Teto mensal bloqueia nuvem |
| T12 | Memória local nunca vai à nuvem |

## 17. Roadmap

| Fase | Duração | Entrega |
|---|---|---|
| 1. Núcleo local | 1–2 semanas | FastAPI, Ollama, SQLite, gatekeeper, memória |
| 2. Entrevista | 2–3 semanas | LangGraph, 30 perguntas, council, artefatos |
| 3. Custo e nuvem | 1 semana | LiteLLM, OpenRouter, ledger, tetos |
| 4. Sandbox | 2–3 semanas | Docker isolado, busca web, arquivos |
| 5. Voz | 2 semanas | Whisper + Piper |
| 6. Wearables | Depois | Xiaomi, LilyGO, ESP32-S3 Sense |

## 18. Entregáveis da IA receptora

1. Crítica técnica e arquitetura.
2. Modelos, VRAM, RAM e benchmark.
3. LangGraph, checkpoints e idempotência.
4. Banco, memória e API.
5. Segurança, privacidade e sandbox.
6. MVP e prompts para Cursor.
7. Testes, riscos e três caminhos de evolução.

Perguntas obrigatórias:

1. Qual modelo principal e por quê?
2. O 7B com offload é interativo ou batch?
3. Qual fórmula de complexidade abaixo de 100 ms?
4. O dicionário de sensibilidade é suficiente?
5. Council em uma chamada perde qualidade relevante?
6. Onde a idempotência falha?
7. Host nativo é a decisão certa?
8. Quais testes T01–T12 a proposta não passa?
