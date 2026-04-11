"""
TAAR v6 — Shared Memory Layer
Cross-node context sync, conflict resolution, global state compression.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time, hashlib, json


@dataclass
class NodeSlice:
    node_id: str
    summary: str = ""
    last_update: float = field(default_factory=time.time)
    mission_results: list[str] = field(default_factory=list)
    local_episodes: int = 0


class DistributedMemory:
    """
    Shared memory across cluster nodes.
    Key principles:
    - Nodes write summaries, not raw state
    - Conflicts resolved by timestamp (latest wins)
    - Global state is a compressed view, not a full replica
    """

    def __init__(self):
        self.global_summary: dict[str, Any] = {
            "missions_completed": 0,
            "missions_failed": 0,
            "total_episodes": 0,
            "system_stability": 1.0,
            "last_consensus_ts": time.time(),
        }
        self.node_slices: dict[str, NodeSlice] = {}
        self.event_log: list[dict] = []
        self._compressed_context: dict[str, Any] = {}

    def write_node_slice(self, node_id: str, summary: str,
                         mission_result: str | None = None,
                         episodes_count: int = 0):
        """Node writes a compressed summary (not raw state)."""
        if node_id not in self.node_slices:
            self.node_slices[node_id] = NodeSlice(node_id=node_id)
        s = self.node_slices[node_id]
        s.summary = summary
        s.last_update = time.time()
        s.local_episodes += episodes_count
        if mission_result:
            s.mission_results.append(mission_result)
        self._invalidate_compressed()

    def read_global_summary(self) -> dict[str, Any]:
        """Returns compressed global state."""
        return dict(self.global_summary)

    def merge_node_summaries(self) -> dict[str, str]:
        """Returns node_id → summary map for LLM context."""
        return {nid: s.summary for nid, s in self.node_slices.items() if s.summary}

    def log_event(self, event_type: str, node_id: str, data: dict):
        self.event_log.append({
            "type": event_type,
            "node_id": node_id,
            "data": data,
            "ts": time.time(),
        })
        # Trim log to last 200 events
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]

    def update_global_stats(self, completed: int = 0, failed: int = 0):
        self.global_summary["missions_completed"] += completed
        self.global_summary["missions_failed"] += failed
        total = self.global_summary["missions_completed"] + self.global_summary["missions_failed"]
        self.global_summary["total_episodes"] = total
        if total > 0:
            self.global_summary["system_stability"] = (
                self.global_summary["missions_completed"] / total
            )
        self.global_summary["last_consensus_ts"] = time.time()

    def get_context_for_llm(self) -> str:
        """Returns compressed context string for LLM prompts."""
        summary = self.merge_node_summaries()
        events_recent = self.event_log[-10:]
        ctx = []
        ctx.append(f"System: {self.global_summary['missions_completed']}✓ {self.global_summary['missions_failed']}✗ stability={self.global_summary['system_stability']:.2f}")
        if summary:
            ctx.append("Node summaries:")
            for nid, s in summary.items():
                ctx.append(f"  [{nid}] {s[:100]}")
        if events_recent:
            ctx.append("Recent events:")
            for e in events_recent:
                ctx.append(f"  [{e['node_id']}] {e['type']}: {str(e['data'])[:60]}")
        return "\n".join(ctx)

    def _invalidate_compressed(self):
        self._compressed_context.clear()

    def get_stats(self) -> dict:
        return {
            "nodes": len(self.node_slices),
            "events": len(self.event_log),
            "global": self.global_summary,
        }
