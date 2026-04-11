#!/usr/bin/env python3
"""
ATOM OS — Main Bootstrap
Loads all services and registers them in the ServiceRegistry.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ── Resolve ATOM OS package root ──────────────────────────────────────────
ATOM_ROOT = Path(__file__).parent           # atomos_pkg/
ATOM_SRC  = ATOM_ROOT / "atomos"            # atomos_pkg/atomos/
WORKSPACE = Path("/home/workspace")

# Ensure workspace+atomos in path for TAAR agents
for p in (str(WORKSPACE), str(ATOM_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("atomos")


# ── Phase 0: Bootstrap ───────────────────────────────────────────────────
def _bootstrap() -> None:
    """Ensure 'agents' is resolvable before any imports."""
    if "agents" not in sys.modules:
        import types
        stub = types.ModuleType("agents")
        stub.__path__ = [str(WORKSPACE / "agents")]
        sys.modules["agents"] = stub


# ── Phase 1: Core Types ───────────────────────────────────────────────────
def _load_core_types():
    from atomos.core.types import (
        ServiceCard, ServiceHealth, HealthReport,
        ServiceRegistry as _SR, AgentCard, AuditEntry,
    )
    return _SR()


# ── Phase 2: Service Registry ─────────────────────────────────────────────
def _boot_services() -> dict:
    from atomos.core.service_registry import ServiceRegistry
    from atomos.core.boot_log import BootLog

    registry = ServiceRegistry()
    boot_log = BootLog()

    # ── Load ATOM OS core modules ──────────────────────────────────────
    core_modules = {
        "memory":        "atomos.memory.memory",
        "runtime":       "atomos.runtime.ollama_runtime",
        "vision":        "atomos.vision.camera",
        "voice":         "atomos.voice.stt_tts",
        "mcp":           "atomos.mcp.mcp_gateway",
        "observability": "atomos.observability.metrics_collector",
        "tools":         "atomos.tools.shell_tools",
        "ui":            "atomos.ui.cli",
        "swarm":         "atomos.swarm.swarm_engine",
        "devops":        "atomos.devops.devops_agent",
        "perception":    "atomos.perception.perception",
    }

    for sid, mod_path in core_modules.items():
        try:
            mod = __import__(mod_path, fromlist=[sid])
            cls = getattr(mod, sid.replace("_", "").title(), None) or getattr(mod, "Service", None)
            if cls:
                inst = cls()
                registry.register(sid, inst)
                boot_log.add(sid, "registered", "ok")
            else:
                registry.register(sid, None)
                boot_log.add(sid, "registered", "stub")
        except Exception as e:
            log.debug("[%s] skipped: %s", sid, e)
            boot_log.add(sid, "skipped", str(e)[:40])

    # ── Load TAAR agents from /home/workspace/agents ──────────────────
    _bootstrap()
    import importlib, types

    _agents_dir = WORKSPACE / "agents"
    _skip = {"trusted_context", "policy_kernel_v3", "taar_v10"}

    for _f in sorted(os.listdir(_agents_dir)):
        if not _f.endswith(".py") or _f.startswith("_") or _f[:-3] in _skip:
            continue
        _mod_name = _f[:-3]
        try:
            _mod = importlib.import_module(f"agents.{_mod_name}")
            sys.modules[_mod_name] = _mod
            # Try to register a known class from this module
            for _cls_name in ("DevOpsAgent", "SwarmEngine", "MissionController",
                              "AicOs", "TaarV14", "TaarV15"):
                if hasattr(_mod, _cls_name):
                    registry.register(_mod_name, getattr(_mod, _cls_name)())
                    boot_log.add(_mod_name, "registered", "taar")
                    break
            else:
                registry.register(_mod_name, _mod)
                boot_log.add(_mod_name, "registered", "module")
        except Exception as e:
            boot_log.add(_mod_name, "failed", str(e)[:40])

    return {"registry": registry, "boot_log": boot_log}


# ── Phase 3: CLI / REPL ──────────────────────────────────────────────────
def _run_repl(registry) -> None:
    log.info("ATOM OS REPL ready. Type 'exit' to quit.")
    while True:
        try:
            cmd = input("atomos> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd or cmd == "exit":
            break
        if cmd == "services":
            for s in registry.list_services():
                print(f"  {s}")
        elif cmd == "health":
            r = registry.health_check()
            for h in r.checks:
                print(f"  [{h.status.name}] {h.service_id}")
        elif cmd == "agents":
            from atomos.core.service_registry import list_agents
            for a in list_agents(registry):
                print(f"  {a}")
        else:
            print(f"Unknown command: {cmd}. Try: services | health | agents")


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(prog="atomos")
    parser.add_argument("--boot-only", action="store_true",
                        help="Bootstrap and print boot report, then exit.")
    parser.add_argument("--services", action="store_true",
                        help="List all registered services.")
    parser.add_argument("--health", action="store_true",
                        help="Run health checks for all services.")
    args = parser.parse_args()

    log.info("ATOM OS v14.2 booting...")
    result = _boot_services()
    registry = result["registry"]
    boot_log = result["boot_log"]

    print("\n" + "=" * 60)
    print("  ATOM OS v14.2 — BOOT REPORT")
    print("=" * 60)
    for entry in boot_log.entries:
        icon = "✅" if entry.status == "ok" else ("⚠️" if entry.status == "skipped" else "❌")
        print(f"  {icon} [{entry.service_id:<35}] {entry.status} {entry.note}")
    print("=" * 60)
    print(f"  Total registered: {len(registry.list_services())}")
    print(f"  Boot status: {'ALL SYSTEMS GO' if boot_log.all_ok else 'DEGRADED MODE'}")
    print("=" * 60 + "\n")

    if args.boot_only:
        return

    if args.services:
        for s in registry.list_services():
            print(f"  {s}")
        return

    if args.health:
        r = registry.health_check()
        for h in r.checks:
            print(f"  [{h.status.name}] {h.service_id}")
        print(f"\n  Overall: {r.overall_status}")
        return

    _run_repl(registry)


if __name__ == "__main__":
    main()
