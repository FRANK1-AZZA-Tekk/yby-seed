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

CREATE TABLE IF NOT EXISTS mission_ledger (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    board TEXT NOT NULL DEFAULT '',
    model_routed TEXT NOT NULL,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    attempts INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mission_ledger_created_at
    ON mission_ledger (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mission_ledger_mission_id
    ON mission_ledger (mission_id);
