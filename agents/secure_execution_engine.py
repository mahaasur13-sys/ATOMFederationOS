"""
TAAR v14-secure — Secure Execution Engine
Step-by-step execution with user approval at each step.
"""
import uuid
from dataclasses import dataclass


class SecureExecutionEngine:
    """Executes only APPROVED steps. No autonomy."""

    def __init__(self, gateway):
        self.gateway = gateway
        self.execution_log = []

    def parse_intent(self, intent: str) -> tuple[list, dict]:
        """Parse user intent into steps. Returns (steps, impact)."""
        steps = []
        impact = {"files_changed": [], "commands": [], "risks": [], "risk_level": "low"}

        # Simple command parser
        parts = intent.replace(" then ", " ; ").replace(" and ", " ; ").split(";")
        for i, part in enumerate(parts, 1):
            part = part.strip()
            if not part:
                continue

            step = {"step": i, "command": part, "description": "", "impact": {}}

            # Detect risks
            risks = []
            if "delete" in part.lower() or "rm " in part.lower():
                risks.append("file_deletion")
            if "git" in part.lower() and "push" in part.lower():
                risks.append("remote_push")
            if "pip install" in part.lower():
                risks.append("package_install")
            if any(d in part for d in ["/etc/", "/usr/", "/root/"]):
                risks.append("system_path")
                impact["risk_level"] = "high"

            step["risks"] = risks
            steps.append(step)

        # Build impact
        impact["commands"] = [s["command"] for s in steps]
        impact["risk_level"] = impact.get("risk_level", "medium" if len(steps) > 3 else "low")

        return steps, impact

    def simulate(self, steps: list) -> dict:
        """Dry-run simulation. Returns expected outcome."""
        results = []
        for step in steps:
            allowed, reason = self.gateway.validate(step["command"])
            if allowed:
                results.append(f"step_{step['step']}: OK (would execute)")
            else:
                results.append(f"step_{step['step']}: BLOCKED ({reason})")
        return {
            "expected_outcome": "; ".join(results),
            "dry_run": True,
        }

    def execute_approved(self, steps: list, executor_fn) -> list[dict]:
        """
        Execute ONLY approved steps.
        Each step must have been approved through gateway.
        """
        results = []
        for step in steps:
            allowed, reason = self.gateway.validate(step["command"])
            if not allowed:
                results.append({
                    "step": step["step"],
                    "command": step["command"],
                    "status": "blocked",
                    "reason": reason,
                })
                continue

            # Execute via provided function
            try:
                exec_result = executor_fn(step["command"])
                results.append({
                    "step": step["step"],
                    "command": step["command"],
                    "status": "executed",
                    "result": exec_result,
                })
                self.execution_log.append({
                    "step": step["step"],
                    "command": step["command"],
                    "result": exec_result,
                })
            except Exception as e:
                results.append({
                    "step": step["step"],
                    "command": step["command"],
                    "status": "error",
                    "error": str(e),
                })
                break  # STOP on error (fail-safe)

        return results
