"""
Testes dos Agentes (Interview, Governance, Learning, Bayesian)

Cobertura:
- Interview agent (3 modos: Basic, Junior, Pro)
- Governance agent (validação de segurança)
- Learning agent (PostgreSQL + pgvector)
- Bayesian teaching (atualização de crenças)

Execução:
pytest tests/test_agents.py -v --cov=src/agents

Licença: MIT
"""

import pytest
from src.agents.interview_agent import InterviewAgent
from src.agents.governance_agent import GovernanceAgent
from src.agents.bayesian_teaching import BayesianTeaching


@pytest.fixture
def interview_agent():
    """Interview agent para testes"""
    return InterviewAgent()


@pytest.fixture
def governance_agent():
    """Governance agent para testes"""
    return GovernanceAgent()


@pytest.fixture
def bayesian_teaching():
    """Bayesian teaching para testes"""
    return BayesianTeaching()


# === Testes Interview Agent ===

@pytest.mark.asyncio
async def test_interview_basic(interview_agent):
    """Testar entrevista modo Basic"""
    result = await interview_agent.interview(
        "Crie um backup dos meus PDFs",
        mode="basic"
    )
    
    assert result["intent"] in ["backup_automation", "file_operations"]
    assert "slots" in result
    assert "confidence" in result


@pytest.mark.asyncio
async def test_interview_junior(interview_agent):
    """Testar entrevista modo Junior"""
    result = await interview_agent.interview(
        "Quero automatizar meu CRM",
        mode="junior"
    )
    
    assert result["mode"] == "junior"
    assert "clarification_questions" in result
    assert len(result["clarification_questions"]) > 0


@pytest.mark.asyncio
async def test_interview_pro(interview_agent):
    """Testar entrevista modo Pro"""
    result = await interview_agent.interview(
        "Sistema de gestão de estoque",
        mode="pro"
    )
    
    assert result["mode"] == "pro"
    assert "prd" in result
    assert len(result["prd"]) > 100  # PRD deve ter conteúdo


# === Testes Governance Agent ===

@pytest.mark.asyncio
async def test_governance_safe_code(governance_agent):
    """Testar código seguro"""
    safe_code = '''
import json
import zipfile

def backup(source, dest):
    with zipfile.ZipFile(dest, 'w') as zipf:
        zipf.write(source)
'''
    
    is_allowed, reason = governance_agent.check(safe_code, "backup")
    
    assert is_allowed == True
    assert "Aprovado" in reason


@pytest.mark.asyncio
async def test_governance_dangerous_code(governance_agent):
    """Testar código perigoso"""
    dangerous_code = '''
import os
os.system("rm -rf /")
'''
    
    is_allowed, reason = governance_agent.check(dangerous_code, "execute")
    
    assert is_allowed == False
    assert "perigoso" in reason.lower()


@pytest.mark.asyncio
async def test_governance_imports(governance_agent):
    """Testar validação de imports"""
    code_with_dangerous_import = '''
import os
import sys
print("Hello")
'''
    
    is_allowed, reason = governance_agent.check(code_with_dangerous_import, "execute")
    
    assert is_allowed == False
    assert "import" in reason.lower()


# === Testes Bayesian Teaching ===

@pytest.mark.asyncio
async def test_bayesian_update(bayesian_teaching):
    """Testar atualização bayesiana"""
    posterior = bayesian_teaching.update(
        "test_belief",
        feedback="success",
        likelihood_success=0.9
    )
    
    assert posterior > 0.5  # Posterior deve aumentar com feedback positivo
    assert posterior <= 1.0


@pytest.mark.asyncio
async def test_bayesian_update_negative(bayesian_teaching):
    """Testar atualização bayesiana com feedback negativo"""
    posterior = bayesian_teaching.update(
        "test_belief",
        feedback="error",
        likelihood_success=0.9
    )
    
    assert posterior < 0.5  # Posterior deve diminuir com feedback negativo
    assert posterior >= 0.0


@pytest.mark.asyncio
async def test_bayesian_get_best_strategy(bayesian_teaching):
    """Testar obtenção de melhor estratégia"""
    # Atualizar crenças
    bayesian_teaching.update("strategy_a", "success")
    bayesian_teaching.update("strategy_b", "error")
    
    best = bayesian_teaching.get_best_strategy(["strategy_a", "strategy_b"])
    
    assert best == "strategy_a"  # strategy_a deve ser melhor


@pytest.mark.asyncio
async def test_bayesian_converge(bayesian_teaching):
    """Testar convergência"""
    iterations = bayesian_teaching.converge(
        "test_belief",
        target_confidence=0.95,
        max_iterations=20
    )
    
    assert iterations <= 20  # Deve convergir em <= 20 iterações
    
    # Verificar confiança final
    final_confidence = bayesian_teaching.beliefs["test_belief"]
    assert final_confidence >= 0.95


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
