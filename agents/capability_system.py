"""
TAAR v14.2 — Capability-Based Security System
Instead of ALLOW/BLOCK → capability set check
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class Capability(Enum):
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    FILESYSTEM_EXEC = "filesystem.exec"
    SYSTEM_PROCESS_LIST = "system.process.list"
    SYSTEM_PROCESS_KILL = "system.process.kill"
    SYSTEM_PROCESS_SPAWN = "system.process.spawn"
    SYSTEM_NETWORK_NONE = "system.network.none"
    SYSTEM_NETWORK_OUTBOUND = "system.network.outbound"
    SYSTEM_NETWORK_FULL = "system.network.full"
    SYSTEM_GATEWAY_READ = "system.gateway.read"
    SYSTEM_GATEWAY_WRITE = "system.gateway.write"
    SYSTEM_GATEWAY_ADMIN = "system.gateway.admin"
    CODE_EXECUTION_LOCAL = "code.execution.local"
    CODE_EXECUTION_SHELL = "code.execution.shell"
    AUDIT_READ = "audit.read"
    AUDIT_WRITE = "audit.write"
    INFRA_READ = "infra.read"
    INFRA_WRITE = "infra.write"
    INFRA_DEPLOY = "infra.deploy"
    INFRA_DESTROY = "infra.destroy"


# ─── Role Definitions ───────────────────────────────────────────────────────

ROLE_HUMAN_ADMIN = frozenset({
    Capability.FILESYSTEM_READ,
    Capability.FILESYSTEM_WRITE,
    Capability.FILESYSTEM_DELETE,
    Capability.FILESYSTEM_EXEC,
    Capability.SYSTEM_PROCESS_LIST,
    Capability.SYSTEM_PROCESS_KILL,
    Capability.SYSTEM_PROCESS_SPAWN,
    Capability.SYSTEM_NETWORK_FULL,
    Capability.SYSTEM_GATEWAY_READ,
    Capability.SYSTEM_GATEWAY_WRITE,
    Capability.SYSTEM_GATEWAY_ADMIN,
    Capability.CODE_EXECUTION_LOCAL,
    Capability.CODE_EXECUTION_SHELL,
    Capability.AUDIT_READ,
    Capability.AUDIT_WRITE,
    Capability.INFRA_READ,
    Capability.INFRA_WRITE,
    Capability.INFRA_DEPLOY,
    Capability.INFRA_DESTROY,
})

ROLE_DEVOPS_AGENT = frozenset({
    Capability.FILESYSTEM_READ,
    Capability.FILESYSTEM_WRITE,
    Capability.FILESYSTEM_DELETE,
    Capability.FILESYSTEM_EXEC,
    Capability.SYSTEM_PROCESS_LIST,
    Capability.SYSTEM_PROCESS_KILL,
    Capability.SYSTEM_PROCESS_SPAWN,
    Capability.SYSTEM_NETWORK_OUTBOUND,
    Capability.CODE_EXECUTION_LOCAL,
    Capability.CODE_EXECUTION_SHELL,
    Capability.AUDIT_READ,
    Capability.AUDIT_WRITE,
    Capability.INFRA_READ,
    Capability.INFRA_WRITE,
    Capability.INFRA_DEPLOY,
})

ROLE_COPILOT = frozenset({
    Capability.FILESYSTEM_READ,
    Capability.FILESYSTEM_WRITE,
    Capability.SYSTEM_PROCESS_LIST,
    Capability.SYSTEM_NETWORK_OUTBOUND,
    Capability.CODE_EXECUTION_LOCAL,
    Capability.AUDIT_READ,
    Capability.INFRA_READ,
})

ROLE_AUDITOR = frozenset({
    Capability.FILESYSTEM_READ,
    Capability.SYSTEM_PROCESS_LIST,
    Capability.SYSTEM_NETWORK_NONE,
    Capability.AUDIT_READ,
    Capability.AUDIT_WRITE,
    Capability.INFRA_READ,
})

ROLE_TAAR_INTERNAL = frozenset({
    Capability.FILESYSTEM_READ,
    Capability.SYSTEM_PROCESS_LIST,
    Capability.SYSTEM_NETWORK_NONE,
    Capability.CODE_EXECUTION_LOCAL,
    Capability.AUDIT_READ,
    Capability.INFRA_READ,
})


def capabilities_for_role(role: str) -> FrozenSet[Capability]:
    """Get capability set for role name."""
    table = {
        "human_admin": ROLE_HUMAN_ADMIN,
        "devops": ROLE_DEVOPS_AGENT,
        "copilot": ROLE_COPILOT,
        "auditor": ROLE_AUDITOR,
        "taar_internal": ROLE_TAAR_INTERNAL,
    }
    return table.get(role.lower(), ROLE_TAAR_INTERNAL)


# ─── Required Capabilities by Action Type ────────────────────────────────────

ACTION_REQUIRED_CAPABILITIES = {
    "shell": {Capability.CODE_EXECUTION_SHELL},
    "write_file": {Capability.FILESYSTEM_WRITE},
    "delete_file": {Capability.FILESYSTEM_DELETE},
    "read_file": {Capability.FILESYSTEM_READ},
    "exec_file": {Capability.FILESYSTEM_EXEC},
    "list_process": {Capability.SYSTEM_PROCESS_LIST},
    "kill_process": {Capability.SYSTEM_PROCESS_KILL},
    "spawn_process": {Capability.SYSTEM_PROCESS_SPAWN},
    "network_request": {Capability.SYSTEM_NETWORK_OUTBOUND},
    "gateway_read": {Capability.SYSTEM_GATEWAY_READ},
    "gateway_write": {Capability.SYSTEM_GATEWAY_WRITE},
    "gateway_admin": {Capability.SYSTEM_GATEWAY_ADMIN},
    "audit_read": {Capability.AUDIT_READ},
    "audit_write": {Capability.AUDIT_WRITE},
    "deploy": {Capability.INFRA_DEPLOY},
    "destroy": {Capability.INFRA_DESTROY},
}


@dataclass(frozen=True)
class ActionRequirements:
    """Required capabilities for an action."""
    action_type: str
    required: FrozenSet[Capability]
    optional: FrozenSet[Capability] = frozenset()
    min_role: str = "taar_internal"


def get_required_capabilities(action_type: str) -> ActionRequirements:
    """Map action_type → required capabilities."""
    required = ACTION_REQUIRED_CAPABILITIES.get(action_type, frozenset())
    return ActionRequirements(action_type=action_type, required=required)


if __name__ == "__main__":
    print("=== Capability System ===")
    for role, caps in [
        ("human_admin", ROLE_HUMAN_ADMIN),
        ("devops", ROLE_DEVOPS_AGENT),
        ("copilot", ROLE_COPILOT),
        ("auditor", ROLE_AUDITOR),
        ("taar_internal", ROLE_TAAR_INTERNAL),
    ]:
        print(f"\n{role}: {len(caps)} capabilities")
        for cap in sorted(caps, key=lambda c: c.value):
            print(f"  + {cap.value}")

    print("\n=== Action → Capabilities Mapping ===")
    for at, caps in ACTION_REQUIRED_CAPABILITIES.items():
        print(f"  {at}: {[c.value for c in sorted(caps)]}")
