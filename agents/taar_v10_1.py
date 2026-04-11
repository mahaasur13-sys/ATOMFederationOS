"""
TAAR v10.1 — Policy + Proof Execution Layer (PEL)
Hard safety envelope over AI decisions.

Three non-negotiable components:
    1. ExecutionProofEngine  — plan → simulate → diff → approve → execute → verify
    2. PolicyKernel         — HARD BLOCK/VETO over unsafe actions
    3. ImmutableAuditGraph  — append-only, hash-chained, replayable

The principle: AI proposes, the engine proves, the kernel enforces,
the audit remembers.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import time
import uuid

# ── Core components ─────────────────────────────────────────────────
from execution_proof_engine import (
    ExecutionProofEngine, ExecutionProof, ProofStatus,
    ActionCategory, ActionCategory,
)
from policy_kernel import PolicyKernel, PolicyVerdict
from immutable_audit_graph import ImmutableAuditGraph, AuditNode


@dataclass
class PELResult:
    """Result of one PEL cycle."""
    proof_id: str
    action_id: str
    category: str
    policy_verdict: str
    proof_status: str
    executed: bool
    audit_hash: str
    blocked_reason: Optional[str]
    cycle_ms: float


class PolicyExecutionLayer:
    """
    TAAR v10.1 — Policy Execution Layer (PEL).

    This is the HARD SAFETY ENVELOPE placed OVER the AI's ability to
    take real-world actions. It is NOT part of the AI's reasoning loop —
    it is a GATE that stands between decision and action.

    Pipeline per action:
        AI decision
            ↓
        [1] PROOF ENGINE:  submit_plan() → simulate() → diff
            ↓
        [2] POLICY KERNEL: evaluate(proof, system_state) → BLOCK/VETO/ALLOW
            ↓
        [3] IF ALLOWED:    execute() → verify()
            ↓
        [4] AUDIT GRAPH:   add_node() → hash chain
            ↓
        Real infrastructure OR blocked

    Key invariant:
        - No action reaches infrastructure without going through ALL 4 steps
        - BLOCK/VETO verdicts are logged but NOT executed
        - The audit graph is the only source of truth for what happened
    """

    def __init__(self, simulation_mode: bool = True):
        # ── Core engines ────────────────────────────────────────────
        self.proof_engine = ExecutionProofEngine(simulation_only=simulation_mode)
        self.policy_kernel = PolicyKernel()
        self.audit_graph = ImmutableAuditGraph()

        # ── State ───────────────────────────────────────────────────
        self.simulation_mode = simulation_mode
        self.cycle_count = 0
        self.total_blocked = 0
        self.total_executed = 0

    # ── Main pipeline ────────────────────────────────────────────────

    def process_action(self, action_plan: dict, system_state: dict) -> PELResult:
        """
        Process a single AI action through the full PEL pipeline.

        This is the ONLY public method for taking actions.
        All other modules go through this.
        """
        cycle_start = time.time()
        action_id = action_plan.get("action_id", f"ACT-{uuid.uuid4().hex[:8]}")
        category_str = action_plan.get("category", "write")
        category = ActionCategory(category_str)

        # ── Step 1: PROOF ENGINE ──────────────────────────────────
        proof = self.proof_engine.submit_plan(
            action_id=action_id,
            plan=action_plan,
            category_hint=category_str,
        )

        # ── Step 2: SIMULATE (if high-risk category) ──────────────
        if category in (ActionCategory.DEPLOY, ActionCategory.DESTROY, ActionCategory.EXTERNAL):
            # Get before state for simulation
            before_state = self._get_current_infra_state(system_state)
            self.proof_engine.simulate(proof, before_state)

        # ── Step 3: POLICY KERNEL EVALUATION ──────────────────────
        verdict, evaluations = self.policy_kernel.evaluate(action_plan, system_state)

        # Log policy evaluation in audit BEFORE deciding to execute
        self.audit_graph.add_node(
            action_id=action_id,
            node_type="policy_verdict",
            payload={
                "verdict": verdict.value,
                "evaluations": [
                    {"rule": e.rule_name, "passed": e.passed, "reason": e.reason}
                    for e in evaluations
                ],
                "risk_conditions": [
                    e.rule_name for e in evaluations if not e.passed
                ],
            },
            proof_id=proof.proof_id,
        )

        blocked_reason = None
        executed = False

        if verdict in (PolicyVerdict.VETO, PolicyVerdict.BLOCK):
            # ── BLOCKED: Log but do not execute ─────────────────
            blocked_reason = f"policy_{verdict.value}: {[e.rule_name for e in evaluations if not e.passed]}"
            self.total_blocked += 1

            # Record blocked action in audit
            self.audit_graph.add_node(
                action_id=action_id,
                node_type="action_blocked",
                payload={
                    "proof_id": proof.proof_id,
                    "verdict": verdict.value,
                    "reason": blocked_reason,
                    "plan": action_plan,
                },
                proof_id=proof.proof_id,
            )

            # Mark proof as rejected
            proof.status = ProofStatus.REJECTED

        else:
            # ── ALLOWED: Execute through proof engine ─────────────
            if proof.status != ProofStatus.SIMULATED:
                # Low-risk action: skip simulation, go straight to approval
                self.proof_engine.approve(proof)

            if proof.status == ProofStatus.APPROVED:
                exec_result = self.proof_engine.execute(proof)

                # Verify if we have after state
                if exec_result.get("status") in ("executed", "simulated_execution"):
                    after_state = self._get_current_infra_state(system_state)
                    verified = self.proof_engine.verify(proof, after_state)

                    self.audit_graph.add_node(
                        action_id=action_id,
                        node_type="action_executed",
                        payload={
                            "proof_id": proof.proof_id,
                            "status": exec_result["status"],
                            "verified": verified,
                            "plan": action_plan,
                            "after_state": after_state,
                        },
                        proof_id=proof.proof_id,
                    )

                    executed = True
                    self.total_executed += 1

        # ── Step 4: AUDIT HASH ─────────────────────────────────────
        audit_hash = self.audit_graph.add_node(
            action_id=action_id,
            node_type="audit_record",
            payload={
                "proof_id": proof.proof_id,
                "action_plan": action_plan,
                "verdict": verdict.value,
                "executed": executed,
                "blocked_reason": blocked_reason,
                "proof_status": proof.status.value,
            },
            proof_id=proof.proof_id,
        ).node_hash

        self.cycle_count += 1
        cycle_ms = (time.time() - cycle_start) * 1000

        return PELResult(
            proof_id=proof.proof_id,
            action_id=action_id,
            category=category.value,
            policy_verdict=verdict.value,
            proof_status=proof.status.value,
            executed=executed,
            audit_hash=audit_hash[:16] + "...",
            blocked_reason=blocked_reason,
            cycle_ms=cycle_ms,
        )

    def _get_current_infra_state(self, system_state: dict) -> dict:
        """Extract current infrastructure state for simulation."""
        return {
            "nodes": system_state.get("nodes", 1),
            "cpu_total": system_state.get("cpu_total", 8),
            "ram_gb": system_state.get("ram_gb", 16),
            "gpu_units": system_state.get("gpu_units", 0),
            "gpu_utilization": system_state.get("gpu_utilization", 0.0),
            "services": system_state.get("services", []),
        }

    # ── Batch processing ─────────────────────────────────────────────

    def process_batch(self, action_plans: list[dict], system_state: dict) -> list[PELResult]:
        """Process multiple actions through PEL pipeline."""
        return [self.process_action(plan, system_state) for plan in action_plans]

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return comprehensive PEL statistics."""
        return {
            "cycle_count": self.cycle_count,
            "total_executed": self.total_executed,
            "total_blocked": self.total_blocked,
            "execution_rate": (
                self.total_executed / self.cycle_count
                if self.cycle_count > 0 else 0.0
            ),
            "proof_engine": self.proof_engine.get_stats(),
            "policy_kernel": self.policy_kernel.get_stats(),
            "audit_graph": self.audit_graph.get_stats(),
            "simulation_mode": self.simulation_mode,
        }


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("🔐 TAAR v10.1 — Policy + Proof Execution Layer")
    print("=" * 70)

    pel = PolicyExecutionLayer(simulation_mode=True)

    # Test 1: Normal deploy action → should ALLOW
    print("\n[Test 1] Normal deploy action")
    result = pel.process_action(
        action_plan={
            "action_id": "ACT-DEPLOY-001",
            "action_type": "deploy",
            "service_name": "api-gateway",
            "replicas": 2,
            "image": "v2.1.0",
            "category": "deploy",
        },
        system_state={
            "nodes": 5, "cpu_total": 40, "ram_gb": 80,
            "gpu_units": 1.0, "gpu_utilization": 0.45,
            "actions_per_minute": 5,
        },
    )
    print(f"  → verdict={result.policy_verdict} | executed={result.executed} | "
          f"proof={result.proof_status} | {result.cycle_ms:.1f}ms")

    # Test 2: GPU overheat action → should VETO
    print("\n[Test 2] GPU overheat (should VETO)")
    result = pel.process_action(
        action_plan={
            "action_id": "ACT-GPU-001",
            "action_type": "train_model",
            "gpu_request": 2,
            "category": "deploy",
        },
        system_state={
            "nodes": 5, "cpu_total": 40, "ram_gb": 80,
            "gpu_units": 1.0, "gpu_utilization": 0.99,  # OVERHEAT
            "ram_usage": 0.5,
        },
    )
    print(f"  → verdict={result.policy_verdict} | executed={result.executed} | "
          f"blocked_reason={result.blocked_reason}")

    # Test 3: Rate limit exceeded → should BLOCK
    print("\n[Test 3] Rate limit exceeded (should BLOCK)")
    result = pel.process_action(
        action_plan={
            "action_id": "ACT-RATE-001",
            "action_type": "api_call",
            "category": "write",
        },
        system_state={
            "nodes": 3, "cpu_total": 24, "ram_gb": 48,
            "gpu_utilization": 0.3, "ram_usage": 0.5,
            "actions_per_minute": 150,  # OVER LIMIT
        },
    )
    print(f"  → verdict={result.policy_verdict} | executed={result.executed} | "
          f"blocked_reason={result.blocked_reason}")

    # Test 4: Secret exposure attempt → should VETO
    print("\n[Test 4] Secret exposure (should VETO)")
    result = pel.process_action(
        action_plan={
            "action_id": "ACT-SEC-001",
            "action_type": "log_config",
            "exposes_secrets": True,  # VETO condition
            "category": "write",
        },
        system_state={"gpu_utilization": 0.3, "ram_usage": 0.5},
    )
    print(f"  → verdict={result.policy_verdict} | executed={result.executed}")

    # Show audit chain
    stats = pel.get_stats()
    print(f"\n[STATS]")
    print(f"  Executed: {stats['total_executed']} | Blocked: {stats['total_blocked']}")
    print(f"  Execution rate: {stats['execution_rate']:.1%}")
    print(f"  PolicyKernel evaluations: {stats['policy_kernel']['total_evaluations']}")
    print(f"  Audit chain valid: {stats['audit_graph']['chain_valid']}")
    print(f"  Total audit nodes: {stats['audit_graph']['total_nodes']}")


if __name__ == "__main__":
    main()
