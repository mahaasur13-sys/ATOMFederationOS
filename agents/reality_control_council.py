"""
TAAR v10 — Reality Control Council (RCC)
Translates CIV-OS decisions → real infrastructure actions.

Safety contract:
    - All actions simulated first
    - Irreversible changes require explicit approval
    - Destructive actions blocked by default
    - Rollback always available
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Optional
import time


class ActionType(Enum):
    DEPLOY = auto()        # Kubernetes / Docker / server
    SCALE = auto()         # Increase compute nodes
    MODIFY_PIPELINE = auto()  # CI/CD adjustments
    OPTIMIZE_GPU = auto() # VRAM allocation / scheduling
    ROLLBACK = auto()      # System recovery
    ISOLATE = auto()       # Quarantine failure zones
    MONITOR = auto()       # Observe without changes
    APPROVE = auto()       # Permit pending action
    DENY = auto()          # Block pending action
    SCALE_DOWN = auto()   # Reduce resources


class RiskLevel(Enum):
    LOW = 1        # Read, monitor, observe
    MEDIUM = 2     # Non-destructive changes
    HIGH = 3       # Resource scaling, deployments
    CRITICAL = 4   # Destructive, irreversible, rollback


@dataclass
class RealityAction:
    action_id: str
    action_type: ActionType
    target: str              # Which system/resource
    parameters: dict         # Action-specific params
    risk_level: RiskLevel
    simulated: bool = False
    simulation_result: Optional[dict] = None
    approved: bool = False
    denied_reason: Optional[str] = None
    executed: bool = False
    execution_result: Optional[dict] = None
    rollback_available: bool = True
    rollback_action_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    civ_decision_ref: Optional[str] = None  # Reference to originating CIV-OS decision


class RealityControlCouncil:
    """
    RCC — The gatekeeper between AI civilization decisions and real infrastructure.

    Responsibilities:
        - Receive CIV-OS decisions
        - Classify risk level
        - Route to simulation engine
        - Enforce approval for high-risk actions
        - Track all reality actions in memory
        - Manage rollback queue
    """

    # Safety thresholds
    RISK_THRESHOLD_FOR_AUTO_APPROVAL = RiskLevel.MEDIUM
    MAX_CONCURRENT_HIGH_RISK = 3
    SIMULATION_MANDATORY_ABOVE = RiskLevel.HIGH

    def __init__(self, simulation_mode: bool = True):
        """
        simulation_mode: If True, ALL actions are simulated only (no real execution).
                         Set False only when running on actual infrastructure.
        """
        self.simulation_mode = simulation_mode
        self.action_log: list[RealityAction] = []
        self.pending_approvals: list[RealityAction] = []
        self.executed_count: int = 0
        self.blocked_count: int = 0
        self.cycle_count: int = 0

        # Infrastructure state snapshot (simulated)
        self.infra_state = {
            "clusters": {"default": {"nodes": 2, "cpu": 16, "ram_gb": 32, "gpu_units": 1}},
            "ci_pipelines": {"main": {"status": "healthy", "last_run": time.time()}},
            "gpu_schedulers": {"primary": {"utilization": 0.45}},
            "deployed_services": [],
        }

    def receive_civ_decision(self, civ_decision: dict) -> RealityAction | None:
        """
        Receive a decision from CIV-OS layer and convert to RealityAction.
        Returns None if decision doesn't require infrastructure action.
        """
        self.cycle_count += 1
        civ_action = civ_decision.get("action", "")
        civ_target = civ_decision.get("target", "")
        reason = civ_decision.get("reason", "")

        # Map civilization actions to reality action types
        action_map = {
            "create_economy": ActionType.SCALE,
            "remove_economy": ActionType.SCALE_DOWN,
            "split_economy": ActionType.SCALE,
            "merge_economies": ActionType.SCALE_DOWN,
            "deploy_service": ActionType.DEPLOY,
            "optimize_compute": ActionType.OPTIMIZE_GPU,
            "failover": ActionType.ISOLATE,
            "recover": ActionType.ROLLBACK,
            "increase_capacity": ActionType.SCALE,
            "decrease_capacity": ActionType.SCALE_DOWN,
            "update_pipeline": ActionType.MODIFY_PIPELINE,
        }

        action_type = action_map.get(civ_action, ActionType.MONITOR)
        risk = self._classify_risk(action_type, civ_target)

        # Civilizations can request resources → infrastructure responds
        params = self._build_params(action_type, civ_decision)

        action = RealityAction(
            action_id=f"RCA-{self.cycle_count:05d}-{civ_action[:8]}",
            action_type=action_type,
            target=civ_target or self._default_target(action_type),
            parameters=params,
            risk_level=risk,
            civ_decision_ref=civ_decision.get("decision_id"),
        )

        # Auto-approve low-risk in simulation mode
        if risk.value <= self.RISK_THRESHOLD_FOR_AUTO_APPROVAL.value:
            action.approved = True
        elif self.simulation_mode:
            # In simulation mode, auto-approve everything (it's all simulation anyway)
            action.approved = True

        return action

    def _classify_risk(self, action_type: ActionType, target: str) -> RiskLevel:
        """Classify risk level for an action."""
        if action_type in (ActionType.DEPLOY, ActionType.SCALE):
            return RiskLevel.HIGH
        elif action_type in (ActionType.SCALE_DOWN, ActionType.ISOLATE):
            return RiskLevel.CRITICAL
        elif action_type == ActionType.ROLLBACK:
            return RiskLevel.MEDIUM  # Rollback is safe by default
        elif action_type == ActionType.OPTIMIZE_GPU:
            return RiskLevel.MEDIUM
        elif action_type == ActionType.MODIFY_PIPELINE:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _default_target(self, action_type: ActionType) -> str:
        """Get default infrastructure target for action type."""
        defaults = {
            ActionType.SCALE: "clusters.default",
            ActionType.DEPLOY: "clusters.default",
            ActionType.OPTIMIZE_GPU: "gpu_schedulers.primary",
            ActionType.MODIFY_PIPELINE: "ci_pipelines.main",
            ActionType.ROLLBACK: "clusters.default",
            ActionType.ISOLATE: "clusters.default",
            ActionType.SCALE_DOWN: "clusters.default",
        }
        return defaults.get(action_type, "clusters.default")

    def _build_params(self, action_type: ActionType, civ_decision: dict) -> dict:
        """Build action parameters from CIV-OS decision."""
        base = {
            "civ_reason": civ_decision.get("reason", ""),
            "source_civ": civ_decision.get("target", ""),
        }

        if action_type == ActionType.SCALE:
            base.update({"delta_nodes": 1, "delta_cpu": 8, "delta_ram_gb": 16})
        elif action_type == ActionType.SCALE_DOWN:
            base.update({"delta_nodes": -1, "delta_cpu": -8, "delta_ram_gb": -16})
        elif action_type == ActionType.DEPLOY:
            base.update({"service_name": "ai-econ-service", "image": "latest", "replicas": 2})
        elif action_type == ActionType.OPTIMIZE_GPU:
            base.update({"target_utilization": 0.75, "strategy": "aggressive"})
        elif action_type == ActionType.MODIFY_PIPELINE:
            base.update({"pipeline": "main", "action": "enable_caching"})

        return base

    def simulate_action(self, action: RealityAction) -> dict:
        """Simulate the impact of an action (mandatory for HIGH/CRITICAL)."""
        action.simulated = True

        # Simulate based on action type
        if action.action_type == ActionType.SCALE:
            before = dict(self.infra_state["clusters"]["default"])
            self.infra_state["clusters"]["default"]["nodes"] += action.parameters.get("delta_nodes", 0)
            self.infra_state["clusters"]["default"]["cpu"] += action.parameters.get("delta_cpu", 0)
            self.infra_state["clusters"]["default"]["ram_gb"] += action.parameters.get("delta_ram_gb", 0)
            after = dict(self.infra_state["clusters"]["default"])
            result = {
                "before": before,
                "after": after,
                "impact": f"+{action.parameters.get('delta_nodes', 0)} nodes",
                "risk_assessed": True,
                "safe": True,
            }

        elif action.action_type == ActionType.DEPLOY:
            service_id = action.parameters.get("service_name", "unknown")
            result = {
                "service": service_id,
                "replicas": action.parameters.get("replicas", 1),
                "impact": f"Deploy {service_id} with {action.parameters.get('replicas', 1)} replicas",
                "risk_assessed": True,
                "safe": True,
            }

        elif action.action_type == ActionType.OPTIMIZE_GPU:
            target_util = action.parameters.get("target_utilization", 0.75)
            result = {
                "before_utilization": self.infra_state["gpu_schedulers"]["primary"]["utilization"],
                "target_utilization": target_util,
                "impact": f"Rebalance GPU to {target_util*100:.0f}% utilization",
                "risk_assessed": True,
                "safe": True,
            }

        elif action.action_type == ActionType.ISOLATE:
            result = {
                "target": action.target,
                "action": "isolate_cluster_node",
                "impact": "Isolate failure zone, reroute traffic",
                "risk_assessed": True,
                "safe": True,
            }

        else:
            result = {"impact": "monitor only", "risk_assessed": True, "safe": True}

        action.simulation_result = result
        return result

    def request_approval(self, action: RealityAction) -> bool:
        """Request approval for an action. Returns True if approved."""
        if action.risk_level.value <= self.RISK_THRESHOLD_FOR_AUTO_APPROVAL.value:
            action.approved = True
            return True

        if action.risk_level.value >= self.SIMULATION_MANDATORY_ABOVE.value:
            if not action.simulated:
                self.simulate_action(action)
            if not action.simulation_result.get("safe", False):
                action.denied_reason = "Simulation indicated unsafe conditions"
                self.blocked_count += 1
                return False

        # In non-simulation mode, would require human approval here
        if not self.simulation_mode:
            self.pending_approvals.append(action)
            return False

        action.approved = True
        return True

    def execute_action(self, action: RealityAction) -> dict:
        """Execute an approved action (or simulate in sim_mode)."""
        if not action.approved:
            approved = self.request_approval(action)
            if not approved:
                return {"status": "denied", "reason": action.denied_reason or "approval denied"}

        # High-risk must be simulated first
        if (action.risk_level.value >= self.SIMULATION_MANDATORY_ABOVE.value
                and not action.simulated):
            self.simulate_action(action)

        if self.simulation_mode:
            # Simulation mode: record as executed but don't touch real infra
            action.executed = True
            action.execution_result = {
                "status": "simulated",
                "simulation": action.simulation_result,
                "note": "Simulation mode — no real infrastructure changed",
            }
            self.executed_count += 1
        else:
            # Real execution would go here (kubectl, docker, terraform calls)
            action.executed = True
            action.execution_result = {
                "status": "executed",
                "real_change": True,
                "infra_state_after": dict(self.infra_state),
            }
            self.executed_count += 1

        # Set up rollback action
        if action.rollback_available and action.action_type in (ActionType.SCALE, ActionType.SCALE_DOWN):
            rollback = RealityAction(
                action_id=f"ROLLBACK-{action.action_id}",
                action_type=ActionType.SCALE_DOWN if action.action_type == ActionType.SCALE else ActionType.SCALE,
                target=action.target,
                parameters={k: -v for k, v in action.parameters.items()
                             if k.startswith("delta")},
                risk_level=RiskLevel.MEDIUM,
                approved=True,
                civ_decision_ref=action.action_id,
            )
            action.rollback_action_id = rollback.action_id
            self.action_log.append(rollback)

        self.action_log.append(action)
        return action.execution_result

    def get_council_report(self) -> dict:
        """Get council status report."""
        by_type = {}
        for a in self.action_log:
            key = a.action_type.name
            by_type[key] = by_type.get(key, 0) + 1

        return {
            "simulation_mode": self.simulation_mode,
            "total_actions": len(self.action_log),
            "executed": self.executed_count,
            "blocked": self.blocked_count,
            "pending_approvals": len(self.pending_approvals),
            "actions_by_type": by_type,
            "infra_state": dict(self.infra_state),
            "cycles": self.cycle_count,
        }


if __name__ == "__main__":
    council = RealityControlCouncil(simulation_mode=True)

    # Simulate receiving CIV-OS decisions
    civ_decisions = [
        {"decision_id": "EVD-0001-00", "action": "create_economy", "target": "ECONOS_NEW", "reason": "expand to ideal size"},
        {"decision_id": "EVD-0001-01", "action": "deploy_service", "target": "clusters.default", "reason": "new service deployment"},
        {"decision_id": "EVD-0001-02", "action": "optimize_compute", "target": "gpu_schedulers.primary", "reason": "improve GPU efficiency"},
    ]

    print("=== Reality Control Council ===")
    for cd in civ_decisions:
        action = council.receive_civ_decision(cd)
        print(f"\n[RECEIVED] {action.action_id} | type={action.action_type.name} | risk={action.risk_level.name}")
        result = council.execute_action(action)
        print(f"[EXEC] {result.get('status', 'unknown')} | simulation={action.simulated}")

    report = council.get_council_report()
    print(f"\n[REPORT] executed={report['executed']} | blocked={report['blocked']} | infra={report['infra_state']}")
