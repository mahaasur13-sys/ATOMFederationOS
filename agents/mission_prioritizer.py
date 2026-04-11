"""
TAAR v5 — Mission Prioritizer
Ranks missions by: stability impact × failure_reduction × resource_cost
Drops low-value missions under high load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from agents.system_observer import SystemState
from agents.mission_generator import GeneratedMission


@dataclass
class PrioritizedMission:
    mission: GeneratedMission
    score: float
    estimated_cost: float  # 0.0-1.0 (resource units)
    stability_impact: float  # expected improvement
    should_drop: bool = False


class MissionPrioritizer:
    # Resource cost estimates per target metric
    COST_MAP = {
        "system_stability": 0.4,
        "task_failure_rate": 0.3,
        "gpu_pressure": 0.5,
        "memory_pressure": 0.3,
        "policy_drift": 0.2,
        "mission_success_rate": 0.4,
        "execution_efficiency": 0.1,
        "memory_size": 0.05,
    }

    # Stability weight factors
    STABILITY_WEIGHT = 1.5   # higher priority to stability
    FAILURE_REDUCTION_WEIGHT = 1.2
    RESOURCE_COST_WEIGHT = 0.8  # lower = prefer cheap missions

    # Drop threshold (under high load, drop below this score)
    DROP_THRESHOLD_UNDER_LOAD = 0.30
    DROP_THRESHOLD_NORMAL = 0.15

    def __init__(self):
        self._decisions: list[dict] = []

    def prioritize(
        self,
        missions: list[GeneratedMission],
        state: SystemState,
    ) -> list[PrioritizedMission]:
        # System load factor
        system_load = max(state.gpu_pressure, state.memory_pressure, state.cpu_load)
        drop_threshold = (
            self.DROP_THRESHOLD_UNDER_LOAD if system_load > 0.80
            else self.DROP_THRESHOLD_NORMAL
        )

        prioritized: list[PrioritizedMission] = []

        for m in missions:
            cost = self.COST_MAP.get(m.target_metric, 0.3)
            estimated_cost = cost

            # Stability impact: higher for critical/high priority missions
            base_impact = {
                "critical": 0.9,
                "high": 0.7,
                "medium": 0.5,
                "low": 0.3,
            }.get(m.priority, 0.5)

            # Adjust by how far the target metric currently is from ideal
            if m.target_metric == "system_stability":
                deviation = 1.0 - state.system_stability
                stability_impact = base_impact * (deviation + 0.5)
            elif m.target_metric == "task_failure_rate":
                deviation = state.task_failure_rate
                stability_impact = base_impact * (deviation + 0.5)
            elif m.target_metric == "gpu_pressure":
                deviation = state.gpu_pressure
                stability_impact = base_impact * (deviation + 0.3)
            elif m.target_metric == "mission_success_rate":
                deviation = 1.0 - state.mission_success_rate
                stability_impact = base_impact * (deviation + 0.5)
            else:
                stability_impact = base_impact

            # Composite score
            score = (
                stability_impact * self.STABILITY_WEIGHT
                + (1.0 - state.task_failure_rate) * self.FAILURE_REDUCTION_WEIGHT
                - estimated_cost * self.RESOURCE_COST_WEIGHT
            )

            # Boost critical missions
            if m.priority == "critical":
                score *= 1.5

            should_drop = score < drop_threshold and system_load > 0.70

            pm = PrioritizedMission(
                mission=m,
                score=round(score, 3),
                estimated_cost=round(estimated_cost, 2),
                stability_impact=round(stability_impact, 3),
                should_drop=should_drop,
            )
            prioritized.append(pm)

        # Sort by score descending
        prioritized.sort(key=lambda x: x.score, reverse=True)

        self._decisions.append({
            "system_load": round(system_load, 3),
            "drop_threshold": drop_threshold,
            "input_count": len(missions),
            "output_count": sum(1 for p in prioritized if not p.should_drop),
            "dropped": sum(1 for p in prioritized if p.should_drop),
        })

        return prioritized

    def get_stats(self) -> dict:
        return {
            "decisions": len(self._decisions),
            "recent_drops": self._decisions[-1]["dropped"] if self._decisions else 0,
        }


if __name__ == "__main__":
    from agents.system_observer import SystemObserver
    from agents.mission_generator import MissionGenerator

    obs = SystemObserver()
    state = obs.observe()
    gen = MissionGenerator()
    missions = gen.generate(state)

    pri = MissionPrioritizer()
    ranked = pri.prioritize(missions, state)

    print(f"System load: {max(state.gpu_pressure, state.memory_pressure, state.cpu_load):.3f}")
    print(f"Input: {len(missions)} missions\n")
    for pm in ranked:
        drop = " [DROP]" if pm.should_drop else ""
        print(f"  score={pm.score:.3f} cost={pm.estimated_cost} [{pm.mission.priority}]{drop} {pm.mission.goal}")
