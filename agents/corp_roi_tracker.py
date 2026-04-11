"""
TAAR v13 — ROI Tracker & Performance Ledger
Tracks cost/benefit for every task and employee.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time

class PerformanceRating(str, Enum):
    EXCEPTIONAL = "exceptional"  # ROI > 5x
    GOOD = "good"                # ROI 2-5x
    ADEQUATE = "adequate"        # ROI 1-2x
    POOR = "poor"                # ROI < 1x

@dataclass
class TaskOutcome:
    task_id: str
    employee_id: str
    department: str
    cost: float
    value: float
    roi: float
    rating: PerformanceRating
    duration_ms: float
    quality_score: float
    timestamp: float = field(default_factory=time.time)

class ROITracker:
    def __init__(self):
        self.outcomes: list[TaskOutcome] = []
        self.employee_scores: dict[str, list[float]] = {}

    def record(self, task_id: str, employee_id: str, department: str,
               cost: float, value: float, duration_ms: float, quality_score: float = 0.8) -> TaskOutcome:
        roi = value / max(0.01, cost)
        rating = (PerformanceRating.EXCEPTIONAL if roi > 5 else
                  PerformanceRating.GOOD if roi > 2 else
                  PerformanceRating.ADEQUATE if roi > 1 else PerformanceRating.POOR)
        outcome = TaskOutcome(task_id, employee_id, department, cost, value, roi, rating, duration_ms, quality_score)
        self.outcomes.append(outcome)
        self.employee_scores.setdefault(employee_id, []).append(roi)
        return outcome

    def employee_roi(self, employee_id: str) -> dict:
        scores = self.employee_scores.get(employee_id, [])
        if not scores:
            return {"avg_roi": 0.0, "tasks": 0, "rating": PerformanceRating.POOR}
        avg = sum(scores) / len(scores)
        rating = (PerformanceRating.EXCEPTIONAL if avg > 5 else
                  PerformanceRating.GOOD if avg > 2 else
                  PerformanceRating.ADEQUATE if avg > 1 else PerformanceRating.POOR)
        return {"avg_roi": avg, "tasks": len(scores), "rating": rating}

    def corp_roi(self) -> dict:
        if not self.outcomes:
            return {"total_cost": 0, "total_value": 0, "corp_roi": 0.0, "rating": PerformanceRating.POOR}
        total_cost = sum(o.cost for o in self.outcomes)
        total_value = sum(o.value for o in self.outcomes)
        corp_roi = total_value / max(0.01, total_cost)
        return {
            "total_cost": total_cost, "total_value": total_value,
            "corp_roi": corp_roi, "total_tasks": len(self.outcomes),
            "rating": (PerformanceRating.EXCEPTIONAL if corp_roi > 5 else
                      PerformanceRating.GOOD if corp_roi > 2 else
                      PerformanceRating.ADEQUATE if corp_roi > 1 else PerformanceRating.POOR),
            "by_department": self._by_department(),
        }

    def _by_department(self) -> dict:
        depts: dict[str, list[TaskOutcome]] = {}
        for o in self.outcomes:
            depts.setdefault(o.department, []).append(o)
        return {d: {"roi": sum(x.roi for x in v) / max(1, len(v)), "tasks": len(v)}
                for d, v in depts.items()}

    def promote_candidates(self) -> list[str]:
        return [eid for eid, scores in self.employee_scores.items()
                if sum(scores)/len(scores) > 3.0 and len(scores) >= 3]

    def fire_candidates(self) -> list[str]:
        return [eid for eid, scores in self.employee_scores.items()
                if sum(scores)/len(scores) < 0.5 and len(scores) >= 3]

if __name__ == "__main__":
    tracker = ROITracker()
    for _ in range(3):
        tracker.record("T001", "E003", "DevOps", cost=0.5, value=3.5, duration_ms=500)
        tracker.record("T002", "E002", "Engineering", cost=1.2, value=1.5, duration_ms=2000)
    print("Corp ROI:", tracker.corp_roi())
    print("Promote:", tracker.promote_candidates())
    print("Fire:", tracker.fire_candidates())
