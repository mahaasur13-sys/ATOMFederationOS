"""
ATOM OS — CLI Interface
Commands: /run /plan /fix /audit /status /help
"""

from __future__ import annotations
import logging
import sys

from atomos.core.service_registry import register, get_service

logger = logging.getLogger("atomos.ui.cli")


@register("cli", module_type="ui", init_order=95)
class CLI:
    """
    Command-line interface for ATOM OS.
    All commands start with / (slash).
    """

    COMMANDS = {
        "/run": "execute_task",
        "/plan": "show_plan",
        "/fix": "devops_fix",
        "/audit": "audit_log",
        "/status": "system_status",
        "/health": "health_check",
        "/services": "list_services",
        "/help": "show_help",
    }

    def init(self) -> None:
        logger.info("  CLI ready")

    def parse_and_execute(self, line: str) -> dict:
        """Parse slash command and execute."""
        line = line.strip()
        if not line.startswith("/"):
            return {"error": "Commands start with / (e.g. /run, /help)"}

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        handler = self.COMMANDS.get(cmd)
        if not handler:
            return {"error": f"Unknown command: {cmd}. Try /help"}

        return getattr(self, handler)(args)

    # ── Handlers ──────────────────────────────────────────

    def execute_task(self, args: str) -> dict:
        if not args:
            return {"error": "Usage: /run <task description>"}
        try:
            from atomos.core.service_registry import get_registry
            r = get_registry()
            taar = r.get("taar_v14")
            result = taar.run_task(args)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def show_plan(self, args: str) -> dict:
        if not args:
            return {"error": "Usage: /plan <task>"}
        try:
            from atomos.core.service_registry import get_registry
            r = get_registry()
            tg = r.get("task_graph")
            task_graph = tg.build(args)
            return {"plan": task_graph}
        except Exception as e:
            return {"error": str(e)}

    def devops_fix(self, args: str) -> dict:
        if not args:
            return {"error": "Usage: /fix <CI error message>"}
        try:
            from atomos.core.service_registry import get_registry
            r = get_registry()
            agent = r.get("devops_agent")
            result = agent.run(ci_logs=args, repo_path="/home/workspace")
            return {"devops_result": result}
        except Exception as e:
            return {"error": str(e)}

    def audit_log(self, args: str) -> dict:
        from atomos.core.service_registry import get_registry
        r = get_registry()
        limit = int(args) if args.isdigit() else 10
        try:
            ledger = r.get("audit_ledger")
            entries = ledger.get_recent(limit=limit)
            return {"entries": entries}
        except Exception:
            return {"entries": [], "note": "Audit ledger not available"}

    def system_status(self, args: str) -> dict:
        from atomos.core.service_registry import get_registry
        r = get_registry()
        stats = r.get_boot_stats()
        return {"status": stats}

    def health_check(self, args: str) -> dict:
        from atomos.core.service_registry import get_registry
        r = get_registry()
        return r.health_check()

    def list_services(self, args: str) -> dict:
        from atomos.core.service_registry import get_registry
        r = get_registry()
        by_type = r.list_by_type()
        return {"services": by_type}

    def show_help(self, args: str) -> dict:
        return {
            "commands": {
                "/run <task>": "Execute task via TAAR",
                "/plan <task>": "Show execution plan (DAG)",
                "/fix <error>": "Run DevOps self-healing",
                "/audit [n]": "Show last N audit entries",
                "/status": "Show system boot status",
                "/health": "Health check all services",
                "/services": "List all registered services",
                "/help": "Show this help",
            }
        }
