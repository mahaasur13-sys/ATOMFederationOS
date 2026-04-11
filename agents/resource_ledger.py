"""
TAAR v8 — Resource Ledger
Tracks: compute cycles, GPU time, LLM tokens, memory bandwidth, execution cost.
Per-node and system-wide accounting.
"""

from __future__ import annotations
import uuid, time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeResources:
    """Per-node resource snapshot."""
    node_id: str
    gpu_cost: float = 0.0
    llm_cost: float = 0.0
    compute_units: float = 1.0
    execution_efficiency: float = 0.90
    jobs_completed: int = 0
    jobs_failed: int = 0
    uptime_s: float = 0.0
    last_update: float = field(default_factory=time.time)


@dataclass
class LedgerEntry:
    """Individual resource transaction."""
    entry_id: str
    node_id: str
    resource_type: str  # gpu | llm | compute | memory | execution
    amount: float
    cost: float
    job_id: str | None
    timestamp: float = field(default_factory=time.time)


class ResourceLedger:
    """
    Economic accounting layer.
    Tracks resource consumption per node, per job, system-wide.
    Enables cost allocation, billing, efficiency scoring.
    """

    COST_PER_GPU_UNIT = 0.05   # per GPU-second
    COST_PER_LLM_TOKEN = 0.0001
    COST_PER_COMPUTE_UNIT = 0.01
    COST_PER_MEMORY_GB_S = 0.002

    def __init__(self):
        self.nodes: dict[str, NodeResources] = {}
        self.entries: list[LedgerEntry] = []
        self.ledger_history: list[dict] = []

    def register_node(self, node_id: str):
        """Register a new node."""
        self.nodes[node_id] = NodeResources(node_id=node_id)

    def charge(self, node_id: str, resource_type: str,
                amount: float, job_id: str | None = None) -> float:
        """Charge a node for resource usage. Returns cost."""
        cost = self._compute_cost(resource_type, amount)
        entry = LedgerEntry(
            entry_id=f"LE-{uuid.uuid4().hex[:8].upper()}",
            node_id=node_id,
            resource_type=resource_type,
            amount=amount,
            cost=cost,
            job_id=job_id,
        )
        self.entries.append(entry)
        if node_id in self.nodes:
            nr = self.nodes[node_id]
            if resource_type == "gpu":
                nr.gpu_cost = cost
            elif resource_type == "llm":
                nr.llm_cost = cost
        return cost

    def _compute_cost(self, resource_type: str, amount: float) -> float:
        rates = {
            "gpu": self.COST_PER_GPU_UNIT,
            "llm": self.COST_PER_LLM_TOKEN,
            "compute": self.COST_PER_COMPUTE_UNIT,
            "memory": self.COST_PER_MEMORY_GB_S,
            "execution": 0.03,
        }
        rate = rates.get(resource_type, 0.01)
        return round(amount * rate, 6)

    def record_job(self, node_id: str, job_id: str, success: bool,
                   gpu_used: float, llm_tokens: int, compute_s: float):
        """Record a completed job's resource usage."""
        if node_id not in self.nodes:
            self.register_node(node_id)
        nr = self.nodes[node_id]
        nr.jobs_completed += 1
        if not success:
            nr.jobs_failed += 1
        self.charge(node_id, "gpu", gpu_used, job_id)
        self.charge(node_id, "llm", float(llm_tokens), job_id)
        self.charge(node_id, "compute", compute_s, job_id)

    def update_efficiency(self, node_id: str, efficiency: float):
        """Update node's execution efficiency score."""
        if node_id in self.nodes:
            self.nodes[node_id].execution_efficiency = max(0.0, min(1.0, efficiency))

    def get_node_report(self, node_id: str) -> dict:
        """Full resource report for a node."""
        if node_id not in self.nodes:
            return {}
        nr = self.nodes[node_id]
        total_cost = sum(
            e.cost for e in self.entries if e.node_id == node_id
        )
        entries_for_node = [e for e in self.entries if e.node_id == node_id]
        by_type = {}
        for e in entries_for_node:
            by_type.setdefault(e.resource_type, 0.0)
            by_type[e.resource_type] += e.cost
        return {
            "node_id": node_id,
            "total_cost": round(total_cost, 4),
            "cost_by_type": {k: round(v, 4) for k, v in by_type.items()},
            "jobs_completed": nr.jobs_completed,
            "jobs_failed": nr.jobs_failed,
            "efficiency": round(nr.execution_efficiency, 3),
            "uptime_s": round(time.time() - nr.last_update, 1),
        }

    def get_system_report(self) -> dict:
        """System-wide resource accounting."""
        total_entries = len(self.entries)
        total_cost = sum(e.cost for e in self.entries)
        by_type = {}
        for e in self.entries:
            by_type.setdefault(e.resource_type, 0.0)
            by_type[e.resource_type] += e.cost
        active_nodes = [n for n in self.nodes.values() if n.jobs_completed > 0]
        return {
            "total_cost": round(total_cost, 4),
            "cost_by_type": {k: round(v, 4) for k, v in by_type.items()},
            "active_nodes": len(active_nodes),
            "total_jobs_completed": sum(n.jobs_completed for n in self.nodes.values()),
            "total_jobs_failed": sum(n.jobs_failed for n in self.nodes.values()),
            "avg_efficiency": round(
                sum(n.execution_efficiency for n in active_nodes) / len(active_nodes)
                if active_nodes else 0.0, 3
            ),
            "total_entries": total_entries,
        }


if __name__ == "__main__":
    ledger = ResourceLedger()
    ledger.register_node("TAAR_v7_A")
    ledger.register_node("TAAR_v7_B")
    ledger.register_node("OPS_TEAM")

    # Record jobs
    ledger.record_job("TAAR_v7_A", "J1", success=True,
                      gpu_used=1.2, llm_tokens=5000, compute_s=3.5)
    ledger.record_job("TAAR_v7_A", "J2", success=True,
                      gpu_used=0.8, llm_tokens=3200, compute_s=2.1)
    ledger.record_job("TAAR_v7_B", "J3", success=False,
                      gpu_used=2.0, llm_tokens=8000, compute_s=5.0)
    ledger.update_efficiency("TAAR_v7_A", 0.93)
    ledger.update_efficiency("TAAR_v7_B", 0.71)

    print(f"[LEDGER] node_A: {ledger.get_node_report('TAAR_v7_A')}")
    print(f"[LEDGER] node_B: {ledger.get_node_report('TAAR_v7_B')}")
    print(f"[LEDGER] system: {ledger.get_system_report()}")
