"""Testes 100% offline do parser Obsidian, indexador incremental RAG e template do cofre."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.yby.obsidian_rag import (
    InMemoryObsidianStore,
    ObsidianVaultIndexer,
    PgVectorObsidianStore,
    chunk_obsidian_document,
    create_obsidian_store_from_env,
    parse_obsidian_markdown,
)
from src.yby.obsidian_rag.store import _format_pgvector


class FakeObsidianPgCursor:
    """Cursor psycopg assíncrono em memória para validar SQL do PgVectorObsidianStore."""

    def __init__(self, rows: dict[str, dict[str, Any]], executed: list[str]) -> None:
        self._rows = rows
        self._executed = executed
        self._last_one: tuple[Any, ...] | None = None
        self._last_all: list[tuple[Any, ...]] = []
        self.rowcount = 0

    async def __aenter__(self) -> FakeObsidianPgCursor:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        normalized = " ".join(sql.split())
        self._executed.append(normalized)
        self._last_one = None
        self._last_all = []
        self.rowcount = 0
        upper = normalized.upper()

        if "INSERT INTO YBY_OBSIDIAN_CHUNKS" in upper and params is not None:
            chunk_id = str(params[0])
            self._rows[chunk_id] = {
                "chunk_id": chunk_id,
                "source_path": params[1],
                "chunk_index": params[2],
                "heading": params[3],
                "content": params[4],
                "content_hash": params[5],
                "frontmatter": json.loads(params[6]),
                "wikilinks": json.loads(params[7]),
                "tags": json.loads(params[8]),
                "embedding": params[9],
            }
            self.rowcount = 1
        elif "DELETE FROM YBY_OBSIDIAN_CHUNKS" in upper and params is not None:
            target_source = str(params[0])
            keys = [k for k, v in self._rows.items() if v["source_path"] == target_source]
            for key in keys:
                del self._rows[key]
            self.rowcount = len(keys)
        elif "SELECT COUNT(*)" in upper:
            self._last_one = (len(self._rows),)
        elif "FROM YBY_OBSIDIAN_CHUNKS" in upper and "HYBRID_SCORE" in upper:
            for item in list(self._rows.values()):
                self._last_all.append(
                    (
                        item["chunk_id"],
                        item["source_path"],
                        item["heading"],
                        item["content"],
                        item["frontmatter"],
                        item["wikilinks"],
                        item["tags"],
                        0.91,
                        0.45,
                        0.772,
                    )
                )

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self._last_one

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self._last_all


class FakeObsidianPgConnection:
    def __init__(self, rows: dict[str, dict[str, Any]], executed: list[str]) -> None:
        self._rows = rows
        self._executed = executed
        self.committed = False
        self.closed = False

    def cursor(self) -> FakeObsidianPgCursor:
        return FakeObsidianPgCursor(self._rows, self._executed)

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        self.closed = True


def test_parse_frontmatter_wikilinks_embeds_and_tags() -> None:
    sample = """---
spec_id: YBY-SPEC-042
target_node: pc-hub
status: active
offline_ready: true
ui_palette:
  obsidian: "#0D0D0D"
  silicon_green: "#00FF66"
related:
  - "[[TOPOLOGIA_MALHA_YBY.canvas]]"
tags:
  - yby-spec
  - Local-First
---

# Ponte PhoneBox

