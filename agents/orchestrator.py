"""
TAAR v3 — Orchestrator
Global execution loop: TaskGraph + StateMachine + ControlPlane + Resource Manager.
Continuous OS loop: observe → update graph → execute nodes → repair failures → persist.
"""

from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any

from task_graph import TaskGraph, GraphNode, ExecutionMode
from state_machine import StateMachine, NodeStatus
from control_plane import ControlPlane, Decision


@dataclass
class OrchestratorResult:
    task_graph: dict[str, Any]
    state: dict[str, Any]
    execution_log: list[dict]
    resource_usage: dict[str, Any]
    final_result: str


class TAAROrchestrator:
    """
    TAAR v3 Global Orchestration Loop.

    Flow:
        TASK → ControlPlane.route() → TaskGraph.build_graph()
        → StateMachine.init() → NODE EXECUTION LOOP
        → for each ready node: execute via appropriate mode
        → update StateMachine (complete/fail/retry)
        → reroute exhausted failures → persist memory
        → repeat until all done or terminal failure
    """

    def __init__(self, session_id: str = "taar-v3"):
        self.session_id = session_id
        self.cp = ControlPlane()
        self.tg: TaskGraph | None = None
        self.sm: StateMachine | None = None
        self._log: list[dict] = []
        self._max_nodes = 20

    # ── Mode executors ──────────────────────────────────────────────────────

    def _run_devops(self, task: str) -> Any:
        from devops_agent import DevOpsAgent
        agent = DevOpsAgent()
        return agent.run(ci_logs=task, repo_path=".")

    def _run_swarm(self, task: str) -> Any:
        from swarm import SwarmEngine
        s = SwarmEngine(max_workers=4)
        strategy = s.get_strategy(task)
        workers = s.get_num_workers(task)
        return s.run(task, num_workers=workers, strategy=strategy)

    def _run_single(self, task: str) -> Any:
        from langgraph_core import run_task
        return run_task(task, max_iterations=10)

    def _run_tool(self, task: str) -> Any:
        import subprocess
        result = subprocess.run(task, shell=True, capture_output=True, text=True, timeout=60)
        return result.stdout.strip() or result.stderr.strip() or f"exit {result.returncode}"

    # ── Main run ─────────────────────────────────────────────────────────────

    def run(self, task: str, verbose: bool = False) -> OrchestratorResult:
        start_time = time.time()
        self._log = []

        # 1. Control Plane routing
        plan = self.cp.route(task)
        self._log.append({"step": "control_plane", "mode": plan.mode.value,
                           "policy": plan.policy_decision.value, "conf": plan.mode_confidence})

        if plan.policy_decision == Decision.DENY:
            return self._make_result(f"DENT: {plan.policy_reasons}")

        # 2. Build Task Graph
        self.tg = TaskGraph()
        graph = self.tg.build_graph(task)
        self._log.append({"step": "graph_built", "nodes": len(graph["nodes"])})

        # 3. Init State Machine
        self.sm = StateMachine(session_id=self.session_id)

        # Mark all nodes pending
        for node in graph["nodes"]:
            self.sm.update_node_status(node.id, NodeStatus.PENDING)

        # 4. Node Execution Loop
        iteration = 0
        while not self.sm.is_all_done() and not self.sm.is_failure_terminal() and iteration < self._max_nodes:
            iteration += 1
            ready = self.sm.get_ready_nodes(graph)

            for nid in ready:
                node = self.tg._graph[nid]
                self._log.append({"step": "execute_start", "node": nid, "mode": node.mode.value})

                # Skip non-runnable modes
                if node.mode == ExecutionMode.SKIP:
                    self.sm.update_node_status(nid, NodeStatus.COMPLETED, result="skipped")
                    continue

                self.sm.update_node_status(nid, NodeStatus.RUNNING)

                try:
                    result = self.tg.execute_node(
                        node,
                        devops_fn=self._run_devops,
                        swarm_fn=self._run_swarm,
                        single_fn=self._run_single,
                        tool_fn=self._run_tool,
                    )
                    self.sm.update_node_status(nid, NodeStatus.COMPLETED, result=str(result)[:200])
                    self._log.append({"step": "execute_done", "node": nid, "status": "ok"})
                except Exception as e:
                    self._log.append({"step": "execute_error", "node": nid, "error": str(e)})
                    node.retry_count += 1
                    if node.can_retry():
                        self.sm.update_node_status(nid, NodeStatus.RETRY_QUEUE,
                                                   error=str(e), retry_count=node.retry_count)
                        node.mode = self.tg.reroute_node(node)
                    else:
                        self.sm.update_node_status(nid, NodeStatus.FAILED,
                                                   error=str(e), retry_count=node.retry_count)

            time.sleep(0.05)  # yield

        # 5. Aggregate results
        completed_results = {}
        for nid, n in self.tg._graph.items():
            if n.status == "completed":
                completed_results[nid] = n.result

        final = "; ".join(f"{k}:{str(v)[:80]}" for k, v in completed_results.items())

        elapsed = time.time() - start_time
        return OrchestratorResult(
            task_graph=self.tg.to_dict(),
            state=self.sm.to_dict(),
            execution_log=self._log,
            resource_usage={
                "elapsed_s": round(elapsed, 1),
                "nodes_executed": len([e for e in self._log if e.get("step") == "execute_done"]),
                "iterations": iteration,
                "gpu_available": plan.gpu_allowed,
            },
            final_result=final or "no results",
        )

    def _make_result(self, final: str) -> OrchestratorResult:
        return OrchestratorResult(
            task_graph={"nodes": []},
            state={"session_id": self.session_id},
            execution_log=self._log,
            resource_usage={},
            final_result=final,
        )
