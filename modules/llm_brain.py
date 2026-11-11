"""Cérebro LLM do YBY SEED (Passo 2).

OpenRouter primeiro (se houver OPENROUTER_API_KEY no .env).
Sem chave → fallback automático para Ollama local via LiteLLM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from litellm import completion


@dataclass(frozen=True)
class LLMConfig:
    """Configuração resolvida a partir do ambiente."""

    provider: str  # "openrouter" | "ollama"
    model: str
    api_base: str | None = None
    api_key: str | None = None


SYSTEM_PROMPT = (
    "Você é o YBY SEED, orquestrador local-first. "
    "Responda em português, de forma direta e útil. "
    "Sem floreios. Function Over Form."
)


def load_llm_config() -> LLMConfig:
    """Carrega .env e escolhe o provedor ativo."""
    load_dotenv()

    openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    ollama_base = (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_API_BASE")
        or "http://localhost:11434"
    ).rstrip("/")
    ollama_model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
    openrouter_model = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/meta-llama/llama-3.2-3b-instruct:free",
    )

    if openrouter_key:
        model = openrouter_model
        if not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        return LLMConfig(
            provider="openrouter",
            model=model,
            api_key=openrouter_key,
        )

    # LiteLLM espera o prefixo ollama/ para o provedor local
    local_model = ollama_model
    if not local_model.startswith("ollama/"):
        local_model = f"ollama/{local_model}"

    return LLMConfig(
        provider="ollama",
        model=local_model,
        api_base=ollama_base,
    )


def ask_llm(user_text: str, config: LLMConfig | None = None) -> str:
    """Envia o comando do usuário ao LLM e devolve só o texto da resposta."""
    cfg = config or load_llm_config()

    kwargs: dict = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.api_base:
        kwargs["api_base"] = cfg.api_base

    response = completion(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Resposta vazia do modelo")
    return str(content).strip()
