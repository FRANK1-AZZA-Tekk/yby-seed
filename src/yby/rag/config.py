"""Configuração central do RAG local (sem I/O de ingestão ou consulta)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.yby.rag.errors import ConfigurationError

_DEFAULT_KNOWLEDGE_DIR = Path("data/knowledge")
_DEFAULT_CHROMA_DIR = Path("data/chroma")
_DEFAULT_COLLECTION = "yby_knowledge"
_DEFAULT_EMBED_MODEL = "nomic-embed-text"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP_RATIO = 0.15
_DEFAULT_TOP_K = 5
_DEFAULT_MAX_RESULTS = 10
_DEFAULT_TIMEOUT_SECONDS = 30.0
_DEFAULT_ACCESS_LEVEL = "private"
_DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024
_DEFAULT_MAX_FILES_PER_RUN = 100


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _positive_int(name: str, raw: str, default: int) -> int:
    value = raw.strip() if raw.strip() else str(default)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser inteiro, recebi {raw!r}") from exc
    if parsed < 1:
        raise ConfigurationError(f"{name} deve ser >= 1, recebi {parsed}")
    return parsed


def _positive_float(name: str, raw: str, default: float) -> float:
    value = raw.strip() if raw.strip() else str(default)
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser número, recebi {raw!r}") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{name} deve ser > 0, recebi {parsed}")
    return parsed


@dataclass(frozen=True)
class RagConfig:
    """Parâmetros do índice vetorial local (Chroma + Ollama embeddings)."""

    knowledge_dir: Path
    chroma_dir: Path
    collection_name: str
    embed_model: str
    ollama_base_url: str
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    default_top_k: int
    max_results: int
    timeout_seconds: float
    max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES
    max_files_per_run: int = _DEFAULT_MAX_FILES_PER_RUN
    default_access_level: str = _DEFAULT_ACCESS_LEVEL

    def __post_init__(self) -> None:
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ConfigurationError(
                "chunk_overlap_tokens deve ser menor que chunk_size_tokens"
            )
        if self.default_top_k > self.max_results:
            raise ConfigurationError("default_top_k não pode exceder max_results")
        if not self.collection_name.strip():
            raise ConfigurationError("collection_name não pode ser vazio")
        if self.max_file_bytes < 1:
            raise ConfigurationError("max_file_bytes deve ser >= 1")
        if self.max_files_per_run < 1:
            raise ConfigurationError("max_files_per_run deve ser >= 1")

    @property
    def chunk_overlap_ratio(self) -> float:
        return self.chunk_overlap_tokens / self.chunk_size_tokens

    @classmethod
    def default(cls) -> RagConfig:
        root = _repo_root()
        overlap = int(_DEFAULT_CHUNK_SIZE * _DEFAULT_CHUNK_OVERLAP_RATIO)
        return cls(
            knowledge_dir=(root / _DEFAULT_KNOWLEDGE_DIR).resolve(),
            chroma_dir=(root / _DEFAULT_CHROMA_DIR).resolve(),
            collection_name=_DEFAULT_COLLECTION,
            embed_model=_DEFAULT_EMBED_MODEL,
            ollama_base_url=_DEFAULT_OLLAMA_URL,
            chunk_size_tokens=_DEFAULT_CHUNK_SIZE,
            chunk_overlap_tokens=overlap,
            default_top_k=_DEFAULT_TOP_K,
            max_results=_DEFAULT_MAX_RESULTS,
            timeout_seconds=_DEFAULT_TIMEOUT_SECONDS,
            max_file_bytes=_DEFAULT_MAX_FILE_BYTES,
            max_files_per_run=_DEFAULT_MAX_FILES_PER_RUN,
        )

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = True) -> RagConfig:
        if load_dotenv_file:
            load_dotenv(override=False)

        root = _repo_root()
        knowledge = os.getenv("YBY_RAG_KNOWLEDGE_DIR", "").strip()
        chroma = os.getenv("YBY_RAG_CHROMA_DIR", "").strip()
        ollama = (
            os.getenv("YBY_RAG_OLLAMA_URL", "").strip()
            or os.getenv("YBY_OLLAMA_BASE_URL", "").strip()
            or _DEFAULT_OLLAMA_URL
        )

        chunk_size = _positive_int(
            "YBY_RAG_CHUNK_SIZE",
            os.getenv("YBY_RAG_CHUNK_SIZE", ""),
            _DEFAULT_CHUNK_SIZE,
        )
        overlap_raw = os.getenv("YBY_RAG_CHUNK_OVERLAP", "").strip()
        if overlap_raw:
            chunk_overlap = _positive_int("YBY_RAG_CHUNK_OVERLAP", overlap_raw, 1)
        else:
            chunk_overlap = int(chunk_size * _DEFAULT_CHUNK_OVERLAP_RATIO)

        return cls(
            knowledge_dir=Path(knowledge or root / _DEFAULT_KNOWLEDGE_DIR).expanduser().resolve(),
            chroma_dir=Path(chroma or root / _DEFAULT_CHROMA_DIR).expanduser().resolve(),
            collection_name=os.getenv("YBY_RAG_COLLECTION", _DEFAULT_COLLECTION).strip()
            or _DEFAULT_COLLECTION,
            embed_model=os.getenv("YBY_RAG_EMBED_MODEL", _DEFAULT_EMBED_MODEL).strip()
            or _DEFAULT_EMBED_MODEL,
            ollama_base_url=ollama.rstrip("/"),
            chunk_size_tokens=chunk_size,
            chunk_overlap_tokens=chunk_overlap,
            default_top_k=_positive_int(
                "YBY_RAG_TOP_K",
                os.getenv("YBY_RAG_TOP_K", ""),
                _DEFAULT_TOP_K,
            ),
            max_results=_positive_int(
                "YBY_RAG_MAX_RESULTS",
                os.getenv("YBY_RAG_MAX_RESULTS", ""),
                _DEFAULT_MAX_RESULTS,
            ),
            timeout_seconds=_positive_float(
                "YBY_RAG_TIMEOUT",
                os.getenv("YBY_RAG_TIMEOUT", ""),
                _DEFAULT_TIMEOUT_SECONDS,
            ),
            default_access_level=os.getenv("YBY_RAG_ACCESS_LEVEL", _DEFAULT_ACCESS_LEVEL).strip()
            or _DEFAULT_ACCESS_LEVEL,
            max_file_bytes=_positive_int(
                "YBY_RAG_MAX_FILE_BYTES",
                os.getenv("YBY_RAG_MAX_FILE_BYTES", ""),
                _DEFAULT_MAX_FILE_BYTES,
            ),
            max_files_per_run=_positive_int(
                "YBY_RAG_MAX_FILES_PER_RUN",
                os.getenv("YBY_RAG_MAX_FILES_PER_RUN", ""),
                _DEFAULT_MAX_FILES_PER_RUN,
            ),
        )

    def ensure_data_dirs(self) -> None:
        """Cria diretórios de dados se não existirem (local, sem nuvem)."""

        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)