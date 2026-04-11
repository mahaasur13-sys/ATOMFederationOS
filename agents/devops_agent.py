"""
TAAR DevOps — Orchestration Layer
DevOpsAgent.run(ci_logs: str, repo_path: str = ".") → dict

Pipeline:
    analyze_logs() → patch_engine.generate_patch() → safety_gate.validate_patch()
    → apply_patch() → rerun_pipeline()
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agents.ci_analyzer import analyze_logs
from agents.patch_engine import generate_patch, apply_patch
from agents.safety_gate import validate_patch, get_safety_report


# ─────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────

@dataclass
class DevOpsResult:
    status: str               # "applied" | "blocked" | "manual_review" | "error"
    analysis: dict[str, Any] # from ci_analyzer
    patch: dict[str, Any]    # from patch_engine
    safety_report: dict      # from safety_gate
    pipeline_output: str     # from rerun_pipeline
    applied_at: str          # ISO timestamp


# ─────────────────────────────────────────
# AGENT
# ─────────────────────────────────────────

class DevOpsAgent:
    """Self-healing DevOps agent for CI/CD pipelines."""

    def run(self, ci_logs: str, repo_path: str = ".") -> dict[str, Any]:
        print(f"[DEVOPS] analyzing CI failure...")

        # 1. ANALYZE — extract root cause
        analysis = analyze_logs(ci_logs)
        print(f"[ROOT CAUSE] {analysis['root_cause']}")

        # 2. GENERATE PATCH — create fix
        patch = generate_patch(analysis=analysis, context=ci_logs)
        print(f"[PATCH GENERATED] type={patch['type']}, auto={patch['auto']}")

        if not patch.get("auto", False):
            print("[BLOCKED] non-auto patch — manual review required")
            return self._result(
                status="manual_review",
                analysis=analysis,
                patch=patch,
                safety_report={"safe": None, "violations": []},
                pipeline_output="",
            )

        # 3. SAFETY GATE — validate before apply
        safety_report = get_safety_report(patch)
        if not safety_report.safe:
            print(f"[BLOCKED] unsafe patch detected — {safety_report.violations}")
            return self._result(
                status="blocked",
                analysis=analysis,
                patch=patch,
                safety_report={"safe": False, "violations": safety_report.violations},
                pipeline_output="",
            )

        # 4. APPLY PATCH
        print(f"[APPLYING] {patch['command']}")
        success = apply_patch(repo_path, patch)
        if not success:
            print(f"[FAILED] patch apply failed")
            return self._result(
                status="error",
                analysis=analysis,
                patch=patch,
                safety_report={"safe": True, "violations": []},
                pipeline_output="apply failed",
            )

        # 5. COMMIT + RERUN PIPELINE
        commit_msg = self._commit_changes(repo_path, analysis)
        pipeline_output = self.rerun_pipeline(repo_path)

        print(f"[APPLIED] {commit_msg}")
        return self._result(
            status="applied",
            analysis=analysis,
            patch=patch,
            safety_report={"safe": True, "violations": []},
            pipeline_output=pipeline_output,
        )

    def rerun_pipeline(self, repo_path: str) -> str:
        """Simulate CI pipeline re-run (git status + triggered workflow)."""
        try:
            output = subprocess.getoutput(
                f"cd {repo_path} && git status --short 2>&1"
            )
            # Check if gh CLI is available and authenticated
            gh_check = subprocess.getoutput("gh auth status 2>&1")
            if "Authenticated" in gh_check:
                # Trigger workflow re-run
                rerun = subprocess.getoutput(
                    f"cd {repo_path} && gh run list --limit 1 --json name,databaseId,status 2>/dev/null "
                    '|| echo "gh run list unavailable"'
                )
                output += f"\n[GH RE-RUN]\n{rerun}"
            else:
                output += "\n[CI RE-RUN] gh not authenticated — simulate only"
            return output
        except Exception as e:
            return str(e)

    def _commit_changes(self, repo_path: str, analysis: dict) -> str:
        """Commit applied changes with descriptive message."""
        try:
            msg = f"fix: {analysis.get('failure_type', '?')} — {analysis.get('root_cause', '')[:72]}"
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return "git add failed"
            result = subprocess.run(
                ["git", "diff", "--cached", "--stat"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                subprocess.run(
                    ["git", "commit", "-m", msg],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                )
                return f"committed: {msg}"
            return "no changes to commit"
        except Exception:
            return "git commit failed"

    def _result(
        self,
        status: str,
        analysis: dict,
        patch: dict,
        safety_report: dict,
        pipeline_output: str,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "analysis": analysis,
            "patch": patch,
            "safety_report": safety_report,
            "pipeline_output": pipeline_output,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
