# Ferramentas YBY — desenho (Tarefa 4)

Registro central em `src/yby/tools/` com três ferramentas de leitura/consulta: **sem escrita, execução, rede ou hardware**.

## Módulos

| Módulo | Função |
|--------|--------|
| `base.py` | `ToolRegistry`, `ToolDefinition`, `ToolResponse`, risco, timeout, auditoria |
| `schemas.py` | Pydantic de entrada/saída por ferramenta |
| `security.py` | Allowlist (`YBY_TOOLS_READ_ROOTS`), extensões seguras, anti-`..`/symlink |
| `knowledge_tools.py` | `search_knowledge` → `RagRetriever` |
| `file_tools.py` | `list_files`, `read_file` |
| `registry.py` | `create_default_registry()` |

## Ferramentas

### `search_knowledge` (risco **low**)

- Args: `query`, `top_k`, `doc_type`, `tags`, `access_level`, `max_context_chars`
- Saída: hits estruturados + `context_text` (dado, não instrução)
- ACL do RAG via `caller_access_level` no registry

### `list_files` (risco **low**)

- Args: `directory`, `pattern`, `max_entries`
- Somente arquivos com extensão `.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.pdf`
- Caminhos retornados **relativos** à raiz allowlist

### `read_file` (risco **medium**)

- Args: `path`, `max_bytes`, `encoding`
- Mesma allowlist e extensões; bloqueia binário e nomes sensíveis (`.env`, etc.)

## Segurança

- `assert_allowed_path`: rejeita `..`, symlinks e absolutos fora da allowlist
- Erros estruturados (`ToolError`), sem stack trace para o LLM
- Log JSON `event: tool_call` em `yby.tools`

## Agente (T5)

`create_default_registry()` expõe `describe_all()` com JSON Schema para o planejador.

## Verificação

```bash
python3 -m ruff check src/yby/tools tests/test_tools_registry.py tests/test_knowledge_tools.py tests/test_file_tools.py
python3 -m pytest tests/test_tools_registry.py tests/test_knowledge_tools.py tests/test_file_tools.py -q
```