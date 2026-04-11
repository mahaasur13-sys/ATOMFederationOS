"""
TAAR v10 — Civilization to Reality Translation Layer
Maps civilization concepts → infrastructure actions.

Translation rules:
    trade            → bandwidth allocation / network QoS
    job              → CI/CD pipeline execution
    economy growth   → cluster resource scheduling
    war/conflict     → failover + isolation + traffic rerouting
    treaty/peace     → remove isolation, restore routing
    resource scarcity → scale up / provision new nodes
    oversupply       → scale down / decommission nodes
    alliance         → shared resource pools
    embargo         → block resource sharing
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranslationResult:
    """Result of translating a civilization action to infrastructure."""
    infra_action_type: str      # What infrastructure action to take
    target: str                 # Which infra component
    parameters: dict            # Action parameters
    priority: int               # 1=high, 5=low
    translation_fidelity: float  # 0-1: how well reality matched civ intent
    simulation_needed: bool
    safety_level: str           # LOW / MEDIUM / HIGH / CRITICAL
    notes: str = ""


class CivToRealityTranslator:
    """
    CivToReality — The translation layer between AI civilization (TAAR v9)
    and real infrastructure (TAAR v10).

    Each civilization concept has a specific infrastructure equivalent.
    """

    def translate(self, civ_action: str, civ_context: dict) -> TranslationResult:
        """
        Translate a civilization action → infrastructure action.
        """
        if civ_action == "create_economy":
            return self._translate_economy_create(civ_context)
        elif civ_action == "remove_economy":
            return self._translate_economy_remove(civ_context)
        elif civ_action == "split_economy":
            return self._translate_economy_split(civ_context)
        elif civ_action == "deploy_service":
            return self._translate_deploy_service(civ_context)
        elif civ_action == "trade":
            return self._translate_trade(civ_context)
        elif civ_action in ("declare_war", "initiate_conflict"):
            return self._translate_conflict(civ_context)
        elif civ_action in ("sign_treaty", "end_conflict"):
            return self._translate_peace(civ_context)
        elif civ_action == "allocate_resources":
            return self._translate_resource_allocation(civ_context)
        elif civ_action == "optimize_compute":
            return self._translate_gpu_optimization(civ_context)
        elif civ_action == "failover":
            return self._translate_failover(civ_context)
        elif civ_action == "increase_capacity":
            return self._translate_capacity_increase(civ_context)
        elif civ_action == "decrease_capacity":
            return self._translate_capacity_decrease(civ_context)
        else:
            return TranslationResult(
                infra_action_type="MONITOR",
                target="system",
                parameters={"civ_action": civ_action},
                priority=5,
                translation_fidelity=0.0,
                simulation_needed=False,
                safety_level="LOW",
                notes=f"No translation rule for: {civ_action}",
            )

    # ── Economy Actions ────────────────────────────────────────────

    def _translate_economy_create(self, ctx: dict) -> TranslationResult:
        """New economy = new cluster namespace + resource quota."""
        return TranslationResult(
            infra_action_type="SCALE",
            target="clusters.default",
            parameters={
                "delta_nodes": 1,
                "delta_cpu": 8,
                "delta_ram_gb": 16,
                "namespace": ctx.get("target", "new_economy"),
            },
            priority=2,
            translation_fidelity=0.95,
            simulation_needed=True,
            safety_level="MEDIUM",
            notes="New economy maps to compute node provisioning",
        )

    def _translate_economy_remove(self, ctx: dict) -> TranslationResult:
        """Economy removal = deprovision resources."""
        return TranslationResult(
            infra_action_type="SCALE_DOWN",
            target="clusters.default",
            parameters={
                "delta_nodes": -1,
                "delta_cpu": -8,
                "delta_ram_gb": -16,
            },
            priority=2,
            translation_fidelity=0.85,
            simulation_needed=True,
            safety_level="HIGH",
            notes="Removing economy — ensure no active workloads",
        )

    def _translate_economy_split(self, ctx: dict) -> TranslationResult:
        """Economy split = dedicated resource pool for each new economy."""
        return TranslationResult(
            infra_action_type="SCALE",
            target="clusters.default",
            parameters={
                "delta_nodes": 2,
                "delta_cpu": 16,
                "delta_ram_gb": 32,
                "action": "split_resource_pool",
            },
            priority=2,
            translation_fidelity=0.80,
            simulation_needed=True,
            safety_level="HIGH",
            notes="Split requires careful resource partitioning",
        )

    # ── Service Actions ─────────────────────────────────────────────

    def _translate_deploy_service(self, ctx: dict) -> TranslationResult:
        """Deploy = kubernetes deployment or docker service."""
        return TranslationResult(
            infra_action_type="DEPLOY",
            target=f"clusters.default/services/{ctx.get('service_name', 'ai-svc')}",
            parameters={
                "service_name": ctx.get("service_name", "ai-econ-service"),
                "image": ctx.get("image", "latest"),
                "replicas": ctx.get("replicas", 2),
            },
            priority=1,
            translation_fidelity=0.98,
            simulation_needed=True,
            safety_level="MEDIUM",
            notes="Deploy maps directly to container orchestration",
        )

    # ── Trade Actions ───────────────────────────────────────────────

    def _translate_trade(self, ctx: dict) -> TranslationResult:
        """Trade = network bandwidth allocation / QoS ticket."""
        trade_resource = ctx.get("resource", "gpu_compute")
        amount = ctx.get("amount", 10.0)

        if trade_resource == "gpu_compute":
            return TranslationResult(
                infra_action_type="ALLOCATE_BANDWIDTH",
                target="network.primary",
                parameters={
                    "bandwidth_mbps": amount * 100,
                    "priority": "normal",
                    "qos_tier": "economy_trade",
                },
                priority=3,
                translation_fidelity=0.75,
                simulation_needed=False,
                safety_level="LOW",
                notes=f"GPU trade ({amount} units) → network bandwidth allocation",
            )
        else:
            return TranslationResult(
                infra_action_type="MONITOR",
                target="network",
                parameters={"trade": ctx},
                priority=4,
                translation_fidelity=0.5,
                simulation_needed=False,
                safety_level="LOW",
                notes="Generic trade — monitor only",
            )

    # ── Conflict / War ─────────────────────────────────────────────

    def _translate_conflict(self, ctx: dict) -> TranslationResult:
        """War = failover + isolation of affected cluster zones."""
        return TranslationResult(
            infra_action_type="ISOLATE",
            target=f"clusters.default/zones/{ctx.get('target', 'default')}",
            parameters={
                "action": "isolate_failure_zone",
                "failover_to": "backup_cluster",
                "traffic_reroute": True,
            },
            priority=1,
            translation_fidelity=0.90,
            simulation_needed=False,
            safety_level="HIGH",
            notes="War/conflict → automatic failover and zone isolation",
        )

    def _translate_peace(self, ctx: dict) -> TranslationResult:
        """Peace treaty = restore connectivity, remove isolation."""
        return TranslationResult(
            infra_action_type="RESTORE_CONNECTIVITY",
            target="clusters.default",
            parameters={
                "action": "remove_isolation",
                "restore_routes": True,
            },
            priority=2,
            translation_fidelity=0.85,
            simulation_needed=True,
            safety_level="MEDIUM",
            notes="Peace treaty → restore normal routing",
        )

    # ── Resource Actions ───────────────────────────────────────────

    def _translate_resource_allocation(self, ctx: dict) -> TranslationResult:
        """Resource allocation = GPU/CPU scheduling adjustment."""
        return TranslationResult(
            infra_action_type="OPTIMIZE_GPU",
            target="gpu_schedulers.primary",
            parameters={
                "target_utilization": ctx.get("target_utilization", 0.75),
                "strategy": "aggressive" if ctx.get("urgency") == "high" else "conservative",
            },
            priority=2,
            translation_fidelity=0.90,
            simulation_needed=True,
            safety_level="MEDIUM",
            notes="Resource scarcity → scale compute",
        )

    def _translate_gpu_optimization(self, ctx: dict) -> TranslationResult:
        """GPU optimization = VRAM reallocation + scheduling."""
        return TranslationResult(
            infra_action_type="OPTIMIZE_GPU",
            target="gpu_schedulers.primary",
            parameters={
                "target_utilization": ctx.get("target_utilization", 0.80),
                "rebalance_vram": True,
            },
            priority=2,
            translation_fidelity=0.92,
            simulation_needed=False,
            safety_level="LOW",
            notes="Optimize GPU scheduling for better VRAM utilization",
        )

    def _translate_failover(self, ctx: dict) -> TranslationResult:
        """Failover = move workloads to backup nodes."""
        return TranslationResult(
            infra_action_type="ISOLATE",
            target="clusters.default",
            parameters={
                "action": "trigger_failover",
                "move_to": "backup_node",
                "health_check": True,
            },
            priority=1,
            translation_fidelity=0.95,
            simulation_needed=False,
            safety_level="HIGH",
            notes="Failover maps directly to infrastructure redundancy",
        )

    def _translate_capacity_increase(self, ctx: dict) -> TranslationResult:
        """Capacity increase = scale up cluster nodes."""
        return TranslationResult(
            infra_action_type="SCALE",
            target="clusters.default",
            parameters={
                "delta_nodes": ctx.get("delta_nodes", 1),
                "delta_cpu": ctx.get("delta_cpu", 8),
                "delta_ram_gb": ctx.get("delta_ram_gb", 16),
            },
            priority=2,
            translation_fidelity=0.95,
            simulation_needed=True,
            safety_level="MEDIUM",
            notes="Capacity increase → node provisioning",
        )

    def _translate_capacity_decrease(self, ctx: dict) -> TranslationResult:
        """Capacity decrease = decommission nodes."""
        return TranslationResult(
            infra_action_type="SCALE_DOWN",
            target="clusters.default",
            parameters={
                "delta_nodes": ctx.get("delta_nodes", -1),
                "delta_cpu": ctx.get("delta_cpu", -8),
                "delta_ram_gb": ctx.get("delta_ram_gb", -16),
            },
            priority=3,
            translation_fidelity=0.88,
            simulation_needed=True,
            safety_level="HIGH",
            notes="Capacity decrease → graceful node decommissioning",
        )

    # ── Batch Translation ───────────────────────────────────────────

    def translate_batch(self, civ_decisions: list[dict]) -> list[TranslationResult]:
        """Translate multiple civilization decisions."""
        results = []
        for decision in civ_decisions:
            result = self.translate(decision.get("action"), decision)
            results.append(result)
        return results

    def get_translation_report(self, results: list[TranslationResult]) -> dict:
        """Get summary report of batch translation."""
        by_type = {}
        for r in results:
            key = r.infra_action_type
            by_type[key] = by_type.get(key, 0) + 1

        avg_fidelity = sum(r.translation_fidelity for r in results) / len(results) if results else 0

        return {
            "total_translations": len(results),
            "by_infra_type": by_type,
            "average_fidelity": round(avg_fidelity, 3),
            "simulation_required": sum(1 for r in results if r.simulation_needed),
            "safety_breakdown": {
                sl: sum(1 for r in results if r.safety_level == sl)
                for sl in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            },
        }


if __name__ == "__main__":
    translator = CivToRealityTranslator()

    decisions = [
        {"action": "create_economy", "target": "ECONOS_X", "reason": "expansion"},
        {"action": "trade", "resource": "gpu_compute", "amount": 10.0},
        {"action": "declare_war", "target": "ECONOS_B"},
        {"action": "optimize_compute", "target_utilization": 0.80},
        {"action": "increase_capacity", "delta_nodes": 2},
    ]

    print("=== Translation Results ===")
    for d in decisions:
        r = translator.translate(d["action"], d)
        print(f"\n[{d['action']}]")
        print(f"  → {r.infra_action_type} on {r.target}")
        print(f"  fidelity={r.translation_fidelity} | safety={r.safety_level} | sim={r.simulation_needed}")

    report = translator.get_translation_report(
        translator.translate_batch(decisions)
    )
    print("\n=== Report ===")
    print(report)
