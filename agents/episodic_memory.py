"""
TAAR v4 — Episodic Memory System
Stores EXPERIENCE GRAPHS (not logs).
Each episode = one mission outcome + decisions + learned policies.
"""

from __future__ import annotations

import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Decision:
    state: str        # what happened
    action: str        # what was done
    reason: str        # why


@dataclass
class LearnedPolicy:
    """How routing/execution policies evolved from this episode."""
    swarm_threshold_modified: bool = False
    devops_sensitivity_modified: bool = False
    new_swarm_triggers: list[str] = field(default_factory=list)
    blocked_shell_patterns: list[str] = field(default_factory=list)
    mode_overrides: dict[str, str] = field(default_factory=dict)   # intent_pattern → mode


@dataclass
class Episode:
    """One mission = one episode."""
    episode_id: str
    mission_id: str
    goal: str
    outcome: str              # success | partial | failure
    duration_s: float
    graphs_executed: int
    nodes_completed: int
    nodes_failed: int
    decisions: list[dict] = field(default_factory=list)  # [{state, action, reason}]
    resource_usage: dict[str, Any] = field(default_factory=dict)
    final_result: str = ""
    learned: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.timestamp))
        return d


class EpisodicMemory:
    """
    Experience store: episodes + queries + policy extraction.
    NOT a log dump — structured experience with retrieval.
    """

    def __init__(self, store_path: str = "/tmp/taar_episodes.jsonl"):
        self.store_path = store_path
        self._episodes: list[Episode] = []
        self._load()

    def _load(self):
        """Load existing episodes from disk."""
        try:
            with open(self.store_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    self._episodes.append(Episode(**d))
        except FileNotFoundError:
            pass

    def store(self, episode: Episode):
        """Persist episode to disk + memory."""
        self._episodes.append(episode)
        try:
            with open(self.store_path, "a") as f:
                f.write(json.dumps(episode.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def add_decision(self, episode_id: str, state: str, action: str, reason: str):
        """Add a decision record to an in-memory episode."""
        for ep in reversed(self._episodes):
            if ep.episode_id == episode_id:
                ep.decisions.append(Decision(state=state, action=action, reason=reason).to_dict())
                break

    def query_outcomes(self, goal_pattern: str = "", limit: int = 5) -> list[Episode]:
        """Find recent episodes matching goal pattern."""
        results = []
        for ep in reversed(self._episodes):
            if goal_pattern and goal_pattern.lower() not in ep.goal.lower():
                continue
            results.append(ep)
            if len(results) >= limit:
                break
        return results

    def get_success_rate(self, mode: str = "") -> float:
        """Calculate success rate across all episodes (optionally per mode)."""
        if not self._episodes:
            return 0.0
        if mode:
            eps = [e for e in self._episodes if e.learned.get("mode") == mode]
        else:
            eps = self._episodes
        if not eps:
            return 0.0
        return sum(1 for e in eps if e.outcome == "success") / len(eps)

    def extract_policy_hints(self) -> dict[str, Any]:
        """Derive routing hints from recent failure patterns."""
        recent = self._episodes[-10:]
        hints = {
            "devops_trigger_extra": [],
            "swarm_threshold_adjustment": 0,
            "fallback_mode": "TOOL",
            "total_episodes": len(self._episodes),
            "success_rate": self.get_success_rate(),
        }
        for ep in recent:
            if ep.outcome == "failure":
                # If SINGLE failed repeatedly → suggest DEVOPS or TOOL
                if ep.learned.get("mode") == "SINGLE":
                    hints["fallback_mode"] = "TOOL"
                # If no graphs completed → add devops trigger
                if ep.graphs_executed == 0:
                    hints["devops_trigger_extra"].append(ep.goal[:60])
        return hints

    def summarize(self) -> dict[str, Any]:
        """Quick summary of all stored episodes."""
        if not self._episodes:
            return {"total": 0, "success_rate": 0.0, "recent": []}
        recent = self._episodes[-5:]
        return {
            "total": len(self._episodes),
            "success_rate": self.get_success_rate(),
            "recent": [{"id": e.episode_id, "goal": e.goal[:50],
                        "outcome": e.outcome} for e in recent],
            "hints": self.extract_policy_hints(),
        }
