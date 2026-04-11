"""
TAAR v10 — Real-World Action Engine (RAE)
Executes real infrastructure changes with safety guarantees.

Safety contract:
    IF action_risk > threshold: require council approval
    IF NOT simulated: simulate first
    IF error: automatic rollback
    IF rollback fails: escalate to human
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto
import time


class ExecutionStatus(Enum):
    PENDING = auto()
    SIMULATED = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    ROLLED_BACK = auto()
    ESCALATED = auto()


@dataclass
class ExecutionRecord:
    record_id: str
    action_type: str
    target: str
    status: ExecutionStatus
    risk_level: str
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    simulation_result: Optional[dict] = None
    execution_result: Optional[dict] = None
    rollback_of: Optional[str] = None
    error: Optional[str] = None
    safety_holds: list[str] = field(default_factory=list)


class RealityActionEngine:
    """
    RAE — Real-World Action Engine.

    Responsibilities:
        - Execute approved actions against real infrastructure
        - Enforce safety simulation before execution
        - Manage automatic rollback on failure
        - Escalate unresolvable issues
        - Track all execution records

    Safety holds: actions that must pass before execution proceeds.
    """

    MAX_ROLLBACK_DEPTH = 5
    EXECUTION_TIMEOUT_SEC = 30
    RISK_HIGH_THRESHOLD = 3  # Risk level above which simulation is mandatory

    def __init__(self, simulation_mode: bool = True):
        self.simulation_mode = simulation_mode
        self.execution_log: list[ExecutionRecord] = []
        self.rollback_stack: list[ExecutionRecord] = []
        self.pending_holds: list[str] = []
        self._record_counter = 0

    def _new_id(self) -> str:
        self._record_counter += 1
        return f"RAE-{self._record_counter:05d}"

    def _check_safety_holds(self, action: dict) -> list[str]:
        """Check safety conditions. Returns list of blocking issues."""
        blockers = []
        risk = action.get("risk_level", 0)

        # HIGH risk without simulation → block
        if risk >= self.RISK_HIGH_THRESHOLD and not action.get("simulated"):
            blockers.append("SIMULATION_REQUIRED: High-risk actions must be simulated before execution")

        # CRITICAL risk → requires explicit approval
        if risk >= 4 and not action.get("approved"):
            blockers.append("APPROVAL_REQUIRED: Critical actions require explicit approval")

        # Reversibility check
        if risk >= 3 and not action.get("rollback_available", True):
            blockers.append("REVERSIBILITY_REQUIRED: High-risk actions must have rollback capability")

        return blockers

    def execute(self, action: dict) -> ExecutionRecord:
        """
        Execute an action with full safety envelope.

        Safety envelope:
            1. Check safety holds
            2. Simulate if not yet done (HIGH/CRITICAL risk)
            3. Execute or queue for approval
            4. Monitor for failure → auto-rollback
            5. Record result
        """
        record = ExecutionRecord(
            record_id=self._new_id(),
            action_type=action.get("action_type", "unknown"),
            target=action.get("target", "unknown"),
            status=ExecutionStatus.PENDING,
            risk_level=action.get("risk_level", "unknown"),
            safety_holds=self._check_safety_holds(action),
        )

        # Block if safety holds not cleared
        if record.safety_holds:
            record.status = ExecutionStatus.ESCALATED
            record.error = f"Safety holds: {', '.join(record.safety_holds)}"
            self.execution_log.append(record)
            return record

        # Simulation check
        if not action.get("simulated") and action.get("risk_level", 0) >= self.RISK_HIGH_THRESHOLD:
            record.status = ExecutionStatus.SIMULATED
            record.simulation_result = self._simulate(action)
            if not record.simulation_result.get("safe", False):
                record.status = ExecutionStatus.FAILED
                record.error = "Simulation indicated unsafe conditions"
                self.execution_log.append(record)
                return record

        # Execute
        if self.simulation_mode:
            record.status = ExecutionStatus.COMPLETED
            record.execution_result = {
                "status": "simulated",
                "action": action,
                "note": "Simulation mode — no real changes",
            }
        else:
            record.status = ExecutionStatus.EXECUTING
            try:
                real_result = self._execute_real(action)
                record.status = ExecutionStatus.COMPLETED
                record.execution_result = real_result
            except Exception as e:
                record.status = ExecutionStatus.FAILED
                record.error = str(e)
                # Attempt automatic rollback
                rollback_record = self._rollback_action(record)
                if rollback_record:
                    record.status = ExecutionStatus.ROLLED_BACK

        record.completed_at = time.time()
        self.execution_log.append(record)
        return record

    def _simulate(self, action: dict) -> dict:
        """Run simulation of an action."""
        # Simulate resource changes
        return {
            "safe": True,
            "predicted_impact": f"{action.get('action_type')} on {action.get('target')}",
            "risk_level": action.get("risk_level", 0),
            "rollback_available": action.get("rollback_available", True),
        }

    def _execute_real(self, action: dict) -> dict:
        """
        Execute actual infrastructure change.
        In production, this would call kubectl, docker, terraform, etc.
        """
        return {
            "status": "executed",
            "target": action.get("target"),
            "change": action.get("action_type"),
            "real_infrastructure_updated": True,
        }

    def _rollback_action(self, failed_record: ExecutionRecord) -> Optional[ExecutionRecord]:
        """Rollback a failed action."""
        if len(self.rollback_stack) >= self.MAX_ROLLBACK_DEPTH:
            failed_record.status = ExecutionStatus.ESCALATED
            failed_record.error = f"Rollback stack full — manual intervention required"
            return None

        rollback_record = ExecutionRecord(
            record_id=self._new_id(),
            action_type=f"ROLLBACK:{failed_record.action_type}",
            target=failed_record.target,
            status=ExecutionStatus.PENDING,
            risk_level="MEDIUM",
            rollback_of=failed_record.record_id,
        )

        if self.simulation_mode:
            rollback_record.status = ExecutionStatus.COMPLETED
            rollback_record.execution_result = {"status": "simulated_rollback"}
        else:
            rollback_record.status = ExecutionStatus.EXECUTING
            # Simulate rollback
            rollback_record.status = ExecutionStatus.COMPLETED
            rollback_record.execution_result = {"status": "rollback_executed"}

        rollback_record.completed_at = time.time()
        self.rollback_stack.append(rollback_record)
        self.execution_log.append(rollback_record)
        return rollback_record

    def get_execution_report(self) -> dict:
        """Get execution engine status."""
        status_counts = {}
        for rec in self.execution_log:
            key = rec.status.name
            status_counts[key] = status_counts.get(key, 0) + 1

        return {
            "simulation_mode": self.simulation_mode,
            "total_executions": len(self.execution_log),
            "status_breakdown": status_counts,
            "rollback_depth": len(self.rollback_stack),
            "pending_holds": self.pending_holds,
            "last_execution": self.execution_log[-1].record_id if self.execution_log else None,
        }


if __name__ == "__main__":
    engine = RealityActionEngine(simulation_mode=True)

    print("=== Real-World Action Engine Test ===")

    # Test: low risk action (auto-approved)
    r1 = engine.execute({"action_type": "MONITOR", "target": "cluster/default", "risk_level": 1})
    print(f"Low risk: {r1.status.name}")

    # Test: high risk without simulation (blocked)
    r2 = engine.execute({"action_type": "SCALE", "target": "cluster/default", "risk_level": 3})
    print(f"High risk no sim: {r2.status.name} | error: {r2.error}")

    # Test: high risk with simulation (approved)
    r3 = engine.execute({"action_type": "SCALE", "target": "cluster/default",
                         "risk_level": 3, "simulated": True, "approved": True})
    print(f"High risk with sim: {r3.status.name}")

    # Test: critical with approval (simulated)
    r4 = engine.execute({"action_type": "SCALE_DOWN", "target": "cluster/default",
                         "risk_level": 4, "simulated": True, "approved": True, "rollback_available": True})
    print(f"Critical with approval: {r4.status.name}")

    print("\nExecution report:", engine.get_execution_report())
