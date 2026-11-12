"""CLI de ingestão: uv run python -m src.yby_seed.memory.ingest --dir ./docs --domain esp_idf"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg
from openai import OpenAI

from src.yby_seed.config import get_settings
from src.yby_seed.memory.chunking import iter_semantic_chunks

EMBED_MODEL = "nomic-embed-text"


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise SystemExit("instale pypdf para ingerir PDFs: uv sync --extra pdf") from exc
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    return ""


def _embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [row.embedding for row in response.data]


def ingest_directory(directory: Path, domain: str, database_url: str | None) -> int:
    settings = get_settings()
    dsn = database_url or os.environ.get("YBY_DATABASE_URL", "").strip()
    if not dsn:
        dsn = (
            f"postgresql://yby:{os.environ.get('POSTGRES_PASSWORD', 'yby_local_dev')}"
            "@127.0.0.1:5432/yby_brain"
        )

    client = OpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    )

    schema_path = Path(__file__).with_name("schema.sql")
    inserted = 0

    with psycopg.connect(dsn) as conn:
        conn.execute(schema_path.read_text(encoding="utf-8"))
        conn.commit()

        paths = sorted(
            p
            for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".pdf"}
        )

        for path in paths:
            digest = _file_hash(path)
            exists = conn.execute(
                "SELECT 1 FROM ingested_sources WHERE source_hash = %s AND domain = %s",
                (digest, domain),
            ).fetchone()
            if exists:
                continue

            raw = _read_text(path)
            if not raw.strip():
                continue

            chunks = list(iter_semantic_chunks(raw))
            vectors = _embed_batch(client, chunks)
            rel = str(path.relative_to(directory))
            for idx, (content, embedding) in enumerate(zip(chunks, vectors, strict=True)):
                meta = {"chunk_index": idx, "path": rel}
                conn.execute(
                    """
                    INSERT INTO knowledge_chunks
                        (source_file, source_hash, domain, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (rel, digest, domain, content, json.dumps(meta), embedding),
                )
                inserted += 1
            conn.execute(
                """
                INSERT INTO ingested_sources (source_hash, domain, source_file)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (digest, domain, rel),
            )
        conn.commit()

    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingestão RAG offline YBY SEED")
    parser.add_argument("--dir", type=Path, required=True, help="Diretório de documentos")
    parser.add_argument("--domain", required=True, help="Domínio: esp_idf, lvgl, modbus, yby_arch…")
    parser.add_argument("--database-url", default="", help="Override de YBY_DATABASE_URL")
    args = parser.parse_args(argv)

    if not args.dir.is_dir():
        print(f"Diretório inválido: {args.dir}", file=sys.stderr)
        return 1

    count = ingest_directory(args.dir, args.domain, args.database_url or None)
    print(f"Ingestão concluída: {count} chunks novos (domínio={args.domain})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
