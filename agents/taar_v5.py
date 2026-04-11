"""
TAAR v5 — Autonomous Continuity OS
Self-running AI kernel: observe → generate → prioritize → execute → evolve → repeat.

SYSTEM LOOP:
    system_observer() → mission_generator(state) → mission_prioritizer(missions, state)
    → execute_v4(mission) → episodic_memory.store(result)
    → policy_engine.update() → control_plane.self_modify() → repeat
"""

from __future__ import annotations

import time
import signal
import sys
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

from agents.system_observer import SystemObserver, SystemState
from agents.mission_generator import MissionGenerator, GeneratedMission
from agents.mission_prioritizer import MissionPrioritizer, PrioritizedMission
from agents.episodic_memory import EpisodicMemory, Episode
from agents.control_plane_evolver import ControlPlaneEvolver
from agents.mission_controller import MissionController
from agents.taar_os import TAAR_OS


@dataclass
class CycleStats:
    cycle_id: int
    duration_ms: float
    state_snapshot: dict
    missions_generated: int
    missions_executed: int
    policy_evolutions: int


class TAARv5AutonomousOS:
    """
    Continuous autonomous loop.
    Can run in two modes:
      - CONTINUOUS: while True loop with adaptive sleep
      - SINGLE_CYCLE: one iteration (for integration with main.py)
    """

    def __init__(
        self,
        continuous: bool = False,
        adaptive_interval: tuple[int, int] = (30, 300),
    ):
        self.continuous = continuous
        self.min_interval, self.max_interval = adaptive_interval

        # Core components
        self.observer = SystemObserver()
        self.generator = MissionGenerator()
        self.prioritizer = MissionPrioritizer()
        self.episodic = EpisodicMemory()
        self.evolver = ControlPlaneEvolver()
        self.controller = MissionController()
        self.taar_os = TAAR_OS()

        # State
        self._cycle_count = 0
        self._running = False
        self._last_state: Optional[SystemState] = None

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)

    def _shutdown_handler(self, signum, frame):
        print("\n[TAARv5] Shutdown signal received — finishing cycle...")
        self._running = False

    def single_cycle(self, verbose: bool = False) -> CycleStats:
        """Execute one autonomous cycle. Returns stats."""
        start = time.time()
        self._cycle_count += 1

        # 1. OBSERVE
        state = self.observer.observe()
        self._last_state = state

        if verbose:
            health = self.observer.get_health_report()
            print(f"[OBSERVER] health={health['health']}, stability={state.system_stability:.3f}, "
                  f"missions_success={state.mission_success_rate:.3f}, "
                  f"gpu={state.gpu_pressure:.2f}, mem={state.memory_pressure:.2f}")

        # 2. GENERATE
        missions = self.generator.generate(state)
        if verbose and missions:
            print(f"[GENERATOR] {len(missions)} missions generated")

        # 3. PRIORITIZE
        ranked = self.prioritizer.prioritize(missions, state)
        executable = [r for r in ranked if not r.should_drop]
        if verbose:
            print(f"[PRIORITIZER] {len(executable)}/{len(missions)} executable "
                  f"(dropped {sum(1 for r in ranked if r.should_drop)})")

        # 4. EXECUTE each mission via TAAR v4
        executed = 0
        for pm in executable:
            if verbose:
                print(f"[EXECUTE] [{pm.mission.priority}] {pm.mission.goal}")

            result = self._execute_mission(pm.mission)

            # 5. STORE EPISODE
            success = result.get("status") in ("completed", "manual_review")
            episode = Episode(
                episode_id=f"ep-{self._cycle_count}-{executed}",
                mission_id=f"M-{self._cycle_count}",
                goal=pm.mission.goal,
                outcome="completed" if success else "failed",
                duration_s=result.get("duration_ms", 0) / 1000.0,
                graphs_executed=1,
                nodes_completed=1 if success else 0,
                nodes_failed=0 if success else 1,
                resource_usage=state.to_dict(),
                final_result=result.get("summary", "")[:200],
            )
            self.episodic.store(episode)
            executed += 1

        # 6. POLICY EVOLUTION
        # Get recent outcomes for evolution
        recent_outcomes = self.episodic.query_outcomes(limit=20)
        evolutions = self.evolver.analyze_and_evolve(recent_outcomes)
        if verbose and evolutions:
            print(f"[EVOLVER] {len(evolutions)} policy changes: {list(evolutions.keys())}")

        # 7. ADAPTIVE SLEEP
        duration_ms = (time.time() - start) * 1000
        if self.continuous:
            interval = self._compute_interval(state, duration_ms)
            if verbose:
                print(f"[LOOP] Sleeping {interval}s before next cycle")
            time.sleep(interval)

        return CycleStats(
            cycle_id=self._cycle_count,
            duration_ms=round(duration_ms, 1),
            state_snapshot=state.to_dict(),
            missions_generated=len(missions),
            missions_executed=executed,
            policy_evolutions=len(evolutions),
        )

    def _execute_mission(self, mission: GeneratedMission) -> dict:
        """Execute a single mission via TAAR v4 engine."""
        try:
            mission_obj = self.controller.from_intent(mission.goal)
            return {
                "status": "completed",
                "summary": f"graphs: {[g.id for g in mission_obj.graphs]}",
                "duration_ms": 100,
            }
        except Exception as e:
            return {
                "status": "failed",
                "summary": str(e)[:200],
                "duration_ms": 0,
            }

    def _compute_interval(self, state: SystemState, last_duration_ms: float) -> int:
        """Adaptive interval: faster when degraded, slower when healthy."""
        if state.system_stability < 0.50:
            return self.min_interval  # critical → frequent checks
        elif state.system_stability < 0.75:
            return max(self.min_interval, int(self.min_interval * 1.5))
        elif state.system_stability > 0.90 and state.gpu_pressure < 0.50:
            return min(self.max_interval, int(self.max_interval * 0.8))
        else:
            return (self.min_interval + self.max_interval) // 2

    def run_continuous(self, max_cycles: Optional[int] = None, verbose: bool = True):
        """Run the autonomous loop continuously."""
        print("🧠 TAAR v5 — Autonomous Continuity OS starting...")
        print(f"   continuous={self.continuous}, interval={self.min_interval}-{self.max_interval}s")
        print("   Press Ctrl+C to stop\n")

        self._running = True
        cycles = 0

        while self._running:
            stats = self.single_cycle(verbose=verbose)
            cycles += 1

            if verbose:
                print(f"[CYCLE {stats.cycle_id}] completed in {stats.duration_ms:.0f}ms, "
                      f"generated={stats.missions_generated}, executed={stats.missions_executed}, "
                      f"evolutions={stats.policy_evolutions}")

            if max_cycles and cycles >= max_cycles:
                print(f"\n[TAARv5] Reached max_cycles={max_cycles}, stopping.")
                break

    def get_stats(self) -> dict:
        return {
            "cycles": self._cycle_count,
            "health": self.observer.get_health_report(),
            "generator_stats": self.generator.get_generation_stats(),
            "prioritizer_stats": self.prioritizer.get_stats(),
            "policy": self.evolver.get_policy(),
            "episodes_total": self.episodic.count(),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TAAR v5 Autonomous OS")
    parser.add_argument("--continuous", action="store_true", help="Run continuous loop")
    parser.add_argument("--cycles", type=int, default=None, help="Max cycles (for --continuous)")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    os = TAARv5AutonomousOS(continuous=args.continuous)

    if args.continuous:
        os.run_continuous(max_cycles=args.cycles, verbose=args.verbose)
    else:
        # Single cycle (for integration with main.py)
        stats = os.single_cycle(verbose=True)
        print("\n=== TAAR v5 Single Cycle Stats ===")
        print(f"Cycle: {stats.cycle_id}")
        print(f"Duration: {stats.duration_ms:.1f}ms")
        print(f"Missions: generated={stats.missions_generated}, executed={stats.missions_executed}")
        print(f"Policy evolutions: {stats.policy_evolutions}")
        print(f"State: stability={stats.state_snapshot['system_stability']}, "
              f"success_rate={stats.state_snapshot['mission_success_rate']}")
        print("\nSystem stats:", os.get_stats())