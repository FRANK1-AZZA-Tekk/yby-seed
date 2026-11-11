import os

import httpx
from langchain_core.tools import tool


QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = "yby_memory"


@tool
def search_yby_memory(query: str, limit: int = 5) -> str:
    """Busca conhecimento anterior do projeto YBY na memória vetorial."""
    response = httpx.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        headers={"api-key": QDRANT_API_KEY},
        json={
            "vector": {"name": "default", "vector": [0.0] * 384},
            "limit": limit,
            "with_payload": True,
        },
        timeout=10,
    )
    response.raise_for_status()
    return str(response.json())
