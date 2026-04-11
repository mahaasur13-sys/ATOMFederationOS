"""
TAAR v13 — Autonomous AI Corporation OS (AIC-OS)
INTAKE → STRATEGY → ORGANIZE → ALLOCATE → EXECUTE → VERIFY → REPORT → OPTIMIZE → EVOLVE

CEO = Control Plane (from v11)
Board = Governance (Layer 5)
Org = Registry + Allocator (Layers 1, 3)
Budget = BudgetController (Layer 3)
ROI = ROITracker (Layer 6)
"""
from __future__ import annotations
import uuid, time
from dataclasses import dataclass, field

# ── Layer imports ──────────────────────────────────────────────
from corp_governance_board import GovernanceBoard, RiskLevel, VoteVerdict
from corp_org_registry import OrgRegistry, AIEmployee, AgentTier
from corp_role_allocator import RoleAllocator
from corp_budget_controller import BudgetController, BudgetCategory
from corp_roi_tracker import ROITracker, PerformanceRating

@dataclass
class CorpTask:
    id: str
    description: str
    task_type: str
    required_skills: list[str]
    risk: RiskLevel
    budget_cost: float
    expected_value: float
    deadline: float
    department: str = ""
    assigned_to: str = ""
    roi: float = 0.0
    status: str = "intake"
    created_at: float = field(default_factory=time.time)

@dataclass
class CorpCycle:
    cycle_id: str
    intake: list[CorpTask]
    strategy: list[str]
    allocated: list[CorpTask]
    executed: list[CorpTask]
    verified: list[CorpTask]
    total_cost: float = 0.0
    total_value: float = 0.0
    duration_ms: float = 0.0

