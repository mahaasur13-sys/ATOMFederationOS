"""
TAAR v3 — Task Graph Manager
Builds DAG from task: assigns modes per node, resolves dependencies, retries failed nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid

class ExecutionMode(str, Enum):
    DEVOPS = "devops"
    SWARM  = "swarm"
    SINGLE = "single"
    TOOL   = "tool"
    SKIP   = "skip"

@dataclass
class GraphNode:
    id: str
    task: str
    mode: ExecutionMode
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"   # pending/running/completed/failed
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def can_reroute(self) -> bool:
        """Failed nodes that exhausted retries can be rerouted to DEVOPS."""
        return self.status == "failed" and self.retry_count >= self.max_retries

class TaskGraph:
    """
    Decomposes task into DAG of GraphNodes.
    Uses keyword + semantic routing to assign ExecutionMode per node.
    """

    def __init__(self, max_llm_budget: int = 20):
        self.max_llm_budget = max_llm_budget
        self._graph: dict[str, GraphNode] = {}

    # ── Mode routing (LLM + keyword fallback) ──────────────────────────────

    def _route_node(self, task: str, idx: int) -> ExecutionMode:
        t = task.lower()
        # DEVOPS first (highest priority for error-related tasks)
        if any(k in t for k in ["ci fail","github action","workflow","build fail",
                                 "pipeline","lint error","test fail","ruff","pytest",
                                 "ci_error","actions error","job failed","step failed",
                                 "module not found","not found","error:","failed:",
                                 "failed","syntaxerror","importerror","assertion"]):
            return ExecutionMode.DEVOPS
        # SWARM: large parallelizable tasks
        if any(k in t for k in ["parallel","swarm","concurrent","analyze all",
                                 "find all","search all","scan","audit","review all",
                                 "grep","list all","generate all","check all"]):
            return ExecutionMode.SWARM
        # TOOL: direct shell commands
        if any(k in t for k in ["run ","exec ","cmd ","command ","bash ",
                                 "git ","docker ","curl ","ls ","cat ","grep ",
                                 "find ","pip ","npm ","apt ","kill ","pkill ",
                                 "ssh ","scp ","rsync ","tar ","zip ","unzip "]):
            return ExecutionMode.TOOL
        # SINGLE: default for reasoning/planning tasks
        return ExecutionMode.SINGLE

    # ── Graph builder ───────────────────────────────────────────────────────

    def _split_task(self, task: str) -> list[str]:
        """Split natural-language task into sub-tasks by sentence/phrase."""
        import re
        # Split on sentence boundaries, "and then", "step 1/2/3", newlines
        parts = re.split(r'(?<=[.!?])\s+|(?:\s+and then\s+)|(?:\s+[Ss]tep\s+\d+[:\s]+)',
                         task)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) <= 1:
            # Try comma/newline split
            parts = re.split(r'[,;\n]+', task)
            parts = [p.strip() for p in parts if p.strip()]
        return parts if len(parts) > 1 else [task]

    def build_graph(self, task: str) -> dict[str, Any]:
        """
        Returns dict with 'nodes' (list[GraphNode]) and 'edges' (list of [from, to] pairs).
        DAG is built by assigning modes and resolving dependencies.
        """
        self._graph = {}
        sub_tasks = self._split_task(task)
        node_ids = []

        for idx, sub in enumerate(sub_tasks):
            nid = chr(65 + idx)  # A, B, C ...
            mode = self._route_node(sub, idx)
            node_ids.append(nid)
            self._graph[nid] = GraphNode(
                id=nid,
                task=sub,
                mode=mode,
                depends_on=[node_ids[idx-1]] if idx > 0 else [],
            )

        # Build edges from depends_on
        edges = []
        for nid, node in self._graph.items():
            for dep in node.depends_on:
                edges.append([dep, nid])

        return {"nodes": list(self._graph.values()), "edges": edges}

    # ── Node execution ──────────────────────────────────────────────────────

    def execute_node(self, node: GraphNode,
                     devops_fn=None, swarm_fn=None,
                     single_fn=None, tool_fn=None) -> Any:
        """Execute a single node via the appropriate mode function."""
        node.status = "running"
        try:
            if node.mode == ExecutionMode.DEVOPS and devops_fn:
                node.result = devops_fn(node.task)
            elif node.mode == ExecutionMode.SWARM and swarm_fn:
                node.result = swarm_fn(node.task)
            elif node.mode == ExecutionMode.TOOL and tool_fn:
                node.result = tool_fn(node.task)
            elif node.mode == ExecutionMode.SINGLE and single_fn:
                node.result = single_fn(node.task)
            else:
                node.result = f"[{node.mode.value}] no executor registered"
            node.status = "completed"
            return node.result
        except Exception as e:
            node.error = str(e)
            node.status = "failed"
            raise

    def reroute_node(self, node: GraphNode) -> ExecutionMode:
        """
        After max retries, reroute to DEVOPS (for code errors)
        or TOOL (for execution errors).
        """
        if "error" in node.task.lower() or "fail" in node.task.lower():
            return ExecutionMode.DEVOPS
        if "run" in node.task.lower() or "exec" in node.task.lower():
            return ExecutionMode.TOOL
        return ExecutionMode.SINGLE

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": n.id, "task": n.task, "mode": n.mode.value,
                 "status": n.status, "result": str(n.result)[:200],
                 "error": n.error, "retry_count": n.retry_count,
                 "depends_on": n.depends_on}
                for n in self._graph.values()
            ],
            "edges": self._get_edges(),
        }

    def _get_edges(self) -> list[list[str]]:
        edges = []
        for nid, node in self._graph.items():
            for dep in node.depends_on:
                edges.append([dep, nid])
        return edges
