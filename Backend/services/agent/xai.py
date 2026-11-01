"""Explicabilidade e fidelidade.

Importância de features (permutação global e oclusão local) para os modelos de
ML; correspondência entre a `evidence` citada pelo LLM e a telemetria; rubrica de
justificativa; e fidelidade contrafactual (a classe reage à métrica citada?).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Sequence

import numpy as np

from Backend.services.agent.actions import plan_actions
from Backend.services.agent.telemetry import FEATURE_FIELDS, Telemetry


def permutation_importance(
    model: Any,
    X: Any,
    y: Sequence[Any],
    *,
    n_repeats: int = 10,
    random_state: int = 0,
) -> dict[str, float]:
    from sklearn.inspection import permutation_importance as sklearn_pi

    result = sklearn_pi(
        model, X, y, n_repeats=n_repeats, random_state=random_state
    )
    return {
        name: float(mean)
        for name, mean in zip(FEATURE_FIELDS, result.importances_mean)
    }


def occlusion_importance(
    model: Any,
    sample: Telemetry,
    baseline: Telemetry,
    *,
    classes: Sequence[Any],
) -> dict[str, float]:
    """Queda na probabilidade da classe predita ao ocluir cada feature."""
    def _row(s: Telemetry) -> np.ndarray:
        return np.asarray([[float(s.to_mapping()[n]) for n in FEATURE_FIELDS]])

    probs = model.predict_proba(_row(sample))[0]
    model_classes = list(getattr(model, "classes_", classes))
    target_label = model_classes[int(np.argmax(probs))]
    target_col = model_classes.index(target_label)
    base_prob = float(probs[target_col])

    importances: dict[str, float] = {}
    for name in FEATURE_FIELDS:
        occluded = replace(sample, **{name: getattr(baseline, name)})
        occluded_prob = float(model.predict_proba(_row(occluded))[0][target_col])
        importances[name] = base_prob - occluded_prob
    return importances


def evidence_matches_telemetry(
    output: Any, sample: Telemetry, *, tol: float = 0.05
) -> list[bool]:
    """Para cada item de evidence, se o valor bate com a telemetria."""
    mapping = sample.to_mapping()
    results = []
    for item in getattr(output, "evidence", []) or []:
        metric = str(item.get("metric", ""))
        if metric not in mapping:
            results.append(False)
            continue
        try:
            cited = float(item.get("value"))
        except (TypeError, ValueError):
            results.append(False)
            continue
        actual = float(mapping[metric])
        results.append(abs(cited - actual) <= tol * max(1.0, abs(actual)))
    return results


def rubric_score(output: Any, sample: Telemetry, *, label: str | None = None) -> int:
    """0-3: cita evidência válida? coerente com a classe? ação plausível?"""
    score = 0
    if getattr(output, "abstain", False):
        return 0
    matches = evidence_matches_telemetry(output, sample)
    if matches and all(matches):
        score += 1
    scenario = getattr(output, "predicted_scenario", "")
    root = str(getattr(output, "root_cause", ""))
    if scenario and scenario.replace("_", " ").split()[0].lower() in root.lower():
        score += 1
    plausible = {a.name for a in plan_actions(scenario)}
    if plausible and set(getattr(output, "remediation_playbook", []) or []):
        score += 1
    return score


def counterfactual_fidelity(
    predict_fn: Callable[[Telemetry], str],
    sample: Telemetry,
    metric: str,
    *,
    factor: float = 3.0,
) -> dict[str, Any]:
    """Perturba a métrica citada e verifica se a classe reage."""
    original = predict_fn(sample)
    perturbed = replace(
        sample, **{metric: float(getattr(sample, metric)) * factor}
    )
    new = predict_fn(perturbed)
    return {
        "metric": metric,
        "original": original,
        "perturbed": new,
        "changed": original != new,
    }


def xai_report(
    outputs: Sequence[Any],
    samples: Sequence[Telemetry],
    y_true: Sequence[Any],
    *,
    verifier: Callable[[Any, Telemetry], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Relatório por classe: rubrica média e fidelidade contrafactual."""
    by_class: dict[str, dict[str, float]] = {}
    for output, sample, truth in zip(outputs, samples, y_true):
        label = str(truth)
        bucket = by_class.setdefault(
            label, {"n": 0, "rubric_sum": 0.0, "evidence_hits": 0.0}
        )
        bucket["n"] += 1
        bucket["rubric_sum"] += rubric_score(output, sample)
        matches = evidence_matches_telemetry(output, sample)
        bucket["evidence_hits"] += float(all(matches)) if matches else 0.0
        if verifier is not None:
            verifier(output, sample)

    report = {}
    for label, bucket in by_class.items():
        n = bucket["n"]
        report[label] = {
            "n": n,
            "mean_rubric": bucket["rubric_sum"] / n,
            "evidence_agreement": bucket["evidence_hits"] / n,
        }
    return report
