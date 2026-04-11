"""
TAAR v10 — Global Impact Memory (GIM)
Stores the world-state graph: all infrastructure changes,
system outages, deployments, and civilization-to-reality mappings.

Structure:
    infrastructure_changes: chronological log of all infra modifications
    system_outages: incidents and their resolution
    deployments: service deployment history
    resource_impact: resource consumption per civ action
    civ_to_reality_mapping: which civ decisions mapped to which infra actions
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class InfraChange:
    change_id: str
    change_type: str           # scale, deploy, rollback, isolate, optimize
    civ_origin: Optional[str]  # Which CIV-OS decision triggered this
    target: str                # cluster, service, pipeline
    parameters: dict
    risk_level: str
    simulated: bool
    executed: bool
    impact_magnitude: float    # 0-1: how much this changed the system
    resource_cost: float       # GPU-seconds, CPU-hours consumed
    timestamp: float = field(default_factory=time.time)


@dataclass
class SystemOutage:
    outage_id: str
    cause: str
    affected_systems: list[str]
    start_time: float
    end_time: Optional[float] = None
    resolution: Optional[str] = None
    cascade_level: int = 0     # How many systems were affected


@dataclass
class Deployment:
    deployment_id: str
    service_name: str
    version: str
    cluster: str
    replicas: int
    civ_origin: Optional[str] = None
    status: str = "pending"    # pending / running / failed / rolled_back
    timestamp: float = field(default_factory=time.time)


@dataclass
class ResourceImpact:
    impact_id: str
    civ_decision: str
    resource_type: str         # gpu_compute, cpu_cycle, memory, bandwidth
    amount: float
    unit: str
    economic_value: float      # Estimated value in AI-economy terms


@dataclass
class CivToRealityMapping:
    mapping_id: str
    civ_action: str
    civ_target: str
    civ_reason: str
    reality_action_id: str
    reality_action_type: str
    translation_layer: str    # Which translation function was used
    fidelity: float            # 0-1: how well reality matched civ intent
    timestamp: float = field(default_factory=time.time)


class GlobalImpactMemory:
    """
    GIM — The "memory of the world" for TAAR v10.

    Tracks the complete history of civilization-to-reality translations
    and their actual impact on infrastructure.
    """

    MAX_HISTORY = 10000

    def __init__(self):
        self.infrastructure_changes: list[InfraChange] = []
        self.system_outages: list[SystemOutage] = []
        self.deployments: list[Deployment] = []
        self.resource_impact: list[ResourceImpact] = []
        self.civ_to_reality_mappings: list[CivToRealityMapping] = []
        self._change_counter = 0
        self._outage_counter = 0

    # ── Recording ──────────────────────────────────────────────────

    def record_infra_change(self,
                            change_type: str,
                            civ_origin: Optional[str],
                            target: str,
                            parameters: dict,
                            risk_level: str,
                            simulated: bool,
                            executed: bool,
                            impact_magnitude: float = 0.5,
                            resource_cost: float = 0.0) -> str:
        self._change_counter += 1
        cid = f"IC-{self._change_counter:05d}"
        change = InfraChange(
            change_id=cid,
            change_type=change_type,
            civ_origin=civ_origin,
            target=target,
            parameters=parameters,
            risk_level=risk_level,
            simulated=simulated,
            executed=executed,
            impact_magnitude=impact_magnitude,
            resource_cost=resource_cost,
        )
        self.infrastructure_changes.append(change)
        self._trim(self.infrastructure_changes)
        return cid

    def record_outage(self, cause: str, affected_systems: list[str]) -> str:
        self._outage_counter += 1
        oid = f"OUT-{self._outage_counter:05d}"
        outage = SystemOutage(
            outage_id=oid,
            cause=cause,
            affected_systems=affected_systems,
            start_time=time.time(),
        )
        self.system_outages.append(outage)
        return oid

    def resolve_outage(self, outage_id: str, resolution: str):
        for o in self.system_outages:
            if o.outage_id == outage_id:
                o.end_time = time.time()
                o.resolution = resolution

    def record_deployment(self, service_name: str, version: str,
                          cluster: str, replicas: int,
                          civ_origin: Optional[str] = None) -> str:
        did = f"DEP-{len(self.deployments)+1:05d}"
        self.deployments.append(Deployment(
            deployment_id=did,
            service_name=service_name,
            version=version,
            cluster=cluster,
            replicas=replicas,
            civ_origin=civ_origin,
        ))
        return did

    def record_civ_to_reality_mapping(self,
                                      civ_action: str,
                                      civ_target: str,
                                      civ_reason: str,
                                      reality_action_id: str,
                                      reality_action_type: str,
                                      translation_layer: str,
                                      fidelity: float = 1.0) -> str:
        mid = f"MAP-{len(self.civ_to_reality_mappings)+1:05d}"
        self.civ_to_reality_mappings.append(CivToRealityMapping(
            mapping_id=mid,
            civ_action=civ_action,
            civ_target=civ_target,
            civ_reason=civ_reason,
            reality_action_id=reality_action_id,
            reality_action_type=reality_action_type,
            translation_layer=translation_layer,
            fidelity=fidelity,
        ))
        return mid

    # ── Querying ───────────────────────────────────────────────────

    def get_recent_changes(self, limit: int = 20) -> list[InfraChange]:
        return self.infrastructure_changes[-limit:]

    def get_active_outages(self) -> list[SystemOutage]:
        return [o for o in self.system_outages if o.end_time is None]

    def get_outage_history(self, limit: int = 50) -> list[SystemOutage]:
        return self.system_outages[-limit:]

    def get_active_deployments(self) -> list[Deployment]:
        return [d for d in self.deployments if d.status in ("pending", "running")]

    def get_civ_mappings(self, civ_action: Optional[str] = None) -> list[CivToRealityMapping]:
        if civ_action is None:
            return self.civ_to_reality_mappings
        return [m for m in self.civ_to_reality_mappings if m.civ_action == civ_action]

    def get_total_resource_cost(self) -> dict:
        total = {}
        for change in self.infrastructure_changes:
            rt = change.change_type
            total[rt] = total.get(rt, 0.0) + change.resource_cost
        return total

    # ── Internal ───────────────────────────────────────────────────

    def _trim(self, lst: list, max_size: int = 0):
        if max_size and len(lst) > max_size:
            setattr(self, '_last_trimmed', len(lst) - max_size)

    def get_impact_report(self) -> dict:
        """Get comprehensive impact report."""
        active_outages = self.get_active_outages()
        active_deps = self.get_active_deployments()
        total_cost = self.get_total_resource_cost()

        return {
            "total_infrastructure_changes": len(self.infrastructure_changes),
            "total_outages": len(self.system_outages),
            "active_outages": len(active_outages),
            "total_deployments": len(self.deployments),
            "active_deployments": len(active_deps),
            "total_civ_mappings": len(self.civ_to_reality_mappings),
            "resource_cost_by_type": total_cost,
            "recent_changes": [
                {"id": c.change_id, "type": c.change_type, "target": c.target,
                 "executed": c.executed, "timestamp": c.timestamp}
                for c in self.infrastructure_changes[-10:]
            ],
        }


if __name__ == "__main__":
    gim = GlobalImpactMemory()

    # Record some changes
    c1 = gim.record_infra_change("SCALE", "EVD-0001-00", "cluster/default",
                                  {"delta_nodes": 2}, "HIGH", True, True, 0.7, 1.5)
    c2 = gim.record_infra_change("OPTIMIZE_GPU", "EVD-0001-01", "gpu_schedulers.primary",
                                  {"target_util": 0.75}, "MEDIUM", True, True, 0.3, 0.2)
    gim.record_deployment("ai-econ-service", "v2.1", "default", 3, "EVD-0001-02")
    gim.record_civ_to_reality_mapping("create_economy", "ECONOS_NEW", "expand to ideal size",
                                      c1, "SCALE", "civ_to_reality.scale_cluster", 0.95)

    print("Impact report:", gim.get_impact_report())
