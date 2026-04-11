"""
TAAR v15 — Replay Engine (Deterministic Execution Reconstruction)
Replays any audit chain deterministically.
Given same audit ledger → produces identical state reconstruction.
"""

from __future__ import annotations
import hashlib
import json
from typing import Any


class ReplayEngine:
    """
    Deterministic replay of execution chains.
    Used for: verification, debugging, forensic analysis.
    """

    def __init__(self):
        self.replay_count = 0

    def replay(self, audit_chain: list[dict]) -> dict:
        """
        Replay entire audit chain → reconstruct execution state.
        Deterministic: same chain → same state.
        """
        self.replay_count += 1
        state = {
            "replay_id":   f"replay_{self.replay_count:04d}",
            "blocks_replayed": 0,
            "actions": [],
            "system_state": {},
            "errors": [],
        }

        for block in audit_chain:
            entry = block.get("entry", {})
            self._apply(entry, state)

        state["blocks_replayed"] = len(audit_chain)
        state["replay_hash"] = self._state_hash(state)
        return state

    def replay_from_ledger(self, ledger) -> dict:
        """Replay from an AuditLedger object."""
        return self.replay(ledger.chain)

    def verify_replay(self, audit_chain: list[dict], expected_hash: str) -> bool:
        """
        Verify replay integrity: replay chain and compare hash.
        """
        state = self.replay(audit_chain)
        return state.get("replay_hash") == expected_hash

    def _apply(self, entry: dict, state: dict) -> None:
        """Apply a single entry to the replay state."""
        state["actions"].append(entry)
        etype = entry.get("type", "unknown")
        cmd = entry.get("command", entry.get("path", "?"))

        if etype == "shell":
            state["system_state"]["last_command"] = cmd
            state["system_state"]["last_result"] = "EXECUTED"
        elif etype == "read_file":
            key = f"file_read:{entry.get('path', '?')}"
            state["system_state"][key] = "OK"
        elif etype == "write_file":
            key = f"file_write:{entry.get('path', '?')}"
            state["system_state"][key] = "WRITTEN"
        elif etype == "delete_file":
            key = f"file_deleted:{entry.get('path', '?')}"
            state["system_state"][key] = "DELETED"
        elif etype == "git":
            state["system_state"]["last_git_command"] = cmd
        else:
            state["system_state"][f"action_{etype}"] = cmd

    def _state_hash(self, state: dict) -> str:
        """Deterministic hash — only from replay artifacts, not replay metadata."""
        # Only deterministic fields
        deterministic = {
            "blocks_replayed": state["blocks_replayed"],
            "actions": state["actions"],
            "system_state": state["system_state"],
        }
        serialized = json.dumps(deterministic, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


# ─── Test ─────────────────────────────────────────────────────────────────────

def main():
    from audit_ledger import AuditLedger

    # Build a ledger
    ledger = AuditLedger()
    events = [
        {"type": "shell", "command": "ls -la"},
        {"type": "read_file", "path": "README.md"},
        {"type": "git", "command": "git status"},
        {"type": "shell", "command": "ruff check agents/"},
    ]
    for ev in events:
        ledger.append(ev)

    # Replay
    engine = ReplayEngine()
    state = engine.replay(ledger.chain)

    print(f"Replay ID: {state['replay_id']}")
    print(f"Blocks replayed: {state['blocks_replayed']}")
    print(f"State hash: {state['replay_hash'][:16]}")
    print(f"\nActions ({len(state['actions'])}):")
    for a in state["actions"]:
        print(f"  {a.get('type')} | {a.get('command') or a.get('path', '')}")

    # Verify determinism — replay again
    state2 = engine.replay(ledger.chain)
    print(f"\nDeterminism check: {'PASS ✅' if state['replay_hash'] == state2['replay_hash'] else 'FAIL ❌'}")

    # Chain tamper detection
    tampered_chain = list(ledger.chain)
    tampered_chain[1] = {**tampered_chain[1], "entry": {"type": "shell", "command": "rm -rf /"}}
    state3 = engine.replay(tampered_chain)
    print(f"Tamper detected: {'YES ✅' if state3['replay_hash'] != state['replay_hash'] else 'NO ❌'}")


if __name__ == "__main__":
    main()
