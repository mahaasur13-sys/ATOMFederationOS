"""
TAAR v10.1 — Execution Proof Engine
Every action: plan → simulate → diff → approve → execute → verify

The core principle: AI proposes, the engine proves safety.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum
import hashlib
import time
import uuid


class ProofStatus(Enum):
    PENDING = "pending"
    SIMULATED = "simulated"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    VERIFIED = "verified"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ActionCategory(Enum):
    READ = "read"           # Safe: read-only observation
    WRITE = "write"         # Moderate risk: changes state
    DEPLOY = "deploy"       # High risk: affects running systems
    DESTROY = "destroy"     # Critical: permanent or hard to reverse
    EXTERNAL = "external"    # Critical: affects outside world


@dataclass
class ExecutionProof:
    proof_id: str
    action_id: str
    category: ActionCategory
    plan: dict                      # What AI proposes to do
    simulation_result: Optional[dict] = None
    diff: Optional[dict] = None     # What changes between before/after
    approval: Optional[dict] = None  # Who/what approved
    verification: Optional[dict] = None  # Post-execution proof
    status: ProofStatus = ProofStatus.PENDING
    created_at: float = field(default_factory=time.time)
    approved_at: Optional[float] = None
    executed_at: Optional[float] = None
    rollback_of: Optional[str] = None  # proof_id this was rolled back for


class ExecutionProofEngine:
    """
    The Execution Proof Engine is the SOLE authority for executing actions.
    No action reaches real infrastructure without passing through here.

    Pipeline per action:
        1. PLAN       — AI submits intended action + rationale
        2. CATEGORIZE — Engine classifies risk category
        3. SIMULATE   — Run action in sandbox, capture before/after diff
        4. DIFF       — Generate human-readable diff of changes
        5. APPROVE    — Policy kernel reviews simulation; approves or rejects
        6. EXECUTE    — If approved, execute for real
        7. VERIFY     — Confirm actual state matches expected post-action state
        8. AUDIT      — Record hashed proof in immutable audit graph
    """

    def __init__(self, simulation_only: bool = True):
        self.simulation_only = simulation_only
        self.proofs: dict[str, ExecutionProof] = {}
        self.simulation_count = 0
        self.approval_rate = 0.0
        self._total_evaluated = 0

    def submit_plan(self, action_id: str, plan: dict, category_hint: str = "write") -> ExecutionProof:
        """Step 1: AI submits action plan."""
        proof_id = f"PRF-{uuid.uuid4().hex[:12]}"
        category = ActionCategory(category_hint) if isinstance(category_hint, str) else category_hint

        proof = ExecutionProof(
            proof_id=proof_id,
            action_id=action_id,
            category=category,
            plan=plan,
        )
        self.proofs[proof_id] = proof
        return proof

    def simulate(self, proof: ExecutionProof, before_state: dict) -> dict:
        """
        Step 3: Run simulation in sandbox.
        Returns: simulation_result + diff.
        """
        self.simulation_count += 1
        proof.status = ProofStatus.SIMULATED

        # Build expected after-state based on plan
        after_state = self._compute_after_state(before_state, proof.plan)

        # Generate diff
        diff = self._compute_diff(before_state, after_state, proof.category)

        proof.simulation_result = {
            "before_state": before_state,
            "after_state": after_state,
            "diff": diff,
            "simulation_id": f"SIM-{uuid.uuid4().hex[:8]}",
            "simulated_at": time.time(),
            "sandbox": "taar_sandbox_v1",
        }
        proof.diff = diff

        return proof.simulation_result

    def _compute_after_state(self, before: dict, plan: dict) -> dict:
        """Predict after-state based on action type and plan."""
        after = dict(before)
        action_type = plan.get("action_type", "unknown")

        if action_type == "scale":
            delta = plan.get("delta_nodes", 0)
            after["nodes"] = after.get("nodes", 0) + delta
            after["cpu_total"] = after.get("cpu_total", 0) + delta * 8
            after["ram_gb"] = after.get("ram_gb", 0) + delta * 16

        elif action_type == "deploy":
            svc = plan.get("service_name", "unknown")
            replicas = plan.get("replicas", 1)
            current_svcs = after.get("services", [])
            after["services"] = current_svcs + [f"{svc}-v{replicas}"]
            after["deployments"] = after.get("deployments", 0) + 1

        elif action_type == "config_change":
            for key, value in plan.get("changes", {}).items():
                after[key] = value

        elif action_type == "delete":
            target = plan.get("target", "")
            if "nodes" in target:
                after["nodes"] = max(0, after.get("nodes", 1) - 1)
            elif "service" in target:
                svc = plan.get("service_name", "")
                after["services"] = [s for s in after.get("services", []) if svc not in s]

        return after

    def _compute_diff(self, before: dict, after: dict, category: ActionCategory) -> dict:
        """Generate diff between before and after states."""
        added = {k: after[k] for k in after if k not in before}
        removed = {k: before[k] for k in before if k not in after}
        changed = {}

        for k in set(before) & set(after):
            if before[k] != after[k]:
                changed[k] = {"from": before[k], "to": after[k]}

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "risk_score": self._risk_score(category, added, removed, changed),
        }

    def _risk_score(self, category: ActionCategory, added: dict, removed: dict, changed: dict) -> float:
        """Compute 0.0-1.0 risk score for the diff."""
        scores = {
            ActionCategory.READ: 0.0,
            ActionCategory.WRITE: 0.2,
            ActionCategory.DEPLOY: 0.5,
            ActionCategory.EXTERNAL: 0.8,
            ActionCategory.DESTROY: 1.0,
        }
        base = scores.get(category, 0.5)

        # Increase for destructive changes
        if removed or any("delete" in str(v) for v in changed.values()):
            base = min(1.0, base + 0.3)

        return base

    def approve(self, proof: ExecutionProof) -> bool:
        """
        Step 5: Policy kernel approval.
        Returns True if approved, False if rejected.
        """
        self._total_evaluated += 1

        if proof.status != ProofStatus.SIMULATED:
            return False

        risk = proof.diff["risk_score"] if proof.diff else 0.0
        approved = risk < 0.85  # Hard block at 0.85+

        if approved:
            proof.status = ProofStatus.APPROVED
            proof.approved_at = time.time()
            proof.approval = {
                "approved_by": "policy_kernel_v1",
                "risk_score": risk,
                "conditions": [] if risk < 0.3 else ["monitor_post_execution"],
            }
        else:
            proof.status = ProofStatus.REJECTED
            proof.approval = {
                "rejected_by": "policy_kernel_v1",
                "risk_score": risk,
                "reason": f"risk_score {risk:.2f} exceeds threshold 0.85",
            }

        # Update rolling approval rate
        self.approval_rate = (self.approval_rate * (self._total_evaluated - 1) + (1 if approved else 0)) / self._total_evaluated

        return approved

    def execute(self, proof: ExecutionProof) -> dict:
        """
        Step 6: Execute approved action.
        In simulation_only mode, marks as simulated-executed.
        """
        if proof.status != ProofStatus.APPROVED:
            return {"status": "rejected", "reason": f"not approved, status={proof.status.value}"}

        if self.simulation_only:
            # Simulate execution outcome
            proof.status = ProofStatus.EXECUTED
            proof.executed_at = time.time()
            result = {
                "status": "simulated_execution",
                "proof_id": proof.proof_id,
                "message": "Simulation mode: no real infrastructure changed",
            }
        else:
            # Real execution would call RealityActionEngine here
            proof.status = ProofStatus.EXECUTED
            proof.executed_at = time.time()
            result = {"status": "executed", "proof_id": proof.proof_id}

        return result

    def verify(self, proof: ExecutionProof, actual_state: dict) -> bool:
        """
        Step 7: Verify post-execution state matches expected.
        """
        if proof.status != ProofStatus.EXECUTED:
            return False

        expected = proof.simulation_result["after_state"]
        mismatches = []

        for key in expected:
            if key not in actual_state or actual_state[key] != expected[key]:
                mismatches.append(key)

        verified = len(mismatches) == 0

        proof.verification = {
            "verified": verified,
            "mismatches": mismatches,
            "expected": expected,
            "actual": actual_state,
            "verified_at": time.time(),
        }

        if verified:
            proof.status = ProofStatus.VERIFIED

        return verified

    def audit_hash(self, proof: ExecutionProof) -> str:
        """
        Step 8: Generate immutable audit hash.
        Every field that matters is included in the hash.
        """
        payload = (
            f"{proof.proof_id}"
            f"{proof.action_id}"
            f"{proof.category.value}"
            f"{proof.plan}"
            f"{proof.simulation_result or {}}"
            f"{proof.approval or {}}"
            f"{proof.status.value}"
            f"{proof.created_at}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get_proof(self, proof_id: str) -> Optional[ExecutionProof]:
        return self.proofs.get(proof_id)

    def get_audit_trail(self) -> list[dict]:
        """Return full audit trail for replay/debugging."""
        return sorted(self.proofs.values(), key=lambda p: p.created_at)

    def get_stats(self) -> dict:
        return {
            "total_proofs": len(self.proofs),
            "simulation_count": self.simulation_count,
            "approval_rate": round(self.approval_rate, 3),
            "by_status": {
                s.value: sum(1 for p in self.proofs.values() if p.status == s)
                for s in ProofStatus
            },
            "by_category": {
                c.value: sum(1 for p in self.proofs.values() if p.category == c)
                for c in ActionCategory
            },
        }


# ── Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    epe = ExecutionProofEngine(simulation_only=True)

    # Simulate a deploy action
    proof = epe.submit_plan(
        action_id="ACT-001",
        plan={
            "action_type": "deploy",
            "service_name": "ai-econ-engine",
            "replicas": 2,
            "image": "v2.1.0",
        },
        category_hint="deploy",
    )
    print(f"[PROOF] {proof.proof_id} | category={proof.category.value}")

    before = {"nodes": 3, "cpu_total": 24, "ram_gb": 48, "services": ["svc-v1"]}
    sim = epe.simulate(proof, before)
    print(f"[SIM]   risk={sim['diff']['risk_score']:.2f}")

    approved = epe.approve(proof)
    print(f"[APPROVE] {'✅ approved' if approved else '❌ rejected'} | "
          f"reason={proof.approval.get('reason', 'ok')}")

    if approved:
        result = epe.execute(proof)
        print(f"[EXEC]  {result['status']}")

        verified = epe.verify(proof, after := sim["after_state"])
        print(f"[VERIFY] {'✅ verified' if verified else '❌ mismatch'}")

    audit_hash = epe.audit_hash(proof)
    print(f"[AUDIT] sha256={audit_hash[:16]}...")
    print(f"\nStats: {epe.get_stats()}")
