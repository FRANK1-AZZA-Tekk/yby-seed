"""Structural checks only; agent behavior is not yet implemented/validated."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "src.agents.bayesian_teaching",
        "src.agents.execution_agent",
        "src.agents.governance_agent",
        "src.agents.interview_agent",
        "src.agents.learning_agent",
        "src.agents.planning_agent",
        "src.agents.router_agent",
        "src.agents.validation_agent",
    ],
)
def test_agent_module_imports(module_name):
    module = importlib.import_module(module_name)
    assert module is not None
