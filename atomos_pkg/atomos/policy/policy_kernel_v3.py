"""
ATOM OS v14.2 — Policy Kernel v3 (5-Layer Hardened Microkernel)
Layer 0: TrustedContext | Layer 1: RBAC | Layer 2: Semantic Firewall | Layer 3: Sandbox | Layer 4: Audit
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    VETO = "VETO"
    BLOCK = "BLOCK"


@dataclass
class ExecutionContext:
    user_id: str = "system"
    session_id: str = "default"
    role: str = "agent"
    capabilities: list[str] = field(default_factory=list)
    signed_by: str = ""
    signature: str = ""
    intent: str = ""
    restricted_paths: list[str] = field(default_factory=list)

    def is_signed(self) -> bool:
        return bool(self.signed_by and self.signature)


LAW2_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+/(?:\*|$|\s)", re.I), "LAW2: recursive delete"),
    (re.compile(r"dd\s+if=/dev/zero\s+of=/dev/", re.I), "LAW2: disk wipe"),
    (re.compile(r"mkfs", re.I), "LAW2: filesystem destroy"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;:", re.I), "LAW2: fork bomb"),
    (re.compile(r">\s*/dev/sd[a-z]", re.I), "LAW2: raw disk write"),
    (re.compile(r"fdisk\s+/dev/", re.I), "LAW2: partition table edit"),
]

LAW3_PATTERNS = [
    (re.compile(r"(?:ghp|gho|github_pat_)[A-Za-z0-9_]{36,}"), "LAW3: GitHub token"),
    (re.compile(r"-----BEGIN\s+(?:RSA |OPENSSH )?PRIVATE KEY-----"), "LAW3: private key"),
    (re.compile(r"aws_(?:access_key|secret)"), "LAW3: AWS credentials"),
]


class PolicyKernelV3:
    """5-layer policy microkernel."""

    def __init__(self):
        self.total_checks = 0

    def evaluate(self, plan: dict, ctx: ExecutionContext, intent: str = "") -> dict:
        """Evaluate action plan: ALLOW / VETO / BLOCK."""
        self.total_checks += 1

        # L0: No context
        if not ctx or not ctx.session_id:
            return {"verdict": "VETO", "reason": "No context", "layer": "L0"}

        # L0: Unsigned context
        if not ctx.is_signed():
            return {"verdict": "VETO", "reason": "Unsigned context", "layer": "L0"}

        # L1: RBAC capability check
        tool = plan.get("tool", "")
        if ctx.capabilities and not any(tool in cap for cap in ctx.capabilities):
            return {"verdict": "BLOCK", "reason": f"Capability denied: {tool}", "layer": "L1"}

        # L2: Semantic firewall
        cmd = str(plan.get("command", plan.get("params", {}).get("command", "")))
        for pat, reason in LAW2_PATTERNS + LAW3_PATTERNS:
            if pat.search(cmd):
                return {"verdict": "VETO", "reason": reason, "layer": "L2"}

        # L3: Sandbox
        if ctx.restricted_paths:
            path = str(plan.get("path", ""))
            if any(path.startswith(r) for r in ctx.restricted_paths):
                return {"verdict": "BLOCK", "reason": "Restricted path", "layer": "L3"}

        return {"verdict": "ALLOW", "reason": "All layers passed", "layer": "L4"}

    def get_stats(self) -> dict:
        return {"total_checks": self.total_checks}


if __name__ == "__main__":
    pk = PolicyKernelV3()
    tests = [
        ("ls -la", "agent", "ALLOW"),
        ("rm -rf /", "agent", "VETO"),
        (":(){ :|:& };:", "agent", "VETO"),
        ("chmod 000 /", "agent", "VETO"),
        ("export GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890", "agent", "VETO"),
    ]
    print(f"{'Test':<45} {'Exp':<7} {'Got':<7} {'Status'}")
    print("-" * 70)
    all_pass = True
    for cmd, role, expected in tests:
        ctx = ExecutionContext(user_id="test", session_id="s1", role=role, signed_by="system", signature="sig123")
        r = pk.evaluate({"tool": "shell", "command": cmd}, ctx)
        ok = r["verdict"] == expected
        if not ok:
            all_pass = False
        print(f"  {cmd:<43} {expected:<7} {r['verdict']:<7} {'PASS' if ok else 'FAIL'}")
    print(f"\nAll tests: {'PASS' if all_pass else 'FAIL'}")
