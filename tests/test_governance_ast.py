"""GovernanceAgent usa a guarda AST, não regex."""

from src.agents.governance_agent import GovernanceAgent


def test_bloqueia_import_de_os() -> None:
    agent = GovernanceAgent()
    allowed, reason = agent.check("import os\nos.system('echo oi')\n")
    assert allowed is False
    assert "os" in reason


def test_aceita_math() -> None:
    agent = GovernanceAgent()
    allowed, reason = agent.check("import math\nprint(math.sqrt(4))\n")
    assert allowed is True
    assert reason == "Aprovado"


def test_acao_critica_pede_pessoa() -> None:
    agent = GovernanceAgent()
    allowed, reason = agent.check("import math\n", action="execute_shell")
    assert allowed is False
    assert "aprovação" in reason
