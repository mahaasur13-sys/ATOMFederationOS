"""
TAAR v13 — Organization Registry
Tracks all AI employees, departments, and org structure.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

class AgentTier(str, Enum):
    JUNIOR = "junior"
    SENIOR = "senior"
    LEAD = "lead"
    DIRECTOR = "director"
    EXECUTIVE = "executive"

class AgentStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"

@dataclass
class AIEmployee:
    eid: str
    name: str
    role: str
    tier: AgentTier
    department: str
    capabilities: list[str]
    stats: dict  # efficiency, tasks_completed, failures, avg_response_time
    salary: float  # compute cost per task
    hire_date: float = field(default_factory=time.time)
    status: AgentStatus = AgentStatus.ACTIVE

    def score(self) -> float:
        s = self.stats
        success_rate = s["tasks_completed"] / max(1, s["tasks_completed"] + s["failures"])
        efficiency = s.get("efficiency", 1.0)
        return (success_rate * 0.4 + efficiency * 0.4 + (1.0 / max(1, s.get("avg_response_time", 1))) * 0.2)

class OrgRegistry:
    def __init__(self):
        self.employees: dict[str, AIEmployee] = {}
        self.departments: dict[str, dict] = {}
        self._init_departments()
        self._hire_founding_team()

    def _init_departments(self):
        self.departments = {
            "Engineering": {"head": None, "budget": 100.0, "priority": 10},
            "DevOps": {"head": None, "budget": 80.0, "priority": 9},
            "QA": {"head": None, "budget": 60.0, "priority": 7},
            "Security": {"head": None, "budget": 70.0, "priority": 10},
            "Research": {"head": None, "budget": 50.0, "priority": 6},
            "Infrastructure": {"head": None, "budget": 90.0, "priority": 8},
        }

    def _hire_founding_team(self):
        hires = [
            AIEmployee("E001", "CodeBot-Jr", "code_generation", AgentTier.JUNIOR, "Engineering",
                      ["python", "typescript", "refactor"], {"tasks_completed": 8, "failures": 2, "efficiency": 0.7, "avg_response_time": 2.1}, 0.5),
            AIEmployee("E002", "ArchBot-Sr", "architecture", AgentTier.SENIOR, "Engineering",
                      ["architecture", "python", "system_design"], {"tasks_completed": 12, "failures": 1, "efficiency": 0.9, "avg_response_time": 3.5}, 1.2),
            AIEmployee("E003", "CIOps-Lead", "ci_agent", AgentTier.LEAD, "DevOps",
                      ["ci_cd", "github_actions", "pytest", "ruff"], {"tasks_completed": 20, "failures": 1, "efficiency": 0.95, "avg_response_time": 1.2}, 0.8),
            AIEmployee("E004", "PatchBot", "patch_generation", AgentTier.SENIOR, "DevOps",
                      ["debugging", "ruff", "pytest", "patch"], {"tasks_completed": 15, "failures": 3, "efficiency": 0.85, "avg_response_time": 2.0}, 0.9),
            AIEmployee("E005", "TestBot", "test_generation", AgentTier.JUNIOR, "QA",
                      ["pytest", "coverage", "validation"], {"tasks_completed": 10, "failures": 1, "efficiency": 0.8, "avg_response_time": 2.5}, 0.6),
            AIEmployee("E006", "SecBot", "threat_detector", AgentTier.SENIOR, "Security",
                      ["security", "policy", "audit"], {"tasks_completed": 7, "failures": 0, "efficiency": 1.0, "avg_response_time": 1.8}, 1.0),
            AIEmployee("E007", "ExploreBot", "exploration", AgentTier.JUNIOR, "Research",
                      ["research", "analysis", "strategy"], {"tasks_completed": 5, "failures": 1, "efficiency": 0.75, "avg_response_time": 4.0}, 0.7),
            AIEmployee("E008", "InfraBot", "infra_management", AgentTier.SENIOR, "Infrastructure",
                      ["docker", "k8s", "terraform", "gpu"], {"tasks_completed": 11, "failures": 2, "efficiency": 0.88, "avg_response_time": 2.3}, 1.1),
        ]
        for e in hires:
            self.employees[e.eid] = e
        # Set department heads
        self.departments["Engineering"]["head"] = "E002"
        self.departments["DevOps"]["head"] = "E003"
        self.departments["QA"]["head"] = "E005"
        self.departments["Security"]["head"] = "E006"
        self.departments["Research"]["head"] = "E007"
        self.departments["Infrastructure"]["head"] = "E008"

    def assign_task(self, task_type: str) -> Optional[AIEmployee]:
        candidates = [e for e in self.employees.values()
                    if e.status == AgentStatus.ACTIVE and task_type.lower() in [c.lower() for c in e.capabilities]]
        if not candidates:
            candidates = [e for e in self.employees.values() if e.status == AgentStatus.ACTIVE]
        if not candidates:
            return None
        return max(candidates, key=lambda e: e.score())

    def restructure(self, changes: dict) -> dict:
        results = {}
        for action, params in changes.items():
            if action == "promote" and params["eid"] in self.employees:
                e = self.employees[params["eid"]]
                tiers = list(AgentTier)
                idx = tiers.index(e.tier)
                if idx < len(tiers) - 1:
                    e.tier = tiers[idx + 1]
                    results[params["eid"]] = f"promoted to {e.tier.value}"
            elif action == "downgrade" and params["eid"] in self.employees:
                e = self.employees[params["eid"]]
                tiers = list(AgentTier)
                idx = tiers.index(e.tier)
                if idx > 0:
                    e.tier = tiers[idx - 1]
                    results[params["eid"]] = f"downgraded to {e.tier.value}"
            elif action == "fire" and params["eid"] in self.employees:
                e = self.employees[params["eid"]]
                e.status = AgentStatus.OFFLINE
                results[params["eid"]] = "terminated"
        return results

    def org_chart(self) -> dict:
        return {
            "total_employees": len([e for e in self.employees.values() if e.status != AgentStatus.OFFLINE]),
            "departments": {d: {"head": self.departments[d]["head"], "size": len([e for e in self.employees.values() if e.department == d and e.status != AgentStatus.OFFLINE])} for d in self.departments},
            "avg_score": sum(e.score() for e in self.employees.values()) / max(1, len(self.employees)),
        }

if __name__ == "__main__":
    reg = OrgRegistry()
    chart = reg.org_chart()
    print(f"Org chart: {chart}")
    e = reg.assign_task("ci_cd")
    print(f"Assigned to CI: {e.name if e else 'None'}")
