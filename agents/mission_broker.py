"""
TAAR v6 — Mission Broker
Converts mission → distributed job graph, assigns jobs to nodes,
optimizes for latency + resource cost.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class JobSpec:
    job_id: str
    node: str
    task: str
    priority: int = 1
    dependencies: list[str] = field(default_factory=list)
    resource_hint: str = "cpu"  # cpu | gpu | memory
    payload: dict[str, Any] | None = None

    def __hash__(self):
        return hash(self.job_id)


@dataclass
class JobGraph:
    mission: str
    jobs: list[JobSpec] = field(default_factory=list)
    graph_id: str = field(default_factory=uuid.uuid4)

    def add_job(self, node: str, task: str, priority: int = 1,
                deps: list[str] | None = None, resource_hint: str = "cpu") -> JobSpec:
        j = JobSpec(
            job_id=f"{self.graph_id}_{len(self.jobs)}",
            node=node,
            task=task,
            priority=priority,
            dependencies=deps or [],
            resource_hint=resource_hint,
        )
        self.jobs.append(j)
        return j

    def topological_order(self) -> list[JobSpec]:
        """Return jobs sorted by dependency (deps first)."""
        result, seen = [], set()
        def visit(j: JobSpec):
            if j.job_id in seen:
                return
            for dep_id in j.dependencies:
                for dj in self.jobs:
                    if dj.job_id == dep_id and dj.job_id not in seen:
                        visit(dj)
            seen.add(j.job_id)
            result.append(j)
        for job in self.jobs:
            visit(job)
        return result

    def jobs_for_node(self, node_id: str) -> list[JobSpec]:
        return [j for j in self.jobs if j.node == node_id]

    def summary(self) -> dict:
        return {
            "mission": self.mission,
            "graph_id": str(self.graph_id),
            "total_jobs": len(self.jobs),
            "by_node": {node: len(self.jobs_for_node(node)) for node in set(j.node for j in self.jobs)},
            "execution_order": [j.job_id for j in self.topological_order()],
        }


class MissionBroker:
    """
    Decomposes missions into job graphs and distributes across the cluster.
    """

    def __init__(self):
        self._graphs: dict[str, JobGraph] = {}

    def decompose(self, mission: str, num_nodes: int = 3) -> JobGraph:
        """
        Break a mission into a job graph targeting `num_nodes` nodes.
        Uses pattern matching for common mission types.
        """
        mission_lower = mission.lower()
        graph = JobGraph(mission=mission)

        # ── Multi-step mission patterns ──
        if any(k in mission_lower for k in ["then", " and ", " after "]):
            parts = [p.strip() for p in mission.replace(" then ", "|||").replace(" and ", "|||").replace(" after ", "|||").split("|||")]
            parts = [p for p in parts if p]
            for i, part in enumerate(parts):
                is_last = (i == len(parts) - 1)
                deps = [graph.jobs[-1].job_id] if i > 0 else []
                graph.add_job(
                    node=f"node_{(i % num_nodes)}",
                    task=part,
                    priority=len(parts) - i,
                    deps=deps,
                )

        # ── DevOps / CI mission: analyze → fix → validate ──
        elif any(k in mission_lower for k in ["ci", "ruff", "pytest", "build fail", "module"]):
            graph.add_job(node="node_0", task=f"analyze: {mission}", priority=3, resource_hint="cpu")
            graph.add_job(node="node_1", task=f"fix: {mission}", priority=2, deps=[f"{graph.graph_id}_0"], resource_hint="cpu")
            graph.add_job(node="node_2", task=f"validate after fix: {mission}", priority=1, deps=[f"{graph.graph_id}_1"], resource_hint="cpu")

        # ── Swarm / parallel mission ──
        elif any(k in mission_lower for k in ["swarm", "parallel", "concurrent", "analyze all", "scan all"]):
            for i in range(min(6, num_nodes)):
                graph.add_job(
                    node=f"node_{i}",
                    task=f"execute partition {i+1}/{min(6,num_nodes)}: {mission}",
                    priority=2,
                    resource_hint="gpu" if i < 2 else "cpu",
                )
            # Aggregation job
            graph.add_job(node="node_0", task=f"aggregate results: {mission}", priority=1, deps=[f"{graph.graph_id}_{i}" for i in range(min(6, num_nodes))], resource_hint="cpu")

        # ── Single task: just execute ──
        else:
            graph.add_job(node="node_0", task=mission, priority=1, resource_hint="cpu")

        self._graphs[str(graph.graph_id)] = graph
        return graph

    def get_graph(self, graph_id: str) -> JobGraph | None:
        return self._graphs.get(graph_id)

    def get_stats(self) -> dict:
        return {"total_graphs": len(self._graphs)}
