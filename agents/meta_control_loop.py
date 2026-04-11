"""
TAAR v14 — Meta Control Loop
OBSERVE → MODEL → SIMULATE → DECIDE → PROVE → GOVERN → EXECUTE → AUDIT → LEARN
Every action MUST pass through this loop. No exceptions.
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

class LoopPhase(Enum):
    OBSERVE = auto()
    MODEL = auto()
    SIMULATE = auto()
    DECIDE = auto()
    PROVE = auto()
    GOVERN = auto()
    EXECUTE = auto()
    AUDIT = auto()
    LEARN = auto()
    COMPLETE = auto()
    FAILED = auto()
    BLOCKED = auto()

@dataclass
class LoopState:
    task_id: str
    current_phase: LoopPhase = LoopPhase.OBSERVE
    phase_history: list = field(default_factory=list)
    observation: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    simulation_result: dict = field(default_factory=dict)
    decision: dict = field(default_factory=dict)
    proof: dict = field(default_factory=dict)
    governance_verdict: str = ""
    execution_result: dict = field(default_factory=dict)
    audit_hash: str = ""
    learnings: list = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""

def hash_state(state: dict) -> str:
    s = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def run_phase(loop: LoopState, phase: LoopPhase, executor) -> LoopState:
    loop.phase_history.append({
        "phase": phase.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blocked": loop.blocked
    })
    loop.current_phase = phase
    
    if loop.blocked:
        return loop
    
    if phase == LoopPhase.OBSERVE:
        loop.observation = executor.observe(loop.task_id)
    elif phase == LoopPhase.MODEL:
        loop.model = executor.model(loop.task_id, loop.observation)
    elif phase == LoopPhase.SIMULATE:
        loop.simulation_result = executor.simulate(loop.task_id, loop.model)
        if loop.simulation_result.get("blocked"):
            loop.blocked = True
            loop.block_reason = loop.simulation_result.get("reason", "simulation_blocked")
    elif phase == LoopPhase.DECIDE:
        loop.decision = executor.decide(loop.task_id, loop.model, loop.simulation_result)
    elif phase == LoopPhase.PROVE:
        if loop.blocked:
            loop.proof = {"status": "blocked", "reason": loop.block_reason}
        else:
            loop.proof = executor.prove(loop.task_id, loop.decision)
    elif phase == LoopPhase.GOVERN:
        if loop.blocked:
            loop.governance_verdict = "BLOCKED"
        else:
            loop.governance_verdict = executor.govern(loop.task_id, loop.proof)
            if loop.governance_verdict == "BLOCKED":
                loop.blocked = True
                loop.block_reason = "governance_rejected"
    elif phase == LoopPhase.EXECUTE:
        if loop.blocked:
            loop.execution_result = {"status": "blocked", "reason": loop.block_reason}
        else:
            loop.execution_result = executor.execute(loop.task_id, loop.decision, loop.proof)
    elif phase == LoopPhase.AUDIT:
        loop.audit_hash = executor.audit(loop.task_id, loop)
        loop.model["audit_hash"] = loop.audit_hash
    elif phase == LoopPhase.LEARN:
        loop.learnings = executor.learn(loop.task_id, loop)
    
    return loop

def run_meta_loop(task_id: str, executor) -> LoopState:
    loop = LoopState(task_id=task_id)
    phases = [
        LoopPhase.OBSERVE, LoopPhase.MODEL, LoopPhase.SIMULATE,
        LoopPhase.DECIDE, LoopPhase.PROVE, LoopPhase.GOVERN,
        LoopPhase.EXECUTE, LoopPhase.AUDIT, LoopPhase.LEARN, LoopPhase.COMPLETE
    ]
    for phase in phases:
        loop = run_phase(loop, phase, executor)
        if loop.blocked and phase not in (LoopPhase.COMPLETE,):
            loop.current_phase = LoopPhase.BLOCKED
            break
    
    if not loop.blocked:
        loop.current_phase = LoopPhase.COMPLETE
    
    return loop

def loop_to_output(loop: LoopState) -> dict:
    return {
        "task_id": loop.task_id,
        "final_phase": loop.current_phase.name,
        "blocked": loop.blocked,
        "block_reason": loop.block_reason,
        "proof_status": loop.proof.get("status", "none"),
        "governance": loop.governance_verdict,
        "audit_hash": loop.audit_hash,
        "result": loop.execution_result.get("status") if loop.execution_result else None,
        "phases_completed": len([p for p in loop.phase_history if not p["blocked"]]),
        "learnings": len(loop.learnings),
        "model_hash": hash_state(loop.model) if loop.model else "",
        "observation_hash": hash_state(loop.observation) if loop.observation else "",
    }

if __name__ == "__main__":
    class DummyExecutor:
        def __init__(self):
            self.count = {}
        def observe(self, tid): return {"task": tid, "observed_at": "now"}
        def model(self, tid, obs): return {"model": f"model_for_{tid}"}
        def simulate(self, tid, model):
            if "critical" in tid.lower():
                return {"blocked": True, "reason": "critical_risk"}
            return {"safe": True, "simulation_id": str(uuid.uuid4())[:8]}
        def decide(self, tid, model, sim): return {"plan": f"plan_{tid}", "layers": ["L6", "L5"]}
        def prove(self, tid, decision): return {"proof_id": hashlib.sha256(tid.encode()).hexdigest()[:16], "status": "valid"}
        def govern(self, tid, proof): return "APPROVED"
        def execute(self, tid, decision, proof): return {"executed": True, "result_id": str(uuid.uuid4())[:8]}
        def audit(self, tid, loop):
            return hash_state({"task": tid, "phases": len(loop.phase_history)})
        def learn(self, tid, loop): return [{"lesson": f"learned_from_{tid}"}]
    
    ex = DummyExecutor()
    print("=== META CONTROL LOOP TESTS ===")
    for task in ["normal_task", "critical_delete", "ci_failed_ruff"]:
        loop = run_meta_loop(task, ex)
        out = loop_to_output(loop)
        print(f"\n[{task}]")
        for k, v in out.items():
            print(f"  {k}: {v}")
    
    print("\n✅ Meta control loop operational")
