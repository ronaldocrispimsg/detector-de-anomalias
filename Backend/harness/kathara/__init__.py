"""Rede emulada Kathará para o agente (fase 10).

Módulos: `lab` (monta a topologia), `controller` (aplica/verifica/reverte via
`Kathara.exec`), `metrics` (re-coleta as 12 features), `inject` (injeta a falha).
"""

from __future__ import annotations

from Backend.harness.kathara.controller import KatharaController
from Backend.harness.kathara.lab import build_lab, default_config, load_config

__all__ = ["KatharaController", "build_lab", "default_config", "load_config"]
