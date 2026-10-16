"""
Router deterministico do YBY SEED (MVP).

Decisao de rota unica e previsivel: toda solicitacao do `ask` e direcionada
ao Ollama local. Nao existe rota de nuvem, fallback ou repeticao automatica.

A politica de execucao (offline/privado) acompanha a decisao e sera
consumida pela auditoria opt-in (3B): interacoes privadas nao persistem
metadados de auditoria.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunPolicy:
    """Politica de execucao declarada pelo usuario."""

    offline: bool = False
    private: bool = False


@dataclass(frozen=True)
class RouteDecision:
    """Resultado deterministico do roteamento."""

    route: str
    policy: RunPolicy


def route_request(policy: RunPolicy) -> RouteDecision:
    """Roteia a solicitacao para a unica rota executavel do MVP."""
    return RouteDecision(route="local_ollama", policy=policy)
