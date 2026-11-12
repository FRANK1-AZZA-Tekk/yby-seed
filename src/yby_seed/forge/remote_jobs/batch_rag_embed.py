#!/usr/bin/env python3
"""Batch embed de PDFs técnicos → dump SQL pgvector (1x RTX 3090)."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore[misc, assignment]

EMBED_DIM = 768
DEFAULT_MODELS = ("BAAI/bge-base-en-v1.5", "nomic-ai/nomic-embed-text-v1.5")


def _read_pdf(path: Path) -> str:
    if PdfReader is None:
        raise SystemExit("instale pypdf no host remoto")
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _chunk_text(text: str, max_chars: int = 1800) -> list[str]:
    chunks: list[str] = []
    buf = ""
    for line in text.splitlines():
        if len(buf) + len(line) + 1 > max_chars:
            if buf.strip():
                chunks.append(buf.strip())
            buf = line
        else:
            buf += line + "\n"
    if buf.strip():
        chunks.append(buf.strip())
    return chunks or [text[:max_chars]]


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=Path, default=Path("/workspace/input/pdfs"))
    parser.add_argument("--domain", default="yby_arch")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODELS[0],
        help="sentence-transformers; fallback nomic-embed-text",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/workspace/output/yby_knowledge_dump.sql")
    )
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(args.model, device=device)

    pdfs = sorted(args.pdf_dir.rglob("*.pdf")) if args.pdf_dir.exists() else []
    if not pdfs:
        raise SystemExit(f"nenhum PDF em {args.pdf_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "CREATE EXTENSION IF NOT EXISTS vector;",
        "CREATE TABLE IF NOT EXISTS knowledge_chunks (",
        "  id BIGSERIAL PRIMARY KEY,",
        "  source_file TEXT NOT NULL,",
        "  source_hash CHAR(64) NOT NULL,",
        "  domain TEXT NOT NULL,",
        "  content TEXT NOT NULL,",
        "  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,",
        "  embedding vector(768) NOT NULL,",
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        ");",
    ]

    for pdf in pdfs:
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        text = _read_pdf(pdf)
        chunks = _chunk_text(text)
        for idx in range(0, len(chunks), args.batch_size):
            batch = chunks[idx : idx + args.batch_size]
            vectors = model.encode(batch, normalize_embeddings=True).tolist()
            for offset, (content, vector) in enumerate(zip(batch, vectors, strict=True)):
                if len(vector) != EMBED_DIM:
                    vector = vector[:EMBED_DIM]
                rel = str(pdf.relative_to(args.pdf_dir))
                meta = json.dumps({"chunk_index": idx + offset, "path": rel}, ensure_ascii=False)
                emb = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                lines.append(
                    "INSERT INTO knowledge_chunks "
                    "(source_file, source_hash, domain, content, metadata, embedding) VALUES ("
                    f"'{_sql_escape(rel)}', '{digest}', '{_sql_escape(args.domain)}', "
                    f"'{_sql_escape(content)}', '{_sql_escape(meta)}'::jsonb, '{emb}'::vector);"
                )

    lines.append(f"-- yby-seed rag dump {uuid.uuid4()}")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"dump SQL gerado: {args.output} ({len(pdfs)} PDFs)")


if __name__ == "__main__":
    main()
