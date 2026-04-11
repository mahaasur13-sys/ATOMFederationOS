"""
TAAR v4 — Mission Controller
Decomposes intent → mission → task graphs
Handles lifecycle, re-planning, priority.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MissionStatus(str, Enum):
    CREATED    = "created"
    PLANNED    = "planned"
    ACTIVE     = "active"
    DEGRADED   = "degraded"
    RECOVERING = "recovering"
    COMPLETED  = "completed"
    FAILED     = "failed"
    PAUSED     = "paused"


class MissionPriority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    CRITICAL = "critical"


@dataclass
class GraphSpec:
    """A task graph within a mission."""
    id: str
    goal: str
    dependencies: list[str] = field(default_factory=list)
    mode: str = "SINGLE"         # SINGLE | SWARM | DEVOPS | TOOL
    max_iterations: int = 20
    retries: int = 2
    status: str = "pending"      # pending | running | completed | failed


@dataclass
class Mission:
    mission_id: str
    goal: str
    priority: MissionPriority = MissionPriority.MEDIUM
    graphs: list[GraphSpec] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=lambda: {
        "max_vram_gb": 8,
        "max_llm_calls": 12,
        "time_budget": "medium",
    })
    status: MissionStatus = MissionStatus.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    current_attempt: int = 1
    max_attempts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "goal": self.goal,
            "priority": self.priority.value,
            "graphs": [{"id": g.id, "goal": g.goal, "deps": g.dependencies,
                        "mode": g.mode, "status": g.status} for g in self.graphs],
            "constraints": self.constraints,
            "status": self.status.value,
            "current_attempt": self.current_attempt,
        }


# ─────────────────────────────────────────
# MISSION CONTROLLER
# ─────────────────────────────────────────

class MissionController:
    """
    High-level mission orchestration.
    intent → mission → graph_specs → lifecycle management
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.active_missions: dict[str, Mission] = {}
        self.mission_history: list[Mission] = []

    def from_intent(self, intent: str, constraints: dict[str, Any] | None = None) -> Mission:
        """
        Parse natural-language intent → structured Mission with GraphSpecs.
        Uses keyword + structure analysis (no LLM required).
        """
        intent_lower = intent.lower()
        mission_id = f"M-{uuid.uuid4().hex[:6]}"
        graphs: list[GraphSpec] = []

        # ── CI/CD / DevOps mission ──
        if any(k in intent_lower for k in
               ["ci", "github", "workflow", "lint", "ruff", "pytest",
                "test fail", "error:", "pipeline", "deploy"]):
            graphs.append(GraphSpec(
                id="G1",
                goal=f"analyze and fix: {intent}",
                mode="DEVOPS",
                max_iterations=10,
            ))
            if any(k in intent_lower for k in ["test", "deploy"]):
                graphs.append(GraphSpec(
                    id="G2",
                    goal=f"validate after fix: {intent}",
                    dependencies=["G1"],
                    mode="TOOL",
                ))

        # ── Multi-step build/test/deploy mission ──
        elif any(sep in intent_lower for sep in [" then ", " after ", " and then ", " → ", " -> "]):
            parts = _split_intent(intent_lower)
            for i, part in enumerate(parts):
                deps = [f"G{i}"] if i > 0 else []
                graphs.append(GraphSpec(
                    id=f"G{i+1}",
                    goal=part.strip(),
                    dependencies=deps,
                    mode=self._detect_mode_for_step(part),
                ))

        # ── Parallel scan/analysis mission ──
        elif any(k in intent_lower for k in
                 ["scan", "analyze all", "find all", "search all",
                  "audit", "review all", "parallel"]):
            graphs.append(GraphSpec(
                id="G1",
                goal=f"parallel analysis: {intent}",
                mode="SWARM",
                max_iterations=5,
            ))

        # ── Complex multi-graph mission ──
        elif any(k in intent_lower for k in
                 ["repo", "repository", "project setup", "setup project",
                  "configure", "migrate", "refactor"]):
            graphs.append(GraphSpec(
                id="G1",
                goal=f"phase 1: {intent}",
                mode=self._detect_mode_for_step(intent),
            ))
            graphs.append(GraphSpec(
                id="G2",
                goal=f"phase 2: validate {intent}",
                dependencies=["G1"],
                mode="TOOL",
            ))

        # ── Default: single graph ──
        else:
            graphs.append(GraphSpec(
                id="G1",
                goal=intent,
                mode=self._detect_mode_for_step(intent),
            ))

        mission = Mission(
            mission_id=mission_id,
            goal=intent,
            graphs=graphs,
            constraints=constraints or {},
        )
        self.active_missions[mission_id] = mission
        return mission

    def plan(self, mission: Mission) -> Mission:
        """Mark mission as planned."""
        mission.status = MissionStatus.PLANNED
        mission.updated_at = time.time()
        return mission

    def activate(self, mission_id: str) -> Mission | None:
        m = self.active_missions.get(mission_id)
        if m:
            m.status = MissionStatus.ACTIVE
            m.updated_at = time.time()
        return m

    def update_graph_status(self, mission_id: str, graph_id: str,
                            status: str) -> Mission | None:
        m = self.active_missions.get(mission_id)
        if not m:
            return None
        for g in m.graphs:
            if g.id == graph_id:
                g.status = status
        m.updated_at = time.time()
        return m

    def check_completion(self, mission_id: str) -> tuple[MissionStatus, list[str]]:
        """Check if all graphs are done. Returns (status, completed_graphs)."""
        m = self.active_missions.get(mission_id)
        if not m:
            return MissionStatus.FAILED, []

        completed = [g.id for g in m.graphs if g.status == "completed"]
        failed = [g.id for g in m.graphs if g.status == "failed"]

        if failed:
            if m.current_attempt < m.max_attempts:
                m.status = MissionStatus.RECOVERING
            else:
                m.status = MissionStatus.FAILED
        elif len(completed) == len(m.graphs):
            m.status = MissionStatus.COMPLETED
            self.mission_history.append(m)
            del self.active_missions[mission_id]
        else:
            m.status = MissionStatus.ACTIVE

        m.updated_at = time.time()
        return m.status, completed

    def degrade(self, mission_id: str) -> Mission | None:
        """Downgrade mission: reduce VRAM budget, switch to TOOL-only."""
        m = self.active_missions.get(mission_id)
        if not m:
            return None
        m.status = MissionStatus.DEGRADED
        m.constraints["max_vram_gb"] = 4
        m.constraints["time_budget"] = "short"
        for g in m.graphs:
            if g.mode == "SWARM":
                g.mode = "SINGLE"
            g.retries = max(0, g.retries - 1)
        m.updated_at = time.time()
        return m

    def get_next_ready_graphs(self, mission_id: str) -> list[GraphSpec]:
        """Return graphs whose dependencies are all satisfied."""
        m = self.active_missions.get(mission_id)
        if not m:
            return []
        ready = []
        for g in m.graphs:
            if g.status != "pending":
                continue
            if all(
                next((gx.status == "completed" for gx in m.graphs if gx.id == dep), False)
                for dep in g.dependencies
            ):
                ready.append(g)
        return ready

    def _detect_mode_for_step(self, step: str) -> str:
        step_l = step.lower()
        if any(k in step_l for k in ["ci ", "lint", "ruff", "pytest", "test fail",
                                      "error:", "workflow", "build fail"]):
            return "DEVOPS"
        if any(k in step_l for k in ["parallel", "scan", "analyze all",
                                      "find all", "grep all"]):
            return "SWARM"
        if any(k in step_l for k in ["run ", "execute", "compile",
                                      "pip install", "apt install"]):
            return "TOOL"
        return "SINGLE"

    def get_active_missions(self) -> list[Mission]:
        return list(self.active_missions.values())


def _split_intent(text: str) -> list[str]:
    """Split 'X then Y then Z' into parts."""
    for sep in [" then ", " → ", " -> ", " and then "]:
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text]
