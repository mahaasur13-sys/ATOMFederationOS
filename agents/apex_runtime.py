"""
TAAR v11 — APEX Runtime (full integrated system)
Hooks TAAR v1-v10 components into APEX execution kernel.
"""

from __future__ import annotations
from dataclasses import dataclass
import time

from apex_execution_kernel import APEXExecutionKernel, ExecutionResult, ExecutionState
from mission_controller import MissionController
from devops_agent import DevOpsAgent
from orchestrator import TAAROrchestrator
from swarm import SwarmEngine


class APEXRuntime:
    """
    TAAR v11 — APEX Runtime.

    Connects APEX Execution Kernel with existing TAAR v1-v10 components:
        v1:  langgraph_core, tools_adapter, memory
        v3:  task_graph, state_machine, orchestrator
        v4:  mission_controller, episodic_memory
        v5:  system_observer, mission_generator
        v6:  global_coordinator, mission_broker
        v8:  economy_coordinator, task_market
        v9:  civilization_council
        v10: reality_control_council, infra_abstraction

    Routing logic (RTX 3060 safe mode):
        CI error  → DEVOPS (devops_agent)
        Multi     → SWARM (swarm engine, sequential)
        Single    → SINGLE (orchestrator)
        Mission   → MISSION (mission_controller)
        Unknown   → SINGLE
    """

    def __init__(self, dry_run: bool = True):
        self.kernel = APEXExecutionKernel(dry_run=dry_run)
        self.devops = DevOpsAgent()
        self.orchestrator = TAAROrchestrator()
        self.swarm = SwarmEngine(max_workers=1)  # RTX 3060 safe: 1 worker
        self.mc = MissionController()
        self.cycle_count = 0

    def execute(self, task: str) -> dict:
        """Execute via APEX kernel, then route to component."""
        start = time.time()
        result = self.kernel.execute(task)
        component_result = None

        if result.policy_verdict.verdict == "BLOCK":
            component_result = {
                "status": "blocked",
                "reason": result.policy_verdict.reason,
            }
        elif result.outcome == "vetoed":
            component_result = {
                "status": "vetoed",
                "reason": result.policy_verdict.reason,
            }
        else:
            # Route to appropriate component based on plan
            plan = result.plan
            if plan and "parse CI log" in plan[0]:
                # DEVOPS route
                dev_result = self.devops.run(ci_logs=task, repo_path=".")
                component_result = {
                    "status": "devops_completed",
                    "root_cause": dev_result["analysis"]["root_cause"],
                    "patch": dev_result["patch"].get("command"),
                    "safety": dev_result["safety_report"].get("violations", []),
                }
            elif plan and "decompose task" in plan[0]:
                # SWARM route (sequential)
                sw_result = self.swarm.run(task, num_workers=1)
                component_result = {
                    "status": "swarm_completed",
                    "merged": sw_result.merged_result,
                    "subtasks": len(sw_result.subtasks),
                }
            else:
                # SINGLE route
                orch_result = self.orchestrator.execute_single_task(task)
                component_result = {
                    "status": "orchestrated",
                    "result": str(orch_result)[:200],
                }

        return {
            "apex_result": {
                "task_id": result.task_id,
                "outcome": result.outcome,
                "policy": f"{result.policy_verdict.verdict} — {result.policy_verdict.reason}",
                "state": result.execution_state.value,
                "plan_steps": len(result.plan),
                "audit_entry": result.audit_entry_id[:16],
                "duration_ms": result.duration_ms,
                "tool_calls": len(result.tool_calls),
            },
            "component_result": component_result,
            "total_duration_ms": (time.time() - start) * 1000,
        }

    def get_stats(self) -> dict:
        return {
            "apex_kernel": {
                "active_tasks": len(self.kernel.active_tasks),
                "audit_chain_length": len(self.kernel.audit_graph.chain),
                "chain_valid": self.kernel.audit_graph.is_valid(),
            },
            "components": {
                "devops": "DevOpsAgent",
                "orchestrator": "TAAROrchestrator",
                "swarm": "SwarmEngine (workers=1)",
                "mission": "MissionController",
            },
            "rtx3060_compliance": {
                "max_concurrent_llm": 1,
                "vision_enabled": False,
                "parallel_swarm": False,
            },
        }


def main():
    print("=" * 70)
    print("🚀 TAAR v11 — APEX Runtime")
    print("APEX Kernel + TAAR v1-v10 component integration")
    print("=" * 70)

    runtime = APEXRuntime(dry_run=True)

    test_tasks = [
        "ci failed: ruff F401 agents/tools_adapter.py",
        "build and test all modules",
        "scan workspace for unused imports",
        "rm -rf /home/workspace",
    ]

    for task in test_tasks:
        print(f"\n[TASK] {task}")
        r = runtime.execute(task)
        print(f"  → apex: {r['apex_result']['state']} | {r['apex_result']['outcome']}")
        print(f"  → policy: {r['apex_result']['policy']}")
        print(f"  → component: {r['component_result']['status']}")
        print(f"  → audit: {r['apex_result']['audit_entry']} | {r['apex_result']['duration_ms']:.1f}ms")

    stats = runtime.get_stats()
    print(f"\n[STATS] audit_chain={stats['apex_kernel']['audit_chain_length']} | "
          f"valid={stats['apex_kernel']['chain_valid']} | "
          f"workers={stats['rtx3060_compliance']['max_concurrent_llm']}")


if __name__ == "__main__":
    main()
