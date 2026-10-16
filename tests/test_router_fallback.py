from unittest.mock import MagicMock

from src.agents.router_agent import RouterAgent
from src.core.ollama_client import OllamaTransportError


def test_fallback_on_ollama_failure():
    ollama = MagicMock()
    ollama.generate.side_effect = OllamaTransportError(
        "Falha de conexão com o Ollama."
    )
    router = RouterAgent(ollama)

    result = router.classify("Pergunta de teste")

    assert result == {
        "agent": "planning",
        "intent": "unknown",
        "confidence": 0.5,
        "requires_interview": True,
    }
    ollama.generate.assert_called_once()
