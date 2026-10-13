"""Cliente LLM mínimo e mockável para o YBY SEED."""

import json
import os
from urllib import request


class LLMClient:
    """Abstração mínima de LLM local.

    O provedor padrão é `mock`, para manter testes e desenvolvimento
    independentes de serviços externos. `ollama` usa a API local.
    """

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider or os.getenv("YBY_LLM_PROVIDER", "mock")
        self.model = model or os.getenv("YBY_LLM_MODEL", "llama3.2:3b")

    def generate(self, prompt: str) -> str:
        if self.provider == "mock":
            return f"[mock] Resposta para: {prompt}"
        if self.provider == "ollama":
            return self._generate_ollama(prompt)
        raise ValueError(f"Provedor LLM não suportado: {self.provider}")

    def _generate_ollama(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
        req = request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read())
        return data["message"]["content"]
