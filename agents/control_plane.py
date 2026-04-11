"""
TAAR v2.1 — Control Plane (ATOM OS Orchestration Layer)
Routes tasks to execution modes using LLM classification + policy + resource awareness.
"""

from __future__ import annotations

import json
import time
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict
from enum import Enum

import requests

from gpu_control import GPUControlLayer, GPUStatus
from memory_hierarchy import MemoryHierarchy

# ─────────────────────────────────────────
# Enums & TypedDicts
# ─────────────────────────────────────────

class ExecutionMode(str, Enum):
    SINGLE = "SINGLE"       # LangGraph single-agent
    SWARM = "SWARM"          # Parallel workers (GPU-safe)
    DEVOPS = "DEVOPS"        # CI/CD repair loop
    TOOL = "TOOL"            # No LLM, tools only


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    DEGRADE = "DEGRADE"      # Downgrade mode due to resource pressure


class PressureLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Semantic Router Output ───────────────

class TaskAnalysis(TypedDict):
    mode: str
    confidence: float
    gpu_pressure: str
    memory_pressure: str
    reason: str
    estimated_llm_calls: int
    estimated_vram_mb: int
    is_devops: bool
    is_stateless: bool


@dataclass
class ExecutionPlan:
    mode: ExecutionMode
    mode_confidence: float
    gpu_allowed: bool
    memory_allowed: bool
    policy_decision: Decision
    policy_reasons: list[str]
    max_iterations: int
    budget_factor: float        # 0.0–1.0 — scale of resources to use
    execution_hints: dict[str, Any]
    suggested_downgrade: str | None = None


# ─────────────────────────────────────────
# Policy Engine
# ─────────────────────────────────────────

class PolicyEngine:
    """
    Deterministic policy rules. Returns (decision, reasons).
    No LLM — pure logic over TaskAnalysis + GPU/Memory state.
    """

    MAX_LLM_CALLS_SINGLE = 50
    MAX_LLM_CALLS_SWARM = 20
    MAX_LLM_CALLS_DEVOPS = 10
    MAX_LLM_CALLS_TOOL = 0

    SAFETY_DENY_PATTERNS = [
        re.compile(r"\bsudo\b"),
        re.compile(r"\brm\s+-rf\s+/\b"),
        re.compile(r"\bdd\s+if=\s*/dev/\b"),
        re.compile(r"\bmkfs\b"),
        re.compile(r">\s*/dev/sd"),
    ]

    def evaluate(self, analysis: TaskAnalysis, gpu: GPUStatus | None, mem_stats) -> tuple[Decision, list[str]]:
        reasons = []
        decision = Decision.ALLOW

        # ── Safety: deny dangerous operations ──
        task_lower = analysis.get("reason", "").lower() + " " + analysis.get("mode", "")
        for pat in self.SAFETY_DENY_PATTERNS:
            if pat.search(task_lower):
                return Decision.DENY, [f"Dangerous pattern blocked: {pat.pattern}"]

        # ── Resource pressure: escalate or degrade ──
        if gpu is not None and gpu.vram_util_pct >= 90:
            decision = Decision.DEGRADE
            reasons.append(f"VRAM critical: {gpu.vram_util_pct}%")

        if gpu is not None and gpu.is_overheating:
            decision = Decision.DEGRADE
            reasons.append(f"GPU overheating: {gpu.temperature_c}°C")

        if analysis["memory_pressure"] == "high":
            if decision == Decision.ALLOW:
                decision = Decision.DEGRADE
            reasons.append("Memory pressure high")

        if analysis["gpu_pressure"] == "critical":
            decision = Decision.DEGRADE
            reasons.append("GPU pressure critical")

        # ── Mode-specific constraints ──
        mode = analysis["mode"]
        llm_calls = analysis.get("estimated_llm_calls", 1)

        if mode == "SWARM" and analysis["gpu_pressure"] in ("high", "critical"):
            decision = Decision.DEGRADE
            reasons.append("SWARM denied: GPU pressure")

        if mode == "SINGLE" and llm_calls > self.MAX_LLM_CALLS_SINGLE:
            reasons.append(f"SINGLE: exceeds max LLM calls ({llm_calls} > {self.MAX_LLM_CALLS_SINGLE})")

        if mode == "DEVOPS" and llm_calls > self.MAX_LLM_CALLS_DEVOPS:
            reasons.append(f"DEVOPS: exceeds LLM budget ({llm_calls} > {self.MAX_LLM_CALLS_DEVOPS})")

        # ── Tool-only: always allowed ──
        if mode == "TOOL":
            decision = Decision.ALLOW
            reasons.append("TOOL mode: no LLM required")

        return decision, reasons if reasons else ["allowed"]


