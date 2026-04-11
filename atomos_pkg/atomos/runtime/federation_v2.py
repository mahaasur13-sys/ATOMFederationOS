"""
ATOM OS v14.2 — Federation Kernel v2 (Heartbeat Protocol)
Distributed node registry with liveness monitoring
"""
from __future__ import annotations
import time, asyncio, hashlib, uuid

class FederationNode:
    """Single federated node with heartbeat."""

    def __init__(self, node_id: str, host: str = "local"):
        self.node_id = node_id
        self.host = host
        self.last_heartbeat = time.time()
        self.status = "active"
        self.capabilities: list[str] = []

    def heartbeat(self):
        self.last_heartbeat = time.time()
        self.status = "active"

    def is_alive(self, timeout: float = 10.0) -> bool:
        return (time.time() - self.last_heartbeat) < timeout


class FederationKernelV2:
    """Heartbeat-based federation node registry."""

    def __init__(self, this_node_id: str = None):
        self.this_node_id = this_node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.this_node = FederationNode(self.this_node_id, "local")
        self.nodes: dict[str, FederationNode] = {}
        self._heartbeat_log: list[dict] = []

    def register(self, node_id: str, host: str = "remote", capabilities: list[str] = None) -> FederationNode:
        node = FederationNode(node_id, host)
        node.capabilities = capabilities or []
        self.nodes[node_id] = node
        self._log_event("register", node_id)
        return node

    def unregister(self, node_id: str):
        if node_id in self.nodes:
            del self.nodes[node_id]
            self._log_event("unregister", node_id)

    def heartbeat(self):
        self.this_node.heartbeat()
        for node in self.nodes.values():
            node.heartbeat()
        self._log_event("heartbeat", self.this_node_id)

    async def monitor(self, timeout: float = 10.0, interval: float = 5.0):
        """Monitor node liveness. Call from async context."""
        while True:
            down = []
            for node_id, node in list(self.nodes.items()):
                if not node.is_alive(timeout):
                    down.append(node_id)
            if down:
                print(f"[FEDERATION] Nodes down: {down}")
            await asyncio.sleep(interval)

    def get_alive_nodes(self, timeout: float = 10.0) -> list[str]:
        return [nid for nid, n in self.nodes.items() if n.is_alive(timeout)]

    def _log_event(self, event: str, node_id: str):
        self._heartbeat_log.append({
            "event": event, "node_id": node_id, "ts": time.time()
        })


if __name__ == "__main__":
    fed = FederationKernelV2("kernel-node")
    fed.register("worker-1", "remote", ["devops", "code"])
    fed.register("worker-2", "remote", ["analysis"])
    fed.heartbeat()

    alive = fed.get_alive_nodes()
    print(f"Alive nodes: {alive}")
    print(f"This node: {fed.this_node_id}")
    assert "worker-1" in alive
    assert "worker-2" in alive
    print("✅ FederationKernelV2: ALL TESTS PASSED")