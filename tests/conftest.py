"""Configuração de testes para o YBY SEED.

Regras:
- Nenhum teste depende de serviços externos (Ollama, PostgreSQL, MQTT).
- Dependência opcional ausente (ex.: Pillow da visão) vira skip com motivo explícito.
"""


# ============================================================================
# MARCADORES DE TESTE
# ============================================================================


def pytest_configure(config):
    """Registrar marcadores personalizados."""
    config.addinivalue_line("markers", "skip: marcar teste como skip (integração pendente)")
    config.addinivalue_line("markers", "unit: teste unitário (sem dependências externas)")
    config.addinivalue_line("markers", "integration: teste de integração (requer serviços)")
