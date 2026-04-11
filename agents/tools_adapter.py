"""
TAAR Tools Adapter
Bridges Zo tools (run_bash_command, read_file, etc.) to the tool registry.
Also provides LLM wrapper (Ollama or Zo built-in).
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────
# OLLAMA CONFIG
# ─────────────────────────────────────────

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

# ─────────────────────────────────────────
# LLM PROVIDERS
# ─────────────────────────────────────────

def get_ollama_llm():
    """Returns an Ollama chat completions wrapper."""
    try:
        import requests  # noqa: F401
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "requests", "-q"], check=True)

    def invoke(messages: list[dict]) -> "OllamaResponse":
        import requests as _req
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
        }
        resp = _req.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return OllamaResponse(content=data["message"]["content"])

    return LocalLLM(invoke)


class OllamaResponse:
    """Minimal chat response object."""
    def __init__(self, content: str):
        self.content = content
        self.role = "assistant"


class LocalLLM:
    """Unified local LLM wrapper."""
    def __init__(self, invoke_fn):
        self._invoke = invoke_fn

    def invoke(self, messages: list[dict]) -> OllamaResponse:
        return self._invoke(messages)

    def __call__(self, messages: list[dict]) -> OllamaResponse:
        return self._invoke(messages)


# Singleton LLM instance
_llm_instance = None

def get_llm() -> LocalLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_ollama_llm()
    return _llm_instance

def reset_llm():
    global _llm_instance
    _llm_instance = None


# ─────────────────────────────────────────
# ZO TOOL ADAPTERS
# ─────────────────────────────────────────
# These functions are registered in ToolRegistry
# They replicate the signatures of Zo tools.

def bash_tool(cmd: str, cwd: str | None = None) -> str:
    """
    Execute a bash command via subprocess.
    Mirrors Zo's run_bash_command.
    """
    import subprocess
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"Bash command failed (code {result.returncode}): {output}")
    return output


def read_file_tool(
    target_file: str,
    text_start_line_1_indexed: int | None = None,
    text_end_line_1_indexed_inclusive: int | None = None,
    text_read_entire_file: bool = False,
) -> str:
    """
    Read a file, optionally limited to a line range.
    Mirrors Zo's read_file.
    """
    with open(target_file, "r", encoding="utf-8") as f:
        if text_read_entire_file:
            return f.read()
        if text_start_line_1_indexed:
            lines = f.readlines()
            start = max(0, text_start_line_1_indexed - 1)
            end = None if text_end_line_1_indexed_inclusive is None else text_end_line_1_indexed_inclusive
            return "".join(lines[start:end])
        return f.read()


def write_file_tool(target_file: str, content: str) -> dict:
    """Write content to a file. Mirrors create_or_rewrite_file."""
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)
    return {"written": target_file, "size": len(content)}


def edit_file_tool(target_file: str, operations: list[dict]) -> dict:
    """
    Apply edit operations to a file.
    operations: list of {op: "replace_block" | "insert_after" | ...}
    Simplified — uses string replacement.
    """
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Simplified: handle only replace_block for now
    for op in operations:
        if op.get("op") == "replace_block":
            old_text = op.get("old_text", "")
            new_text = op.get("new_text", "")
            content = content.replace(old_text, new_text, 1)

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)

    return {"edited": target_file, "ops_applied": len(operations)}


def grep_tool(
    location: str = "USER",
    query: str = "",
    include_pattern: str = "",
    exclude_pattern: str = "",
    search_kind: str = "content",
) -> list[str]:
    """
    Grep search in files.
    location: "USER" | "CONVERSATION" | "ALL_CONVERSATIONS"
    search_kind: "content" | "filename"
    """
    import subprocess

    if location == "USER":
        base = "/home/workspace"
    elif location == "CONVERSATION":
        base = "/home/.z/workspaces/con_ZoI9U0rUs53KBUBN"
    else:
        base = "/home/workspace"

    cmd = ["grep", "-rn"]
    if exclude_pattern:
        cmd += ["--exclude", exclude_pattern]
    if include_pattern:
        cmd += ["--include", include_pattern]
    cmd += [query, base]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    return lines


def list_files_tool(path: str, ignore: list[str] | None = None) -> list[str]:
    """List files in a directory."""
    import os
    entries = os.listdir(path)
    if ignore:
        entries = [e for e in entries if e not in ignore]
    return entries


def create_agent_tool(
    instruction: str,
    rrule: str,
    delivery_method: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Create a scheduled agent via Zo API.
    This calls the Zo agent creation endpoint.
    """
    import os
    import requests

    zo_api_key = os.environ.get("ZO_API_KEY", "")
    if not zo_api_key:
        return {"error": "ZO_API_KEY not set — agent creation unavailable"}

    # Use Zo's internal agent creation
    # Note: this uses the /zo/ask API for sub-agents
    payload = {
        "input": instruction,
        "model_name": model or "vercel:minimax/minimax-m2.7",
    }
    resp = requests.post(
        "https://api.zo.computer/zo/ask",
        headers={
            "Authorization": os.environ.get("ZO_CLIENT_IDENTITY_TOKEN", ""),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    return {"status": "ok", "response": resp.json()}


# ─────────────────────────────────────────
# REGISTER TOOLS
# ─────────────────────────────────────────

def register_all_tools(registry):
    """Register all adapted tools in the given ToolRegistry."""
    registry.register("bash", bash_tool)
    registry.register("read_file", read_file_tool)
    registry.register("write_file", write_file_tool)
    registry.register("edit_file", edit_file_tool)
    registry.register("grep", grep_tool)
    registry.register("list_files", list_files_tool)
    registry.register("create_agent", create_agent_tool)


# Auto-register on import
from langgraph_core import TOOL_REGISTRY
register_all_tools(TOOL_REGISTRY)