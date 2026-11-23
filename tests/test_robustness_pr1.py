"""PR-1: shutdown do HybridEngine."""

from __future__ import annotations

from src.engine.hybrid import HybridEngine
from src.engine.providers import CloudProvider, OllamaProvider
from tests.test_engine import _config
from tests.test_providers import _Resp, _Session


def test_hybrid_engine_close_invoca_provedores() -> None:
    ollama_session = _Session(_Resp(200, {"response": "ok"}))
    ollama_session.closed = False
    ollama_session.close = lambda: setattr(ollama_session, "closed", True)  # type: ignore[method-assign]

    cloud_session = _Session(_Resp(200, {"choices": [{"message": {"content": "ok"}}]}))
    cloud_session.closed = False
    cloud_session.close = lambda: setattr(cloud_session, "closed", True)  # type: ignore[method-assign]

    ollama = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=ollama_session)
    cloud = CloudProvider("https://openrouter.ai/api/v1", api_key="k", timeout=1, session=cloud_session)
    engine = HybridEngine(_config(), ollama, cloud)
    engine.close()
    assert ollama_session.closed is True
    assert cloud_session.closed is True