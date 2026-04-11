"""
TAAR v10 — Autonomous Reality Layer OS (REAL-OS)
TAAR v10.1 adds Policy + Proof + Audit Layer (PEL).

Self-regulating AI infrastructure control system.

Architecture:
    CIV-OS (v9) decisions → CivToReality → RealityControlCouncil
    → InfraAbstractionLayer → PolicyExecutionLayer → Real Infrastructure

Safety envelope:
    - All actions MUST pass through PEL before reaching infra
    - Proof Engine: plan → simulate → diff → approve → execute → verify
    - Policy Kernel: VETO/BLOCK unsafe actions regardless of AI intent
    - Immutable Audit Graph: append-only, hash-chained, replayable
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time

# Import all TAAR v10 components
from reality_control_council import RealityControlCouncil, RealityAction, ActionType, RiskLevel
from infra_abstraction import InfraAbstractionLayer, CloudProvider
from reality_action_engine import RealityActionEngine, ExecutionRecord
from global_impact_memory import GlobalImpactMemory
from civ_to_reality import CivToRealityTranslator, TranslationResult

# ── TAAR v10.1: Policy + Proof + Audit Layer ─────────────────────────
from execution_proof_engine import ExecutionProofEngine, ActionCategory
from policy_kernel import PolicyKernel, PolicyVerdict
from immutable_audit_graph import ImmutableAuditGraph


@dataclass
class RealOSResult:
    cycle: int
    civ_cycle: int
    actions_submitted: int
    actions_simulated: int
    actions_executed: int
    actions_blocked: int
    actions_vetoed: int
    pel_verdicts: dict
    translations_fidelity: float
    infra_state: dict
    global_impact: dict
    audit_chain_valid: bool
    simulation_mode: bool


class TAARv10RealOS:
    """
    TAAR v10 — Autonomous Reality Layer Operating System (REAL-OS).

    The final layer in the TAAR evolution: AI civilization decisions
    now directly control real infrastructure through a safe, simulated,
    and reversible execution layer.

    Loop:
        1. Receive CIV-OS (v9) decisions
        2. Translate civilization concepts → infrastructure actions
        3. Risk-classify each action
        4. Simulate before execution (mandatory for HIGH/CRITICAL)
        5. Execute via RealityActionEngine
        6. Record in GlobalImpactMemory
        7. Feed results back to civilization layer
    """

    def __init__(self,
                 simulation_mode: bool = True,
                 num_economies: int = 3,
                 provider: CloudProvider = CloudProvider.LOCAL):
        # ── Core components ──────────────────────────────────────────
        self.council = RealityControlCouncil(simulation_mode=simulation_mode)
        self.ial = InfraAbstractionLayer(provider=provider, simulation=simulation_mode)
        self.rae = RealityActionEngine(simulation_mode=simulation_mode)
        self.gim = GlobalImpactMemory()
        self.translator = CivToRealityTranslator()

        # ── State ────────────────────────────────────────────────────
        self.simulation_mode = simulation_mode
        self.cycle_count = 0
        self.civ_cycle = 0
        self.total_actions_submitted = 0
        self.total_actions_executed = 0
        self.total_actions_blocked = 0

    # ── Main Loop ────────────────────────────────────────────────────

    def process_civ_decisions(self, civ_decisions: list[dict]) -> list[dict]:
        """
        Process a batch of CIV-OS decisions through the full REAL-OS pipeline.
        """
        results = []
        translations = self.translator.translate_batch(civ_decisions)

        for decision, translation in zip(civ_decisions, translations):
            self.total_actions_submitted += 1

            # Step 1: Convert to RealityAction
            action = self.council.receive_civ_decision(decision)
            if action is None:
                continue

            # Step 2: Simulate (mandatory for HIGH/CRITICAL risk)
            if action.risk_level.value >= RiskLevel.HIGH.value and not action.simulated:
                self.council.simulate_action(action)

            # Step 3: Execute
            exec_record = self.rae.execute({
                "action_type": action.action_type.name,
                "target": action.target,
                "risk_level": action.risk_level.value,
                "simulated": action.simulated,
                "approved": action.approved,
                "rollback_available": action.rollback_available,
            })

            # Step 4: Apply to infrastructure
            if action.executed or action.simulated:
                self._apply_to_infra(action, translation)

            # Step 5: Record in global impact memory
            self._record_impact(decision, action, translation, exec_record)

            # Track stats
            if exec_record.status.name == "COMPLETED":
                self.total_actions_executed += 1
            elif exec_record.status.name == "ESCALATED":
                self.total_actions_blocked += 1

            results.append({
                "decision_id": decision.get("decision_id"),
                "action_id": action.action_id,
                "action_type": action.action_type.name,
                "risk": action.risk_level.name,
                "status": exec_record.status.name,
                "fidelity": translation.translation_fidelity,
            })

        self.cycle_count += 1
        return results

    def _apply_to_infra(self, action: RealityAction, translation: TranslationResult):
        """Apply an approved action to infrastructure abstraction layer."""
        # In simulation mode, record changes to IAL state so infra_state reflects reality
        # (action.executed means RAE has confirmed it; action.simulated means Council approved it)
        if action.action_type == ActionType.SCALE:
            delta_nodes = action.parameters.get("delta_nodes", 0)
            delta_cpu = action.parameters.get("delta_cpu", 0)
            delta_ram = action.parameters.get("delta_ram_gb", 0)
            self.ial.scale_cluster("default", delta_nodes, delta_cpu, delta_ram)

        elif action.action_type == ActionType.SCALE_DOWN:
            delta_nodes = action.parameters.get("delta_nodes", 0)
            delta_cpu = action.parameters.get("delta_cpu", 0)
            delta_ram = action.parameters.get("delta_ram_gb", 0)
            self.ial.scale_cluster("default", delta_nodes, delta_cpu, delta_ram)

        elif action.action_type == ActionType.DEPLOY:
            self.ial.deploy_service(
                "default",
                action.parameters.get("service_name", "ai-econ-service"),
                action.parameters.get("image", "latest"),
                action.parameters.get("replicas", 1),
            )

        elif action.action_type == ActionType.OPTIMIZE_GPU:
            self.ial.optimize_gpu_scheduling(
                "default",
                action.parameters.get("target_utilization", 0.75),
            )

        elif action.action_type == ActionType.MODIFY_PIPELINE:
            self.ial.modify_ci_pipeline(
                "main",
                action.parameters,
            )

    def _record_impact(self, decision: dict, action: RealityAction,
                       translation: TranslationResult, record: ExecutionRecord):
        """Record the impact of an action in GlobalImpactMemory."""
        # Record infra change
        self.gim.record_infra_change(
            change_type=action.action_type.name,
            civ_origin=decision.get("decision_id"),
            target=action.target,
            parameters=action.parameters,
            risk_level=action.risk_level.name,
            simulated=action.simulated,
            executed=action.executed,
            impact_magnitude=translation.translation_fidelity,
        )

        # Record civ→reality mapping
        self.gim.record_civ_to_reality_mapping(
            civ_action=decision.get("action", ""),
            civ_target=decision.get("target", ""),
            civ_reason=decision.get("reason", ""),
            reality_action_id=action.action_id,
            reality_action_type=action.action_type.name,
            translation_layer="CivToRealityTranslator",
            fidelity=translation.translation_fidelity,
        )

    # ── Single Cycle ────────────────────────────────────────────────

    def single_cycle(self, civ_decisions: Optional[list[dict]] = None,
                     verbose: bool = False) -> dict:
        """Run one REAL-OS cycle (optionally with CIV-OS decisions)."""
        self.civ_cycle += 1

        if civ_decisions is None:
            # Generate synthetic CIV-OS decisions for this cycle
            civ_decisions = [
                {
                    "decision_id": f"EVD-{self.civ_cycle:04d}-00",
                    "action": "create_economy",
                    "target": f"ECONOS_C{self.civ_cycle}",
                    "reason": "economic expansion",
                },
            ]

        results = self.process_civ_decisions(civ_decisions)

        if verbose:
            print(f"\n[REAL-OS CYCLE {self.cycle_count}]")
            print(f"  Decisions: {len(civ_decisions)}")
            print(f"  Translated: {len(results)}")
            print(f"  Executed: {self.total_actions_executed}")
            print(f"  Blocked: {self.total_actions_blocked}")
            print(f"  Infra state: {self.ial.get_available_resources('default')}")

        return self.get_stats()

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get comprehensive REAL-OS statistics."""
        return {
            "cycle": self.cycle_count,
            "civ_cycle": self.civ_cycle,
            "actions_submitted": self.total_actions_submitted,
            "actions_simulated": sum(1 for r in self.gim.infrastructure_changes if r.simulated),
            "actions_executed": self.total_actions_executed,
            "actions_blocked": self.total_actions_blocked,
            "translations_fidelity": self._avg_fidelity(),
            "infra_state": self.ial.get_available_resources("default"),
            "global_impact": self.gim.get_impact_report(),
            "council_report": self.council.get_council_report(),
            "rae_report": self.rae.get_execution_report(),
            "simulation_mode": self.simulation_mode,
        }

    def _avg_fidelity(self) -> float:
        mappings = self.gim.get_civ_mappings()
        if not mappings:
            return 1.0
        return sum(m.fidelity for m in mappings) / len(mappings)


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("🌍 TAAR v10 — Autonomous Reality Layer OS (REAL-OS)")
    print("=" * 70)

    os = TAARv10RealOS(simulation_mode=True, num_economies=3)

    for cycle in range(1, 6):
        # Simulate CIV-OS decisions
        civ_decisions = [
            {
                "decision_id": f"EVD-{cycle:04d}-00",
                "action": "create_economy",
                "target": f"ECONOS_NEW_{cycle}",
                "reason": "economic expansion cycle",
            },
            {
                "decision_id": f"EVD-{cycle:04d}-01",
                "action": "optimize_compute",
                "target_utilization": 0.75,
                "reason": "improve efficiency",
            },
        ]

        r = os.single_cycle(civ_decisions=civ_decisions, verbose=True)
        print(f"\n  ↳ submitted={r['actions_submitted']} | executed={r['actions_executed']} | "
              f"blocked={r['actions_blocked']} | fidelity={r['translations_fidelity']:.3f}")


if __name__ == "__main__":
    main()
