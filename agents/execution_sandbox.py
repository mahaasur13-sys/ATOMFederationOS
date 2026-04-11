"""
TAAR v14.2 — Execution Sandbox Layer
Layer 4: Isolated execution environment for ALLOWED actions
"""

from __future__ import annotations
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SandboxMode(Enum):
    CONTAINED = "contained"      # Read-only, no network
    LIMITED = "limited"           # Read + limited write, no network
    OPERATIONAL = "operational"   # Read + write + filtered network
    FULL = "full"                # Full access (admin only)


@dataclass
class SandboxConfig:
    """Sandbox constraints for an execution."""
    mode: SandboxMode = SandboxMode.CONTAINED
    root_dir: str = "/sandbox"
    allowed_dirs: tuple[str, ...] = ("/tmp",)
    blocked_dirs: tuple[str, ...] = ("/etc", "/root", "/home")
    network_policy: str = "deny_all"   # deny_all | outbound | full
    cpu_quota_pct: int = 50
    memory_limit_mb: int = 512
    read_only_filesystem: bool = True
    env_whitelist: tuple[str, ...] = ("PATH", "HOME", "USER")
    execution_timeout_sec: int = 30
    audit_enabled: bool = True


@dataclass
class SandboxResult:
    """Result from sandbox execution."""
    sandbox_id: str
    allowed: bool
    constraints: dict
    execution_path: str | None
    proof: str
    error: str | None = None


class ExecutionSandbox:
    """
    PolicyKernel does NOT execute commands directly.
    It returns ALLOW_WITH_CONSTRAINTS → Sandbox enforces those constraints.

    This is a CONCEPTUAL sandbox — real implementation would use:
    - namespace isolation (Linux namespaces, gVisor)
    - seccomp filters
    - landlock BPF
    - overlayfs for filesystem containment
    """

    SANDBOX_BASE = "/sandbox"

    def __init__(self):
        self.is_initialized = False
        self.sandbox_counter = 0
        self.active_sandboxes: dict[str, dict] = {}

    def initialize(self) -> bool:
        """Create sandbox root if not exists."""
        try:
            os.makedirs(self.SANDBOX_BASE, exist_ok=True)
            self.is_initialized = True
            return True
        except OSError:
            return False

    def prepare_sandbox(self, config: SandboxConfig) -> SandboxResult:
        """
        Create an isolated execution environment.
        Returns proof of sandbox creation.
        """
        self.sandbox_counter += 1
        sandbox_id = f"sb-{self.sandbox_counter:04d}-{datetime.now(timezone.utc).strftime('%H%M%S')}"

        proof_input = f"{sandbox_id}:{config.mode.value}:{self.sandbox_counter}"
        proof = hashlib.sha256(proof_input.encode()).hexdigest()[:16]

        self.active_sandboxes[sandbox_id] = {
            "config": config,
            "proof": proof,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "executions": 0,
        }

        return SandboxResult(
            sandbox_id=sandbox_id,
            allowed=True,
            constraints=self._build_constraints(config),
            execution_path=f"{self.SANDBOX_BASE}/{sandbox_id}",
            proof=proof,
            error=None,
        )

    def _build_constraints(self, config: SandboxConfig) -> dict:
        """Build constraint manifest from config."""
        return {
            "mode": config.mode.value,
            "root_dir": f"{self.SANDBOX_BASE}/{config.mode.value}",
            "allowed_dirs": list(config.allowed_dirs),
            "blocked_dirs": list(config.blocked_dirs),
            "network_policy": config.network_policy,
            "cpu_quota_pct": config.cpu_quota_pct,
            "memory_limit_mb": config.memory_limit_mb,
            "read_only": config.read_only_filesystem,
            "env_whitelist": list(config.env_whitelist),
            "execution_timeout_sec": config.execution_timeout_sec,
            "audit_enabled": config.audit_enabled,
        }

    def get_constraints_for_action(self, action_type: str, capability_set: set) -> SandboxConfig:
        """
        Derive sandbox config from action type + capabilities.
        More restricted capabilities → more restrictive sandbox.
        """
        from capability_system import Capability

        cap_values = {c.value if isinstance(c, Capability) else c for c in capability_set}

        # Most restrictive
        if "filesystem.delete" in cap_values or "filesystem.exec" in cap_values:
            mode = SandboxMode.CONTAINED
            network = "deny_all"
            read_only = True
        elif "filesystem.write" in cap_values:
            mode = SandboxMode.LIMITED
            network = "deny_all"
            read_only = False
        elif "code.execution.shell" in cap_values:
            mode = SandboxMode.OPERATIONAL
            network = "outbound"
            read_only = False
        else:
            mode = SandboxMode.CONTAINED
            network = "deny_all"
            read_only = True

        return SandboxConfig(
            mode=mode,
            allowed_dirs=("/tmp", "/home/workspace"),
            blocked_dirs=("/etc", "/root", "/home/.ssh", "/proc"),
            network_policy=network,
            cpu_quota_pct=50,
            memory_limit_mb=512,
            read_only_filesystem=read_only,
            execution_timeout_sec=30,
            audit_enabled=True,
        )

    def get_stats(self) -> dict:
        return {
            "initialized": self.is_initialized,
            "sandbox_root": self.SANDBOX_BASE,
            "total_created": self.sandbox_counter,
            "active": len(self.active_sandboxes),
        }


if __name__ == "__main__":
    print("=== Execution Sandbox Layer ===\n")

    sandbox = ExecutionSandbox()
    sandbox.initialize()

    configs = [
        SandboxConfig(mode=SandboxMode.CONTAINED, network_policy="deny_all"),
        SandboxConfig(mode=SandboxMode.LIMITED, network_policy="deny_all"),
        SandboxConfig(mode=SandboxMode.OPERATIONAL, network_policy="outbound"),
    ]

    for cfg in configs:
        r = sandbox.prepare_sandbox(cfg)
        print(f"Sandbox: {r.sandbox_id}")
        print(f"  mode={cfg.mode.value}, network={cfg.network_policy}")
        print(f"  proof={r.proof}")
        print(f"  constraints: {r.constraints['mode']}, {r.constraints['network_policy']}")
        print()

    print(f"Sandbox stats: {sandbox.get_stats()}")
