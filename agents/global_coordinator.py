"""
TAAR v6 — Global Coordinator
system brain: distributes missions → nodes, tracks health, fault isolation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid, time
from collections import defaultdict


@dataclass
class NodeHealth:
    node_id: str
    gpu_load: float = 0.0
    cpu_load: float = 0.0
    latency_ms: float = 0.0
    failure_rate: float = 0.0
    availability: float = 1.0
    missions_completed: int = 0
    missions_failed: int = 0
    last_seen: float = field(default_factory=time.time)

    def score(self) -> float:
        """Higher = more capable right now."""
        return (
            (1 - self.gpu_load) * 0.3 +
            (1 - self.cpu_load) * 0.2 +
            (1 - self.latency_ms / 1000.0) * 0.2 +
            (1 - self.failure_rate) * 0.3
        ) * self.availability


class GlobalCoordinator:
    """
    Central brain of the distributed cluster.
    Assigns missions to nodes, monitors health, handles fault isolation.
    """

    def __init__(self):
        self.nodes: dict[str, NodeHealth] = {}
        self.assignments: dict[str, str] = {}  # mission_id → node_id
        self._mission_history: list[dict] = []

    def register_node(self, node_id: str) -> NodeHealth:
        self.nodes[node_id] = NodeHealth(node_id=node_id)
        return self.nodes[node_id]

    def update_node_health(self, node_id: str, gpu: float, cpu: float, latency: float = 0.0):
        if node_id not in self.nodes:
            self.register_node(node_id)
        h = self.nodes[node_id]
        h.gpu_load = min(1.0, max(0.0, gpu))
        h.cpu_load = min(1.0, max(0.0, cpu))
        h.latency_ms = max(0.0, latency)
        h.last_seen = time.time()

    def mark_mission_complete(self, node_id: str, mission_id: str, success: bool):
        if node_id in self.nodes:
            h = self.nodes[node_id]
            if success:
                h.missions_completed += 1
                h.failure_rate = h.missions_failed / max(1, h.missions_completed + h.missions_failed)
            else:
                h.missions_failed += 1
                h.failure_rate = h.missions_failed / max(1, h.missions_completed + h.missions_failed)
        self._mission_history.append({
            "mission_id": mission_id,
            "node_id": node_id,
            "success": success,
            "ts": time.time(),
        })
        if mission_id in self.assignments:
            del self.assignments[mission_id]

    def get_best_node(self, exclude: set[str] | None = None) -> Optional[str]:
        """Return node_id with highest capability score."""
        candidates = {
            nid: h for nid, h in self.nodes.items()
            if h.availability > 0.5 and (exclude is None or nid not in exclude)
        }
        if not candidates:
            return None
        return max(candidates, key=lambda nid: candidates[nid].score())

    def assign_mission(self, mission_id: str, node_id: str):
        self.assignments[mission_id] = node_id

    def get_node_for_mission(self, mission_id: str) -> Optional[str]:
        return self.assignments.get(mission_id)

    def isolate_node(self, node_id: str, reason: str):
        if node_id in self.nodes:
            self.nodes[node_id].availability = 0.0
        # Reassign pending missions from this node
            for mid, nid in list(self.assignments.items()):
                if nid == node_id:
                    new_node = self.get_best_node(exclude={node_id})
                    if new_node:
                        self.assignments[mid] = new_node
                        print(f"[COORDINATOR] Reassigned {mid} → {new_node} (node {node_id} isolated: {reason})")

    def get_cluster_health(self) -> dict:
        if not self.nodes:
            return {"cluster_stability": 0.0, "total_nodes": 0, "healthy_nodes": 0}
        healthy = sum(1 for h in self.nodes.values() if h.availability > 0.5)
        avg_failure = sum(h.failure_rate for h in self.nodes.values()) / len(self.nodes)
        return {
            "cluster_stability": healthy / max(1, len(self.nodes)),
            "total_nodes": len(self.nodes),
            "healthy_nodes": healthy,
            "avg_failure_rate": avg_failure,
            "nodes": {
                nid: {
                    "score": h.score(),
                    "gpu": h.gpu_load,
                    "cpu": h.cpu_load,
                    "availability": h.availability,
                    "failure_rate": h.failure_rate,
                }
                for nid, h in self.nodes.items()
            },
        }

    def get_stats(self) -> dict:
        return {
            "total_nodes": len(self.nodes),
            "active_missions": len(self.assignments),
            "total_processed": len(self._mission_history),
        }
