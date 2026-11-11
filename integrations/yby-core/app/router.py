import os

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI


def get_model(task_type: str, sensitive: bool = False):
    local_model = ChatOllama(
        model=os.getenv("YBY_LOCAL_MODEL", "qwen2.5-coder:3b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.2,
        num_ctx=int(os.getenv("YBY_NUM_CTX", "2048")),
    )

    if sensitive or task_type in {"chat", "firmware", "memory"}:
        return local_model

    cloud_model = ChatOpenAI(
        model=os.getenv("YBY_CLOUD_MODEL", "openai/gpt-4o-mini"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.2,
    )

    return cloud_model
