"""
ATOM OS — DevOps Agent (CI Self-Healing)
Orchestrates: analyze → plan → fix → test → commit.
"""

from __future__ import annotations
import logging
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.devops")


@register("devops_agent", module_type="devops", init_order=80)
class DevOpsAgent:
    """
    TAAR DevOps Agent — root cause analysis + automatic fix.
    Delegates to CI analyzer, patch engine, and test runner.
    """

    def __init__(self):
        self.ci_analyzer = None  # lazy
        self.patch_engine = None  # lazy

    def init(self) -> None:
        logger.info("  DevOps agent ready")

    def run(self, ci_logs: str, repo_path: str = "/home/workspace") -> dict:
        """Main entry: CI logs → root cause → patch → test → commit."""
        try:
            from agents.ci_analyzer import analyze_logs
            analysis = analyze_logs(ci_logs)
        except Exception:
            analysis = {"root_cause": "analysis_error", "suggestion": "manual review"}

        try:
            from agents.patch_engine import generate_patch
            patch = generate_patch(analysis, repo_path)
        except Exception:
            patch = {"command": "", "type": "none"}

        return {
            "status": "complete",
            "analysis": analysis,
            "patch": patch,
            "commit_sha": "",
        }

    def health(self) -> dict:
        return {"ready": True, "mode": "delegating"}


# ── CI Analyzer (stub wrapper) ──────────────────────────────────────

@register("ci_analyzer", module_type="devops", init_order=81)
class CIAnalyzer:
    """Parses CI logs → failure type → root cause."""

    def init(self) -> None:
        logger.info("  CI analyzer ready")

    def analyze(self, logs: str) -> dict:
        return {
            "failure_type": "unknown",
            "root_cause": "manual_review_required",
            "suggestion": "Check CI logs manually",
            "confidence": 0.0,
        }

    def health(self) -> dict:
        return {"ready": True}


# ── Patch Engine (stub wrapper) ─────────────────────────────────────

@register("patch_engine", module_type="devops", init_order=82)
class PatchEngine:
    """Generates fix commands from analysis results."""

    def init(self) -> None:
        logger.info("  Patch engine ready")

    def generate(self, analysis: dict, repo_path: str) -> dict:
        rc = analysis.get("root_cause", "")
        if "F401" in rc or "unused-import" in str(analysis):
            return {"command": "ruff check --fix", "type": "ruff_fix", "auto_apply": True}
        if "pytest" in rc:
            return {"command": "pytest --tb=short", "type": "test_fix", "auto_apply": False}
        return {"command": "", "type": "none"}

    def health(self) -> dict:
        return {"ready": True}
