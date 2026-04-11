"""
TAAR v15 — Audit Ledger (Immutable Hash Chain)
Every execution event is recorded with cryptographic chaining.
Tampering with any entry breaks the entire chain.
"""

from __future__ import annotations
import hashlib
import json
import time
from typing import Any


class AuditLedger:
    """
    Append-only hash chain ledger.
    Each entry: {entry, hash, prev_hash, ts, seq}
    Genesis block: prev_hash = "GENESIS"
    """

    GENESIS = "GENESIS"
    LEDGER_VERSION = "v15"

    def __init__(self, label: str = "default"):
        self.label = label
        self.chain: list[dict] = []
        self.seq = 0

    def append(
        self,
        entry: dict,
        proof_id: str | None = None,
        trace_hash: str | None = None,
        verdict: str | None = None,
    ) -> dict:
        """
        Append a new entry to the ledger.
        Returns the ledger block with hash chain links.
        """
        self.seq += 1
        prev_hash = self.chain[-1]["hash"] if self.chain else self.GENESIS

        block = {
            "seq":        self.seq,
            "ts":         time.time(),
            "entry":      entry,
            "proof_id":   proof_id,
            "trace_hash": trace_hash,
            "verdict":    verdict,
            "prev_hash":  prev_hash,
            "ledger":     self.LEDGER_VERSION,
        }

        # Hash everything for tamper-evidence
        block["hash"] = self._hash_block(block)

        self.chain.append(block)
        return block

    def verify(self) -> tuple[bool, str]:
        """
        Verify entire chain integrity.
        Returns (valid, error_msg).
        """
        if not self.chain:
            return True, "empty ledger"

        for i, block in enumerate(self.chain):
            expected_hash = self._hash_block(block)
            if block["hash"] != expected_hash:
                return False, f"block {i} hash mismatch — tampered"

            if i > 0:
                expected_prev = self.chain[i - 1]["hash"]
                if block["prev_hash"] != expected_prev:
                    return False, f"chain broken at block {i}"

        return True, "ledger intact"

    def get_audit_trail(
        self,
        filter_verdict: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Query the audit trail."""
        entries = self.chain
        if filter_verdict:
            entries = [b for b in entries if b.get("verdict") == filter_verdict]
        if limit:
            entries = entries[-limit:]
        return entries

    def last_hash(self) -> str:
        return self.chain[-1]["hash"] if self.chain else self.GENESIS

    def _hash_block(self, block: dict) -> str:
        """Deterministic hash — excludes the 'hash' field itself."""
        payload = {
            k: v for k, v in block.items()
            if k not in ("hash",)
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


# ─── Test ─────────────────────────────────────────────────────────────────────

def main():
    ledger = AuditLedger("test_ledger")

    # Simulate 4 execution events
    events = [
        {"type": "shell", "command": "ls -la", "user": "admin"},
        {"type": "read_file", "path": "README.md", "user": "copilot"},
        {"type": "git", "command": "git status", "user": "admin"},
        {"type": "shell", "command": "ruff check agents/", "user": "ci"},
    ]

    for ev in events:
        block = ledger.append(ev, proof_id=f"pf_{ev['seq']:03d}" if "seq" in ev else None)
        print(f"Block {block['seq']}: hash={block['hash'][:16]} prev={block['prev_hash'][:6]}")

    # Verify
    valid, msg = ledger.verify()
    print(f"\nLedger verify: {valid} — {msg}")
    print(f"Last hash: {ledger.last_hash()[:16]}")

    # Query
    print(f"\nAll entries: {len(ledger.chain)}")
    for b in ledger.get_audit_trail(limit=2):
        print(f"  [{b['seq']}] {b['entry']} verdict={b.get('verdict')}")


if __name__ == "__main__":
    main()
