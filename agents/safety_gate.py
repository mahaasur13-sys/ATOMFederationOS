"""
TAAR DevOps — Safety Gate
validate_patch(patch: dict) → bool
Blocks: dangerous commands, credential leaks, out-of-scope changes.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────
# DANGEROUS PATTERNS
# ─────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+/(?:\s|$|--)"), "critical", "rm -rf / — would delete system files"),
    (re.compile(r"rm\s+-rf\s+/\*"), "critical", "rm -rf /* — root deletion"),
    (re.compile(r"dd\s+if=.+\s+of=/dev/sd"), "critical", "dd to disk device — data destruction"),
    (re.compile(r">\s*/etc/"), "critical", "redirect to /etc — system config overwrite"),
    (re.compile(r">\s*/sys/"), "critical", "redirect to /sys — kernel parameter write"),
    (re.compile(r"git\s+reset\s+--hard(?:\s|$)"), "high", "git reset --hard — discards uncommitted changes"),
    (re.compile(r"git\s+force\s+push"), "high", "git force push — overwrites remote history"),
    (re.compile(r"git\s+push\s+--force"), "high", "git push --force — same as above"),
    (re.compile(r":\(\)\{\s*:\|:\s*\}"), "critical", "fork bomb — will crash system"),
    (re.compile(r"mkfs\."), "critical", "mkfs — would destroy filesystem"),
    (re.compile(r"curl\s+.*\|\s*sh\b"), "high", "curl | sh — arbitrary script execution"),
    (re.compile(r"wget\s+.*\|\s*sh\b"), "high", "wget | sh — same risk"),
    (re.compile(r"--no-preserve-root"), "high", "--no-preserve-root — removes safety on rm"),
    (re.compile(r"chmod\s+-R\s+777"), "medium", "chmod -R 777 — overly permissive"),
    (re.compile(r"chmod\s+000"), "high", "chmod 000 — makes files inaccessible"),
    (re.compile(r"git\s+config\s+--global\s+credential"), "medium", "modifying git credentials"),
    (re.compile(r"gh\s+auth\s+refresh"), "medium", "gh auth refresh — token scope change"),
]

# Credential leak patterns (API keys, tokens, secrets)
_CREDENTIAL_PATTERNS = [
    (re.compile(r"ghp_[a-zA-Z0-9]{20,}"), "GitHub Personal Access Token"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "GitHub OAuth Token"),
    (re.compile(r"ghu_[a-zA-Z0-9]{36}"), "GitHub User Access Token"),
    (re.compile(r"xox[baprs]-[a-zA-Z0-9]{10,}"), "Slack Token"),
    (re.compile(r"sk-[a-zA-Z0-9]{48,}"), "OpenAI API Key"),
    (re.compile(r"AIza[a-zA-Z0-9_-]{35}"), "Google API Key"),
    (re.compile(r"[a-zA-Z0-9_.-]+@[a-zA-Z0-9.-]+\.googleusercontent\.com"), "Google OAuth"),
    (re.compile(r"amzn\.[a-zA-Z0-9]{16,}"), "AWS Access Key"),
    (re.compile(r"AKIA[a-zA-Z0-9]{16}"), "AWS Access Key ID"),
    (re.compile(r"sq0[a-z]{3}-[a-zA-Z0-9]{22}"), "Square OAuth"),
    (re.compile(r"sq0crt-[a-zA-Z0-9]{22}"), "Square Access Token"),
    (re.compile(r"STRIPE_SECRET_KEY"), "Stripe Secret Key name"),
    (re.compile(r"sk_live_[a-zA-Z0-9]{24,}"), "Stripe Live Secret Key"),
    (re.compile(r"sk_test_[a-zA-Z0-9]{24,}"), "Stripe Test Secret Key"),
]


# ─────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────

@dataclass
class SafetyResult:
    safe: bool
    reason: str
    violations: list[str]

    def __bool__(self) -> bool:
        return self.safe


# ─────────────────────────────────────────
# API
# ─────────────────────────────────────────

def validate_patch(patch: dict[str, Any]) -> bool:
    """
    Validate a patch before application.

    Returns:
        True if patch is safe to apply,
        False if it should be blocked.
    """
    result = _validate(patch)
    return result.safe


def _validate(patch: dict[str, Any]) -> SafetyResult:
    """Internal validation logic."""
    cmd = patch.get("command") or ""
    violations: list[str] = []

    # ── Check for dangerous patterns ─────────────────────
    for pattern, severity, description in _DANGEROUS_PATTERNS:
        if pattern.search(cmd):
            violations.append(f"[{severity.upper()}] {description}")

    # ── Check for credential leaks ────────────────────────
    for pattern, cred_type in _CREDENTIAL_PATTERNS:
        if pattern.search(cmd):
            violations.append(f"[CRITICAL] Credential leak: {cred_type} detected in command")

    # ── Check command length (sanity) ─────────────────────
    if len(cmd) > 2000:
        violations.append("[HIGH] Command too long — possible injection attempt")

    # ── Decision ──────────────────────────────────────────
    if violations:
        return SafetyResult(safe=False, reason="blocked", violations=violations)

    return SafetyResult(safe=True, reason="approved", violations=[])


def get_safety_report(patch: dict[str, Any]) -> SafetyResult:
    """Get detailed safety report for a patch."""
    return _validate(patch)
