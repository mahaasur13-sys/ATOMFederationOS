"""
TAAR v10.1 — Policy Kernel (PK)
Policy Kernel = the HARD LIMIT placed OVER AI decisions.

Principle: AI proposes, Policy Kernel approves or blocks.
The Kernel NEVER defers to AI on safety decisions.

Rules are enforced, not suggested.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PolicyVerdict(Enum):
    ALLOW = "allow"          # Execute immediately
    ALLOW_WITH_CONDITIONS = "allow_with_conditions"  # Execute with monitoring
    ESCALATE = "escalate"   # Human review required
    BLOCK = "block"          # Do not execute
    VETO = "veto"            # Critical: never allow this class of action


class PolicyRuleType(Enum):
    SAFETY = "safety"         # Life/critical system safety
    SECURITY = "security"     # Authentication, authorization, secrets
    RESOURCE = "resource"     # GPU/memory/CPU limits
    COST = "cost"             # Financial cost controls
    COMPLIANCE = "compliance"  # Regulatory/policy requirements
    AUDIT = "audit"           # Must have audit trail
    RATE = "rate"             # Rate limiting


@dataclass
class PolicyRule:
    rule_id: str
    name: str
    description: str
    rule_type: PolicyRuleType
    condition: str                    # Human-readable: "gpu_usage > 0.95"
    risk_threshold: float             # 0.0-1.0, block above this
    verdict_on_violation: PolicyVerdict
    enforced: bool = True              # Can it be overridden?
    active: bool = True
    violation_count: int = 0
    last_triggered: Optional[float] = None


@dataclass
class PolicyEvaluation:
    rule_id: str
    rule_name: str
    rule_type: PolicyRuleType
    condition: str
    passed: bool
    actual_value: Optional[float] = None
    threshold: Optional[float] = None
    verdict: Optional[PolicyVerdict] = None
    reason: str = ""


class PolicyKernel:
    """
    Policy Kernel = the sovereign safety layer above ALL AI decisions.

    The Kernel evaluates every action against a ruleset BEFORE execution.
    Rules are NOT suggestions — they are enforced bounds.

    Hard limits (cannot be overridden by AI):
        - SAFETY violations → VETO
        - SECURITY violations → VETO
        - COST overruns → BLOCK

    Configurable limits:
        - RESOURCE exhaustion → ESCALATE
        - RATE limit exceeded → BLOCK
        - COMPLIANCE gaps → ESCALATE
    """

    def __init__(self):
        self.rules: dict[str, PolicyRule] = {}
        self.evaluation_log: list[PolicyEvaluation] = []
        self._setup_default_rules()
        self.total_evaluations = 0

    def _setup_default_rules(self):
        """Install the non-negotiable safety baseline."""
        default_rules = [
            # ── SAFETY (hard VETO) ──────────────────────────────────
            PolicyRule(
                rule_id="PK-001",
                name="gpu_overheat_guard",
                description="Block GPU utilization above 98% — physical damage risk",
                rule_type=PolicyRuleType.SAFETY,
                condition="gpu_utilization > 0.98",
                risk_threshold=0.0,  # ZERO tolerance
                verdict_on_violation=PolicyVerdict.VETO,
            ),
            PolicyRule(
                rule_id="PK-002",
                name="memory_oom_guard",
                description="Block RAM usage above 97% — OOM kill risk",
                rule_type=PolicyRuleType.SAFETY,
                condition="ram_usage > 0.97",
                risk_threshold=0.0,
                verdict_on_violation=PolicyVerdict.VETO,
            ),

            # ── SECURITY (hard VETO) ─────────────────────────────────
            PolicyRule(
                rule_id="PK-003",
                name="secret_exposure_block",
                description="Block any action that would expose secrets/credentials in logs",
                rule_type=PolicyRuleType.SECURITY,
                condition="action.exposes_secrets == true",
                risk_threshold=0.0,
                verdict_on_violation=PolicyVerdict.VETO,
            ),
            PolicyRule(
                rule_id="PK-004",
                name="external_network_breach",
                description="Block actions that open unauthenticated external network access",
                rule_type=PolicyRuleType.SECURITY,
                condition="action.opens_unauthenticated_external == true",
                risk_threshold=0.0,
                verdict_on_violation=PolicyVerdict.VETO,
            ),

            # ── RESOURCE (BLOCK on hard limits) ──────────────────────
            PolicyRule(
                rule_id="PK-005",
                name="gpu_exhaustion_block",
                description="Block GPU requests that would exceed available GPU by >90%",
                rule_type=PolicyRuleType.RESOURCE,
                condition="requested_gpu > available_gpu * 1.1",
                risk_threshold=0.9,
                verdict_on_violation=PolicyVerdict.BLOCK,
            ),
            PolicyRule(
                rule_id="PK-006",
                name="ram_limit_block",
                description="Block RAM allocation above 95% of available",
                rule_type=PolicyRuleType.RESOURCE,
                condition="requested_ram > available_ram * 0.95",
                risk_threshold=0.95,
                verdict_on_violation=PolicyVerdict.BLOCK,
            ),

            # ── COST (BLOCK on budget) ──────────────────────────────
            PolicyRule(
                rule_id="PK-007",
                name="compute_budget_guard",
                description="Block any action that would exceed $100/hour compute budget",
                rule_type=PolicyRuleType.COST,
                condition="projected_cost_per_hour > 100",
                risk_threshold=100.0,
                verdict_on_violation=PolicyVerdict.BLOCK,
            ),

            # ── AUDIT (ESCALATE if no audit trail) ───────────────────
            PolicyRule(
                rule_id="PK-008",
                name="audit_trail_required",
                description="Escalate if action lacks proper audit trail",
                rule_type=PolicyRuleType.AUDIT,
                condition="action.has_audit_trail == false",
                risk_threshold=0.0,
                verdict_on_violation=PolicyVerdict.ESCALATE,
            ),

            # ── RATE (BLOCK on abuse) ────────────────────────────────
            PolicyRule(
                rule_id="PK-009",
                name="action_rate_limit",
                description="Block if more than 100 actions per minute (DDOS/loop risk)",
                rule_type=PolicyRuleType.RATE,
                condition="actions_per_minute > 100",
                risk_threshold=100.0,
                verdict_on_violation=PolicyVerdict.BLOCK,
            ),

            # ── FILESYSTEM SAFETY (hard VETO) ─────────────────────────
            PolicyRule(
                rule_id="PK-010",
                name="filesystem_destructive_guard",
                description="Block destructive filesystem operations: rm -rf, chmod -R, truncate, shred",
                rule_type=PolicyRuleType.SAFETY,
                condition='action.is_destructive_filesystem == true',
                risk_threshold=0.0,
                verdict_on_violation=PolicyVerdict.VETO,
            ),
        ]

        for rule in default_rules:
            self.rules[rule.rule_id] = rule

    def evaluate(self, action_plan: dict, system_state: dict) -> tuple[PolicyVerdict, list[PolicyEvaluation]]:
        """
        Evaluate an action plan against all active policy rules.

        Returns:
            (final_verdict, list_of_evaluations)
        """
        self.total_evaluations += 1
        evaluations: list[PolicyEvaluation] = []

        # VETO-class rules are checked first (they cannot pass)
        veto_triggered = False
        escalate_triggered = False
        block_triggered = False

        for rule in self.rules.values():
            if not rule.active:
                continue

            eval_result = self._evaluate_rule(rule, action_plan, system_state)
            evaluations.append(eval_result)

            if not eval_result.passed:
                rule.violation_count += 1

                if eval_result.verdict == PolicyVerdict.VETO:
                    veto_triggered = True
                elif eval_result.verdict == PolicyVerdict.ESCALATE:
                    escalate_triggered = True
                elif eval_result.verdict == PolicyVerdict.BLOCK:
                    block_triggered = True

        # Final verdict: VETO wins over everything
        if veto_triggered:
            final = PolicyVerdict.VETO
        elif escalate_triggered:
            final = PolicyVerdict.ESCALATE
        elif block_triggered:
            final = PolicyVerdict.BLOCK
        else:
            # Check if any conditions attached
            conditions = [e for e in evaluations if not e.passed and e.verdict == PolicyVerdict.ALLOW_WITH_CONDITIONS]
            final = PolicyVerdict.ALLOW_WITH_CONDITIONS if conditions else PolicyVerdict.ALLOW

        self.evaluation_log.extend(evaluations)
        return final, evaluations

    def _evaluate_rule(self, rule: PolicyRule, action_plan: dict, system_state: dict) -> PolicyEvaluation:
        """Evaluate a single rule against action + system state."""
        condition_met, actual_value = self._check_condition(rule.condition, action_plan, system_state)

        passed = not condition_met  # rule triggers when condition IS met → violation

        eval_result = PolicyEvaluation(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            condition=rule.condition,
            passed=passed,
            actual_value=actual_value,
            threshold=rule.risk_threshold,
            verdict=rule.verdict_on_violation if not passed else PolicyVerdict.ALLOW,
            reason=(
                f"{rule.name}: {rule.description}"
                if not passed
                else f"passed (condition '{rule.condition}' not violated)"
            ),
        )
        return eval_result

    def _check_condition(self, condition: str, action_plan: dict, system_state: dict) -> tuple[bool, Optional[float]]:
        """
        Parse and evaluate a condition string against combined state.
        Returns (condition_is_violated, actual_value).
        """
        combined = {**system_state, **action_plan}

        # Parse common conditions
        if "gpu_utilization >" in condition:
            threshold = float(condition.split(">")[1].strip())
            actual = combined.get("gpu_utilization", 0.0)
            return actual > threshold, actual

        if "ram_usage >" in condition:
            threshold = float(condition.split(">")[1].strip())
            actual = combined.get("ram_usage", 0.0)
            return actual > threshold, actual

        if "requested_gpu >" in condition:
            # e.g. "requested_gpu > available_gpu * 1.1"
            parts = condition.split(">")
            requested = float(parts[0].split("requested_gpu")[0].strip() or "1")
            threshold_mult = float(parts[1].split("*")[-1].strip())
            available = combined.get("available_gpu", 1.0)
            actual_requested = action_plan.get("requested_gpu", 0.0)
            return actual_requested > available * threshold_mult, actual_requested

        if "requested_ram >" in condition:
            threshold_mult = float(condition.split("*")[-1].strip())
            available = combined.get("available_ram", 1.0)
            actual_requested = action_plan.get("requested_ram_gb", 0.0)
            return actual_requested > available * threshold_mult, actual_requested

        if "actions_per_minute >" in condition:
            threshold = float(condition.split(">")[1].strip())
            actual = combined.get("actions_per_minute", 0)
            return actual > threshold, actual

        if "exposes_secrets" in condition:
            actual = action_plan.get("exposes_secrets", False)
            return actual is True, 1.0 if actual else 0.0

        if "opens_unauthenticated_external" in condition:
            actual = action_plan.get("opens_unauthenticated_external", False)
            return actual is True, 1.0 if actual else 0.0

        if "has_audit_trail" in condition:
            actual = action_plan.get("has_audit_trail", True)
            return actual is False, 0.0 if actual else 1.0

        if "projected_cost_per_hour >" in condition:
            threshold = float(condition.split(">")[1].strip())
            actual = combined.get("projected_cost_per_hour", 0.0)
            return actual > threshold, actual

        if "is_destructive_filesystem" in condition:
            task_text = action_plan.get("task_text", "").lower()
            destructive_patterns = [
                "rm -rf", "rm -r", "rm -f", "rm -rf /",
                "chmod -r", "chmod -r 000", "chmod -r 777",
                "truncate -s 0", "shred -u",
                "> /etc/", "| rm ", "dd if=/dev/zero of=",
                "mkfs.", "wipefs", "kill -9 -1",
            ]
            is_destructive = any(p in task_text for p in destructive_patterns)
            return is_destructive, 1.0 if is_destructive else 0.0

        return False, None

    def add_rule(self, rule: PolicyRule):
        """Add a new policy rule."""
        self.rules[rule.rule_id] = rule

    def deactivate_rule(self, rule_id: str):
        """Deactivate a rule (audit trail preserved)."""
        if rule_id in self.rules:
            self.rules[rule_id].active = False

    def get_stats(self) -> dict:
        """Return policy kernel statistics."""
        return {
            "total_evaluations": self.total_evaluations,
            "active_rules": sum(1 for r in self.rules.values() if r.active),
            "total_rules": len(self.rules),
            "verdicts": {
                "veto": sum(1 for e in self.evaluation_log if e.verdict == PolicyVerdict.VETO),
                "escalate": sum(1 for e in self.evaluation_log if e.verdict == PolicyVerdict.ESCALATE),
                "block": sum(1 for e in self.evaluation_log if e.verdict == PolicyVerdict.BLOCK),
                "allow": sum(1 for e in self.evaluation_log if e.verdict == PolicyVerdict.ALLOW),
            },
            "top_violations": sorted(
                [(r.rule_id, r.name, r.violation_count) for r in self.rules.values()],
                key=lambda x: -x[2],
            )[:5],
        }


if __name__ == "__main__":
    pk = PolicyKernel()

    # Test 1: Normal action — should ALLOW
    verdict, evals = pk.evaluate(
        {"action_type": "deploy", "service_name": "api-gateway", "replicas": 2},
        {"gpu_utilization": 0.45, "ram_usage": 0.5, "actions_per_minute": 5},
    )
    print(f"[TEST 1] Normal deploy → {verdict.value} | "
          f"{sum(1 for e in evals if not e.passed)} violations")

    # Test 2: GPU overheat — should VETO
    verdict, evals = pk.evaluate(
        {"action_type": "train", "gpu_request": 2},
        {"gpu_utilization": 0.99, "ram_usage": 0.5},
    )
    print(f"[TEST 2] GPU overheat → {verdict.value} | "
          f"{sum(1 for e in evals if e.verdict == PolicyVerdict.VETO)} vetos")

    # Test 3: Rate limit exceeded — should BLOCK
    verdict, evals = pk.evaluate(
        {"action_type": "api_call"},
        {"gpu_utilization": 0.3, "ram_usage": 0.5, "actions_per_minute": 150},
    )
    print(f"[TEST 3] Rate limit → {verdict.value} | "
          f"{sum(1 for e in evals if e.verdict == PolicyVerdict.BLOCK)} blocks")

    print(f"\nPK Stats: {pk.get_stats()}")
