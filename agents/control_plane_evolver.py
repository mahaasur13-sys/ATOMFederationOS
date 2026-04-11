"""
TAAR v5 — Control Plane Self-Modification Engine
Analyzes mission outcomes → adjusts routing weights/thresholds.
IF repeated failure pattern: modify control_plane routing logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from agents.episodic_memory import Episode


@dataclass
class PolicyDelta:
    param: str
    old_value: float
    new_value: float
    reason: str
    confidence: float  # 0.0-1.0


class ControlPlaneEvolver:
    """
    Evolves control_plane parameters based on accumulated experience.
    Reads from episodic_memory, writes to a policy snapshot.
    """

    # Default parameters (can be overridden)
    DEFAULTS = {
        "devops_sensitivity": 0.70,
        "swarm_threshold": 0.50,
        "single_agent_fallback": True,
        "max_swarm_workers": 8,
        "retry_rate_on_failure": 0.30,
        "stability_threshold": 0.75,
        "gpu_pressure_modulate": 0.85,
    }

    def __init__(self):
        self._current_policy = dict(self.DEFAULTS)
        self._change_log: list[PolicyDelta] = []
        self._failure_patterns: dict[str, int] = {}  # pattern → count

    def analyze_and_evolve(self, episodes: list[Episode]) -> dict[str, PolicyDelta]:
        """
        Scan recent episodes for failure patterns.
        Returns dict of param → PolicyDelta for changed params.
        """
        recent = episodes[-20:]  # last 20 episodes
        changes: dict[str, PolicyDelta] = {}

        # Helper: derive success from outcome string
        def is_success(ep) -> bool:
            return ep.outcome == "completed"

        # Helper: derive execution_mode from goal (best effort)
        def get_mode(ep) -> str:
            g = ep.goal.lower()
            if "devops" in g or "ci" in g or "build" in g or "ruff" in g or "test" in g:
                return "DEVOPS"
            if "swarm" in g or "parallel" in g or "concurrent" in g:
                return "SWARM"
            return "SINGLE"

        # ── Pattern: repeated DEVOPS failures ──
        devops_failures = [e for e in recent if get_mode(e) == "DEVOPS" and not is_success(e)]
        if len(devops_failures) >= 3:
            old = self._current_policy["devops_sensitivity"]
            new = max(0.30, old - 0.10)
            changes["devops_sensitivity"] = PolicyDelta(
                param="devops_sensitivity",
                old_value=old,
                new_value=new,
                reason=f"{len(devops_failures)} recent DEVOPS failures",
                confidence=min(len(devops_failures) / 10.0, 1.0),
            )

        # ── Pattern: high GPU pressure during SWARM ──
        swarm_high_gpu = [
            e for e in recent
            if get_mode(e) == "SWARM"
            and e.resource_usage
            and e.resource_usage.get("gpu_pressure", 0) > 0.85
        ]
        if len(swarm_high_gpu) >= 2:
            old = self._current_policy["max_swarm_workers"]
            new = max(2, old - 2)  # reduce workers under GPU pressure
            changes["max_swarm_workers"] = PolicyDelta(
                param="max_swarm_workers",
                old_value=old,
                new_value=new,
                reason=f"{len(swarm_high_gpu)} SWARM missions with high GPU pressure",
                confidence=0.7,
            )

        # ── Pattern: SINGLE mode success → boost single fallback ──
        single_successes = [e for e in recent if get_mode(e) == "SINGLE" and is_success(e)]
        if len(single_successes) >= 5 and self._current_policy["single_agent_fallback"]:
            # Already using single as fallback, good
            changes["stability_threshold"] = PolicyDelta(
                param="stability_threshold",
                old_value=self._current_policy["stability_threshold"],
                new_value=0.70,  # can be more aggressive
                reason=f"{len(single_successes)} consecutive SINGLE successes",
                confidence=0.6,
            )

        # ── Pattern: TOOL mode used as fallback often ──
        tool_fallbacks = [e for e in recent if get_mode(e) == "TOOL"]
        if len(tool_fallbacks) >= 4:
            old = self._current_policy["retry_rate_on_failure"]
            new = min(0.50, old + 0.05)  # try retry more before falling to TOOL
            changes["retry_rate_on_failure"] = PolicyDelta(
                param="retry_rate_on_failure",
                old_value=old,
                new_value=new,
                reason=f"{len(tool_fallbacks)} TOOL mode fallbacks (retry more first)",
                confidence=0.5,
            )

        # Apply changes
        for param, delta in changes.items():
            self._current_policy[param] = delta.new_value
            self._change_log.append(delta)

        return changes

    def get_policy(self) -> dict:
        return dict(self._current_policy)

    def get_change_log(self) -> list[PolicyDelta]:
        return list(self._change_log)

    def reset_to_defaults(self):
        self._current_policy = dict(self.DEFAULTS)
        self._change_log.clear()

    def get_stats(self) -> dict:
        return {
            "policy_version": len(self._change_log),
            "total_evolutions": len(self._change_log),
            "current_policy": self._current_policy,
            "active_patterns": len(self._failure_patterns),
        }


if __name__ == "__main__":
    from agents.episodic_memory import EpisodicMemory
    from agents.system_observer import SystemObserver

    mem = EpisodicMemory()
    obs = SystemObserver()
    evolver = ControlPlaneEvolver()

    print("=== ControlPlaneEvolver test ===")
    print("Default policy:", evolver.get_policy())

    # Get recent outcomes for evolution
    episodes = mem.query_outcomes(limit=20)
    if episodes:
        changes = evolver.analyze_and_evolve(episodes)
        print(f"\nEvolutions: {len(changes)}")
        for p, d in changes.items():
            print(f"  {p}: {d.old_value} → {d.new_value} ({d.reason})")
    else:
        print("\nNo episodes yet — generate some missions first")

    print("\nFinal policy:", evolver.get_policy())
