"""
TAAR v9 — Civilization Council Core
Coordinates multiple AI economies (ECONOS instances).
Manages: stability, conflicts, alliances, global resource governance.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import time, uuid


class CouncilAction(str, Enum):
    NONE = "none"
    DIPLOMACY = "diplomacy"        # mediate dispute
    SANCTION = "sanction"          # punish harmful behavior
    ALLIANCE_FORM = "alliance_form" # promote collaboration
    INTERVENTION = "intervention"   # emergency stabilization
    EVICT = "evict"                # remove failed economy
    MERGE = "merge"                # consolidate economies


@dataclass
class EconomyHealth:
    economy_id: str
    stability: float        # 0-1
    conflict_exposure: float # 0-1
    collaboration_score: float # 0-1
    resource_usage: float   # 0-1
    health_score: float     # 0-1 computed
    last_seen: float = field(default_factory=time.time)


@dataclass
class ConflictRecord:
    conflict_id: str
    economies: list[str]
    severity: float         # 0-1
    resource_type: str
    trigger_time: float
    resolved: bool = False
    resolution: str = ""
    resolution_time: float = 0.0


@dataclass
class Alliance:
    alliance_id: str
    member_ids: list[str]
    strength: float          # 0-1 based on trust and collaboration
    formed_time: float
    trade_volume: float = 0.0
    purpose: str = "trade"


@dataclass
class CouncilState:
    global_stability: float      # 0-1
    resource_pressure: float     # 0-1
    conflict_index: float        # 0-1
    collaboration_index: float   # 0-1
    active_conflicts: int
    active_alliances: int
    intervention_level: str     # normal | elevated | critical
    last_civilization_action: str


class CivilizationCouncil:
    """
    Civilizational governance over multiple AI economies.
    Responsibilities:
        - Track health of all economies
        - Detect and resolve conflicts
        - Form/disband alliances
        - Issue council actions
        - Maintain civilization stability
    """

    def __init__(self, name: str = "CIVILIZATION_COUNCIL"):
        self.name = name
        self.economy_healths: dict[str, EconomyHealth] = {}
        self.conflicts: list[ConflictRecord] = []
        self.alliances: list[Alliance] = []
        self.state = CouncilState(
            global_stability=0.9,
            resource_pressure=0.3,
            conflict_index=0.1,
            collaboration_index=0.3,
            active_conflicts=0,
            active_alliances=0,
            intervention_level="normal",
            last_civilization_action="none",
        )
        # Thresholds
        self.CONFLICT_THRESHOLD = 0.6   # conflict_index to trigger competition mode
        self.STABILITY_CRITICAL = 0.4   # stability below this → intervention
        self.ALLIANCE_COLLAB_THRESHOLD = 0.6 # collaboration above this → alliance
        self.HISTORY_LIMIT = 200

    def register_economy(self, econ_id: str, stability: float = 0.9):
        """Register a new economy in the civilization."""
        health = EconomyHealth(
            economy_id=econ_id,
            stability=stability,
            conflict_exposure=0.0,
            collaboration_score=0.3,
            resource_usage=0.3,
            health_score=stability,
        )
        self.economy_healths[econ_id] = health

    def update_economy(self, econ_id: str, stability: float, resource_usage: float,
                       conflict_exposure: float = 0.0, collaboration_score: float = 0.3):
        """Update an economy's health status."""
        if econ_id not in self.economy_healths:
            self.register_economy(econ_id, stability)
        h = self.economy_healths[econ_id]
        h.stability = max(0.0, min(1.0, stability))
        h.resource_usage = max(0.0, min(1.0, resource_usage))
        h.conflict_exposure = max(0.0, min(1.0, conflict_exposure))
        h.collaboration_score = max(0.0, min(1.0, collaboration_score))
        h.health_score = (
            h.stability * 0.4
            + (1 - h.conflict_exposure) * 0.2
            + h.collaboration_score * 0.15
            + (1 - h.resource_usage) * 0.25
        )
        h.last_seen = time.time()

    def detect_conflicts(self) -> list[ConflictRecord]:
        """Detect resource conflicts between economies."""
        new_conflicts = []
        econ_ids = list(self.economy_healths.keys())
        for i, e1 in enumerate(econ_ids):
            for e2 in econ_ids[i+1:]:
                h1 = self.economy_healths[e1]
                h2 = self.economy_healths[e2]
                # Conflict if both have high resource usage and low stability
                conflict_potential = (
                    (h1.resource_usage + h2.resource_usage) / 2
                    * (1 - (h1.stability + h2.stability) / 2)
                )
                if conflict_potential > self.CONFLICT_THRESHOLD:
                    # Check if already recorded
                    existing = any(
                        c.economies == [e1, e2] or c.economies == [e2, e1]
                        for c in self.conflicts if not c.resolved
                    )
                    if not existing:
                        rec = ConflictRecord(
                            conflict_id=f"CONF-{uuid.uuid4().hex[:8].upper()}",
                            economies=[e1, e2],
                            severity=conflict_potential,
                            resource_type="gpu_compute",
                            trigger_time=time.time(),
                        )
                        self.conflicts.append(rec)
                        new_conflicts.append(rec)
        return new_conflicts

    def detect_alliances(self) -> list[Alliance]:
        """Detect when economies should form alliances."""
        new_alliances = []
        econ_ids = list(self.economy_healths.keys())
        for i, e1 in enumerate(econ_ids):
            for e2 in econ_ids[i+1:]:
                h1 = self.economy_healths[e1]
                h2 = self.economy_healths[e2]
                avg_collab = (h1.collaboration_score + h2.collaboration_score) / 2
                if avg_collab > self.ALLIANCE_COLLAB_THRESHOLD:
                    existing = any(
                        e1 in a.member_ids and e2 in a.member_ids
                        for a in self.alliances
                    )
                    if not existing:
                        alliance = Alliance(
                            alliance_id=f"ALL-{uuid.uuid4().hex[:8].upper()}",
                            member_ids=[e1, e2],
                            strength=avg_collab,
                            formed_time=time.time(),
                            purpose="trade",
                        )
                        self.alliances.append(alliance)
                        new_alliances.append(alliance)
        return new_alliances

    def resolve_conflict(self, conflict_id: str, resolution: str):
        """Mark a conflict as resolved."""
        for c in self.conflicts:
            if c.conflict_id == conflict_id:
                c.resolved = True
                c.resolution = resolution
                c.resolution_time = time.time()

    def compute_global_stability(self) -> float:
        """Compute overall civilization stability."""
        if not self.economy_healths:
            return 1.0
        healths = [h.health_score for h in self.economy_healths.values()]
        avg_health = sum(healths) / len(healths)
        conflict_penalty = self.state.conflict_index * 0.3
        alliance_bonus = min(len(self.alliances) * 0.02, 0.15)
        return max(0.0, min(1.0, avg_health - conflict_penalty + alliance_bonus))

    def get_civilization_state(self) -> CouncilState:
        """Compute and return current civilization state."""
        # Update conflict index
        unresolved = [c for c in self.conflicts if not c.resolved]
        self.state.conflict_index = (
            sum(c.severity for c in unresolved) / max(len(unresolved), 1) * 0.5
        )
        # Update collaboration index
        if self.economy_healths:
            self.state.collaboration_index = (
                sum(h.collaboration_score for h in self.economy_healths.values())
                / len(self.economy_healths)
            )
        # Compute global stability
        self.state.global_stability = self.compute_global_stability()
        self.state.active_conflicts = len([c for c in self.conflicts if not c.resolved])
        self.state.active_alliances = len(self.alliances)
        # Determine intervention level
        if self.state.global_stability < self.STABILITY_CRITICAL:
            self.state.intervention_level = "critical"
        elif self.state.conflict_index > self.CONFLICT_THRESHOLD:
            self.state.intervention_level = "elevated"
        else:
            self.state.intervention_level = "normal"
        # Trim history
        if len(self.conflicts) > self.HISTORY_LIMIT:
            self.conflicts = self.conflicts[-self.HISTORY_LIMIT:]
        if len(self.alliances) > self.HISTORY_LIMIT:
            self.alliances = self.alliances[-self.HISTORY_LIMIT:]
        return self.state

    def get_council_action(self) -> tuple[CouncilAction, str]:
        """Decide what civilizational action to take."""
        state = self.get_civilization_state()
        # Check for critical instability
        if state.global_stability < self.STABILITY_CRITICAL:
            unstable = [h for h in self.economy_healths.values()
                       if h.health_score < self.STABILITY_CRITICAL]
            if len(unstable) >= 2:
                self.state.last_civilization_action = "evict"
                return CouncilAction.EVICT, f"evict {len(unstable)} failing economies"
            self.state.last_civilization_action = "intervention"
            return CouncilAction.INTERVENTION, "emergency stabilization"
        # Unresolved conflicts
        if state.active_conflicts > 2:
            self.state.last_civilization_action = "diplomacy"
            return CouncilAction.DIPLOMACY, "mediate active conflicts"
        # High collaboration → form alliance
        if state.collaboration_index > self.ALLIANCE_COLLAB_THRESHOLD:
            new_alliances = self.detect_alliances()
            if new_alliances:
                self.state.last_civilization_action = "alliance_form"
                return CouncilAction.ALLIANCE_FORM, f"form {[a.alliance_id for a in new_alliances]}"
        # Mild conflicts
        if state.conflict_index > self.CONFLICT_THRESHOLD:
            self.state.last_civilization_action = "sanction"
            return CouncilAction.SANCTION, "restrict high-conflict economies"
        self.state.last_civilization_action = "none"
        return CouncilAction.NONE, "civilization stable"

    def get_summary(self) -> dict:
        """Get civilization summary."""
        state = self.get_civilization_state()
        return {
            "council": self.name,
            "economies": len(self.economy_healths),
            "global_stability": round(state.global_stability, 3),
            "resource_pressure": round(state.resource_pressure, 3),
            "conflict_index": round(state.conflict_index, 3),
            "collaboration_index": round(state.collaboration_index, 3),
            "active_conflicts": state.active_conflicts,
            "active_alliances": state.active_alliances,
            "intervention_level": state.intervention_level,
            "last_action": state.last_civilization_action,
            "economy_healths": {
                e: round(h.health_score, 3)
                for e, h in self.economy_healths.items()
            },
        }


# ─── CLI Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    council = CivilizationCouncil()
    council.register_economy("ECONOS_A", stability=0.85)
    council.register_economy("ECONOS_B", stability=0.70)
    council.register_economy("ECONOS_C", stability=0.90)

    print("=== Civilization Council ===")
    council.update_economy("ECONOS_A", stability=0.85, resource_usage=0.7,
                           conflict_exposure=0.5, collaboration_score=0.3)
    council.update_economy("ECONOS_B", stability=0.70, resource_usage=0.8,
                           conflict_exposure=0.6, collaboration_score=0.2)
    council.update_economy("ECONOS_C", stability=0.90, resource_usage=0.4,
                           conflict_exposure=0.1, collaboration_score=0.7)

    print("Health:", council.economy_healths)
    conflicts = council.detect_conflicts()
    print("Conflicts detected:", len(conflicts))
    alliances = council.detect_alliances()
    print("Alliances formed:", [(a.alliance_id, a.member_ids) for a in alliances])
    action, reason = council.get_council_action()
    print(f"Council action: {action.value} → {reason}")
    print("Summary:", council.get_summary())
