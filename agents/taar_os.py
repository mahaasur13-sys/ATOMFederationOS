"""
TAAR v4 — Mission Execution OS
Mission-level autonomous execution: intent → mission → graphs → result.
Integrates: MissionController + TaskGraph + StateMachine +
            ControlPlane + GPUControl + MemoryHierarchy + EpisodicMemory + PolicyEngine
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from mission_controller import MissionController, Mission, MissionStatus, GraphSpec
from episodic_memory import EpisodicMemory, Episode
from policy_engine import PolicyEngine, DEFAULT_WEIGHTS


@dataclass
class MissionResult:
    """Full output of a mission execution."""
    mission: dict
    task_graphs: list[dict]
    state: dict
    execution_log: list[dict]
    resource_usage: dict[str, Any]
    episodic_update: dict
    policy_evolution: dict
    final_result: str

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self)}


class TAAR_OS:
    """
    TAAR v4 — Mission Execution OS.
    Global execution loop:
        observe → load mission → build graphs → execute → update state
        → store episodic memory → evolve policies → re-evaluate
    """

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or f"taar-os-{uuid.uuid4().hex[:6]}"
        self.mission_ctrl = MissionController(session_id=self.session_id)
        self.episodic = EpisodicMemory()
        self.policy = PolicyEngine()
        self.active_mission: Mission | None = None
        self._execution_log: list[dict] = []
        self._resource_usage: dict[str, Any] = {
            "vrams_used_gb": 0.0,
            "llm_calls": 0,
            "total_time_s": 0.0,
        }

    def run(self, intent: str, verbose: bool = False) -> MissionResult:
        """
        Full mission lifecycle:
        1. Parse intent → Mission
        2. Plan → Activate
        3. Execute each graph via TAAR v3 engine
        4. Track state, handle failures/recovery
        5. Store episode in EpisodicMemory
        6. Evolve policies
        7. Return structured result
        """
        start_time = time.time()
        episode_id = f"E-{uuid.uuid4().hex[:6]}"
        self._execution_log = []

        self._log(f"🎯 MISSION START: {intent[:80]}")

        # ── Step 1: INTENT → MISSION ──
        mission = self.mission_ctrl.from_intent(intent)
        self.active_mission = mission
        self._log(f"📋 Mission created: {mission.mission_id}, graphs={len(mission.graphs)}")

        # ── Step 2: PLAN + ACTIVATE ──
        mission = self.mission_ctrl.plan(mission)
        mission = self.mission_ctrl.activate(mission.mission_id)
        self._log(f"▶️  Mission activated: {mission.status.value}")

        # ── Step 3: EXECUTE GRAPHS ──
        completed_graphs: list[str] = []
        failed_graphs: list[str] = []
        graph_results: list[dict] = []

        while True:
            ready = self.mission_ctrl.get_next_ready_graphs(mission.mission_id)
            if not ready:
                break

            for spec in ready:
                self._log(f"▶ GRAPH {spec.id} starting: mode={spec.mode}")
                self.mission_ctrl.update_graph_status(mission.mission_id, spec.id, "running")

                result = self._execute_graph(spec, intent)

                status = "completed" if result["status"] == "done" else "failed"
                self.mission_ctrl.update_graph_status(mission.mission_id, spec.id, status)
                completed_graphs.append(spec.id) if status == "completed" else failed_graphs.append(spec.id)
                graph_results.append({"graph_id": spec.id, **result})

                # Update mission status
                mission_status, _ = self.mission_ctrl.check_completion(mission.mission_id)
                self._log(f"📊 Mission status after {spec.id}: {mission_status.value}")

                # Handle degradation
                if mission_status == MissionStatus.DEGRADED:
                    self._log("⚠️  Mission degraded — switching to conservative mode")
                    self.mission_ctrl.degrade(mission.mission_id)
                if mission_status == MissionStatus.RECOVERING:
                    self._log("🔄 Mission recovering — retrying failed graphs")

                if mission_status in (MissionStatus.COMPLETED, MissionStatus.FAILED):
                    break
            if mission_status in (MissionStatus.COMPLETED, MissionStatus.FAILED):
                break

        # ── Step 4: DETERMINE OUTCOME ──
        elapsed = time.time() - start_time
        if mission.status == MissionStatus.COMPLETED:
            outcome = "success"
            final_result = f"Mission completed. Graphs: {', '.join(completed_graphs)}"
        elif mission.status == MissionStatus.FAILED:
            outcome = "failure"
            final_result = f"Mission failed. Failed graphs: {', '.join(failed_graphs)}"
        else:
            outcome = "partial"
            final_result = f"Mission partially complete. Completed: {', '.join(completed_graphs)}"

        self._log(f"🏁 MISSION END: outcome={outcome}, elapsed={elapsed:.1f}s")

        # ── Step 5: EPISODIC MEMORY UPDATE ──
        episode = Episode(
            episode_id=episode_id,
            mission_id=mission.mission_id,
            goal=intent,
            outcome=outcome,
            duration_s=elapsed,
            graphs_executed=len(graph_results),
            nodes_completed=len(completed_graphs),
            nodes_failed=len(failed_graphs),
            decisions=[{"state": f"graph {g['graph_id']}", "action": g["status"],
                        "reason": "completed" if g["status"] == "done" else "failed"}
                       for g in graph_results],
            resource_usage=dict(self._resource_usage),
            final_result=final_result,
            learned={"mode": graph_results[0]["status"] if graph_results else "none"},
        )
        self.episodic.store(episode)

        # ── Step 6: POLICY EVOLUTION ──
        episodic_summary = self.episodic.summarize()
        policy_evo = self.policy.evolve(episodic_summary)

        # ── Step 7: BUILD RESULT ──
        result = MissionResult(
            mission=mission.to_dict(),
            task_graphs=graph_results,
            state={
                "status": mission.status.value,
                "completed": completed_graphs,
                "failed": failed_graphs,
                "total_graphs": len(mission.graphs),
            },
            execution_log=self._execution_log,
            resource_usage={
                **self._resource_usage,
                "elapsed_s": round(elapsed, 2),
            },
            episodic_update=episode.to_dict(),
            policy_evolution=policy_evo,
            final_result=final_result,
        )

        return result

    def _execute_graph(self, spec: GraphSpec, mission_intent: str) -> dict[str, Any]:
        """Execute a single graph spec via appropriate engine."""
        from orchestrator import TAAROrchestrator

        start = time.time()
        status = "done"
        output = ""

        try:
            if spec.mode == "DEVOPS":
                # DevOps repair pipeline
                from devops_agent import DevOpsAgent
                agent = DevOpsAgent()
                r = agent.run(ci_logs=spec.goal, repo_path=".")
                output = str(r)
                self._resource_usage["llm_calls"] += 1

            elif spec.mode == "SWARM":
                # Swarm parallel execution
                from swarm import SwarmEngine
                swarm = SwarmEngine(max_workers=4)
                result = swarm.run(spec.goal, num_workers=4, strategy="parallel")
                output = result.merged_result or str(result)
                self._resource_usage["llm_calls"] += 2

            elif spec.mode == "TOOL":
                # Direct shell execution
                import subprocess
                # Extract command from goal
                cmd = spec.goal.replace("run ", "").replace("execute ", "").strip()
                try:
                    output = subprocess.check_output(
                        cmd, shell=True, stderr=subprocess.STDOUT, timeout=30
                    ).decode(errors="replace")
                except subprocess.TimeoutExpired:
                    output = "TIMEOUT: command exceeded 30s"
                except Exception as e:
                    output = f"ERROR: {e}"

            else:  # SINGLE
                orch = TAAROrchestrator(session_id=self.session_id)
                result = orch.run(spec.goal, verbose=False)
                output = result.final_result[:500]
                self._resource_usage["llm_calls"] += 3

        except Exception as e:
            status = "failed"
            output = f"Graph execution error: {e}"

        self._resource_usage["total_time_s"] += time.time() - start
        return {"status": status, "output": output}

    def _log(self, msg: str):
        """Add to execution log."""
        self._execution_log.append({
            "ts": time.strftime("%H:%M:%S"),
            "msg": msg,
        })
