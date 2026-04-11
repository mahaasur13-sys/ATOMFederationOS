"""
TAAR DevOps — CI Log Analyzer
analyze_logs(ci_logs: str) → dict with root_cause, file_path, line_number, failure_type
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class FailureType(str, Enum):
    PYTEST_FAILURE = "pytest_failure"
    RUFF_ERROR = "ruff_error"
    RUFF_WARNING = "ruff_warning"
    IMPORT_ERROR = "import_error"
    IMPORT_ERROR_ALT = "importerror"
    PIP_INSTALL_ERROR = "pip_install_error"
    PYTHON_SYNTAX = "python_syntax"
    YAML_ERROR = "yaml_error"
    GITHUB_ACTIONS = "github_actions"
    UNKNOWN = "unknown"


# Each pattern uses (?P<name>...) named groups so groupdict() works
_PATTERNS = [
    # Space-separated: ERROR: E999 path:line or ERROR: E999 path:line: message
    (FailureType.RUFF_ERROR,
     re.compile(r"ERROR:\s+(?P<error_code>[A-Z]\d+)\s+(?P<file_path>\S+?\.py):(?P<line_number>\d+):\s*(?P<message>.*)")),
    # ── RUFF (anchored=false to handle "Run ruff check ..." prefixes) ──
    # Strip "ruff error" prefix text first, then match file.py:line:col:code message
    (FailureType.RUFF_ERROR,
     re.compile(r"(?:[Rr]uff\s+[Ee]rror\s+)?(?P<file_path>[^:\s]+\.py)\s*:(?P<line_number>\d+):\d+:\s+(?P<error_code>[A-Z]\d+)\s*(?P<message>.*)")),
    (FailureType.RUFF_WARNING,
     re.compile(r"(?:[Rr]uff\s+[Ww]arning\s+)?(?P<file_path>[^:\s]+\.py)\s*:(?P<line_number>\d+):\d+:\s+(?P<error_code>[A-ZW]\d+)\s*(?P<message>.*)")),
    (FailureType.PYTEST_FAILURE,
     re.compile(r"FAILED\s+(?P<test_path>[^:]+::[^:]+)(?::(?P<details>.+))?")),

    (FailureType.IMPORT_ERROR,
     re.compile(r"ModuleNotFoundError:\s*No module named\s+[\"']?(?P<module_name>[^\s\"']+)")),
    (FailureType.IMPORT_ERROR_ALT,
     re.compile(r"ImportError:\s*(?P<import_detail>.+?)(?:\n|$)")),
    (FailureType.PIP_INSTALL_ERROR,
     re.compile(r"(?:ERROR:\s+)?Could not find a version that satisfies the requirement\s+(?P<package_name>[^\s]+)")),
    (FailureType.PYTHON_SYNTAX,
     re.compile(r"SyntaxError:\s*(?P<syntax_error>.+)")),
    (FailureType.YAML_ERROR,
     re.compile(r"yaml\.(?:safe_load|scan|parse|YAMLError):\s*(?P<yaml_error>.+)")),
    (FailureType.GITHUB_ACTIONS,
     re.compile(r"(?:Error|FAIL|FAILED|error):\s*(?P<ga_message>.+)")),

]

_SUGGESTIONS = {
    FailureType.IMPORT_ERROR: "pip install {module_name}",
    FailureType.PIP_INSTALL_ERROR: "check package name — version may not exist",
    FailureType.PYTEST_FAILURE: "fix test or update assertion",
    FailureType.RUFF_ERROR: "auto-fix with: ruff check --fix {file_path}",
    FailureType.RUFF_WARNING: "auto-fix with: ruff check --fix {file_path}",
    FailureType.PYTHON_SYNTAX: "fix syntax error in source",
    FailureType.YAML_ERROR: "validate YAML syntax",
    FailureType.UNKNOWN: "manual investigation required",
}


def analyze_logs(ci_logs: str) -> dict[str, Any]:
    for ft_enum, pattern in _PATTERNS:
        m = pattern.search(ci_logs)
        if not m:
            continue

        gd = m.groupdict()
        ft_val = ft_enum.value

        if ft_val in ("ruff_error", "ruff_warning"):
            safe_gd = {k: str(v) for k, v in gd.items() if v is not None}
            tpl = _SUGGESTIONS.get(ft_enum, "fix manually")
            try:
                suggestion = tpl.format_map(safe_gd)
            except (KeyError, ValueError):
                suggestion = tpl
            return {
                "root_cause": f"{gd.get('error_code', '?')}: {gd.get('message', '').strip()}",
                "failure_type": ft_val,
                "file_path": gd.get("file_path"),
                "line_number": int(gd["line_number"]) if gd.get("line_number") else None,
                "error_code": gd.get("error_code"),
                "suggestion": suggestion,
                "details": gd,
            }

        if ft_val == "pytest_failure":
            test_path = gd.get("test_path", "") or ""
            return {
                "root_cause": f"Test failed: {test_path}",
                "failure_type": ft_val,
                "file_path": test_path.split("::")[0] if test_path else None,
                "line_number": None,
                "error_code": gd.get("details"),
                "suggestion": _SUGGESTIONS.get(ft_enum, "fix test"),
                "details": gd,
            }

        if ft_val in ("import_error",):
            module = (gd.get("module_name") or "").strip()
            return {
                "root_cause": f"Missing module: {module}",
                "failure_type": "import_error",
                "file_path": None,
                "line_number": None,
                "error_code": "ModuleNotFoundError",
                "suggestion": f"pip install {module}" if module else "pip install <module>",
                "details": gd,
            }

        if ft_val == "pip_install_error":
            return {
                "root_cause": f"Package not found: {gd.get('package_name', '')}",
                "failure_type": ft_val,
                "file_path": None,
                "line_number": None,
                "error_code": "PIP_ERROR",
                "suggestion": _SUGGESTIONS.get(ft_enum),
                "details": gd,
            }

        # Generic fallback
        first_field = list(gd.values())[0] if gd else str(m.group(0))
        return {
            "root_cause": str(first_field) if first_field else str(m.group(0)),
            "failure_type": ft_val,
            "file_path": None,
            "line_number": None,
            "error_code": None,
            "suggestion": _SUGGESTIONS.get(ft_enum, "manual fix required"),
            "details": gd,
        }

    # Fallback: ERROR: E999 path:line
    fallback = re.compile(r"ERROR:\s+(?P<error_code>[A-Z]\d+)\s+(?P<file_path>\S+?)(?::(?P<line_number>\d+))?(?:\s+[:\-]\s+(?P<message>.+))?")
    m = fallback.search(ci_logs)
    if m:
        gd = m.groupdict()
        msg = (gd.get("message") or "").strip()
        return {
            "root_cause": f"{gd.get('error_code', '?')}: {msg}",
            "failure_type": "unknown",
            "file_path": gd.get("file_path"),
            "line_number": int(gd["line_number"]) if gd.get("line_number") else None,
            "error_code": gd.get("error_code"),
            "suggestion": _SUGGESTIONS.get(FailureType.UNKNOWN, "manual investigation required"),
            "details": gd,
        }

    return {
        "root_cause": "unknown — no patterns matched",
        "failure_type": FailureType.UNKNOWN.value,
        "file_path": None,
        "line_number": None,
        "error_code": None,
        "suggestion": "manual investigation required",
        "details": {},
    }