class AICorporationOS:
    def __init__(self):
        self.board = GovernanceBoard()
        self.org = OrgRegistry()
        self.allocator = RoleAllocator(self.org)
        self.budget = BudgetController()
        self.roi = ROITracker()
        self.cycles: list[CorpCycle] = []
        self.pending_tasks: list[CorpTask] = []

    # ── INTAKE ─────────────────────────────────────────────────
    def intake(self, tasks: list[str]) -> list[CorpTask]:
        corp_tasks = []
        for t in tasks:
            ct = CorpTask(
                id=f"T-{len(self.pending_tasks)+1:04d}",
                description=t,
                task_type=self._classify_task(t),
                required_skills=self._extract_skills(t),
                risk=self._assess_risk(t),
                budget_cost=self._estimate_cost(t),
                expected_value=self._estimate_value(t),
                deadline=time.time() + 3600
            )
            corp_tasks.append(ct)
            self.pending_tasks.append(ct)
        return corp_tasks

    def _classify_task(self, t: str) -> str:
        t_lower = t.lower()
        if any(k in t_lower for k in ["ci fail", "ruff", "pytest", "build", "pipeline"]):
            return "ci_agent"
        if any(k in t_lower for k in ["deploy", "docker", "k8s", "infra"]):
            return "deployment"
        if any(k in t_lower for k in ["write code", "generate", "implement", "create"]):
            return "code_generation"
        if any(k in t_lower for k in ["patch", "fix", "bug", "error"]):
            return "patch_generation"
        if any(k in t_lower for k in ["test", "qa", "validate"]):
            return "test_generation"
        if any(k in t_lower for k in ["security", "audit", "scan", "threat"]):
            return "threat_detector"
        if any(k in t_lower for k in ["research", "analyze", "strategy", "explore"]):
            return "exploration"
        return "general"

    def _extract_skills(self, t: str) -> list[str]:
        t_lower = t.lower()
        skills = []
        mapping = {
            "ci_agent": ["ci_cd", "github_actions", "pytest", "ruff"],
            "deployment": ["docker", "k8s", "terraform", "deploy"],
            "code_generation": ["python", "typescript", "code"],
            "patch_generation": ["debugging", "ruff", "pytest", "patch"],
            "test_generation": ["pytest", "coverage", "validation"],
            "threat_detector": ["security", "policy", "audit"],
            "exploration": ["research", "analysis", "strategy"],
        }
        for k, v in mapping.items():
            if k in t_lower:
                skills.extend(v)
        return list(set(skills)) or ["general"]

    def _assess_risk(self, t: str) -> RiskLevel:
        t_lower = t.lower()
        if any(k in t_lower for k in ["delete", "drop", "rm -rf", "destroy", "truncate"]):
            return RiskLevel.CRITICAL
        if any(k in t_lower for k in ["deploy", "production", "migration", "pipeline"]):
            return RiskLevel.HIGH
        if any(k in t_lower for k in ["write", "create", "modify", "patch"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _estimate_cost(self, t: str) -> float:
        t_lower = t.lower()
        if "ci" in t_lower or "build" in t_lower:
            return 0.5
        if "deploy" in t_lower:
            return 2.0
        if "write code" in t_lower or "implement" in t_lower:
            return 3.0
        return 1.0

    def _estimate_value(self, t: str) -> float:
        t_lower = t.lower()
        if "ci" in t_lower or "ruff" in t_lower:
            return 10.0
        if "deploy" in t_lower:
            return 8.0
        if "write code" in t_lower or "implement" in t_lower:
            return 15.0
        return 5.0

    # ── STRATEGY ────────────────────────────────────────────────
    def strategy_phase(self, tasks: list[CorpTask]) -> list[str]:
        decisions = []
        for t in tasks:
            roi_est = t.expected_value / max(0.01, t.budget_cost)
            t.roi = roi_est
            decisions.append(f"{t.id}: {t.task_type} (ROI={roi_est:.1f}x, risk={t.risk.value})")
        return decisions

    # ── ORGANIZE ───────────────────────────────────────────────
    def organize(self, tasks: list[CorpTask]) -> list[CorpTask]:
        for t in tasks:
            assignment = self.allocator.allocate(
                t.id, t.task_type, t.required_skills, t.budget_cost
            )
            t.assigned_to = assignment.employee.eid if assignment.employee else "unassigned"
            t.department = assignment.department
            t.status = "organized"
        return tasks

    # ── ALLOCATE ───────────────────────────────────────────────
    def allocate_budget(self, tasks: list[CorpTask]) -> dict:
        approved = []
        for t in tasks:
            # Submit to governance board
            pid = self.board.submit(
                topic=t.description[:80], action_plan={"task_id": t.id, "type": t.task_type},
                risk=t.risk, budget_cost=t.budget_cost, expected_roi=t.roi,
                proposer=t.assigned_to or "CEO"
            )
            decision = self.board.vote(pid)
            if decision in (VoteVerdict.APPROVED, VoteVerdict.OVERRIDE):
                if self.budget.can_afford(BudgetCategory.LLM_CALLS, t.budget_cost):
                    self.budget.request(BudgetCategory.LLM_CALLS, t.budget_cost, t.department)
                    t.status = "allocated"
                    approved.append(t)
                else:
                    t.status = "budget_denied"
            else:
                t.status = "board_denied"
        return {"approved": approved, "denied": [t for t in tasks if t not in approved]}

    # ── EXECUTE ────────────────────────────────────────────────
    def execute(self, tasks: list[CorpTask]) -> list[CorpTask]:
        executed = []
        for t in tasks:
            employee = self.org.employees.get(t.assigned_to)
            start = time.time()
            # Simulate execution
            success = t.status == "allocated" and t.risk != RiskLevel.CRITICAL
            duration = (time.time() - start) * 1000
            if success:
                self.roi.record(t.id, t.assigned_to, t.department,
                              cost=t.budget_cost, value=t.expected_value,
                              duration_ms=duration, quality_score=0.85)
                t.status = "executed"
            else:
                t.status = "execution_failed"
            executed.append(t)
        return executed

    # ── VERIFY ─────────────────────────────────────────────────
    def verify(self, tasks: list[CorpTask]) -> list[CorpTask]:
        verified = []
        for t in tasks:
            outcome = self.roi.corp_roi()
            t.status = "verified"
            verified.append(t)
        return verified

    # ── EVOLVE ────────────────────────────────────────────────
    def evolve(self) -> dict:
        org_before = self.org.org_chart()
        changes = {}
        # Promote high performers
        for eid in self.roi.promote_candidates():
            result = self.org.restructure({"promote": {"eid": eid}})
            changes.update(result)
        # Fire low performers
        for eid in self.roi.fire_candidates():
            result = self.org.restructure({"fire": {"eid": eid}})
            changes.update(result)
        org_after = self.org.org_chart()
        return {"changes": changes, "org_before": org_before, "org_after": org_after}

    # ── MAIN CYCLE ─────────────────────────────────────────────
    def run_cycle(self, task_descriptions: list[str]) -> CorpCycle:
        cycle_id = f"CYCLE-{len(self.cycles)+1:04d}"
        start = time.time()
        print(f"\n{'='*60}")
        print(f"🏢 AIC-OS CYCLE: {cycle_id}")
        print(f"{'='*60}")
        # INTAKE
        print(f"\n[INTAKE] {len(task_descriptions)} tasks received")
        tasks = self.intake(task_descriptions)
        for t in tasks:
            print(f"  {t.id}: {t.task_type} | risk={t.risk.value} | cost=${t.budget_cost} | expected=${t.expected_value}")
        # STRATEGY
        print(f"\n[STRATEGY]")
        decisions = self.strategy_phase(tasks)
        for d in decisions:
            print(f"  {d}")
        # ORGANIZE
        print(f"\n[ORGANIZE]")
        tasks = self.organize(tasks)
        for t in tasks:
            emp = self.org.employees.get(t.assigned_to)
            print(f"  {t.id} → {emp.name if emp else 'unassigned'} ({t.department})")
        # ALLOCATE
        print(f"\n[ALLOCATE] Budget check + Board approval")
        alloc_result = self.allocate_budget(tasks)
        for t in alloc_result["approved"]:
            print(f"  ✅ {t.id} approved (${t.budget_cost})")
        for t in alloc_result["denied"]:
            print(f"  ❌ {t.id} denied: {t.status}")
        # EXECUTE
        print(f"\n[EXECUTE]")
        tasks = self.execute(alloc_result["approved"])
        for t in tasks:
            print(f"  → {t.id}: {t.status}")
        # VERIFY
        print(f"\n[VERIFY]")
        tasks = self.verify(tasks)
        roi_report = self.roi.corp_roi()
        print(f"  Corp ROI: {roi_report['corp_roi']:.2f}x | rating={roi_report['rating'].value}")
        # EVOLVE
        print(f"\n[EVOLVE]")
        evo = self.evolve()
        for eid, action in evo["changes"].items():
            print(f"  {eid}: {action}")
        if not evo["changes"]:
            print("  (no org changes needed)")
        duration_ms = (time.time() - start) * 1000
        cycle = CorpCycle(
            cycle_id=cycle_id,
            intake=list(tasks),
            strategy=decisions,
            allocated=alloc_result["approved"],
            executed=[t for t in tasks if t.status == "executed"],
            verified=tasks,
            total_cost=sum(t.budget_cost for t in tasks),
            total_value=sum(t.expected_value for t in tasks),
            duration_ms=duration_ms
        )
        self.cycles.append(cycle)
        print(f"\n[SUMMARY] cost=${cycle.total_cost:.1f} | value=${cycle.total_value:.1f} | ROI={cycle.total_value/max(0.01,cycle.total_cost):.2f}x | {duration_ms:.1f}ms")
        return cycle

    def get_corp_status(self) -> dict:
        roi_report = self.roi.corp_roi()
        return {
            "cycles": len(self.cycles),
            "total_tasks": sum(len(c.intake) for c in self.cycles),
            "corp_roi": roi_report["corp_roi"],
            "corp_rating": roi_report["rating"].value,
            "employees": len([e for e in self.org.employees.values() if e.status.value != "offline"]),
            "departments": len(self.org.departments),
            "budget_util": self.budget.get_report()["total_util"],
            "board_stats": self.board.get_report(),
        }

if __name__ == "__main__":
    aic = AICorporationOS()
    # ── Test cases ────────────────────────────────────────────
    test_tasks = [
        "ci failed: ruff F401 agents/tools_adapter.py",
        "build and test all modules",
        "deploy new service to production",
        "write unit tests for agents/orchestrator.py",
        "security audit on codebase",
        "research: compare LangGraph vs CrewAI",
        "delete all log files in workspace",
    ]
    cycle = aic.run_cycle(test_tasks)
    print(f"\n{'='*60}")
    print("🏢 AIC-OS STATUS:")
    print(f"{'='*60}")
    status = aic.get_corp_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
