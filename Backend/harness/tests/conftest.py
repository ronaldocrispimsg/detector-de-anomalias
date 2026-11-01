"""Conftest do harness de testes.

O Kathará lê `sys.stdin` com `select()` durante o startup do laboratório. Sob a
captura do pytest o `stdin` é um pseudoarquivo sem `fileno()` e a chamada quebra.
Para os testes marcados `integration`, damos um `stdin` real (`/dev/null`).
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def _real_stdin_for_integration(request):
    if request.node.get_closest_marker("integration") is None:
        yield
        return
    saved = sys.stdin
    try:
        sys.stdin = open("/dev/null")  # noqa: SIM115 - restaurado no finally
    except OSError:
        yield
        return
    try:
        yield
    finally:
        sys.stdin = saved
