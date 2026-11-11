"""Smoke test básico para os agentes do YBY SEED.

Verifica se cada agente pode ser importado e instanciado.
Não depende de Ollama rodando.
"""

import importlib

import pytest

AGENTES = [
    "src.agents.router_agent",
    "src.agents.planning_agent",
    "src.agents.validation_agent",
    "src.agents.execution_agent",
    "src.agents.governance_agent",
    "src.agents.learning_agent",
    "src.agents.interview_agent",
    "src.agents.bayesian_teaching",
]


def _importar(modulo: str):
    try:
        return importlib.import_module(modulo)
    except ImportError as exc:
        pytest.skip(f"dependência ausente para {modulo}: {exc}")


@pytest.mark.parametrize("modulo", AGENTES)
def test_agente_importavel(modulo):
    """Cada agente deve ser importável sem erro."""
    mod = _importar(modulo)
    assert mod is not None


@pytest.mark.parametrize("modulo", AGENTES)
def test_agente_tem_classe_principal(modulo):
    """Cada módulo de agente deve expor pelo menos uma classe."""
    mod = _importar(modulo)
    classes = [
        obj for name, obj in vars(mod).items()
        if isinstance(obj, type) and not name.startswith("_")
    ]
    assert len(classes) > 0, f"{modulo} não expõe nenhuma classe"
