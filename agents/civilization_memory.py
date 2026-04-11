"""
TAAR v9 — Civilization Memory Graph
Stores civilization-level events: wars, alliances, trade, crises, evolution.
Structure:
    { economy_interactions, wars, alliances, trade_history, resource_crises, evolution_events }
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class EconomyInteraction:
    interaction_id: str
    econ_a: str
    econ_b: str
    interaction_type: str  # trade | conflict | alliance | neutral
    strength: float        # -1 to 1
    timestamp: float


@dataclass
class ResourceCrisis:
    crisis_id: str
    crisis_type: str        # gpu_shortage | llm_cost_spike | memory_exhaustion
    severity: float         # 0-1
    economies_affected: list[str]
    start_time: float
    resolved: bool = False
    resolution_time: float = 0.0


@dataclass
class EvolutionEvent:
    event_id: str
    event_type: str         # economy_born | economy_died | alliance_formed | war_ended
    description: str
    timestamp: float
    data: dict = field(default_factory=dict)


class CivilizationMemory:
    """Global memory for civilization-level events."""

    def __init__(self):
        self.economy_interactions: list[EconomyInteraction] = []
        self.wars: list[dict] = []      # simplified war records
        self.alliances: list[dict] = []  # alliance history
        self.trade_history: list[dict] = []
        self.resource_crises: list[ResourceCrisis] = []
        self.evolution_events: list[EvolutionEvent] = []
        self.HISTORY_LIMIT = 500

    def record_interaction(self, econ_a: str, econ_b: str,
                          interaction_type: str, strength: float):
        """Record an interaction between two economies."""
        # Update existing or create new
        existing = next(
            (i for i in self.economy_interactions
             if (i.econ_a, i.econ_b) in [(econ_a, econ_b), (econ_b, econ_a)]
             and i.interaction_type == interaction_type),
            None
        )
        if existing:
            existing.strength = (existing.strength + strength) / 2
        else:
            self.economy_interactions.append(EconomyInteraction(
                interaction_id=f"INT-{len(self.economy_interactions)+1:04d}",
                econ_a=econ_a,
                econ_b=econ_b,
                interaction_type=interaction_type,
                strength=strength,
                timestamp=time.time(),
            ))
        if len(self.economy_interactions) > self.HISTORY_LIMIT:
            self.economy_interactions = self.economy_interactions[-self.HISTORY_LIMIT:]

    def record_war(self, war_id: str, participants: list[str], trigger: str):
        """Record an economic/resource war."""
        self.wars.append({
            "war_id": war_id,
            "participants": participants,
            "trigger": trigger,
            "start_time": time.time(),
            "ended": False,
            "end_time": 0.0,
        })

    def end_war(self, war_id: str, winner: str, terms: str):
        """End a recorded war."""
        for w in self.wars:
            if w.get("war_id") == war_id:
                w["ended"] = True
                w["end_time"] = time.time()
                w["winner"] = winner
                w["terms"] = terms
                self.evolution_events.append(EvolutionEvent(
                    event_id=f"EVT-{len(self.evolution_events)+1:04d}",
                    event_type="war_ended",
                    description=f"War {war_id} ended. Winner: {winner}",
                    timestamp=time.time(),
                    data={"war_id": war_id, "winner": winner},
                ))

    def record_crisis(self, crisis_type: str, severity: float,
                      economies_affected: list[str]) -> ResourceCrisis:
        """Record a resource crisis event."""
        crisis = ResourceCrisis(
            crisis_id=f"CRS-{len(self.resource_crises)+1:04d}",
            crisis_type=crisis_type,
            severity=severity,
            economies_affected=economies_affected,
            start_time=time.time(),
        )
        self.resource_crises.append(crisis)
        self.evolution_events.append(EvolutionEvent(
            event_id=f"EVT-{len(self.evolution_events)+1:04d}",
            event_type="crisis",
            description=f"Resource crisis: {crisis_type} (severity={severity})",
            timestamp=time.time(),
            data={"crisis_type": crisis_type, "severity": severity},
        ))
        return crisis

    def record_trade(self, from_econ: str, to_econ: str,
                     resource: str, amount: float, price: float):
        """Record a cross-economy trade."""
        self.trade_history.append({
            "from": from_econ,
            "to": to_econ,
            "resource": resource,
            "amount": amount,
            "price": price,
            "timestamp": time.time(),
        })
        self.record_interaction(from_econ, to_econ, "trade", strength=0.5)
        if len(self.trade_history) > self.HISTORY_LIMIT:
            self.trade_history = self.trade_history[-self.HISTORY_LIMIT:]

    def record_evolution(self, event_type: str, description: str, data: dict = None):
        """Record a civilization evolution event."""
        self.evolution_events.append(EvolutionEvent(
            event_id=f"EVT-{len(self.evolution_events)+1:04d}",
            event_type=event_type,
            description=description,
            timestamp=time.time(),
            data=data or {},
        ))
        if len(self.evolution_events) > self.HISTORY_LIMIT:
            self.evolution_events = self.evolution_events[-self.HISTORY_LIMIT:]

    def get_memory_summary(self) -> dict:
        """Get civilization memory summary."""
        return {
            "total_interactions": len(self.economy_interactions),
            "wars": {
                "total": len(self.wars),
                "active": len([w for w in self.wars if not w.get("ended")]),
            },
            "alliances": len(self.alliances),
            "trade_events": len(self.trade_history),
            "crises": {
                "total": len(self.resource_crises),
                "active": len([c for c in self.resource_crises if not c.resolved]),
            },
            "evolution_events": len(self.evolution_events),
            "recent_interactions": [
                {"type": i.interaction_type, "a": i.econ_a, "b": i.econ_b}
                for i in self.economy_interactions[-5:]
            ],
        }


if __name__ == "__main__":
    mem = CivilizationMemory()
    mem.record_interaction("ECONOS_A", "ECONOS_B", "trade", 0.7)
    mem.record_interaction("ECONOS_A", "ECONOS_C", "conflict", -0.4)
    mem.record_crisis("gpu_shortage", 0.7, ["ECONOS_A", "ECONOS_B"])
    mem.record_trade("ECONOS_A", "ECONOS_C", "gpu_compute", 5.0, 0.8)
    print("Memory summary:", mem.get_memory_summary())
