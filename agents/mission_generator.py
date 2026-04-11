"""
TAAR v5 — Mission Generator
Generates missions AUTONOMOUSLY from system state.
IF system_stability < threshold: repair missions
IF failure_rate high: debug missions
IF GPU pressure high: optimization missions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from agents.system_observer import SystemState
from agents.episodic_memory import EpisodicMemory


@dataclass
class GeneratedMission:
    goal: str
    priority: str  # "critical" | "high" | "medium" | "low"
    reason: str    # why generated
    target_metric: str  # which metric this targets
    auto_generated: bool = True


class MissionGenerator:
    # Thresholds
    STABILITY_THRESHOLD_CRITICAL = 0.50
    STABILITY_THRESHOLD_WARNING = 0.75
    FAILURE_RATE_HIGH = 0.20
    GPU_PRESSURE_HIGH = 0.85
    MEMORY_PRESSURE_HIGH = 0.80

    def __init__(self, episodic_memory: Optional[EpisodicMemory] = None):
        self._episodic = episodic_memory
        self._gen_history: list[GeneratedMission] = []

    def generate(self, state: SystemState) -> list[GeneratedMission]:
        missions: list[GeneratedMission] = []

        # ── Stability repair (CRITICAL) ──
        if state.system_stability < self.STABILITY_THRESHOLD_CRITICAL:
            missions.append(GeneratedMission(
                goal="repair system stability (critical)",
                priority="critical",
                reason=f"system_stability={state.system_stability:.2f} < {self.STABILITY_THRESHOLD_CRITICAL}",
                target_metric="system_stability",
            ))
        elif state.system_stability < self.STABILITY_THRESHOLD_WARNING:
            missions.append(GeneratedMission(
                goal="improve system stability",
                priority="high",
                reason=f"system_stability={state.system_stability:.2f} < {self.STABILITY_THRESHOLD_WARNING}",
                target_metric="system_stability",
            ))

        # ── Failure rate repair ──
        if state.task_failure_rate > self.FAILURE_RATE_HIGH:
            missions.append(GeneratedMission(
                goal="reduce task failure rate",
                priority="high",
                reason=f"task_failure_rate={state.task_failure_rate:.2f} > {self.FAILURE_RATE_HIGH}",
                target_metric="task_failure_rate",
            ))

        # ── GPU pressure optimization ──
        if state.gpu_pressure > self.GPU_PRESSURE_HIGH:
            missions.append(GeneratedMission(
                goal="optimize GPU memory usage",
                priority="medium",
                reason=f"gpu_pressure={state.gpu_pressure:.2f} > {self.GPU_PRESSURE_HIGH}",
                target_metric="gpu_pressure",
            ))

        # ── Memory pressure optimization ──
        if state.memory_pressure > self.MEMORY_PRESSURE_HIGH:
            missions.append(GeneratedMission(
                goal="reduce memory pressure",
                priority="medium",
                reason=f"memory_pressure={state.memory_pressure:.2f} > {self.MEMORY_PRESSURE_HIGH}",
                target_metric="memory_pressure",
            ))

        # ── Anomaly-driven debug missions ──
        for anomaly in state.anomalies:
            if "high_failure_rate" in anomaly:
                missions.append(GeneratedMission(
                    goal="investigate failure pattern",
                    priority="high",
                    reason=f"anomaly detected: {anomaly}",
                    target_metric="task_failure_rate",
                ))
            elif "low_mission_success" in anomaly:
                missions.append(GeneratedMission(
                    goal="improve mission completion rate",
                    priority="high",
                    reason=f"anomaly detected: {anomaly}",
                    target_metric="mission_success_rate",
                ))

        # ── Policy drift adjustment ──
        if state.policy_drift > 0.30:
            missions.append(GeneratedMission(
                goal="recalibrate routing policy",
                priority="medium",
                reason=f"policy_drift={state.policy_drift:.2f} > 0.30",
                target_metric="policy_drift",
            ))

        # ── Proactive optimization (low load, idle time) ──
        if (state.system_stability >= self.STABILITY_THRESHOLD_WARNING
                and state.gpu_pressure < 0.50
                and state.memory_pressure < 0.60
                and len(missions) == 0):
            missions.append(GeneratedMission(
                goal="optimize swarm execution efficiency",
                priority="low",
                reason="system idle, proactive optimization",
                target_metric="execution_efficiency",
            ))
            missions.append(GeneratedMission(
                goal="clean up episodic memory",
                priority="low",
                reason="system idle, memory maintenance",
                target_metric="memory_size",
            ))

        self._gen_history.extend(missions)
        return missions

    def get_generation_stats(self) -> dict:
        return {
            "total_generated": len(self._gen_history),
            "by_priority": {
                p: sum(1 for m in self._gen_history if m.priority == p)
                for p in ("critical", "high", "medium", "low")
            },
        }


if __name__ == "__main__":
    from agents.system_observer import SystemObserver
    obs = SystemObserver()
    state = obs.observe()
    gen = MissionGenerator()
    missions = gen.generate(state)
    print(f"Generated {len(missions)} missions from healthy state:")
    for m in missions:
        print(f"  [{m.priority}] {m.goal} ({m.reason})")

    # Test with degraded state
    state2 = SystemState(
        system_stability=0.45,
        task_failure_rate=0.30,
        gpu_pressure=0.92,
        anomalies=["high_failure_rate:0.30"],
    )
    missions2 = gen.generate(state2)
    print(f"\nGenerated {len(missions2)} missions from degraded state:")
    for m in missions2:
        print(f"  [{m.priority}] {m.goal}")
