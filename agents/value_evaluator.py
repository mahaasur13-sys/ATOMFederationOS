"""
TAAR v8 — Value Evaluation Engine
Scores AI org performance: value = (success_rate × stability_gain) / resource_cost
Drives market allocation, reputation, and job routing.
"""

from __future__ import annotations
import uuid, time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValueScore:
    """Result of evaluating a job or org."""
    entity_id: str
    entity_type: str  # job | org | mission
    success_rate: float
    stability_gain: float
    resource_cost: float
    value: float
    efficiency: float
    grade: str  # A/B/C/D/F
    evaluated_at: float = field(default_factory=time.time)


@dataclass
class JobEvaluation:
    """Detailed job evaluation record."""
    job_id: str
    org_id: str
    success: bool
    stability_delta: float
    resource_cost: float
    value_score: float
    grade: str
    feedback: str
    suggestions: list[str] = field(default_factory=list)


class ValueEvaluator:
    """
    Economic value scoring for jobs and organizations.
    Formula: value = (success_rate × stability_gain) / resource_cost
    Grades: A (0.8+), B (0.6-0.8), C (0.4-0.6), D (0.2-0.4), F (<0.2)
    """

    def __init__(self):
        self.evaluations: list[JobEvaluation] = []
        self.org_history: dict[str, list[ValueScore]] = {}

    def _compute_value(self, success_rate: float, stability_gain: float,
                       resource_cost: float) -> float:
        """Compute value score."""
        if resource_cost <= 0:
            resource_cost = 0.001
        raw = (success_rate * (1.0 + stability_gain)) / resource_cost
        return round(min(raw, 10.0), 4)  # cap at 10x

    def _grade(self, value: float) -> str:
        if value >= 0.8:
            return "A"
        elif value >= 0.6:
            return "B"
        elif value >= 0.4:
            return "C"
        elif value >= 0.2:
            return "D"
        return "F"

    def evaluate_job(self, job_id: str, org_id: str, success: bool,
                     stability_delta: float, resource_cost: float) -> JobEvaluation:
        """Evaluate a single job execution."""
        sr = 1.0 if success else 0.0
        value = self._compute_value(sr, stability_delta, resource_cost)
        grade = self._grade(value)

        if success:
            feedback = f"[{grade}] Successful execution. value={value:.3f}"
            suggestions = []
        else:
            feedback = f"[{grade}] Failed execution. stability_delta={stability_delta:.3f}"
            suggestions = ["review error logs", "increase retry budget", "lower complexity"]

        eval_record = JobEvaluation(
            job_id=job_id,
            org_id=org_id,
            success=success,
            stability_delta=stability_delta,
            resource_cost=resource_cost,
            value_score=value,
            grade=grade,
            feedback=feedback,
            suggestions=suggestions,
        )
        self.evaluations.append(eval_record)

        # Update org history
        vs = ValueScore(
            entity_id=org_id,
            entity_type="org",
            success_rate=sr,
            stability_gain=stability_delta,
            resource_cost=resource_cost,
            value=value,
            efficiency=value,
            grade=grade,
        )
        self.org_history.setdefault(org_id, []).append(vs)
        return eval_record

    def evaluate_org(self, org_id: str) -> ValueScore:
        """Aggregate org performance over all evaluated jobs."""
        history = self.org_history.get(org_id, [])
        if not history:
            return ValueScore(
                entity_id=org_id, entity_type="org",
                success_rate=0.0, stability_gain=0.0,
                resource_cost=0.0, value=0.0, efficiency=0.0, grade="F"
            )
        n = len(history)
        avg_sr = sum(v.success_rate for v in history) / n
        avg_sg = sum(v.stability_gain for v in history) / n
        avg_rc = sum(v.resource_cost for v in history) / n
        avg_value = sum(v.value for v in history) / n
        avg_eff = sum(v.efficiency for v in history) / n
        grade = self._grade(avg_value)
        return ValueScore(
            entity_id=org_id,
            entity_type="org",
            success_rate=round(avg_sr, 3),
            stability_gain=round(avg_sg, 3),
            resource_cost=round(avg_rc, 4),
            value=round(avg_value, 4),
            efficiency=round(avg_eff, 4),
            grade=grade,
        )

    def get_market_signals(self, org_id: str) -> dict:
        """Generate buy/sell/hold signals for org based on performance."""
        vs = self.evaluate_org(org_id)
        signals = {"signal": "HOLD", "confidence": 0.5, "reason": ""}
        if vs.grade == "A":
            signals = {"signal": "BUY", "confidence": vs.value, "reason": f"A-grade org (value={vs.value:.2f})"}
        elif vs.grade == "B":
            signals = {"signal": "BUY", "confidence": 0.7, "reason": "B-grade org, stable performer"}
        elif vs.grade == "F":
            signals = {"signal": "SELL", "confidence": 0.9, "reason": "F-grade org, reallocate jobs"}
        elif vs.grade == "D":
            signals = {"signal": "SELL", "confidence": 0.7, "reason": "D-grade org, monitor closely"}
        return signals

    def get_top_orgs(self, n: int = 3) -> list[ValueScore]:
        """Get top N orgs by value score."""
        all_orgs = list(self.org_history.keys())
        scored = [self.evaluate_org(oid) for oid in all_orgs]
        scored.sort(key=lambda v: v.value, reverse=True)
        return scored[:n]


if __name__ == "__main__":
    ve = ValueEvaluator()

    # Evaluate jobs
    e1 = ve.evaluate_job("J1", "DEV_TEAM", success=True,
                          stability_delta=0.12, resource_cost=0.50)
    e2 = ve.evaluate_job("J2", "DEV_TEAM", success=True,
                          stability_delta=0.08, resource_cost=0.30)
    e3 = ve.evaluate_job("J3", "OPS_TEAM", success=False,
                          stability_delta=-0.05, resource_cost=0.70)
    e4 = ve.evaluate_job("J4", "QA_TEAM", success=True,
                          stability_delta=0.06, resource_cost=0.25)

    print(f"[EVAL] J1: {e1.feedback}")
    print(f"[EVAL] J3: {e3.feedback}")
    print(f"[EVAL] J4: {e4.feedback}")
    print(f"[EVAL] DEV_TEAM: {ve.evaluate_org('DEV_TEAM')}")
    print(f"[EVAL] OPS_TEAM: {ve.evaluate_org('OPS_TEAM')}")
    print(f"[EVAL] QA_TEAM: {ve.evaluate_org('QA_TEAM')}")
    print(f"[EVAL] top orgs: {ve.get_top_orgs()}")
    print(f"[EVAL] signals DEV: {ve.get_market_signals('DEV_TEAM')}")
