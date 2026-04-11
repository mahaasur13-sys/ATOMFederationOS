"""
TAAR v13 — Role Allocator
Maps incoming tasks to the right employee with best fit.
"""
from __future__ import annotations
from dataclasses import dataclass
from corp_org_registry import OrgRegistry, AIEmployee, AgentTier

@dataclass
class TaskAssignment:
    task_id: str
    employee: AIEmployee
    confidence: float
    department: str
    estimated_cost: float
    estimated_time: float

class RoleAllocator:
    def __init__(self, registry: OrgRegistry):
        self.registry = registry
        self.assignments: list[TaskAssignment] = []

    def allocate(self, task_id: str, task_type: str, required_skills: list[str],
                budget: float, urgency: str = "normal") -> TaskAssignment:
        candidates = [e for e in self.registry.employees.values()
                     if e.status.value != "offline"]
        scored = []
        for e in candidates:
            skill_match = sum(1 for s in required_skills
                            if s.lower() in [c.lower() for c in e.capabilities]) / max(1, len(required_skills))
            tier_bonus = {"executive": 1.3, "director": 1.2, "lead": 1.1, "senior": 1.0, "junior": 0.85}.get(e.tier.value, 1.0)
            if urgency == "high":
                tier_bonus = 1.0  # ignore tier for urgent tasks
            score = skill_match * 0.6 + e.score() * 0.3 * tier_bonus + (1.0 / max(1, e.stats.get("avg_response_time", 1))) * 0.1
            scored.append((e, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        best, score = scored[0] if scored else (None, 0.0)
        assignment = TaskAssignment(
            task_id=task_id, employee=best, confidence=score,
            department=best.department if best else "unassigned",
            estimated_cost=best.salary * 2 if best else 999.0,
            estimated_time=best.stats.get("avg_response_time", 3.0) * 1.5 if best else 99.0
        )
        self.assignments.append(assignment)
        return assignment

if __name__ == "__main__":
    reg = OrgRegistry()
    alloc = RoleAllocator(reg)
    a = alloc.allocate("T001", "ci_agent", ["ci_cd", "github_actions"], budget=5.0)
    print(f"Assigned: {a.employee.name if a.employee else 'None'} ({a.department}) | confidence={a.confidence:.2f}")
