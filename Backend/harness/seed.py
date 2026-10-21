"""Controle de seed para reprodutibilidade.

Fixa seed de stdlib e numpy sempre; de frameworks de ML só quando já estiverem
instalados, para não forçar import pesado no caminho padrão.
"""

from __future__ import annotations

import importlib.util
import os
import random

import numpy as np


def _seed_optional_frameworks(seed: int) -> None:
    if importlib.util.find_spec("torch") is not None:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def set_seed(seed: int) -> int:
    """Fixa PYTHONHASHSEED, random e numpy; devolve a seed aplicada."""
    seed = int(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    _seed_optional_frameworks(seed)
    return seed
