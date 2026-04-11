"""
TAAR DevOps — Patch Engine
generate_patch(analysis: dict) → dict with command + description
apply_patch(repo_path: str, patch: dict) → bool
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────
# PATCH TYPES
# ─────────────────────────────────────────

class PatchType:
    RUFF_FIX = "ruff_fix"       # auto: ruff --fix
    BLACK_FIX = "black_fix"    # auto: black
    PIP_INSTALL = "pip_install" # auto: pip install <package>
    ENV_VAR = "env_var"        # auto: export VAR=value
    EDIT_FILE = "edit_file"     # manual: sed/AST edit
    MANUAL = "manual"           # manual review required


# ─────────────────────────────────────────
# API
# ─────────────────────────────────────────

def generate_patch(analysis: dict[str, Any], context: str = "") -> dict[str, Any]:
    """
    Generate a patch from analysis result.

    Args:
        analysis: from ci_analyzer.analyze_logs()
        context: raw CI log text (optional, for context-aware patches)

    Returns:
        {
            "type": str,          # PatchType value
            "command": str | None,# shell command to apply (None for manual)
            "description": str,   # human-readable description
            "auto": bool,         # True if auto-applicable
            "target": str | None, # file path or package name
            "confidence": float,  # 0.0–1.0
        }
    """
    ft = analysis.get("failure_type", "")
    fp = analysis.get("file_path", "")
    ln = analysis.get("line_number")
    suggestion = analysis.get("suggestion", "")

    # ── RUFF ──────────────────────────────────────────────
    if ft in ("ruff_error", "ruff_warning") and fp:
        return {
            "type": PatchType.RUFF_FIX,
            "command": f"ruff check --fix {fp}",
            "description": f"Ruff auto-fix for {os.path.basename(fp)}:{ln} — {analysis.get('error_code', '')}",
            "auto": True,
            "target": fp,
            "confidence": 0.95,
        }

    # ── IMPORT ERROR → PIP INSTALL ─────────────────────────
    if ft == "import_error":
        module = analysis.get("details", {}).get("module_name") or analysis.get("error_code", "")
        if module:
            # Try to find which package provides this module
            package = _module_to_package(module)
            return {
                "type": PatchType.PIP_INSTALL,
                "command": f"pip install {package}",
                "description": f"Install missing package: {package} (module: {module})",
                "auto": True,
                "target": package,
                "confidence": 0.80,
            }

    # ── PYTEST FAILURE ────────────────────────────────────
    if ft == "pytest_failure":
        return {
            "type": PatchType.MANUAL,
            "command": None,
            "description": f"Pytest failure requires manual fix: {suggestion}",
            "auto": False,
            "target": fp,
            "confidence": 0.0,
        }

    # ── FALLBACK ─────────────────────────────────────────
    return {
        "type": PatchType.MANUAL,
        "command": None,
        "description": suggestion or "manual fix required",
        "auto": False,
        "target": fp,
        "confidence": 0.0,
    }


def apply_patch(repo_path: str, patch: dict[str, Any]) -> bool:
    """
    Apply a generated patch to the repository.

    Returns:
        True if patch was applied successfully,
        False if patch failed or was manual type.
    """
    if not patch.get("auto", False):
        return False

    if not patch.get("command"):
        return False

    try:
        result = subprocess.run(
            patch["command"],
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode in (0, 1)  # 1 = fixes applied
    except Exception:
        return False


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _module_to_package(module: str) -> str:
    """Map Python module name to pip package name (common cases)."""
    KNOWN = {
        "numpy": "numpy",
        "pandas": "pandas",
        "yaml": "pyyaml",
        "PIL": "pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "requests": "requests",
        " bs4": "beautifulsoup4",
        "lxml": "lxml",
        "matplotlib": "matplotlib",
        "scipy": "scipy",
    }
    base = module.split(".")[0].split("[")[0].strip()
    return KNOWN.get(base, base)
