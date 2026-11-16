# RAG local — desenho (MVP YBY SEED)

Status: **Tarefas 1–3** (fundação, ingestão, recuperação). Ferramentas (T4) e agente (T5) são etapas seguintes.

Alinhamento: D1 (PC-first), D4/D5 (local, sem Docker no núcleo), D8 (vault), D10 (shell separado), [`ROADMAP.md`](../ROADMAP.md) P1.

## Arquitetura

```text
Corpus allowlisted (docs/, data/knowledge/, vault opcional)
        ↓ ingestão (T2)
Chroma persistente em data/chroma/ + manifest SHA-256
        ↓ embeddings Ollama (nomic-embed-text)
        ↓ consulta (T3)
search_knowledge (T4) → agente mínimo (T5)
```

- **Vector store:** Chroma embedded (`data/chroma/`), coleção `yby_knowledge` (configurável).
- **Embeddings:** Ollama local, padrão `nomic-embed-text` — sem APIs pagas neste pipeline.
- **Legado:** `src/rag/` (AST, Qdrant no `docker-compose.yml`) permanece; novo código em `src/yby/rag/`.
- **Fora do `ask`:** o núcleo `yby.py ask` não depende do RAG neste MVP.

## Fluxo de ingestão (T2) — implementado

Módulos: `loaders.py`, `chunking.py`, `embedder.py`, `ingest.py`.

1. Somente arquivos sob `data/knowledge` (sem `../`, sem symlinks de escape).
2. Tipos: `.md`, `.txt`, `.pdf` (`.docx` reservado).
3. Limite: `YBY_RAG_MAX_FILE_BYTES` (padrão 10 MiB), `YBY_RAG_MAX_FILES_PER_RUN` (100).
4. `content_hash` SHA-256; manifest `data/chroma/ingest_manifest.json`.
5. Se hash inalterado → skip; se mudou → delete chunks da `source` e reinserir.
6. Chunk 800 / overlap 120; Markdown com `MarkdownNodeParser` + `SentenceSplitter`.
7. Metadados por chunk incluem `content_hash`, `chunk_index`, `chunk_total`.
8. Logs JSON sem conteúdo do documento (`yby.rag.ingest`).

## Fluxo de recuperação (T3) — implementado

Módulo: `retrieve.py` (`RagRetriever`, `search_knowledge`).

1. Valida query não vazia; exige índice com `count() >= 1` (`RetrievalError` se vazio).
2. Embedding da query via `create_embedder()` (Ollama `nomic-embed-text` ou mock nos testes).
3. Busca vetorial Chroma/LlamaIndex com `top_k` limitado a `max_results`.
4. Filtros de metadados: `doc_type`, `access_level`, `language`; `tags` com pós-filtro (oversample).
5. ACL pós-busca: `caller_access_level` (`public` \| `team` \| `private`) — nunca expõe nível acima da permissão do chamador.
6. Hits estruturados: `text`, `score`, `source` **relativo** a `knowledge_dir`, `title`, `doc_type`, `tags`, `access_level`, `chunk_index`, `chunk_total`, `content_hash`, `language`.
7. `context_text` com aviso anti-injeção e teto `YBY_RAG_MAX_CONTEXT_CHARS` (padrão 4000).
8. Log JSON (`yby.rag.retrieve`): hash parcial da query, contagens e `source` relativos — sem corpo dos chunks.

**Reranking local:** não incluído neste MVP; melhoria futura (ex. boosting léxico sobre o `top_k` vetorial) sem APIs externas.

## Metadados obrigatórios

| Campo | Descrição |
|--------|-----------|
| `source` | Caminho do arquivo fonte |
| `title` | Título ou nome derivado |
| `doc_type` | `md` \| `txt` \| `pdf` |
| `language` | ex. `pt-BR` |
| `created_at` / `updated_at` | ISO8601 |
| `tags` | lista |
| `access_level` | `private` (padrão) |
| `chunk_index` / `chunk_total` | posição no documento |
| `content_hash` | SHA-256 do arquivo |

Schemas: `src/yby/rag/models.py`. Config: `src/yby/rag/config.py`.

## Segurança

- Allowlist de leitura (`YBY_TOOLS_READ_ROOTS` na T4); sem acesso irrestrito ao FS.
- Não indexar `.env`, chaves ou `data/chroma/` como corpus.
- Conteúdo recuperado é **dado**, não instrução (anti prompt-injection).
- Sem execução de código, escrita em disco ou rede no MVP RAG.
- Logs locais estruturados; sem envio de corpus à nuvem.

## Limites do MVP

- Sem integração obrigatória ao `yby ask`.
- Sem Qdrant/Docker para o novo pipeline (Chroma embedded).
- Sem MCP, web search, `run_python` ou multi-agentes.
- Modelo de **chat** do agente segue D4 (`qwen2.5-coder:3b`) salvo decisão explícita do dono.

## Próximas etapas

| Tarefa | Entrega |
|--------|---------|
| 2 | `ingest.py` usando `RagConfig` + manifest |
| 3 | `retrieve.py` + filtros e limite de contexto |
| 4 | `src/yby/tools/registry.py` (search_knowledge, list_files, read_file) |
| 5 | `src/yby/agent/` — loop Ollama + ferramentas (ver `docs/AGENT_DESIGN.md`) |

## Variáveis de ambiente

Ver `.env.example` (`YBY_RAG_*`). Nenhum segredo é necessário para embeddings locais.

## Verificação (Tarefa 1)

```bash
python3 -m ruff check src/yby/rag tests/test_rag_config.py
python3 -m pytest tests/test_rag_config.py -q
```