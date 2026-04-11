"""
TAAR v13 — Budget Controller
Manages GPU time, token budget, compute allocation per department.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time

class BudgetCategory(str, Enum):
    GPU_COMPUTE = "gpu_compute"
    LLM_CALLS = "llm_calls"
    CPU_WORKERS = "cpu_workers"
    STORAGE = "storage"
    NETWORK = "network"

@dataclass
class Budget:
    category: BudgetCategory
    allocated: float
    spent: float = 0.0
    cycle_start: float = field(default_factory=time.time)

    def remaining(self) -> float:
        return max(0.0, self.allocated - self.spent)

    def utilization(self) -> float:
        return self.spent / max(0.001, self.allocated)

    def is_overbudget(self) -> bool:
        return self.spent > self.allocated

class BudgetController:
    def __init__(self):
        self.budgets: dict[BudgetCategory, Budget] = {
            BudgetCategory.GPU_COMPUTE: Budget(BudgetCategory.GPU_COMPUTE, 100.0),
            BudgetCategory.LLM_CALLS: Budget(BudgetCategory.LLM_CALLS, 50.0),
            BudgetCategory.CPU_WORKERS: Budget(BudgetCategory.CPU_WORKERS, 200.0),
            BudgetCategory.STORAGE: Budget(BudgetCategory.STORAGE, 30.0),
            BudgetCategory.NETWORK: Budget(BudgetCategory.NETWORK, 20.0),
        }
        self.dept_budgets: dict[str, dict[BudgetCategory, float]] = {
            "Engineering": {BudgetCategory.LLM_CALLS: 20.0, BudgetCategory.GPU_COMPUTE: 30.0},
            "DevOps": {BudgetCategory.LLM_CALLS: 10.0, BudgetCategory.CPU_WORKERS: 80.0},
            "QA": {BudgetCategory.LLM_CALLS: 8.0, BudgetCategory.CPU_WORKERS: 40.0},
            "Security": {BudgetCategory.LLM_CALLS: 5.0, BudgetCategory.GPU_COMPUTE: 10.0},
            "Research": {BudgetCategory.LLM_CALLS: 15.0, BudgetCategory.GPU_COMPUTE: 40.0},
            "Infrastructure": {BudgetCategory.GPU_COMPUTE: 20.0, BudgetCategory.CPU_WORKERS: 60.0},
        }
        self.cycle = 0

    def request(self, category: BudgetCategory, amount: float, department: str = "General") -> bool:
        if self.budgets[category].is_overbudget():
            return False
        self.budgets[category].spent += amount
        return True

    def can_afford(self, category: BudgetCategory, amount: float) -> bool:
        return self.budgets[category].remaining() >= amount

    def reset_cycle(self):
        self.cycle += 1
        for b in self.budgets.values():
            b.spent = 0.0
            b.cycle_start = time.time()

    def get_report(self) -> dict:
        return {
            "cycle": self.cycle,
            "categories": {c.value: {"allocated": b.allocated, "spent": b.spent,
                                     "remaining": b.remaining(), "util": b.utilization()}
                          for c, b in self.budgets.items()},
            "total_util": sum(b.utilization() for b in self.budgets.values()) / len(self.budgets),
        }

if __name__ == "__main__":
    bc = BudgetController()
    ok1 = bc.request(BudgetCategory.LLM_CALLS, 5.0, "DevOps")
    ok2 = bc.request(BudgetCategory.GPU_COMPUTE, 150.0, "Research")
    print(f"LLM request: {'OK' if ok1 else 'DENIED'} | GPU request: {'OK' if ok2 else 'DENIED'}")
    print("Report:", bc.get_report())
