"""Política de prompt versionada.

O conjunto de classes é fechado e explícito; o formato de saída é fixo. A
telemetria entra sem rótulo. Zeroshot e fewshot diferem apenas pela presença de
exemplos rotulados (que vêm somente do treino).
"""

from __future__ import annotations

from typing import Sequence

from Backend.services.agent.representation import serialize
from Backend.services.agent.telemetry import CLASSES, Telemetry

PROMPT_VERSION = "v1"

CLASS_LIST = ", ".join(CLASSES)

SYSTEM_INSTRUCTIONS = (
    "Você é um agente de operações de rede (NOC). Dada a telemetria de um host, "
    "classifique o fenômeno em UMA das classes listadas, informe a severidade e "
    "proponha mitigação. Responda SOMENTE com um objeto JSON válido, sem texto "
    "fora do JSON. Seja conciso: no máximo 2 itens em evidence e 2 passos em "
    "remediation_playbook; root_cause e impact com até 12 palavras."
)

SCHEMA_INSTRUCTIONS = (
    "Formato da resposta (JSON):\n"
    "{\n"
    '  "predicted_scenario": "<uma classe>",\n'
    '  "is_anomaly": <true|false>,\n'
    '  "confidence": <0.0 a 1.0>,\n'
    '  "severity": "<OK|WARNING|CRITICAL>",\n'
    '  "evidence": [{"metric": "<nome>", "value": <numero>, "threshold": <numero>}],\n'
    '  "root_cause": "<curto>",\n'
    '  "impact": "<curto>",\n'
    '  "remediation_playbook": ["<passo>", "..."]\n'
    "}"
)

Example = tuple[str, str]


def build_prompt(
    sample: Telemetry,
    *,
    mode: str = "zero_shot",
    examples: Sequence[Example] | None = None,
    context: Sequence[str] | None = None,
) -> str:
    parts: list[str] = [
        SYSTEM_INSTRUCTIONS,
        "",
        f"Classes possíveis (responda com exatamente uma): {CLASS_LIST}.",
        "",
        serialize(sample),
    ]
    if context:
        parts.append("")
        parts.append("Evidências históricas de padrões semelhantes (sem rótulo):")
        parts.extend(f"- {item}" for item in context)
    if mode == "few_shot":
        if not examples:
            raise ValueError("modo few_shot exige exemplos do treino")
        parts.append("")
        parts.append("Exemplos resolvidos:")
        for text, label in examples:
            parts.append("[EXEMPLO]")
            parts.append(text)
            parts.append(f"[RESPOSTA] {label}")
    parts.append("")
    parts.append(SCHEMA_INSTRUCTIONS)
    return "\n".join(parts)
