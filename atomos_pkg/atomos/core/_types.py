"""
ATOM OS — Core Types
Shared dataclasses used across all modules.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Execution ───────────────────────────────────────────────────────


class ActionType(str, Enum):
    SHELL = "shell"
    READ = "read_file"
    WRITE = "write_file"
    GIT = "git"
    DEV = "devops"
    HTTP = "http_request"
    K8S = "kubernetes"
    VISION = "vision"
    VOICE = "voice"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    BLOCKED = "blocked"


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    VETO = "VETO"
    BLOCK = "BLOCK"
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    DENIED = "DENIED"


@dataclass
class Action:
    action_id: str
    tool: str
    params: dict[str, Any]
    context: dict[str, Any]
    action_type: str = "shell"
    intent: str = ""
    user_approved: bool = False
    sandbox_allowed: bool = True
    allowed_domains: list[str] = field(default_factory=list)

    def to_hash_input(self) -> dict:
        return {
            "action_id": self.action_id,
            "tool": self.tool,
            "params": self.params,
            "action_type": self.action_type,
        }

    @property
    def hash(self) -> str:
        h = hashlib.sha256(str(self.to_hash_input()).encode())
        return h.hexdigest()


@dataclass
class Task:
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    plan: list[Action] = field(default_factory=list)
    result: Any = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    session_id: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def duration_ms(self) -> float:
        if not self.completed_at:
            return 0.0
        start = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.completed_at.replace("Z", "+00:00"))
        return (end - start).total_seconds() * 1000


@dataclass
class ExecutionContext:
    user_id: str = "system"
    session_id: str = "default"
    role: str = "agent"
    capabilities: list[str] = field(default_factory=list)
    signed_by: str = ""
    signature: str = ""
    intent: str = ""
    allowed_domains: list[str] = field(default_factory=list)
    restricted_paths: list[str] = field(default_factory=list)
    sandbox_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_signed(self) -> bool:
        return bool(self.signed_by and self.signature)

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = f"session-{int(time.time())}"


# ── Policy ──────────────────────────────────────────────────────────


@dataclass
class PolicyVerdict:
    verdict: Verdict
    reason: str
    blocked_rules: list[str] = field(default_factory=list)
    allowed_conditions: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    policy_version: str = "v3"

    @property
    def is_allowed(self) -> bool:
        return self.verdict in (Verdict.ALLOW, Verdict.APPROVED)


@dataclass
class SandboxConstraints:
    allowed_dirs: list[str] = field(default_factory=list)
    read_only_dirs: list[str] = field(default_factory=list)
    allowed_domains: list[str] = field(default_factory=list)
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    timeout_seconds: int = 30
    env_vars: dict[str, str] = field(default_factory=dict)
    network_access: bool = False


# ── Audit ───────────────────────────────────────────────────────────


@dataclass
class AuditEntry:
    entry_id: str
    action: Action
    context: ExecutionContext
    verdict: PolicyVerdict
    result: Any
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    chain_hash: str = ""
    prev_hash: str = ""

    def to_hash_input(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "action": self.action.to_hash_input(),
            "verdict": self.verdict.verdict.value,
            "result_hash": str(hash(str(self.result))),
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
        }


@dataclass
class PolicyTrace:
    trace_id: str
    task_id: str
    steps: list[dict[str, Any]]
    context: ExecutionContext
    policy_id: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None

    @property
    def trace_hash(self) -> str:
        h = hashlib.sha256(str(self.steps).encode())
        return h.hexdigest()


# ── Boot ─────────────────────────────────────────────────────────────


@dataclass
class BootConfig:
    config_dir: str = "config"
    log_dir: str = "logs"
    data_dir: str = "data"
    enable_vision: bool = False
    enable_voice: bool = False
    enable_mcp: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder-7b"
    log_level: str = "INFO"
