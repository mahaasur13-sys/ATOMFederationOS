"""
TAAR v14 — System Mapper
Maps tasks to required TAAR layers (L0–L6)
Decides which TAAR versions are responsible
"""

import json
from typing import Optional

# Layer definitions
LAYER_MAP = {
    "L0": {"name": "Reality Interface", "versions": ["v10", "v11"], "weight": 1.0},
    "L1": {"name": "Civilization", "versions": ["v9"], "weight": 0.8},
    "L2": {"name": "Economy", "versions": ["v8"], "weight": 0.7},
    "L3": {"name": "Distributed Execution", "versions": ["v6", "v7"], "weight": 0.6},
    "L4": {"name": "Mission", "versions": ["v4", "v5"], "weight": 0.5},
    "L5": {"name": "Task Graph", "versions": ["v3"], "weight": 0.4},
    "L6": {"name": "Cognitive", "versions": ["v1", "v2"], "weight": 0.3},
}

LAYER_KEYWORDS = {
    "L0": ["deploy", "infra", "kubernetes", "docker", "server", "cloud", "production", "reality", "physical"],
    "L1": ["civilization", "trade", "economy", "world", "global", "multi-agent", "society"],
    "L2": ["market", "budget", "cost", "roi", "value", "bid", "resource allocation", "economy"],
    "L3": ["cluster", "distributed", "swarm", "parallel", "concurrent", "multi-node"],
    "L4": ["mission", "autonomous", "long-running", "goal", "self-evolve", "episodic"],
    "L5": ["task graph", "dag", "orchestrate", "pipeline", "workflow"],
    "L6": ["analyze", "search", "fix", "debug", "review", "single", "simple", "tool"],
}

RISK_PATTERNS = {
    "critical": ["delete all", "drop table", "rm -rf", "shutdown", "destroy", "kill all"],
    "high": ["deploy production", "migration", "cluster", "reboot", "restart"],
    "medium": ["create", "update", "modify", "change", "refactor"],
    "low": ["read", "search", "list", "analyze", "review", "check", "fix"],
}

EXECUTION_MODES = {
    "MODE_A": {"name": "full_reasoning", "llm_contexts": 1, "compression": False},
    "MODE_B": {"name": "compressed_reasoning", "llm_contexts": 1, "compression": True},
    "MODE_C": {"name": "tool_only", "llm_contexts": 0, "compression": False},
    "MODE_D": {"name": "observation_only", "llm_contexts": 0, "compression": False},
}

class SystemMapper:
    def __init__(self):
        self.usage_stats = {"L0": 0, "L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0}
    
    def map(self, task: str) -> dict:
        """Map task to required layers and risk profile"""
        task_lower = task.lower()
        
        # Detect required layers
        required_layers = []
        for layer, keywords in LAYER_KEYWORDS.items():
            for kw in keywords:
                if kw in task_lower:
                    if layer not in required_layers:
                        required_layers.append(layer)
        
        # Default to L6 (cognitive) if nothing detected
        if not required_layers:
            required_layers = ["L6"]
        
        # Detect risk
        risk = "low"
        for lvl, patterns in RISK_PATTERNS.items():
            for p in patterns:
                if p in task_lower:
                    risk = lvl
        
        # Select execution mode based on risk and complexity
        complexity = len(required_layers)
        if risk == "critical":
            mode = "MODE_D"
        elif risk == "high" or complexity >= 4:
            mode = "MODE_B"
        elif complexity >= 2:
            mode = "MODE_A"
        else:
            mode = "MODE_A"
        
        # Topological ordering
        order = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]
        sorted_layers = sorted(required_layers, key=lambda x: order.index(x))
        
        # Versions responsible
        version_map = {}
        for layer in sorted_layers:
            version_map[layer] = LAYER_MAP[layer]["versions"]
            self.usage_stats[layer] += 1
        
        return {
            "layers": sorted_layers,
            "topology": "→".join(sorted_layers),
            "versions": version_map,
            "risk_level": risk,
            "execution_mode": mode,
            "layer_count": len(sorted_layers),
            "vram_required_gb": len(sorted_layers) * 0.5,  # 0.5GB per layer
        }
    
    def get_stats(self) -> dict:
        return dict(self.usage_stats)

if __name__ == "__main__":
    mapper = SystemMapper()
    test_tasks = [
        "ci failed: ruff F401 agents/tools.py",
        "deploy to production cluster",
        "run market optimization across 3 economies",
        "analyze all files and review security",
        "delete all docker containers",
        "swarm analyze 1000 log entries",
        "mission: self-heal CI pipeline for 7 days",
    ]
    
    print("=== SYSTEM MAPPER TESTS ===")
    for task in test_tasks:
        result = mapper.map(task)
        print(f"\n[TASK] {task}")
        print(f"  → topology: {result['topology']}")
        print(f"  → risk: {result['risk_level']}")
        print(f"  → mode: {result['execution_mode']}")
        print(f"  → versions: {result['versions']}")
    
    print(f"\n✅ Layer usage: {mapper.get_stats()}")
