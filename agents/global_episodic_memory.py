"""
TAAR v6 — Global Episodic Memory Graph
Stores distributed mission outcomes, node failures, policy evolution history.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time, json
from pathlib import Path


@dataclass
class DistEpisode:
    episode_id: str
    mission: str
    nodes_involved: list[str]
    outcome: str  # completed | failed | degraded
    duration_s: float
    node_results: dict[str, str]  # node_id → result
    decision_path: list[str]
    learned: str = ""
    policy_delta: dict[str, Any] | None = None
    ts: float = field(default_factory=time.time)


class GlobalEpisodicMemory:
    """
    Shared episodic memory across all cluster nodes.
    Stores mission outcomes, node failures, policy evolution.
    """

    def __init__(self, storage_path: str = "/tmp/taar_v6_episodes.jsonl"):
        self._episodes: list[DistEpisode] = []
        self._node_failures: list[dict] = []
        self._policy_history: list[dict] = []
        self._perf_trend: list[float] = []  # rolling stability scores
        self._storage_path = storage_path
        self._load()

    def store(self, ep: DistEpisode):
        self._episodes.append(ep)
        # Update performance trend
        outcome_val = 1.0 if ep.outcome == "completed" else 0.0 if ep.outcome == "failed" else 0.5
        self._perf_trend.append(outcome_val)
        if len(self._perf_trend) > 50:
            self._perf_trend = self._perf_trend[-50:]
        self._save()

    def record_node_failure(self, node_id: str, mission_id: str, reason: str):
        self._node_failures.append({
            "node_id": node_id,
            "mission_id": mission_id,
            "reason": reason,
            "ts": time.time(),
        })

    def record_policy_delta(self, param: str, old_val: float, new_val: float, reason: str, by_node: str):
        self._policy_history.append({
            "param": param,
            "old_value": old_val,
            "new_value": new_val,
            "reason": reason,
            "by_node": by_node,
            "ts": time.time(),
        })

    def get_success_rate(self, last_n: int = 20) -> float:
        recent = self._episodes[-last_n:]
        if not recent:
            return 1.0
        completed = sum(1 for e in recent if e.outcome == "completed")
        return completed / len(recent)

    def get_trend(self) -> str:
        if len(self._perf_trend) < 5:
            return "insufficient_data"
        recent = self._perf_trend[-10:]
        if all(recent[-1] >= r for r in recent[:-1]):
            return "improving"
        if all(recent[-1] <= r for r in recent[:-1]):
            return "declining"
        return "stable"

    def query(self, last_n: int = 20) -> list[DistEpisode]:
        return list(self._episodes[-last_n:])

    def get_stats(self) -> dict:
        return {
            "total_episodes": len(self._episodes),
            "node_failures": len(self._node_failures),
            "policy_changes": len(self._policy_history),
            "success_rate": self.get_success_rate(),
            "trend": self.get_trend(),
        }

    def _save(self):
        try:
            data = [
                {
                    **vars(ep),
                    "ts": ep.ts,
                }
                for ep in self._episodes[-100:]
            ]
            Path(self._storage_path).write_text(
                "\n".join(json.dumps(r) for r in data)
            )
        except Exception:
            pass

    def _load(self):
        try:
            if Path(self._storage_path).exists():
                for line in Path(self._storage_path).read_text().strip().split("\n"):
                    if line:
                        d = json.loads(line)
                        self._episodes.append(DistEpisode(**d))
        except Exception:
            pass
