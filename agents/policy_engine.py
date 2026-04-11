"""
TAAR v4 — Policy Evolution Engine
Analyzes past mission outcomes → modifies routing weights / strategies.
IF repeated failure pattern detected: modify routing weights
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Routing weights used by ControlPlane
DEFAULT_WEIGHTS = {
    "devops_score":      {"ci_error": 0.9, "workflow": 0.9, "lint": 0.8, "test_fail": 0.85,
                          "build": 0.6, "deploy": 0.7, "ruff": 0.9, "pytest": 0.85,
                          "error:": 0.5, "failed": 0.4, "module": 0.6},
    "swarm_score":        {"scan": 0.9, "analyze all": 0.9, "find all": 0.85,
                          "search all": 0.85, "audit": 0.8, "review all": 0.8,
                          "parallel": 0.9, "grep all": 0.85},
    "tool_score":         {"run ": 0.8, "execute": 0.7, "build": 0.6, "compile": 0.7,
                          "install": 0.8, "pip install": 0.9, "apt install": 0.9},
    "mode_threshold":     0.5,        # minimum score to switch mode
    "swarm_threshold":    0.75,       # confidence needed for SWARM
    "devops_threshold":   0.65,       # confidence needed for DEVOPS
}


@dataclass
class PolicyDelta:
    """What changed in the policy."""
    trigger: str
    before: Any
    after: Any
    reason: str


class PolicyEngine:
    """
    Analyzes episodic memory → evolves routing/execution policy.
    Reads episode outcomes → adjusts ControlPlane weights.
    """

    def __init__(self):
        self.weights = {k: dict(v) if isinstance(v, dict) else v
                        for k, v in DEFAULT_WEIGHTS.items()}
        self.deltas: list[PolicyDelta] = []
        self._evolution_log: list[dict] = []

    def evolve(self, episodic_summary: dict[str, Any]) -> dict[str, Any]:
        """
        Main entry: receive episodic memory summary → return adjusted weights.
        Also logs what changed and why.
        """
        hints = episodic_summary.get("hints", {})
        sr = hints.get("success_rate", 1.0)
        fallback = hints.get("fallback_mode", "TOOL")
        devops_extra = hints.get("devops_trigger_extra", [])

        changes = []

        # ── Rule 1: Low success rate → tighten DEVOPS triggers ──
        if sr < 0.5 and sr > 0:
            old = self.weights["devops_threshold"]
            self.weights["devops_threshold"] = max(0.4, old - 0.1)
            changes.append(PolicyDelta(
                trigger="low_success_rate",
                before=f"devops_threshold={old}",
                after=f"devops_threshold={self.weights['devops_threshold']}",
                reason=f"success_rate={sr:.0%}, widening DEVOPS detection",
            ))

        # ── Rule 2: Repeated SINGLE failures → suggest TOOL fallback ──
        if fallback == "TOOL":
            old = self.weights["mode_threshold"]
            self.weights["mode_threshold"] = max(0.3, old - 0.1)
            changes.append(PolicyDelta(
                trigger="single_failure_loop",
                before=f"mode_threshold={old}",
                after=f"mode_threshold={self.weights['mode_threshold']}",
                reason="SINGLE mode repeatedly failing → lower threshold",
            ))

        # ── Rule 3: Missing CI patterns → boost CI keywords ──
        if devops_extra:
            for kw in devops_extra[:3]:
                # Extract likely keyword from goal
                word = kw.split()[0] if kw else "error"
                if word not in self.weights["devops_score"]:
                    self.weights["devops_score"][word] = 0.7
                    changes.append(PolicyDelta(
                        trigger="new_devops_pattern",
                        before=f"'{word}' not in devops_score",
                        after=f"devops_score['{word}']=0.7",
                        reason=f"Detected from failed mission: {kw[:40]}",
                    ))

        # ── Rule 4: High success rate → slightly raise SWARM threshold ──
        if sr >= 0.8:
            old = self.weights["swarm_threshold"]
            self.weights["swarm_threshold"] = min(0.85, old + 0.05)
            changes.append(PolicyDelta(
                trigger="high_success_rate",
                before=f"swarm_threshold={old}",
                after=f"swarm_threshold={self.weights['swarm_threshold']}",
                reason=f"success_rate={sr:.0%}, confidence OK to raise bar",
            ))

        # Log evolution
        for d in changes:
            self.deltas.append(d)
            self._evolution_log.append({
                "trigger": d.trigger,
                "before": d.before,
                "after": d.after,
                "reason": d.reason,
            })

        return {
            "weights": self.weights,
            "changes": [d.__dict__ for d in changes],
            "total_evolutions": len(self.deltas),
        }

    def get_weights(self) -> dict[str, Any]:
        return dict(self.weights)

    def get_evolution_log(self) -> list[dict]:
        return self._evolution_log[-20:]   # last 20 changes

    def reset_to_default(self):
        """Reset all weights to defaults. Useful after manual override."""
        self.weights = {k: dict(v) if isinstance(v, dict) else v
                        for k, v in DEFAULT_WEIGHTS.items()}
        self.deltas.clear()
        self._evolution_log.append({"action": "reset_to_default"})
