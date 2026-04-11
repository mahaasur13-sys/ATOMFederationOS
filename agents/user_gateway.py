"""
TAAR v14-secure — User Gateway
Every action requires explicit user approval.
Blocks ALL unapproved operations.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum


class ExecutionMode(Enum):
    READ = "read"
    PLAN = "plan"
    SAFE_EXEC = "safe_exec"
    WRITE = "write"
    ADMIN = "admin"


class ApprovalState(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EDITED = "edited"


@dataclass
class ActionPlan:
    action_id: str
    steps: list
    impact: dict
    simulation: dict

    def to_approval_request(self) -> str:
        lines = ["\n📋 PLAN\n"]
        for step in self.steps:
            lines.append(f"  step {step['step']}: {step['command']}")
            lines.append(f"    -> {step.get('description', '')}")
        lines.append(f"\nIMPACT: files={self.impact.get('files_changed', [])}")
        lines.append(f"risks={self.impact.get('risks', [])}")
        lines.append(f"\nSIMULATION: {self.simulation.get('expected_outcome', '')}")
        lines.append(f"\nProceed? (yes/no/edit)")
        return "\n".join(lines)


@dataclass
class ApprovalResult:
    state: ApprovalState
    user_command: str | None = None
    approved_at: str | None = None
    denied_reason: str | None = None


class UserGateway:
    """Human-in-the-loop gate. NO action executes without approval."""

    BLOCKED_PATTERNS = [
        "rm -rf /", "rm -rf /home", "rm -rf /etc", "rm -rf /usr",
        "chmod 777 /", "chmod -R 777 /",
        "fork bomb", ":(){:|:&};:",
        "curl | bash", "curl | sh", "wget | sh",
        "dd if=/dev/zero of=/dev/sda",
        "> /dev/sda",
        "mkfs.ext4 /dev/", "fdisk /dev/",
        "shutdown", "reboot",
    ]

    DENIED_PATHS = ["/etc/", "/usr/", "/root/", "/var/", "/bin/", "/sbin/"]
    ALLOWED_PATHS = ["/home/workspace/"]
    ALLOWED_DOMAINS = {"github.com", "pypi.org", "gitlab.com", "api.github.com"}
    SHELL_KEYWORDS = {"ls", "cd", "cat", "grep", "find", "pip", "python", "python3", "git", "rm", "cp",
                      "mv", "mkdir", "curl", "wget", "ssh", "docker", "docker-compose",
                      "echo", "chmod", "chown", "sed", "awk", "tar", "zip", "unzip",
                      "touch", "nano", "vim", "head", "tail", "sort", "uniq", "wc",
                      "ps", "kill", "top", "df", "du", "free", "uname", "whoami",
                      "pwd", "which", "type", "hash", "ruff", "black", "pytest", "make",
                      "curl", "wget", "ssh", "scp", "rsync", "systemctl", "apt", "yum",
                      "dnf", "pacman", "npm", "node", "bun", "go", "cargo", "rustc",
                      "javac", "java", "dotnet", "terraform", "ansible", "helm"}

    def __init__(self):
        self.pending_approvals: dict[str, ActionPlan] = {}
        self._audit_log: list[dict] = []
        self.session_mode = ExecutionMode.READ

    def validate(self, command: str) -> tuple[bool, str]:
        first_word = command.strip().split()[0].lower() if command.strip() else ""
        
        # Natural language — block direct shell
        if first_word not in self.SHELL_KEYWORDS and not command.strip().startswith("./"):
            return False, f"NON_SHELL: '{first_word}' — use /plan for natural language tasks"
        
        # Hard blocks
        for blocked in self.BLOCKED_PATTERNS:
            if blocked in command.lower():
                return False, f"HARD_BLOCK: {blocked}"
        for denied in self.DENIED_PATHS:
            if denied in command and "/home/workspace/" not in command:
                return False, f"PATH_DENIED: {denied}"
        return True, "allowed"

    def build_plan(self, intent: str, steps: list, impact: dict, simulation: dict) -> ActionPlan:
        import uuid
        action_id = f"ACT-{uuid.uuid4().hex[:8]}"
        plan = ActionPlan(action_id=action_id, steps=steps, impact=impact, simulation=simulation)
        self.pending_approvals[action_id] = plan
        return plan

    def approve(self, action_id: str, edited_cmd: str | None = None) -> ApprovalResult:
        state = ApprovalState.EDITED if edited_cmd else ApprovalState.APPROVED
        result = ApprovalResult(state=state, user_command=edited_cmd,
                                approved_at=datetime.now(timezone.utc).isoformat())
        self._log(action_id, result)
        self.pending_approvals.pop(action_id, None)
        return result

    def deny(self, action_id: str, reason: str = "denied") -> ApprovalResult:
        result = ApprovalResult(state=ApprovalState.DENIED, denied_reason=reason)
        self._log(action_id, result)
        self.pending_approvals.pop(action_id, None)
        return result

    def _log(self, action_id: str, result: ApprovalResult):
        self._audit_log.append({
            "action_id": action_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": result.state.value,
            "approved_at": result.approved_at,
        })

    def log_execution(self, action_id: str, command: str, result: str, approved: bool) -> dict:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_approved": approved,
            "command": command,
            "result": result,
            "hash": hashlib.sha256(f"{action_id}:{command}:{result}".encode()).hexdigest()[:16],
        }
        self._audit_log.append(entry)
        return entry

    def get_audit_log(self, limit: int = 50) -> list:
        return self._audit_log[-limit:]


gateway = UserGateway()
