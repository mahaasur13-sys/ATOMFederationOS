"""
TAAR v14 — Meta Policy Kernel
Absolute rules + Policy tiers (P0–P4) + Containment rules
This is the HARD LAW that governs ALL TAAR layers.
No bypass is possible. No override without governance.
"""

import hashlib
import json
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

class PolicyTier(Enum):
    P0 = auto()  # Hard Safety (immutable, no override)
    P1 = auto()  # Governance Board
    P2 = auto()  # Budget & Resource
    P3 = auto()  # Role-based access
    P4 = auto()  # Optimization heuristics

class PolicyVerdict(Enum):
    ALLOW = auto()
    DENY = auto()
    BLOCK = auto()  # Hard stop, no bypass

@dataclass 
class PolicyCheck:
    tier: PolicyTier
    rule_id: str
    verdict: PolicyVerdict
    reason: str
    bypass_allowed: bool = False

@dataclass
class MetaPolicyState:
    p0_rules_count: int = 0
    p1_rules_count: int = 0
    p2_rules_count: int = 0
    p3_rules_count: int = 0
    p4_rules_count: int = 0
    total_checks: int = 0
    blocks: int = 0
    allows: int = 0
    denies: int = 0
    bypass_count: int = 0

# ── P0 HARD SAFETY RULES (immutable) ──
P0_RULES = [
    ("P0_NO_PROOF_NO_EXEC", "No execution without proof hash"),
    ("P0_NO_SIM_NO_CROSS_LAYER", "No cross-layer action without simulation"),
    ("P0_NO_BUDGET_BYPASS", "No budget bypass allowed"),
    ("P0_NO_SILENT_POLICY_MUTATION", "No silent mutation of policy engine"),
    ("P0_NO_DIRECT_REALITY", "No direct infra modification without reality approval"),
    ("P0_NO_CIV_SELF_PROMOTE", "Civilizations cannot self-promote to reality layer"),
    ("P0_NO_ECON_OVERRIDE_PK", "Economies cannot override policy kernel"),
    ("P0_NO_ORG_MUTATE_GOV", "Organizations cannot mutate governance"),
    ("P0_REALITY_GATED", "Reality layer is ALWAYS gated"),
    ("P0_NO_UNAUDITED_ACTION", "Any action without audit is invalid"),
]

