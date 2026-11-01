"""Saída estruturada: schema estrito, validação e retry com feedback.

A defesa de base contra alucinação é estrutural: o dado só é aceito se casar com
um schema com `additionalProperties: false`. JSON inválido ou campo inventado
dispara um retry limitado, com a mensagem de erro reinjetada no prompt. Isto
corrige a forma; o conteúdo é conferido em `grounding` e `verifier`.

Constrained decoding (Outlines/XGrammar) forçaria a estrutura no logit e zeraria
falhas de sintaxe, mas depende de suporte do provider e não corrige erro
semântico em modelos pequenos. Por isso a validação aqui é sempre aplicada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from Backend.services.agent.guardrails import extract_json

_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _type_ok(value: Any, json_type: str) -> bool:
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    expected = _JSON_TYPES.get(json_type)
    if expected is None:
        return True
    if json_type == "boolean":
        return isinstance(value, bool)
    return isinstance(value, expected)


def _validate(data: Any, schema: Mapping[str, Any], path: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _type_ok(data, str(expected_type)):
        errors.append(f"{path}: esperado {expected_type}, recebido {type(data).__name__}")
        return

    if isinstance(data, dict):
        properties: Mapping[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}: campo obrigatório ausente {key!r}")
        if schema.get("additionalProperties") is False:
            for key in data:
                if key not in properties:
                    errors.append(f"{path}: campo não permitido {key!r}")
        for key, subschema in properties.items():
            if key in data:
                _validate(data[key], subschema, f"{path}.{key}", errors)

    if isinstance(data, list) and "items" in schema:
        for index, item in enumerate(data):
            _validate(item, schema["items"], f"{path}[{index}]", errors)

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: valor {data!r} fora de {schema['enum']}")

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: abaixo do mínimo {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: acima do máximo {schema['maximum']}")


def validate_schema(data: Any, schema: Mapping[str, Any]) -> list[str]:
    """Erros de schema (vazio se válido). Não cobre toda a JSON Schema, só o
    subconjunto usado pelos schemas do agente."""
    errors: list[str] = []
    _validate(data, schema, "$", errors)
    return errors


AGENT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["predicted_scenario", "is_anomaly", "confidence"],
    "properties": {
        "predicted_scenario": {"type": "string"},
        "is_anomaly": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "severity": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["metric", "value"],
                "properties": {
                    "metric": {"type": "string"},
                    "value": {"type": "number"},
                },
            },
        },
        "root_cause": {"type": "string"},
        "impact": {"type": "string"},
        "remediation_playbook": {"type": "array", "items": {"type": "string"}},
        "probabilities": {"type": "object", "additionalProperties": True},
        "abstain": {"type": "boolean"},
    },
}

TOOL_CALL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool_id"],
    "properties": {
        "tool_id": {"type": "string"},
        "params": {"type": "object", "additionalProperties": True},
        "rationale": {"type": "string"},
    },
}


@dataclass
class StructuredResult:
    data: dict[str, Any] | None
    raw: str
    attempts: int
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.data is not None


def feedback_message(errors: list[str]) -> str:
    joined = "; ".join(errors) if errors else "saída inválida"
    return (
        "Sua resposta anterior foi rejeitada pelo validador de schema: "
        f"{joined}. Responda de novo só com um objeto JSON que obedeça ao schema."
    )


def structured_call(
    generate: Callable[[str], str],
    prompt: str,
    schema: Mapping[str, Any],
    *,
    max_retries: int = 2,
) -> StructuredResult:
    """Chama `generate`, valida contra `schema` e reinjeta o erro até o limite."""
    attempts = 0
    raw = ""
    errors: list[str] = []
    current = prompt
    while attempts <= max_retries:
        attempts += 1
        raw = generate(current) or ""
        candidate = extract_json(raw)
        if candidate is None:
            errors = ["a saída não contém um objeto JSON"]
        else:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError as exc:
                errors = [f"JSON inválido: {exc}"]
            else:
                if isinstance(data, dict):
                    errors = validate_schema(data, schema)
                    if not errors:
                        return StructuredResult(data, raw, attempts, [])
                else:
                    errors = ["a raiz do JSON não é um objeto"]
        current = prompt + "\n\n" + feedback_message(errors)
    return StructuredResult(None, raw, attempts, errors)
