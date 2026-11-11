"""Testes do GovernanceAgent (regexes corrigidas)."""

from src.agents.governance_agent import GovernanceAgent


def test_bloqueia_os_system():
    gov = GovernanceAgent()
    allowed, reason = gov.check("import os\nos.system('ls')\n")
    assert allowed is False
    assert "perigoso" in reason.lower() or "os.system" in reason


def test_bloqueia_rm_rf():
    gov = GovernanceAgent()
    allowed, reason = gov.check('os.system("rm -rf /")')
    assert allowed is False


def test_bloqueia_eval():
    gov = GovernanceAgent()
    allowed, _ = gov.check("eval('1+1')")
    assert allowed is False
