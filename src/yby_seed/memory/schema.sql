-- YBY SEED — memória vetorial offline (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ingested_sources (
    source_hash CHAR(64) NOT NULL,
    domain TEXT NOT NULL,
    source_file TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_hash, domain)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_hash CHAR(64) NOT NULL,
    domain TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_domain
    ON knowledge_chunks (domain);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
    ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops);
