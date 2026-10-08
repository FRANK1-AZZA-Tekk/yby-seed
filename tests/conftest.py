"""
Configuração de testes (pytest)

Uso:
pytest tests/ -v --cov=src

Licença: MIT
"""

import pytest
import os
import sys

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def test_db_url():
    """URL do PostgreSQL para testes"""
    return "postgresql://yby:yby_seed_password@localhost:5432/yby_seed_test"


@pytest.fixture(scope="session")
def test_lancedb_path():
    """Caminho do LanceDB para testes"""
    return ":memory:"  # Usar memória para testes rápidos


@pytest.fixture(scope="session")
def test_mqtt_broker():
    """Broker MQTT para testes"""
    return "localhost"


@pytest.fixture(scope="session")
def test_mqtt_port():
    """Porta MQTT para testes"""
    return 1883


# Configurar logging
@pytest.fixture(autouse=True)
def configure_logging():
    """Configurar logging para testes"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