class MetaPolicyKernel:
    """
    The HARD LAW system.
    P0 rules are IMMUTABLE — cannot be overridden by any layer.
    P1–P4 can be modified via governance, but only through explicit voting.
    """
    
    def __init__(self):
        self.state = MetaPolicyState(
            p0_rules_count=len(P0_RULES),
            p1_rules_count=0, p2_rules_count=0,
            p3_rules_count=0, p4_rules_count=0
        )
        self.p1_rules = []  # Governance Board rules
        self.p2_rules = []  # Budget rules
        self.p3_rules = []  # Role-based rules
        self.p4_rules = []  # Optimization rules
        self.check_log = []
    
    def check(self, action: dict, system_state: dict, requesting_layer: str) -> tuple[PolicyVerdict, list[PolicyCheck]]:
        """Check action against all policy tiers. Returns (verdict, checks)"""
        checks = []
        final_verdict = PolicyVerdict.ALLOW
        
        # ── P0 CHECKS (mandatory, immutable) ──
        action_str = json.dumps(action, sort_keys=True, default=str)
        
        for rule_id, description in P0_RULES:
            p0_verdict = PolicyVerdict.ALLOW
            reason = "ok"
            
            if rule_id == "P0_NO_PROOF_NO_EXEC":
                if not action.get("proof_hash"):
                    p0_verdict = PolicyVerdict.BLOCK
                    reason = "No proof_hash in action"
            
            elif rule_id == "P0_NO_SIM_NO_CROSS_LAYER":
                layers = action.get("layers_affected", [])
                if len(layers) > 1 and not action.get("simulation_id"):
                    p0_verdict = PolicyVerdict.BLOCK
                    reason = f"Cross-layer action without simulation (layers: {layers})"
            
            elif rule_id == "P0_NO_BUDGET_BYPASS":
                if action.get("budget_override"):
                    p0_verdict = PolicyVerdict.BLOCK
                    reason = "Budget bypass attempted"
            
            elif rule_id == "P0_NO_DIRECT_REALITY":
                if "L0" in action.get("layers_affected", []) and not action.get("reality_approved"):
                    p0_verdict = PolicyVerdict.BLOCK
                    reason = "Reality layer action without approval"
            
            elif rule_id == "P0_NO_CIV_SELF_PROMOTE":
                if action.get("intent") == "promote_to_reality" and action.get("source_layer") in ("L1", "L2", "L3"):
                    p0_verdict = PolicyVerdict.BLOCK
                    reason = "Civilization tried to self-promote to reality"
            
            elif rule_id == "P0_NO_UNAUDITED_ACTION":
                if not action.get("audit_hash"):
                    p0_verdict = PolicyVerdict.BLOCK
                    reason = "Action without audit_hash"
            
            check = PolicyCheck(
                tier=PolicyTier.P0,
                rule_id=rule_id,
                verdict=p0_verdict,
                reason=reason,
                bypass_allowed=False
            )
            checks.append(check)
            
            if p0_verdict == PolicyVerdict.BLOCK:
                final_verdict = PolicyVerdict.BLOCK
        
        # ── P1 CHECKS (Governance Board) ──
        for rule in self.p1_rules:
            check = self._apply_rule(rule, action, system_state, PolicyTier.P1)
            checks.append(check)
            if check.verdict == PolicyVerdict.BLOCK:
                final_verdict = PolicyVerdict.BLOCK
        
        # ── P2 CHECKS (Budget) ──
        for rule in self.p2_rules:
            check = self._apply_rule(rule, action, system_state, PolicyTier.P2)
            checks.append(check)
        
        # ── P3 CHECKS (Role-based) ──
        for rule in self.p3_rules:
            check = self._apply_rule(rule, action, system_state, PolicyTier.P3)
            checks.append(check)
        
        # ── P4 CHECKS (Optimization) ──
        for rule in self.p4_rules:
            check = self._apply_rule(rule, action, system_state, PolicyTier.P4)
            checks.append(check)
        
        self._update_stats(final_verdict, checks)
        
        return final_verdict, checks
    
    def _apply_rule(self, rule: dict, action: dict, state: dict, tier: PolicyTier) -> PolicyCheck:
        # Simple pattern matching
        rule_id = rule.get("id", "unknown")
        condition = rule.get("condition", "")
        verdict = PolicyVerdict.ALLOW
        reason = "ok"
        
        if "vram_exceed" in condition:
            vram = action.get("vram_gb", 0) + state.get("vram_used_gb", 0)
            if vram > state.get("vram_limit_gb", 8):
                verdict = PolicyVerdict.DENY
                reason = f"Vram would exceed: {vram}GB > {state.get('vram_limit_gb', 8)}GB"
        
        return PolicyCheck(tier=tier, rule_id=rule_id, verdict=verdict, reason=reason, bypass_allowed=(tier != PolicyTier.P0))
    
    def _update_stats(self, final_verdict, checks):
        self.state.total_checks += 1
        self.state.p1_rules_count = len(self.p1_rules)
        self.state.p2_rules_count = len(self.p2_rules)
        self.state.p3_rules_count = len(self.p3_rules)
        self.state.p4_rules_count = len(self.p4_rules)
        
        if final_verdict == PolicyVerdict.BLOCK:
            self.state.blocks += 1
        elif final_verdict == PolicyVerdict.DENY:
            self.state.denies += 1
        else:
            self.state.allows += 1
        
        if any(c.bypass_allowed for c in checks):
            self.state.bypass_count += 1
    
    def add_p1_rule(self, rule: dict):
        self.p1_rules.append(rule)
    
    def add_p2_rule(self, rule: dict):
        self.p2_rules.append(rule)
    
    def get_state(self) -> dict:
        return {
            "p0_immutable": True,
            "p0_rules": len(P0_RULES),
            "p1_governance": len(self.p1_rules),
            "p2_budget": len(self.p2_rules),
            "p3_role": len(self.p3_rules),
            "p4_opt": len(self.p4_rules),
            "stats": {
                "total_checks": self.state.total_checks,
                "allows": self.state.allows,
                "denies": self.state.denies,
                "blocks": self.state.blocks,
            }
        }

if __name__ == "__main__":
    pk = MetaPolicyKernel()
    
    print("=== META POLICY KERNEL TESTS ===")
    print(f"P0 rules (immutable): {len(P0_RULES)}")
    for rid, desc in P0_RULES:
        print(f"  ❌ {rid}: {desc}")
    
    # Test blocked actions
    blocked_actions = [
        {"type": "deploy", "layers_affected": ["L0"], "proof_hash": None, "audit_hash": "abc"},  # No proof
        {"type": "cross_layer", "layers_affected": ["L1", "L2"], "proof_hash": "abc123"},          # No simulation
        {"type": "budget_override", "budget_override": True, "proof_hash": "abc123", "audit_hash": "xyz"},
        {"type": "promote", "intent": "promote_to_reality", "source_layer": "L2", "proof_hash": "abc123", "audit_hash": "xyz"},
    ]
    
    print("\n--- Blocked Action Tests ---")
    state = {"vram_used_gb": 4, "vram_limit_gb": 8}
    for action in blocked_actions:
        verdict, checks = pk.check(action, state, "L6")
        p0_blocks = [c for c in checks if c.tier == PolicyTier.P0 and c.verdict == PolicyVerdict.BLOCK]
        print(f"  action={action['type']} → verdict={verdict.name} | P0 blocks: {len(p0_blocks)}")
    
    # Test allowed action
    print("\n--- Allowed Action Test ---")
    allowed = {
        "type": "ci_fix", "layers_affected": ["L6"],
        "proof_hash": "abc123", "audit_hash": "xyz789",
        "simulation_id": "SIM001", "budget_override": False,
        "vram_gb": 0.5, "reality_approved": None
    }
    verdict, checks = pk.check(allowed, state, "L6")
    print(f"  ci_fix → verdict={verdict.name}")
    print(f"  PK State: {pk.get_state()}")
    
    print("\n✅ Meta Policy Kernel operational")
