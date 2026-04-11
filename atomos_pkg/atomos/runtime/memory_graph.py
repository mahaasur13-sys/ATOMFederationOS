"""
ATOM OS v14.2 — Stateful Memory Graph
Persistent node/edge graph for OS runtime memory
"""
from __future__ import annotations
import time, hashlib

class MemoryGraph:
    """In-memory node/edge graph for ATOM OS state."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self._version = 0

    def add_node(self, node_id: str, data: dict):
        self.nodes[node_id] = {
            "data": data,
            "state": "active",
            "version": self._version,
            "created_at": time.time(),
        }
        self._version += 1

    def add_edge(self, from_id: str, to_id: str):
        if from_id in self.nodes and to_id in self.nodes:
            self.edges.append((from_id, to_id))

    def get_state(self, node_id: str) -> dict | None:
        return self.nodes.get(node_id)

    def update_state(self, node_id: str, updates: dict):
        if node_id in self.nodes:
            self.nodes[node_id]["data"].update(updates)
            self.nodes[node_id]["state"] = updates.get("state", self.nodes[node_id]["state"])
            self.nodes[node_id]["version"] = self._version
            self._version += 1

    def query(self, predicate) -> list[str]:
        return [nid for nid, n in self.nodes.items() if predicate(n)]


if __name__ == "__main__":
    g = MemoryGraph()
    g.add_node("session_1", {"intent": "fix ruff error", "risk": 0.3})
    g.add_node("plan_1", {"steps": 3, "status": "safe"})
    g.add_edge("session_1", "plan_1")
    state = g.get_state("plan_1")
    print(f"Nodes: {len(g.nodes)}, Edges: {len(g.edges)}")
    print(f"Session state: {state}")
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    print("✅ MemoryGraph: ALL TESTS PASSED")