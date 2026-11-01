"""Camada do agente de anomalias.

Reúne representação, política de prompt, guardrails de contrato, provedores de
modelo e o loop do agente. A fachada histórica (`anomaly_classifier`) pode
delegar para cá.
"""

from Backend.services.agent.telemetry import (
    CLASSES,
    FEATURE_FIELDS,
    LABEL_FIELD,
    SEVERITY_BY_SCENARIO,
    Telemetry,
)

__all__ = [
    "CLASSES",
    "FEATURE_FIELDS",
    "LABEL_FIELD",
    "SEVERITY_BY_SCENARIO",
    "Telemetry",
]
