"""Controlador real em cima do Kathará.

Implementa a interface `Controller` da fase 06: `apply` roda o comando da
ferramenta na máquina alvo, `verify` re-coleta a métrica e compara na direção
certa, `rollback` roda o comando de rollback. O `exec` do Kathará faz
`shlex.split` em strings, então todo comando vai embrulhado em `sh -c`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Backend.services.agent.actions import ActionSpec
from Backend.services.agent.controllers.base import ActionResult
from Backend.harness.kathara.metrics import collect, sh_wrap

_LOWER = "lower_better"


@dataclass
class KatharaController:
    """Aplica e verifica ações numa rede Kathará em execução."""

    lab_name: str
    manager: Any = None
    targets: dict[str, str] = field(
        default_factory=lambda: {
            "host": "h1",
            "victim": "h1",
            "attacker": "h2",
            "dst": "h3",
            "switch": "bridge",
            "flow": "bridge",
        }
    )
    server: str = "10.0.0.1"
    rng: Any = None
    _pending: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.manager is None:
            from Kathara.manager.Kathara import Kathara

            self.manager = Kathara.get_instance()

    # --- plumbing ---------------------------------------------------------
    def _target_for(self, action: ActionSpec) -> str:
        scope = str(action.parameters.get("scope", "host"))
        return self.targets.get(scope, self.targets["host"])

    def _metric_target(self, action: ActionSpec) -> str:
        scope = str(action.parameters.get("metric_scope") or action.parameters.get("scope", "host"))
        return self.targets.get(scope, self.targets.get("host", "h1"))

    def exec(self, machine: str, command: str) -> tuple[str, str, int]:
        out, err, rc = self.manager.exec(
            machine,
            sh_wrap(command),
            lab_name=self.lab_name,
            stream=False,
            wait=(30, 1.0),
        )
        decode = lambda b: b.decode("utf-8", "replace") if isinstance(b, bytes) else str(b or "")
        return decode(out), decode(err), int(rc)

    def _runner(self, machine: str, command: str) -> str:
        out, _, _ = self.exec(machine, command)
        return out

    # --- Controller -------------------------------------------------------
    def dry_run(self, action: ActionSpec) -> ActionResult:
        return ActionResult(
            action=action.name,
            applied=False,
            verified=False,
            rolled_back=False,
            note="dry_run",
        )

    def apply(self, action: ActionSpec, metric_before: float) -> ActionResult:
        target = self._target_for(action)
        command = str(action.parameters.get("command", ""))
        _, err, rc = self.exec(target, command)
        self._pending = {
            "machine": target,
            "metric_machine": self._metric_target(action),
            "metric": action.parameters.get("verify_metric"),
            "direction": action.parameters.get("direction", _LOWER),
            "rollback": action.rollback,
        }
        return ActionResult(
            action=action.name,
            applied=rc == 0,
            verified=False,
            rolled_back=False,
            metric_before=metric_before,
            metric_after=None,
            note=(err.strip()[:200] if rc != 0 else f"applied on {target}"),
        )

    def verify(self, result: ActionResult, *, margin: float = 0.0) -> bool:
        metric = self._pending.get("metric")
        if not metric:
            result.verified = True
            return True
        machine = self._pending.get("metric_machine") or self._pending["machine"]
        after = float(collect(self._runner, machine, server=self.server)[metric])
        result.metric_after = after
        before = result.metric_before
        if before is None:
            return False
        if self._pending.get("direction", _LOWER) == _LOWER:
            return after < before - margin
        return after > before + margin

    def rollback(self, result: ActionResult) -> ActionResult:
        machine = self._pending.get("machine") or self.targets["host"]
        command = str(self._pending.get("rollback") or "")
        if command:
            self.exec(machine, command)
        result.rolled_back = True
        result.note = "rollback"
        return result
