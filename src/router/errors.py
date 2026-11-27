"""Erros estruturados do roteador offline."""

from __future__ import annotations


class RouterError(Exception):
    """Erro base do roteador offline."""


class ConfigurationError(RouterError):
    """Configuração do roteador inválida ou incompleta."""


class RoutingError(RouterError):
    """Falha ao decidir a rota para um pedido."""


class ModelNotFoundError(RouterError):
    """Perfil ou modelo local referenciado não existe na configuração."""


class SafetyViolationError(RouterError):
    """Pedido ou decisão viola limites de segurança do roteador."""
