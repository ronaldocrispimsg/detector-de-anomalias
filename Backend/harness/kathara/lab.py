"""Monta a topologia Kathará a partir de `configs/kathara.json`.

O nó `bridge` é uma máquina comum que roda `brctl` e liga suas interfaces em uma
bridge Ethernet nativa (decisão da fase 10: sem OVS/Ryu). Os hosts se ligam a
essa bridge por links ponto a ponto do Kathará.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "configs" / "kathara.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path is not None else default_config_path()
    return json.loads(path.read_text(encoding="utf-8"))


def default_config() -> dict[str, Any]:
    return load_config()


def build_lab(config: Mapping[str, Any] | None = None):
    """Cria um `Kathara.model.Lab.Lab` a partir da config. Não sobe nada."""
    from Kathara.model.Lab import Lab

    config = dict(config) if config is not None else default_config()
    lab = Lab(config["lab_name"])

    for name, spec in config["machines"].items():
        lab.new_machine(name, image=spec.get("image", config.get("image", "kathara/base")))
        startup = spec.get("startup", [])
        if startup:
            lab.create_startup_file_from_string(
                lab.get_machine(name), "\n".join(startup)
            )

    for link_name, endpoints in config["links"].items():
        for machine, iface in endpoints:
            lab.connect_machine_to_link(machine, link_name, machine_iface_number=iface)

    return lab


def bridge_iface(config: Mapping[str, Any]) -> str:
    return str(config.get("bridge_iface", "br0"))


def start_lab(lab):
    """Sobe o laboratório no Docker (deploy). Requer daemon em execução."""
    from Kathara.manager.Kathara import Kathara

    Kathara.get_instance().deploy_lab(lab)
    return lab


def stop_lab(lab) -> None:
    """Derruba o laboratório (undeploy)."""
    from Kathara.manager.Kathara import Kathara

    Kathara.get_instance().undeploy_lab(lab_name=lab.name if hasattr(lab, "name") else lab)
