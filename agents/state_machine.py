"""
TAAR v3 — State Machine Engine
Tracks: running / completed / failed / retry_queue
Persists to memory layer on every state change.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time

class NodeStatus(str, Enum):
    PENDING     = "pending"
    RUNNING     = "running"
    COMPLETED   = "completed"
    FAILED      = "failed"
    RETRY_QUEUE = "retry_queue"

@dataclass
class ExecutionTraceEntry:
    timestamp: float
    node_id: str
    from_status: str
    to_status: str
    event: str
    detail: str | None = None

@dataclass
class ResourceSnapshot:
    vram_used_mb: float = 0.0
    ram_used_mb: float = 0.0
    llm_calls: int = 0
    cpu_percent: float = 0.0

@dataclass
class StateSnapshot:
    running: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    retry_queue: list[str] = field(default_factory=list)
    resource: ResourceSnapshot = field(default_factory=ResourceSnapshot)
    execution_trace: list[ExecutionTraceEntry] = field(default_factory=list)

class StateMachine:
    """
    Finite State Machine for DAG execution.
    - Nodes transition: pending → running → completed | failed
    - Failed nodes with retries remaining go to retry_queue
    - Every transition is logged to execution_trace
    - State is persisted to memory layer on every update
    """

    def __init__(self, session_id: str = "default", persist_fn=None):
        self.session_id = session_id
        self.persist_fn = persist_fn  # optional: memory.add_* callback
        self.state = StateSnapshot()
        self._started_at = time.time()

    # ── State transitions ───────────────────────────────────────────────────

    def update_node_status(self, node_id: str, new_status: NodeStatus,
                           result: Any = None, error: str | None = None,
                           retry_count: int = 0) -> None:
        """Transition a node to new_status with full audit trail."""
        old_status = self._get_node_status(node_id)

        entry = ExecutionTraceEntry(
            timestamp=time.time(),
            node_id=node_id,
            from_status=old_status,
            to_status=new_status.value,
            event=f"transition:{old_status}→{new_status.value}",
            detail=error or str(result)[:100] if result else None,
        )
        self.state.execution_trace.append(entry)

        # Remove from all lists
        for lst in [self.state.running, self.state.completed,
                    self.state.failed, self.state.retry_queue]:
            if node_id in lst:
                lst.remove(node_id)

        # Add to new list
        if new_status == NodeStatus.RUNNING:
            self.state.running.append(node_id)
        elif new_status == NodeStatus.COMPLETED:
            self.state.completed.append(node_id)
        elif new_status == NodeStatus.FAILED:
            if retry_count < 2:
                self.state.retry_queue.append(node_id)
            else:
                self.state.failed.append(node_id)
        elif new_status == NodeStatus.RETRY_QUEUE:
            self.state.retry_queue.append(node_id)

        # Persist to memory
        self._persist()

    def _get_node_status(self, node_id: str) -> str:
        for lst_name, lst in [
            ("running", self.state.running),
            ("completed", self.state.completed),
            ("failed", self.state.failed),
            ("retry_queue", self.state.retry_queue),
        ]:
            if node_id in lst:
                return lst_name
        return "pending"

    def get_ready_nodes(self, graph: dict[str, Any]) -> list[str]:
        """Return node IDs whose dependencies are all completed."""
        ready = []
        for node in graph.get("nodes", []):
            nid = node.id if hasattr(node, "id") else node.get("id")
            deps = node.depends_on if hasattr(node, "depends_on") else node.get("depends_on", [])
            if nid not in self.state.completed and nid not in self.state.running:
                if all(d in self.state.completed for d in deps):
                    ready.append(nid)
        return ready

    def is_all_done(self) -> bool:
        return (len(self.state.running) == 0 and
                len(self.state.retry_queue) == 0 and
                (len(self.state.completed) > 0 or len(self.state.failed) > 0))

    def is_failure_terminal(self) -> bool:
        """No more retries, no running tasks, but failures exist."""
        return (len(self.state.retry_queue) == 0 and
                len(self.state.running) == 0 and
                len(self.state.failed) > 0)

    def update_resources(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self.state.resource, k):
                setattr(self.state.resource, k, v)

    def _persist(self) -> None:
        if self.persist_fn:
            try:
                self.persist_fn(self.session_id, self.to_dict())
            except Exception:
                pass  # best-effort

    # ── Serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "elapsed_s": round(time.time() - self._started_at, 1),
            "running": self.state.running,
            "completed": self.state.completed,
            "failed": self.state.failed,
            "retry_queue": self.state.retry_queue,
            "resource_usage": {
                "vram_mb": self.state.resource.vram_used_mb,
                "ram_mb": self.state.resource.ram_used_mb,
                "llm_calls": self.state.resource.llm_calls,
                "cpu_percent": self.state.resource.cpu_percent,
            },
            "execution_trace": [
                {"ts": e.timestamp, "node": e.node_id,
                 "from": e.from_status, "to": e.to_status,
                 "event": e.event, "detail": e.detail}
                for e in self.state.execution_trace
            ],
        }
