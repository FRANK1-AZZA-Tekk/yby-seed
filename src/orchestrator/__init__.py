"""Orquestrador consolidado (origem: yby-core).

Classifica a tarefa e escolhe modelo local vs nuvem sem depender de LangGraph
no núcleo. A integração LangGraph permanece opcional em `graph.py`.
"""

from .classify import classify_task
from .models import ModelChoice, choose_model

__all__ = ["ModelChoice", "choose_model", "classify_task"]
