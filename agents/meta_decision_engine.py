"""
TAAR v14 — Meta Decision Engine
Decides which TAAR version is responsible, whether to split, simulate, escalate.
f(task) → {layer_map, risk_profile, execution_topology}
"""

import uuid
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecutionTopology:
    primary_layer: str
    supporting_layers: list
    version_responsible: list
    split_required: bool
    simulate_civilization_effects: bool
    escalate_to_reality: bool
    execution_mode: str
    confidence: float

class MetaDecisionEngine:
    """
    Brain of TAAR v14 — decides HOW to execute any task.
    Consults system mapper, risk engine, policy kernel.
    """
    
    def __init__(self, system_mapper, policy_kernel):
        self.mapper = system_mapper
        self.pk = policy_kernel
        self.decisions_log = []
    
    def decide(self, task: str, context: dict = None) -> ExecutionTopology:
        """Main decision function f(task) → ExecutionTopology"""
        
        # 1. Map task to layers
        layer_info = self.mapper.map(task)
        
        # 2. Determine if civilization simulation needed
        simulate_civ = self._needs_civilization_simulation(task, layer_info)
        
        # 3. Determine if reality escalation needed
        escalate = self._needs_reality_escalation(task, layer_info)
        
        # 4. Determine if economy split needed
        split = self._needs_economy_split(task, layer_info)
        
        # 5. Select execution mode
        mode = self._select_mode(task, layer_info, context or {})
        
        # 6. Compute confidence
        confidence = self._compute_confidence(layer_info, escalate, simulate_civ)
        
        topology = ExecutionTopology(
            primary_layer=layer_info["layers"][0] if layer_info["layers"] else "L6",
            supporting_layers=layer_info["layers"][1:],
            version_responsible=self._get_versions(layer_info["layers"]),
            split_required=split,
            simulate_civilization_effects=simulate_civ,
            escalate_to_reality=escalate,
            execution_mode=mode,
            confidence=confidence
        )
        
        self.decisions_log.append({
            "task": task,
            "topology": topology,
            "timestamp": "now"
        })
        
        return topology
    
    def _needs_civilization_simulation(self, task: str, layer_info: dict) -> bool:
        """Check if task requires civilization-level effect simulation"""
        civ_keywords = ["economy", "market", "trade", "global", "multi-economy", "civilization"]
        return any(kw in task.lower() for kw in civ_keywords) or "L1" in layer_info["layers"]
    
    def _needs_reality_escalation(self, task: str, layer_info: dict) -> bool:
        """Check if task needs reality layer (infra, deployment)"""
        reality_keywords = ["deploy", "infra", "production", "kubernetes", "server", "cloud"]
        return any(kw in task.lower() for kw in reality_keywords) or "L0" in layer_info["layers"]
    
    def _needs_economy_split(self, task: str, layer_info: dict) -> bool:
        """Check if task requires splitting into multiple economies"""
        split_keywords = ["swarm", "parallel", "multi-node", "cluster", "distributed"]
        return any(kw in task.lower() for kw in split_keywords) and layer_info["risk_level"] in ("high", "critical")
    
    def _select_mode(self, task: str, layer_info: dict, context: dict) -> str:
        """Select execution mode based on VRAM and task complexity"""
        risk = layer_info["risk_level"]
        vram_needed = layer_info["vram_required_gb"]
        mode = "MODE_A"
        
        if risk == "critical":
            mode = "MODE_D"
        elif risk == "high":
            mode = "MODE_B"
        elif vram_needed > 6:
            mode = "MODE_B"
        elif layer_info["layer_count"] >= 4:
            mode = "MODE_A"
        
        return mode
    
    def _compute_confidence(self, layer_info: dict, escalate: bool, simulate_civ: bool) -> float:
        base = 0.9 if layer_info["layer_count"] <= 2 else 0.75
        if escalate:
            base -= 0.1
        if simulate_civ:
            base -= 0.15
        return max(0.5, base)
    
    def _get_versions(self, layers: list) -> list:
        version_map = {
            "L0": "v10/v11", "L1": "v9", "L2": "v8",
            "L3": "v6/v7", "L4": "v4/v5", "L5": "v3", "L6": "v1/v2"
        }
        return [version_map.get(l, "unknown") for l in layers]
    
    def get_stats(self) -> dict:
        return {
            "decisions_made": len(self.decisions_log),
            "splits": sum(1 for d in self.decisions_log if d["topology"].split_required),
            "escalations": sum(1 for d in self.decisions_log if d["topology"].escalate_to_reality),
            "civ_simulations": sum(1 for d in self.decisions_log if d["topology"].simulate_civilization_effects),
        }

if __name__ == "__main__":
    from system_mapper import SystemMapper
    from meta_policy_kernel import MetaPolicyKernel
    
    mapper = SystemMapper()
    pk = MetaPolicyKernel()
    engine = MetaDecisionEngine(mapper, pk)
    
    print("=== META DECISION ENGINE TESTS ===")
    test_tasks = [
        "ci failed: ruff F401",
        "deploy to production kubernetes",
        "run market optimization across 3 economies",
        "swarm analyze 1000 logs",
        "delete all containers",
    ]
    
    for task in test_tasks:
        t = engine.decide(task)
        print(f"\n[TASK] {task}")
        print(f"  primary={t.primary_layer} | supporting={t.supporting_layers}")
        print(f"  versions={t.version_responsible}")
        print(f"  mode={t.execution_mode} | confidence={t.confidence:.2f}")
        print(f"  split={t.split_required} | civ_sim={t.simulate_civilization_effects} | escalate={t.escalate_to_reality}")
    
    print(f"\n✅ Stats: {engine.get_stats()}")
