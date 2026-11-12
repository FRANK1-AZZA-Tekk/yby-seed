"""Orquestração exocórtex (skill → dry-run → confirmação → registro)."""

from src.orchestration.exocortex import ExocortexOutcome, run_exocortex

__all__ = ["ExocortexOutcome", "run_exocortex"]