Conecta [[moto-edge-30-phonebox|PhoneBox Edge 30]] ao [[pc-hub#FastAPI]]
e embute ![[INVENTARIO_NOS_YBY.base]].

Paleta #0D0D0D e #00FF66 não são tags, mas #cockpit e #mqtt/qos1 são.

```python
# [[nao_extrair_de_codigo]]
tag = "#ignorar_tag_codigo"
```
"""
    parsed = parse_obsidian_markdown(sample, source_path="01-specs/phonebox.md")

    assert parsed.title == "Ponte PhoneBox"
    assert parsed.frontmatter["spec_id"] == "YBY-SPEC-042"
    assert parsed.frontmatter["offline_ready"] is True
    assert parsed.frontmatter["ui_palette"]["silicon_green"] == "#00FF66"
    assert parsed.wikilinks == [
        "moto-edge-30-phonebox",
        "pc-hub",
        "TOPOLOGIA_MALHA_YBY.canvas",
    ]
    assert parsed.embeds == ["INVENTARIO_NOS_YBY.base"]
    assert "yby-spec" in parsed.tags
    assert "local-first" in parsed.tags
    assert "cockpit" in parsed.tags
    assert "mqtt/qos1" in parsed.tags
    assert "0d0d0d" not in parsed.tags
    assert "00ff66" not in parsed.tags
    assert "ignorar_tag_codigo" not in parsed.tags
    assert "nao_extrair_de_codigo" not in parsed.wikilinks


def test_parse_without_frontmatter_and_malformed_yaml() -> None:
    plain = "# Nota Simples\n\nTexto com [[pc-hub]] e #offline."
    doc_plain = parse_obsidian_markdown(plain, source_path="00-inbox/simples.md")
    assert doc_plain.frontmatter == {}
    assert doc_plain.title == "Nota Simples"
    assert doc_plain.wikilinks == ["pc-hub"]
    assert doc_plain.tags == ["offline"]

    broken_yaml = "---\n: [invalido\n---\n\n# Recuperada\nConteúdo preservado com [[xiaomi-12]]."
    doc_broken = parse_obsidian_markdown(broken_yaml, source_path="00-inbox/quebrada.md")
    assert doc_broken.frontmatter == {}
    assert doc_broken.title == "Recuperada"
    assert doc_broken.wikilinks == ["xiaomi-12"]


def test_chunk_obsidian_document_respects_headings_and_fences() -> None:
    note = """---
spec_id: YBY-SPEC-001
tags: [arquitetura]
---

# Visão Geral

Introdução do [[pc-hub]].

## Bloco de Código

```bash
# Comentário dentro do bloco não abre nova seção
echo "ok"
```

## Detalhes Longos

""" + ("Parágrafo técnico sobre pgvector e busca híbrida no YBY. " * 25)

    parsed = parse_obsidian_markdown(note, source_path="01-specs/detalhes.md")
    chunks = chunk_obsidian_document(parsed, max_chars=450, overlap=60)

    assert len(chunks) >= 4
    headings = [c.heading for c in chunks]
    assert "Visão Geral" in headings
    assert "Bloco de Código" in headings
    assert "Detalhes Longos" in headings
    assert "Comentário dentro do bloco não abre nova seção" not in headings
    assert all(c.frontmatter["spec_id"] == "YBY-SPEC-001" for c in chunks)
    assert all("arquitetura" in c.tags for c in chunks)


@pytest.mark.asyncio
async def test_incremental_reindex_and_hybrid_search_memory_store(tmp_path: Path) -> None:
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "ignored.md").write_text("# Ignorar", encoding="utf-8")

    spec_dir = tmp_path / "01-specs"
    spec_dir.mkdir()
    note_a = spec_dir / "phonebox.md"
    note_a.write_text(
        "---\nspec_id: SPEC-1\ntags: [phonebox, cockpit]\n---\n\n"
        "# PhoneBox Edge 30\n\nWebhooks HTTP locais para [[pc-hub]] e [[t-watch-s3-plus]].\n",
        encoding="utf-8",
    )
    note_b = spec_dir / "audio.md"
    note_b.write_text(
        "---\nspec_id: SPEC-2\ntags: [audio]\n---\n\n"
        "# Pipeline de Voz\n\nWhisper e Kokoro em CPU no [[pc-hub]].\n",
        encoding="utf-8",
    )

    indexer = ObsidianVaultIndexer(store=InMemoryObsidianStore())

    first = await indexer.reindex_vault(tmp_path)
    assert first.backend == "memory"
    assert first.files_scanned == 2
    assert first.files_indexed == 2
    assert first.files_skipped == 0
    assert first.total_chunks >= 2

    # Segunda execução sem mudanças deve pular tudo (incremental).
    second = await indexer.reindex_vault(tmp_path)
    assert second.files_indexed == 0
    assert second.files_skipped == 2

    # Modificação de um arquivo reindexa apenas ele.
    note_a.write_text(
        note_a.read_text(encoding="utf-8") + "\n## MQTT\nPublica em yby/cockpit/action.\n",
        encoding="utf-8",
    )
    third = await indexer.reindex_vault(tmp_path)
    assert third.files_indexed == 1
    assert third.files_skipped == 1

    # Busca híbrida e filtro por wikilink/tag.
    hits = await indexer.search("webhooks phonebox mqtt", limit=3, tag="phonebox")
    assert hits
    assert hits[0].source_path == "01-specs/phonebox.md"
    assert "t-watch-s3-plus" in hits[0].wikilinks

    link_hits = await indexer.search("voz cpu", limit=3, wikilink="t-watch-s3-plus")
    assert all("t-watch-s3-plus" in h.wikilinks for h in link_hits)

    # Remoção de nota remove chunks obsoletos.
    note_b.unlink()
    fourth = await indexer.reindex_vault(tmp_path)
    assert fourth.files_removed == 1
    assert fourth.files_scanned == 1


@pytest.mark.asyncio
async def test_pgvector_obsidian_store_sql_and_hybrid_search() -> None:
    rows: dict[str, dict[str, Any]] = {}
    executed: list[str] = []

    async def _factory() -> FakeObsidianPgConnection:
        return FakeObsidianPgConnection(rows, executed)

    store = PgVectorObsidianStore(
        dsn="postgresql://yby:local@127.0.0.1:5432/yby_mesh",
        embedding_dim=4,
        connection_factory=_factory,
    )
    await store.ensure_schema()
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in executed)
    assert any("CREATE TABLE IF NOT EXISTS yby_obsidian_chunks" in sql for sql in executed)
    assert any("search_tsv tsvector GENERATED ALWAYS AS" in sql for sql in executed)

    parsed = parse_obsidian_markdown(
        "---\nspec_id: S1\ntags: [pgvector]\n---\n# RAG\nLink [[pc-hub]].",
        source_path="01-specs/rag.md",
    )
    chunks = chunk_obsidian_document(parsed)
    upserted = await store.upsert_chunks(chunks, [[0.5, 0.5, 0.5, 0.5] for _ in chunks])
    assert upserted == len(chunks)
    assert await store.count_chunks() == len(chunks)

    hits = await store.hybrid_search(
        "rag pgvector",
        [0.5, 0.5, 0.5, 0.5],
        limit=3,
        wikilink="pc-hub",
        tag="pgvector",
    )
    assert len(hits) == len(chunks)
    assert hits[0].wikilinks == ["pc-hub"]
    assert any("ts_rank(search_tsv" in sql and "wikilinks @>" in sql for sql in executed)

    deleted = await store.delete_by_source("01-specs/rag.md")
    assert deleted == len(chunks)
    assert await store.count_chunks() == 0

    with pytest.raises(ValueError, match="não finito"):
        _format_pgvector([0.1, float("nan")])

    # Sem DSN configurado -> degrada para memória.
    fallback_store = create_obsidian_store_from_env({})
    assert fallback_store.backend_name == "memory"


def test_vault_template_structure_is_valid() -> None:
    template_root = Path("docs/yby-vault-template")
    assert (template_root / "00-inbox" / ".gitkeep").is_file()

    # 1) Template YBY-Spec compatível com obsidian-markdown e knap.
    spec_text = (template_root / "01-specs" / "TEMPLATE_YBY_SPEC.md").read_text(encoding="utf-8")
    parsed_spec = parse_obsidian_markdown(spec_text, source_path="01-specs/TEMPLATE_YBY_SPEC.md")
    for required_key in ("spec_id", "target_node", "status", "offline_ready", "ui_palette", "tags"):
        assert required_key in parsed_spec.frontmatter
    assert parsed_spec.frontmatter["ui_palette"]["obsidian"] == "#0D0D0D"
    assert parsed_spec.frontmatter["ui_palette"]["silicon_green"] == "#00FF66"
    assert "INVENTARIO_NOS_YBY.base" in parsed_spec.wikilinks
    assert "TOPOLOGIA_MALHA_YBY.canvas" in parsed_spec.wikilinks

    # 2) Obsidian Base YAML + 6 fichas de nós de hardware.
    base_raw = (template_root / "03-hardware" / "INVENTARIO_NOS_YBY.base").read_text(
        encoding="utf-8"
    )
    base_data = yaml.safe_load(base_raw)
    assert isinstance(base_data, dict)
    assert "filters" in base_data and "views" in base_data and "properties" in base_data
    assert len(base_data["views"]) >= 1

    node_dir = template_root / "03-hardware" / "nodes"
    expected_nodes = {
        "pc-hub",
        "xiaomi-12",
        "moto-edge-30-phonebox",
        "t-watch-s3-plus",
        "yby-glass",
        "cybertupa",
    }
    found_ids: set[str] = set()
    for node_file in sorted(node_dir.glob("*.md")):
        doc = parse_obsidian_markdown(
            node_file.read_text(encoding="utf-8"),
            source_path=node_file.name,
        )
        assert doc.frontmatter.get("type") == "hardware-node"
        found_ids.add(str(doc.frontmatter.get("node_id")))
    assert found_ids == expected_nodes

    # 3) JSON Canvas 1.0 válido com arestas íntegras.
    canvas_raw = (template_root / "02-architecture" / "TOPOLOGIA_MALHA_YBY.canvas").read_text(
        encoding="utf-8"
    )
    canvas = json.loads(canvas_raw)
    assert isinstance(canvas.get("nodes"), list) and isinstance(canvas.get("edges"), list)
    node_ids = {node["id"] for node in canvas["nodes"]}
    required_canvas_nodes = {
        "node-fastapi",
        "node-mqtt",
        "node-tailscale",
        "node-edge30",
        "node-xiaomi12",
    }
    assert required_canvas_nodes <= node_ids
    for edge in canvas["edges"]:
        assert edge["fromNode"] in node_ids
        assert edge["toNode"] in node_ids
