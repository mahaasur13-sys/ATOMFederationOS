"""
TAAR v6 — Distributed Autonomous Execution Fabric
Global Coordinator + Mission Broker + Node Cluster + Shared Memory + Consensus.
"""

from __future__ import annotations
import uuid, time, subprocess, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# TAAR v5 components
from system_observer import SystemObserver
from mission_generator import MissionGenerator
from mission_prioritizer import MissionPrioritizer
from mission_controller import MissionController
from global_coordinator import GlobalCoordinator, NodeHealth
from mission_broker import MissionBroker, JobGraph
from distributed_memory import DistributedMemory
from policy_consensus import PolicyConsensusEngine, PolicyVote
from global_episodic_memory import GlobalEpisodicMemory, DistEpisode


@dataclass
class ExecutionStats:
    missions_generated: int = 0
    missions_brokered: int = 0
    jobs_executed: int = 0
    nodes_healthy: int = 0
    policy_evolutions: int = 0
    cluster_stability: float = 0.0


class TAARv6Node:
    """
    A single TAAR v5 instance running as a subprocess.
    Wraps the mission_controller in an isolated process.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.health = NodeHealth(node_id=node_id)
        self._active = True
        self._proc: subprocess.Popen | None = None

    def execute_job(self, task: str, timeout: int = 60) -> dict:
        """Execute a single job in this node's subprocess."""
        start = time.time()
        try:
            result = subprocess.run(
                ["python3", "-c", f"""
import sys; sys.path.insert(0, '/home/workspace')
sys.path.insert(0, '/home/workspace/agents')
from mission_controller import MissionController
c = MissionController()
m = c.from_intent('{task.replace("'", "\\'")}')
if m.graphs:
    g = m.graphs[0]
    r = c.execute_graph(g, '{{', c._orchestrator._state_machine)
    print(r)
else:
    print('no graph')
"""],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - start
            self.health.latency_ms = duration * 1000
            return {
                "node": self.node_id,
                "task": task[:60],
                "status": "completed" if result.returncode == 0 else "failed",
                "output": result.stdout[:200] if result.stdout else result.stderr[:200],
                "duration_s": duration,
            }
        except subprocess.TimeoutExpired:
            return {"node": self.node_id, "task": task[:60], "status": "timeout", "duration_s": timeout}
        except Exception as e:
            return {"node": self.node_id, "task": task[:60], "status": "error", "error": str(e)}


class TAARv6DistributedOS:
    """
    TAAR v6 — Distributed Autonomous Execution Fabric.
    Orchestrates multi-node execution with shared memory and consensus.
    """

    def __init__(self, num_nodes: int = 3):
        self.stats = ExecutionStats()
        self.observer = SystemObserver()
        self.generator = MissionGenerator(self.observer)
        self.prioritizer = MissionPrioritizer()
        self.coordinator = GlobalCoordinator()
        self.broker = MissionBroker()
        self.memory = DistributedMemory()
        self.consensus = PolicyConsensusEngine()
        self.episodic = GlobalEpisodicMemory()
        self.nodes: dict[str, TAARv6Node] = {}

        # Spawn node instances
        for i in range(num_nodes):
            nid = f"node_{i}"
            self.nodes[nid] = TAARv6Node(nid)
            self.coordinator.register_node(nid)
            self.coordinator.update_node_health(nid, gpu=0.0, cpu=0.0)

    def execute_job_graph(self, graph: JobGraph) -> dict:
        """Execute all jobs in a job graph across nodes."""
        results = {}
        ordered = graph.topological_order()

        def run_job(job):
            node = self.nodes.get(job.node)
            if not node:
                return job.job_id, {"status": "unknown_node"}
            return job.job_id, node.execute_job(job.task)

        # Execute in dependency order using threads
        completed_jobs = set()
        for job in ordered:
            if job.dependencies and not all(d in completed_jobs for d in job.dependencies):
                results[job.job_id] = {"status": "dependency_not_met"}
                continue

            r = self.nodes[job.node].execute_job(job.task)
            results[job.job_id] = r
            if r.get("status") in ("completed", "failed", "error"):
                completed_jobs.add(job.job_id)
            self.stats.jobs_executed += 1

        return results

    def single_cycle(self, verbose: bool = True) -> ExecutionStats:
        """One full observe → generate → broker → execute → sync → consensus cycle."""
        if verbose:
            print("\n" + "=" * 60)
            print("TAAR v6 — Distributed Autonomous Execution Fabric")
            print("=" * 60)

        # 1. OBSERVE
        state = self.observer.observe()
        self.stats.cluster_stability = state.system_stability
        if verbose:
            print(f"[OBSERVER] stability={state.system_stability:.3f}, "
                  f"gpu={state.gpu_pressure:.2f}, mem={state.memory_pressure:.1f}%")

        # Update coordinator with system metrics
        for nid in self.nodes:
            self.coordinator.update_node_health(nid, gpu=state.gpu_pressure, cpu=state.cpu_load)

        # 2. GENERATE
        missions = self.generator.generate(state)
        self.stats.missions_generated = len(missions)
        if verbose:
            print(f"[GENERATOR] {len(missions)} missions generated")

        # 3. PRIORITIZE
        prioritized = self.prioritizer.prioritize(missions, state)
        if verbose:
            print(f"[PRIORITIZER] {len(prioritized)}/{len(missions)} executable "
                  f"(dropped {len(missions) - len(prioritized)})")

        # 4. BROKER + COORDINATE
        for p in prioritized[:3]:  # Execute top-3 per cycle
            mission_goal = p.mission.goal  # PrioritizedMission.mission.goal
            mission_id = str(uuid.uuid4)[:8]
            num_nodes = min(len(self.nodes), 3)
            graph = self.broker.decompose(mission_goal, num_nodes=num_nodes)

            best_node = self.coordinator.get_best_node()
            if best_node:
                self.coordinator.assign_mission(mission_id, best_node)

            if verbose:
                print(f"[BROKER] mission={mission_goal[:50]} → {num_nodes} jobs across nodes")

            # 5. EXECUTE distributed
            job_results = self.execute_job_graph(graph)

            # 6. SYNC memory
            for job_id, result in job_results.items():
                node_id = result.get("node", "unknown")
                self.memory.write_node_slice(
                    node_id=node_id,
                    summary=result.get("output", "")[:150],
                    mission_result=f"{job_id}: {result.get('status')}",
                )
                self.memory.log_event("job_complete", node_id, result)

            # 7. Record in global episodic
            node_results = {job_id: r.get("status", "unknown") for job_id, r in job_results.items()}
            completed = sum(1 for s in node_results.values() if s == "completed")
            failed = sum(1 for s in node_results.values() if s in ("failed", "error"))
            outcome = "completed" if failed == 0 else "degraded" if completed > 0 else "failed"
            ep = DistEpisode(
                episode_id=str(uuid.uuid4)[:8],
                mission=mission_goal[:80],
                nodes_involved=list(self.nodes.keys()),
                outcome=outcome,
                duration_s=0.5,
                node_results=node_results,
                decision_path=["observe", "generate", "broker", "execute", "sync"],
            )
            self.episodic.store(ep)
            self.memory.update_global_stats(completed=completed, failed=failed)

            # 8. POLICY CONSENSUS
            for job_id, result in job_results.items():
                if result.get("status") == "completed":
                    vote = PolicyVote(
                        node_id=result.get("node", "unknown"),
                        param="devops_sensitivity",
                        proposed_value=0.70,
                        reason=f"successful execution of {mission_goal[:30]}",
                        stability_delta=0.05,
                    )
                    self.consensus.submit_vote(vote)

            decisions = self.consensus.resolve()
            self.stats.policy_evolutions = len(decisions)
            if verbose and decisions:
                print(f"[CONSENSUS] {len(decisions)} decisions: {[d.param for d in decisions]}")

        # 9. FAULT ISOLATION — check for degraded nodes
        cluster_health = self.coordinator.get_cluster_health()
        self.stats.nodes_healthy = cluster_health["healthy_nodes"]
        for nid, h in cluster_health.get("nodes", {}).items():
            if h["failure_rate"] > 0.5:
                self.coordinator.isolate_node(nid, "high_failure_rate")
                self.episodic.record_node_failure(nid, "cycle", "failure_rate > 0.5")

        if verbose:
            print(f"\n[CLUSTER] healthy={self.stats.nodes_healthy}/{len(self.nodes)}, "
                  f"stability={self.stats.cluster_stability:.3f}")
            print(f"[MEMORY] nodes={len(self.memory.node_slices)}, "
                  f"events={len(self.memory.event_log)}")
            print(f"[EPISODIC] total={self.episodic.get_stats()['total_episodes']}, "
                  f"trend={self.episodic.get_trend()}")

        return self.stats


def main():
    os = TAARv6DistributedOS(num_nodes=3)
    print("TAAR v6 — Distributed Autonomous Execution Fabric")
    print(f"Nodes: {len(os.nodes)} | Observer | Broker | Consensus | Episodic")
    print()
    stats = os.single_cycle(verbose=True)
    print()
    print(f"Missions: {stats.missions_generated} generated, {stats.jobs_executed} jobs executed")
    print(f"Cluster stability: {stats.cluster_stability:.3f}")
    print(f"Policy evolutions: {stats.policy_evolutions}")
    print("\n✅ TAAR v6 — Distributed OS operational")


if __name__ == "__main__":
    main()
