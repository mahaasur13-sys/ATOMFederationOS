"""
TAAR v9 — Civilization Evolution Engine
Responsibilities:
    - Evolve economy structures
    - Create new ECONOS instances automatically
    - Remove failed economies
    - Redistribute civilization resources
    - Track civilizational progress
"""

from __future__ import annotations
from dataclasses import dataclass
import time, random


@dataclass
class EvolutionDecision:
    decision_id: str
    action: str           # create_economy | remove_economy | merge_economies | split_economy
    target: str
    reason: str
    timestamp: float
    executed: bool = False


@dataclass
class EconomySnapshot:
    economy_id: str
    total_value_generated: float
    mission_success_rate: float
    stability: float
    lifespan_cycles: int
    resource_efficiency: float


class CivilizationEvolution:
    """
    Manages civilizational evolution:
        - births/deaths of economies
        - merger/split of economies
        - resource redistribution
        - civilizational progress tracking
    """

    # Thresholds
    MIN_SURVIVAL_RATE = 0.3   # mission_success_rate below this → candidate for removal
    MIN_STABILITY = 0.25       # stability below this → removed
    MAX_ECONOMIES = 8           # hard cap on economies
    IDEAL_ECONOMIES = 4         # target size
    SPLIT_THRESHOLD = 0.90     # performance above this → candidate for split
    MERGE_THRESHOLD = 0.25      # performance below this with same role → merge candidates
    MIN_CYCLES_BEFORE_SPLIT = 5

    def __init__(self):
        self.decisions: list[EvolutionDecision] = []
        self.economy_snapshots: dict[str, list[EconomySnapshot]] = {}
        self.active_economies: set[str] = set()
        self.cycle_count: int = 0
        self.civilizational_progress: float = 0.0  # 0-1
        self.resource_pool: float = 10.0  # shared resources for new economies
        self.history_limit = 200

    def register_economy(self, econ_id: str):
        """Track a new economy."""
        self.active_economies.add(econ_id)
        self.economy_snapshots[econ_id] = []

    def update_economy_performance(self, econ_id: str, snapshot: EconomySnapshot):
        """Update performance record for an economy."""
        if econ_id not in self.active_economies:
            self.register_economy(econ_id)
        if econ_id not in self.economy_snapshots:
            self.economy_snapshots[econ_id] = []
        self.economy_snapshots[econ_id].append(snapshot)
        if len(self.economy_snapshots[econ_id]) > 30:
            self.economy_snapshots[econ_id] = self.economy_snapshots[econ_id][-30:]

    def should_evolve(self, econ_id: str) -> tuple[str, str]:
        """Decide what evolution action to take for an economy."""
        if econ_id not in self.economy_snapshots or not self.economy_snapshots[econ_id]:
            return "none", "no data"
        recent = self.economy_snapshots[econ_id][-5:]
        avg_rate = sum(s.mission_success_rate for s in recent) / len(recent)
        avg_stability = sum(s.stability for s in recent) / len(recent)
        avg_efficiency = sum(s.resource_efficiency for s in recent) / len(recent)
        performance = (avg_rate * 0.5 + avg_stability * 0.3 + avg_efficiency * 0.2)
        if avg_stability < self.MIN_STABILITY:
            return "remove", f"stability={avg_stability:.2f} below {self.MIN_STABILITY}"
        if avg_rate < self.MIN_SURVIVAL_RATE:
            return "remove", f"success_rate={avg_rate:.2f} below {self.MIN_SURVIVAL_RATE}"
        # Only split if economy has enough lifespan data AND perf > threshold
        lifespan = recent[-1].lifespan_cycles if recent else 0
        if (performance > self.SPLIT_THRESHOLD
                and lifespan >= self.MIN_CYCLES_BEFORE_SPLIT
                and len(self.active_economies) < self.MAX_ECONOMIES):
            return "split", f"performance={performance:.2f} above {self.SPLIT_THRESHOLD}"
        if performance > 0.7 and len(self.active_economies) < self.IDEAL_ECONOMIES:
            return "create_economy", f"good conditions, target={self.IDEAL_ECONOMIES}"
        return "none", f"stable (perf={performance:.2f})"

    def compute_evolution_decisions(self) -> list[EvolutionDecision]:
        """Compute evolution decisions for all economies this cycle."""
        self.cycle_count += 1
        decisions = []
        # Check each economy
        for econ_id in list(self.active_economies):
            action, reason = self.should_evolve(econ_id)
            if action != "none":
                decisions.append(EvolutionDecision(
                    decision_id=f"EVD-{self.cycle_count:04d}-{len(decisions):02d}",
                    action=action,
                    target=econ_id,
                    reason=reason,
                    timestamp=time.time(),
                ))
        # Special: birth new economy if count < IDEAL and no candidates
        if len(self.active_economies) < self.IDEAL_ECONOMIES and not decisions:
            if random.random() > 0.5:
                decisions.append(EvolutionDecision(
                    decision_id=f"EVD-{self.cycle_count:04d}-00",
                    action="create_economy",
                    target=f"ECONOS_NEW_{self.cycle_count}",
                    reason=f"expansion to ideal size {self.IDEAL_ECONOMIES}",
                    timestamp=time.time(),
                ))
        # Record all decisions
        self.decisions.extend(decisions)
        if len(self.decisions) > self.history_limit:
            self.decisions = self.decisions[-self.history_limit:]
        return decisions

    def execute_decision(self, decision: EvolutionDecision) -> dict:
        """Execute an evolution decision."""
        decision.executed = True
        if decision.action == "remove":
            self.active_economies.discard(decision.target)
            self.resource_pool += 1.0  # reclaim resources
            return {"action": "removed", "economy": decision.target, "reason": decision.reason}
        elif decision.action == "create_economy":
            self.active_economies.add(decision.target)
            self.resource_pool -= 0.5
            self.economy_snapshots[decision.target] = []
            return {"action": "created", "economy": decision.target, "reason": decision.reason}
        elif decision.action == "split":
            new_id = decision.target + "_SPLIT"
            self.active_economies.add(new_id)
            self.economy_snapshots[new_id] = []
            return {"action": "split", "original": decision.target, "new": new_id}
        return {"action": "noop", "reason": decision.reason}

    def update_progress(self, global_stability: float, total_value: float):
        """Update civilizational progress metric."""
        # Progress grows with stability and value, decays with conflicts
        delta = (global_stability * 0.1 + total_value * 0.01) / (self.cycle_count + 1)
        self.civilizational_progress = min(1.0, self.civilizational_progress + delta)

    def get_evolution_report(self) -> dict:
        """Get evolution status report."""
        pending = [d for d in self.decisions if not d.executed]
        executed = [d for d in self.decisions if d.executed]
        return {
            "active_economies": len(self.active_economies),
            "economy_list": sorted(self.active_economies),
            "total_decisions": len(self.decisions),
            "pending": len(pending),
            "executed": len(executed),
            "civilizational_progress": round(self.civilizational_progress, 4),
            "resource_pool": round(self.resource_pool, 2),
            "cycles": self.cycle_count,
            "pending_decisions": [(d.decision_id, d.action, d.target) for d in pending],
        }


if __name__ == "__main__":
    evo = CivilizationEvolution()
    evo.register_economy("ECONOS_A")
    evo.register_economy("ECONOS_B")
    evo.register_economy("ECONOS_C")

    # Simulate bad performer
    evo.update_economy_performance("ECONOS_A", EconomySnapshot(
        economy_id="ECONOS_A", total_value_generated=1.0,
        mission_success_rate=0.95, stability=0.8, lifespan_cycles=10, resource_efficiency=0.9))
    evo.update_economy_performance("ECONOS_B", EconomySnapshot(
        economy_id="ECONOS_B", total_value_generated=0.5,
        mission_success_rate=0.2, stability=0.2, lifespan_cycles=5, resource_efficiency=0.3))
    evo.update_economy_performance("ECONOS_C", EconomySnapshot(
        economy_id="ECONOS_C", total_value_generated=2.0,
        mission_success_rate=0.9, stability=0.95, lifespan_cycles=20, resource_efficiency=0.85))

    decisions = evo.compute_evolution_decisions()
    print("Decisions:", [(d.decision_id, d.action, d.target, d.reason) for d in decisions])
    for d in decisions:
        result = evo.execute_decision(d)
        print(f"  → {result}")
    print("Report:", evo.get_evolution_report())