# ─────────────────────────────────────────
# Semantic Router (LLM-based)
# ─────────────────────────────────────────

class SemanticRouter:
    """
    LLM-based task classification into ExecutionMode.
    Falls back to keyword heuristic if Ollama unavailable.
    """

    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

    SYSTEM_PROMPT = """You are a task classifier for TAAR v2.1 AI OS.
Classify the incoming task into ONE of these modes:

SINGLE — Single LangGraph agent, deterministic loop, 1 LLM instance
  Use for: creative tasks, planning, reasoning, analysis, multi-step tasks

SWARM — Parallel task decomposition, multiple workers, NO parallel LLM inference
  Use for: "analyze all", "find all", "search all", "scan", "review all", parallel pipelines

DEVOPS — CI/CD repair loop, max 2-4 LLM calls, tools-first
  Use for: "ci failed", "github actions", "pytest error", "ruff error", "build failed",
           "module not found", "pip install", "import error"

TOOL — No LLM, only system tools (fs, git, shell, file editing)
  Use for: read file, write file, git commit, git push, run command, file search

Respond ONLY with valid JSON:
{
  "mode": "SINGLE | SWARM | DEVOPS | TOOL",
  "confidence": 0.0-1.0,
  "gpu_pressure": "low | medium | high",
  "memory_pressure": "low | medium | high",
  "reason": "1-sentence explanation",
  "estimated_llm_calls": 1-50,
  "estimated_vram_mb": 0-12000,
  "is_devops": true/false,
  "is_stateless": true/false
}"""

    def __init__(self, gpu_layer: GPUControlLayer | None = None):
        self.gpu = gpu_layer or GPUControlLayer()

    def classify(self, task: str) -> TaskAnalysis:
        """Classify task. Falls back to keyword routing if LLM unavailable."""
        try:
            return self._llm_classify(task)
        except Exception:
            return self._fallback_classify(task)

    def _llm_classify(self, task: str) -> TaskAnalysis:
        """Use Ollama LLM for classification."""
        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ],
            "stream": False,
            "format": "json",
        }
        resp = requests.post(f"{self.OLLAMA_URL}/api/chat", json=payload, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        content = raw["message"]["content"]

        # Parse JSON
        if isinstance(content, str):
            data = json.loads(content)
        else:
            data = content

        return TaskAnalysis(
            mode=data["mode"],
            confidence=float(data["confidence"]),
            gpu_pressure=data["gpu_pressure"],
            memory_pressure=data["memory_pressure"],
            reason=data["reason"],
            estimated_llm_calls=int(data["estimated_llm_calls"]),
            estimated_vram_mb=int(data["estimated_vram_mb"]),
            is_devops=bool(data["is_devops"]),
            is_stateless=bool(data["is_stateless"]),
        )

    def _fallback_classify(self, task: str) -> TaskAnalysis:
        """Deterministic keyword-based fallback when LLM unavailable."""
        task_lower = task.lower()
        devops_kw = ["ci ", "failed", "github actions", "pytest", "ruff", "error",
                     "module", "not found", "import", "build", "pip ", "install",
                     "syntaxerror", "traceback"]
        swarm_kw = ["parallel", "swarm", "concurrent", "analyze all", "find all",
                    "search all", "scan", "audit", "review all", "grep", "batch"]
        tool_kw = ["read file", "write file", "git commit", "git push", "run command",
                   "search ", "list "]
        single_kw = ["analyze", "plan", "design", "explain", "generate", "create",
                     "build", "implement", "solve", "write code"]

        devops = sum(1 for kw in devops_kw if kw in task_lower)
        swarm = sum(1 for kw in swarm_kw if kw in task_lower)
        tools = sum(1 for kw in tool_kw if kw in task_lower)

        if devops >= 2 or "ci " in task_lower or "pytest" in task_lower or "ruff" in task_lower:
            mode = "DEVOPS"
        elif swarm >= 2:
            mode = "SWARM"
        elif tools >= 2:
            mode = "TOOL"
        elif any(kw in task_lower for kw in ["analyze all", "find all", "search all", "scan"]):
            mode = "SWARM"
        elif any(kw in task_lower for kw in tool_kw):
            mode = "TOOL"
        else:
            mode = "SINGLE"

        gpu_pressure = "low"
        if self.gpu:
            status = self.gpu.get_status()
            gpu_pressure = status.pressure_level()

        return TaskAnalysis(
            mode=mode,
            confidence=0.6,
            gpu_pressure=gpu_pressure,
            memory_pressure="low",
            reason=f"fallback keyword: {mode}",
            estimated_llm_calls=10 if mode == "DEVOPS" else 20,
            estimated_vram_mb=0,
            is_devops=(mode == "DEVOPS"),
            is_stateless=False,
        )


# ─────────────────────────────────────────
# Control Plane v2.1
# ─────────────────────────────────────────

class ControlPlane:
    """
    ATOM OS Orchestration Layer.

    TASK → Semantic Router → Policy Engine → Resource Manager → ExecutionPlan

    Responsibilities:
      - LLM-based (or fallback) task routing
      - Deterministic policy evaluation
      - GPU-aware resource management
      - Tiered memory control
      - Mode selection with automatic degradation
      - LLM call budgeting
    """

    def __init__(
        self,
        gpu_threshold_vram_pct: int = 85,
        gpu_threshold_temp_c: int = 83,
        max_llm_budget: int = 50,
        ollama_url: str | None = None,
        ollama_model: str | None = None,
    ):
        if ollama_url:
            os.environ["OLLAMA_URL"] = ollama_url
        if ollama_model:
            os.environ["OLLAMA_MODEL"] = ollama_model

        self.gpu = GPUControlLayer(
            vram_threshold_pct=gpu_threshold_vram_pct,
            temp_threshold_c=gpu_threshold_temp_c,
        )
        self.memory = MemoryHierarchy(
            vram_free_mb_fn=lambda: self.gpu.get_status().vram_free_mb,
        )
        self.router = SemanticRouter(gpu_layer=self.gpu)
        self.policy = PolicyEngine()

        self.max_llm_budget = max_llm_budget
        self._last_plan: ExecutionPlan | None = None
        self._session_stats = {"llm_calls": 0, "total_time_ms": 0}

    # ── Core Route ─────────────────────────

    def route(self, task: str) -> ExecutionPlan:
        """
        Main entry point. Returns an ExecutionPlan.

        Pipeline:
          1. Classify task (LLM or fallback)
          2. Check resources (GPU + Memory)
          3. Evaluate policy
          4. Build execution plan with degradation if needed
        """
        start = time.time()

        # Step 1: Task analysis (LLM-based or keyword fallback)
        analysis = self.router.classify(task)

        # Step 2: Resource status
        gpu_status = self.gpu.get_status()
        mem_status = self.memory.stats()

        # Step 3: Policy evaluation
        decision, policy_reasons = self.policy.evaluate(analysis, gpu_status, mem_status)

        # Step 4: Build execution plan
        plan = self._build_plan(analysis, gpu_status, mem_status, decision, policy_reasons)

        # Step 5: Auto-degrade if GPU pressure
        if plan.policy_decision == Decision.DEGRADE:
            plan = self._apply_degradation(plan, analysis, gpu_status)

        plan.mode = ExecutionMode(plan.mode.value)
        self._last_plan = plan
        self._session_stats["total_time_ms"] += (time.time() - start) * 1000

        return plan

    def _build_plan(
        self,
        analysis: TaskAnalysis,
        gpu_status: GPUStatus,
        mem_status: Any,
        decision: Decision,
        policy_reasons: list[str],
    ) -> ExecutionPlan:
        mode = ExecutionMode(analysis["mode"])

        # GPU resource check
        if mode == ExecutionMode.SWARM:
            can_swarm, _ = self.gpu.can_run_swarm()
            gpu_allowed = can_swarm
        elif mode in (ExecutionMode.SINGLE, ExecutionMode.DEVOPS):
            can_llm, _ = self.gpu.can_run_llm()
            gpu_allowed = can_llm
        else:
            gpu_allowed = True

        # Memory check
        mem_ok = mem_status.pressure in ("low", "medium")

        # Budget scaling
        llm_budget = min(analysis["estimated_llm_calls"], self.max_llm_budget)
        budget_factor = min(1.0, llm_budget / max(1, self.max_llm_budget))

        # Iteration limits by mode
        max_iters = {
            ExecutionMode.SINGLE: 30,
            ExecutionMode.SWARM: 20,
            ExecutionMode.DEVOPS: 8,
            ExecutionMode.TOOL: 1,
        }.get(ExecutionMode(mode), 20)

        return ExecutionPlan(
            mode=ExecutionMode(mode),
            mode_confidence=analysis["confidence"],
            gpu_allowed=gpu_allowed,
            memory_allowed=mem_ok,
            policy_decision=decision,
            policy_reasons=policy_reasons,
            max_iterations=max_iters,
            budget_factor=budget_factor,
            execution_hints={
                "gpu_pressure": analysis["gpu_pressure"],
                "memory_pressure": analysis["memory_pressure"],
                "estimated_vram_mb": analysis["estimated_vram_mb"],
                "is_devops": analysis["is_devops"],
                "is_stateless": analysis["is_stateless"],
            },
            suggested_downgrade=None,
        )

    def _apply_degradation(
        self,
        plan: ExecutionPlan,
        analysis: TaskAnalysis,
        gpu_status: GPUStatus,
    ) -> ExecutionPlan:
        """Downgrade execution mode based on resource pressure."""
        original_mode = plan.mode

        # Try automatic downgrade via GPU layer
        suggested = self.gpu.suggest_downgrade(plan.mode.value)
        if suggested:
            plan.mode = ExecutionMode(suggested)
            plan.policy_reasons.append(f"Degraded: {original_mode} → {suggested}")

        # If already at TOOL, deny
        elif plan.mode == ExecutionMode.TOOL:
            plan.policy_decision = Decision.DENY
            plan.policy_reasons.append("Denied: resources exhausted")

        # Fallback: SINGLE → TOOL if LLM unavailable
        elif plan.mode == ExecutionMode.SINGLE and not self.gpu.can_run_llm()[0]:
            plan.mode = ExecutionMode.TOOL
            plan.policy_reasons.append("Degraded: SINGLE → TOOL (GPU unavailable)")

        plan.suggested_downgrade = plan.mode.value
        return plan

    # ── Budget Management ──────────────────

    def record_llm_call(self):
        """Track LLM usage for budgeting."""
        self._session_stats["llm_calls"] += 1

    def budget_remaining(self) -> int:
        return max(0, self.max_llm_budget - self._session_stats["llm_calls"])

    def budget_exhausted(self) -> bool:
        return self.budget_remaining() <= 0

    # ── Status ─────────────────────────────

    def status(self) -> dict:
        """Full system snapshot."""
        gpu_m = self.gpu.monitor()
        mem_m = self.memory.stats()

        return {
            "session": self._session_stats.copy(),
            "budget_remaining": self.budget_remaining(),
            "gpu": gpu_m,
            "memory": {
                "ram_used_mb": mem_m.ram_used_mb,
                "nvme_cached_mb": mem_m.nvme_cached_mb,
                "pressure": mem_m.pressure,
            },
            "last_plan": {
                "mode": self._last_plan.mode.value if self._last_plan else None,
                "policy": self._last_plan.policy_decision.value if self._last_plan else None,
                "reasons": self._last_plan.policy_reasons if self._last_plan else [],
            } if self._last_plan else None,
        }
