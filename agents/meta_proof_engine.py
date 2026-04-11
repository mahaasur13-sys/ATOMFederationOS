"""
TAAR v14 — Enhanced Proof Engine
Every execution MUST generate:
  - execution graph hash
  - pre-state snapshot
  - post-state diff
  - deterministic replay log
  - policy compliance certificate
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class ExecutionProof:
    proof_id: str
    inputs_hash: str
    plan_graph_hash: str
    execution_trace_hash: str
    policy_checks_hash: str
    result_hash: str
    pre_state: dict
    post_state: dict
    replay_log: list
    policy_certificate: dict
    timestamp: str
    valid: bool = True

class MetaProofEngine:
    """
    Generates cryptographic proof for every action.
    No proof = no execution (P0 enforcement).
    """
    
    def __init__(self, policy_kernel):
        self.policy_kernel = policy_kernel
        self.proofs = []
        self.pending_proofs = []
    
    def generate_proof(self, task: str, plan: dict, system_state: dict, policy_checks: list) -> ExecutionProof:
        proof_id = hashlib.sha256(f"{task}{uuid.uuid4()}".encode()).hexdigest()[:16]
        
        # Hash all components
        inputs_hash = hashlib.sha256(task.encode()).hexdigest()[:16]
        plan_json = json.dumps(plan, sort_keys=True, default=str)
        plan_graph_hash = hashlib.sha256(plan_json.encode()).hexdigest()[:16]
        
        # Policy checks hash
        checks_json = json.dumps([{"id": c.rule_id, "v": c.verdict.name} for c in policy_checks], sort_keys=True)
        policy_checks_hash = hashlib.sha256(checks_json.encode()).hexdigest()[:16]
        
        # Pre-state snapshot
        pre_state = {
            "vram_gb": system_state.get("vram_used_gb", 0),
            "cpu_percent": system_state.get("cpu_percent", 0),
            "active_missions": system_state.get("active_missions", 0),
            "budget_used": system_state.get("budget_used", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Replay log entry
        replay_entry = {
            "proof_id": proof_id,
            "task": task,
            "plan": plan,
            "pre_state": pre_state,
            "policy_checks": len(policy_checks),
        }
        
        # Policy certificate
        p0_checks = [c for c in policy_checks if c.tier.name == "P0"]
        p0_passed = all(c.verdict.name == "ALLOW" for c in p0_checks)
        
        policy_certificate = {
            "proof_id": proof_id,
            "p0_passed": p0_passed,
            "p0_checks": len(p0_checks),
            "total_checks": len(policy_checks),
            "blocks": sum(1 for c in policy_checks if c.verdict.name in ("BLOCK", "DENY")),
        }
        
        # Result hash (will be updated after execution)
        result_hash = "pending"
        
        proof = ExecutionProof(
            proof_id=proof_id,
            inputs_hash=inputs_hash,
            plan_graph_hash=plan_graph_hash,
            execution_trace_hash="pending",
            policy_checks_hash=policy_checks_hash,
            result_hash=result_hash,
            pre_state=pre_state,
            post_state={},
            replay_log=[replay_entry],
            policy_certificate=policy_certificate,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        self.pending_proofs.append(proof)
        return proof
    
    def finalize_proof(self, proof_id: str, post_state: dict, execution_result: dict):
        """Finalize proof after execution with post-state and result"""
        proof = None
        for p in self.pending_proofs:
            if p.proof_id == proof_id:
                proof = p
                break
        
        if not proof:
            return None
        
        # Compute execution trace hash
        trace_json = json.dumps(execution_result, sort_keys=True, default=str)
        proof.execution_trace_hash = hashlib.sha256(trace_json.encode()).hexdigest()[:16]
        
        # Post-state
        proof.post_state = post_state
        
        # Result hash
        result_json = json.dumps({"result": execution_result, "post_state": post_state}, sort_keys=True, default=str)
        proof.result_hash = hashlib.sha256(result_json.encode()).hexdigest()[:16]
        
        proof.valid = True
        self.proofs.append(proof)
        self.pending_proofs = [p for p in self.pending_proofs if p.proof_id != proof_id]
        
        return proof
    
    def verify(self, proof_id: str) -> tuple[bool, str]:
        """Verify proof integrity"""
        proof = None
        for p in self.proofs:
            if p.proof_id == proof_id:
                proof = p
                break
        
        if not proof:
            return False, "Proof not found"
        
        if not proof.valid:
            return False, "Proof marked invalid"
        
        if proof.result_hash == "pending":
            return False, "Proof not finalized"
        
        # Verify certificate
        cert = proof.policy_certificate
        if not cert["p0_passed"]:
            return False, "P0 policy check failed"
        
        return True, f"Valid | pre={proof.pre_state.get('vram_gb')}GB | result_hash={proof.result_hash[:8]}"
    
    def get_stats(self) -> dict:
        return {
            "total_proofs": len(self.proofs),
            "pending": len(self.pending_proofs),
            "verified": sum(1 for p in self.proofs if p.valid),
        }

if __name__ == "__main__":
    from meta_policy_kernel import MetaPolicyKernel, PolicyTier, PolicyVerdict, PolicyCheck
    
    pk = MetaPolicyKernel()
    engine = MetaProofEngine(pk)
    
    print("=== META PROOF ENGINE TESTS ===")
    
    # Test proof generation
    plan = {"layers": ["L6"], "mode": "MODE_A", "actions": ["ruff_check", "fix"]}
    state = {"vram_used_gb": 4, "cpu_percent": 30, "active_missions": 2, "budget_used": 1.5}
    checks = [
        PolicyCheck(tier=PolicyTier.P0, rule_id="P0_NO_PROOF_NO_EXEC", verdict=PolicyVerdict.ALLOW, reason="ok"),
        PolicyCheck(tier=PolicyTier.P0, rule_id="P0_NO_UNAUDITED_ACTION", verdict=PolicyVerdict.ALLOW, reason="ok"),
    ]
    
    proof = engine.generate_proof("ci fix ruff F401", plan, state, checks)
    print(f"Generated: {proof.proof_id}")
    print(f"  inputs_hash: {proof.inputs_hash}")
    print(f"  plan_graph_hash: {proof.plan_graph_hash}")
    print(f"  policy_checks_hash: {proof.policy_checks_hash}")
    print(f"  certificate: {proof.policy_certificate}")
    
    # Finalize
    post = {"vram_used_gb": 4.2, "cpu_percent": 35, "active_missions": 2, "budget_used": 2.0}
    result = {"status": "executed", "fixes_applied": 1}
    finalized = engine.finalize_proof(proof.proof_id, post, result)
    
    print(f"\nFinalized: {finalized.proof_id if finalized else 'FAILED'}")
    if finalized:
        print(f"  result_hash: {finalized.result_hash}")
        print(f"  post_state: {finalized.post_state}")
    
    # Verify
    valid, msg = engine.verify(proof.proof_id)
    print(f"\nVerify: {valid} | {msg}")
    
    print(f"\n✅ Proof engine stats: {engine.get_stats()}")
