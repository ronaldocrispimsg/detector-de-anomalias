"""Harness de experimentos do agente de anomalias.

Infraestrutura comum a todas as fases: configuração, seed, métricas,
estatística, registro de execuções e orquestração de um trial reproduzível.
"""

from Backend.harness.config import ExperimentConfig, load_config
from Backend.harness.metrics import classification_metrics
from Backend.harness.run_trial import TrialResult, repro, run_trial
from Backend.harness.seed import set_seed

__all__ = [
    "ExperimentConfig",
    "load_config",
    "set_seed",
    "classification_metrics",
    "run_trial",
    "repro",
    "TrialResult",
]
