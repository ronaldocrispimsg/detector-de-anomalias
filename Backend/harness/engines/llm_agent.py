"""Engine que roda o agente LLM sobre uma matriz de features.

Adapta o agente (representação + policy + guardrails) ao protocolo `Engine` do
harness. O motor nunca recebe o rótulo: dele só se sabe a matriz de features.
Cada resposta é validada; resposta inválida tenta de novo e, esgotadas as
tentativas, o motor abstém-se (`ABSTAIN`).
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np

from Backend.services.agent.guardrails import ABSTAIN_LABEL, AgentOutput, parse_output
from Backend.services.agent.policy import PROMPT_VERSION, build_prompt
from Backend.services.agent.telemetry import Telemetry


class LLMAgentEngine:
    """Motor do agente sobre um `ModelProvider`."""

    def __init__(
        self,
        provider: Any,
        *,
        mode: str = "zero_shot",
        examples: Sequence[tuple[str, str]] | None = None,
        context: Sequence[str] | None = None,
        context_fn: Callable[[Telemetry], Sequence[str]] | None = None,
        model_id: str | None = None,
        prompt_version: str = PROMPT_VERSION,
        max_retries: int = 2,
    ) -> None:
        self.provider = provider
        self.mode = mode
        self.examples = list(examples) if examples else None
        self.context = list(context) if context else None
        self.context_fn = context_fn
        self.model_id = model_id or str(getattr(provider, "id", "provider"))
        self.prompt_version = prompt_version
        self.max_retries = max_retries
        self.id = f"llm_agent:{self.mode}:{self.model_id}"
        self.outputs: list[AgentOutput] = []
        self.raw_responses: list[str] = []

    def _prompt(self, sample: Telemetry) -> str:
        context = self.context
        if self.context_fn is not None:
            context = list(self.context_fn(sample))
        return build_prompt(
            sample,
            mode=self.mode,
            examples=self.examples,
            context=context,
        )

    def classify(self, sample: Telemetry) -> AgentOutput:
        last_text = ""
        for _ in range(self.max_retries + 1):
            last_text = self.provider.generate(self._prompt(sample))
            parsed = parse_output(
                last_text,
                model_id=self.model_id,
                prompt_version=self.prompt_version,
            )
            if parsed is not None:
                self.raw_responses.append(last_text)
                return parsed
        self.raw_responses.append(last_text)
        return AgentOutput(
            predicted_scenario=ABSTAIN_LABEL,
            is_anomaly=False,
            confidence=0.0,
            severity="UNKNOWN",
            abstain=True,
            model_id=self.model_id,
            prompt_version=self.prompt_version,
        )

    def predict(self, X: Any) -> np.ndarray:
        matrix = np.asarray(X, dtype=float)
        labels: list[str] = []
        self.outputs = []
        for row in matrix:
            output = self.classify(Telemetry.from_features(row))
            self.outputs.append(output)
            labels.append(output.predicted_scenario)
        return np.asarray(labels, dtype=object)
