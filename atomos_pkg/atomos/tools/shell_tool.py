"""
ATOM OS — Shell Tool (sandboxed subprocess execution)
"""

from __future__ import annotations
import logging
import subprocess
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.tools.shell")


BLOCKED_PATTERNS = [
    "rm -rf /", "dd if=/dev/zero", ":(){ :|:& };:",
    "mkfs", "fdisk /dev/", "> /dev/sda",
]


@register("shell_tool", module_type="tools", init_order=90)
class ShellTool:
    """Sandboxed shell execution via subprocess."""

    def init(self) -> None:
        logger.info("  Shell tool ready")

    def execute(
        self,
        command: str,
        cwd: str = "/home/workspace",
        timeout: int = 30,
        allowed_dirs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute shell command with safety checks."""
        # Safety check
        for blocked in BLOCKED_PATTERNS:
            if blocked in command:
                return {"error": f"Blocked command: {blocked}", "returncode": 1}

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out", "returncode": 124}
        except Exception as e:
            return {"error": str(e), "returncode": 1}

    def health(self) -> dict:
        return {"ready": True, "blocked_patterns": len(BLOCKED_PATTERNS)}


@register("filesystem_tool", module_type="tools", init_order=91)
class FilesystemTool:
    """Safe filesystem read/write operations."""

    def init(self) -> None:
        self.workspace = "/home/workspace"

    def read(self, path: str) -> dict[str, Any]:
        safe_path = path.lstrip("/")
        full = f"/{safe_path}"
        if not safe_path.startswith("home/workspace"):
            return {"error": "Access denied: outside workspace", "returncode": 1}
        try:
            with open(full) as f:
                return {"content": f.read(), "path": path}
        except Exception as e:
            return {"error": str(e), "returncode": 1}

    def write(self, path: str, content: str) -> dict[str, Any]:
        safe_path = path.lstrip("/")
        full = f"/{safe_path}"
        if not safe_path.startswith("home/workspace"):
            return {"error": "Access denied: outside workspace", "returncode": 1}
        try:
            with open(full, "w") as f:
                f.write(content)
            return {"path": path, "bytes_written": len(content)}
        except Exception as e:
            return {"error": str(e), "returncode": 1}

    def health(self) -> dict:
        return {"workspace": self.workspace, "ready": True}


@register("git_tool", module_type="tools", init_order=92)
class GitTool:
    """Git operations: status, diff, commit, push."""

    def init(self) -> None:
        self.repo_root = "/home/workspace"

    def execute(self, command: str) -> dict[str, Any]:
        if not command.startswith("git "):
            return {"error": "Not a git command", "returncode": 1}
        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"error": str(e), "returncode": 1}

    def health(self) -> dict:
        return {"repo_root": self.repo_root, "ready": True}
