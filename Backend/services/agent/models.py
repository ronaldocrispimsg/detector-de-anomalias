"""Provedores de modelo plugáveis.

O agente fala com um provedor texto->texto. Três implementações:

- `MockProvider`: determinístico, para testes e plumbing.
- `HTTPProvider`: endpoint compatível com OpenAI (`/v1/chat/completions`) ou
  Ollama (`/api/chat`), via `urllib` (sem dependências extras).
- `TorchProvider`: `transformers` + `torch` local (import tardio).
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class ModelProvider(Protocol):
    id: str

    def generate(self, prompt: str) -> str:  # pragma: no cover - interface
        ...


@dataclass
class MockProvider:
    """Provedor determinístico: mapeia prompt->resposta por regra ou tabela."""

    responder: Callable[[str], str]
    id: str = "mock"

    def generate(self, prompt: str) -> str:
        return self.responder(prompt)


@dataclass
class HTTPProvider:
    """Endpoint HTTP compatível com OpenAI ou Ollama."""

    base_url: str
    model: str
    api: str = "openai"  # "openai" ou "ollama"
    api_key: str | None = None
    timeout: float = 60.0
    temperature: float = 0.0
    id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.id = f"http:{self.model}"

    def _build_request(self, prompt: str) -> urllib.request.Request:
        if self.api == "ollama":
            url = self.base_url.rstrip("/") + "/api/chat"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": self.temperature},
            }
        else:
            url = self.base_url.rstrip("/") + "/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
            }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers
        )

    def _parse_response(self, body: dict) -> str:
        if self.api == "ollama":
            return body["message"]["content"]
        return body["choices"][0]["message"]["content"]

    def generate(self, prompt: str) -> str:
        request = self._build_request(prompt)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return self._parse_response(body)


class TorchProvider:
    """Modelo local via `transformers` (import tardio de torch)."""

    def __init__(
        self,
        model_name: str,
        *,
        device: str | None = None,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise ImportError(
                "TorchProvider exige 'torch' e 'transformers' instalados"
            ) from exc

        self._torch = torch
        self.model_name = model_name
        self.id = f"torch:{model_name}"
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def generate(self, prompt: str) -> str:
        torch = self._torch
        messages = [{"role": "user", "content": prompt}]
        if getattr(self.tokenizer, "chat_template", None):
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            text = prompt
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=self.temperature > 0,
                temperature=self.temperature if self.temperature > 0 else None,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0][inputs["input_ids"].shape[1] :]
        return self.tokenizer.decode(generated, skip_special_tokens=True)
