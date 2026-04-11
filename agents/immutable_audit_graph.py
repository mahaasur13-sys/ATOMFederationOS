"""
TAAR v10.1 — Immutable Audit Graph
Every action → hashed → stored → replayable.

The audit graph is the source of truth for EVERYTHING that happens.
It is append-only and hash-chained (like a blockchain).

Principles:
    1. Every node = one action/event
    2. Every node references previous node hash (chain integrity)
    3. State cannot be retroactively modified
    4. Full replay possible from genesis
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import hashlib
import json
import time
import uuid


@dataclass
class AuditNode:
    """A single node in the audit graph — immutable once written."""
    node_id: str
    action_id: str
    proof_id: Optional[str]
    node_type: str          # "action" | "policy_verdict" | "infra_change" | "state_snapshot"
    payload: dict           # All relevant data
    prev_hash: str          # Hash of the previous node
    node_hash: str          # This node's hash
    timestamp: float
    sequence: int          # Monotonic sequence number

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "action_id": self.action_id,
            "proof_id": self.proof_id,
            "node_type": self.node_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "node_hash": self.node_hash,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }


class ImmutableAuditGraph:
    """
    Append-only, hash-chained audit graph.

    Every significant event is recorded as a node with:
        - A reference to the previous node's hash (chain integrity)
        - A hash of this node's content (tamper detection)
        - Full payload for replay/debugging

    The graph is append-only. There is no update() or delete().
    To "revoke" something, you add a revocation node — you never remove.
    """

    GENESIS_HASH = "0" * 64  # Hash of the first node

    def __init__(self):
        self.nodes: list[AuditNode] = []
        self._seq = 0
        self._last_hash = self.GENESIS_HASH

    def add_node(
        self,
        action_id: str,
        node_type: str,
        payload: dict,
        proof_id: Optional[str] = None,
    ) -> AuditNode:
        """
        Add a new node to the audit graph.
        Chain integrity is maintained automatically.
        """
        self._seq += 1

        node = AuditNode(
            node_id=f"AUD-{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            proof_id=proof_id,
            node_type=node_type,
            payload=payload,
            prev_hash=self._last_hash,
            node_hash="",  # Computed below
            timestamp=time.time(),
            sequence=self._seq,
        )

        # Compute hash of this node (covers all fields except node_hash itself)
        node.node_hash = self._hash_node(node)

        # Append to chain
        self.nodes.append(node)
        self._last_hash = node.node_hash

        return node

    def _hash_node(self, node: AuditNode) -> str:
        """Compute SHA-256 hash of a node's content."""
        payload = json.dumps(node.payload, sort_keys=True, default=str)
        content = (
            f"{node.node_id}"
            f"{node.action_id}"
            f"{node.proof_id or ''}"
            f"{node.node_type}"
            f"{payload}"
            f"{node.prev_hash}"
            f"{node.timestamp}"
            f"{node.sequence}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_chain(self) -> tuple[bool, list[str]]:
        """
        Verify the entire chain integrity.
        Returns (is_valid, list_of_errors).
        """
        errors = []
        expected_prev = self.GENESIS_HASH

        for node in self.nodes:
            if node.prev_hash != expected_prev:
                errors.append(f"Chain broken at node {node.node_id}: "
                              f"expected prev={expected_prev[:16]}, got {node.prev_hash[:16]}")
            if node.node_hash != self._hash_node(node):
                errors.append(f"Tamper detected at node {node.node_id}: hash mismatch")
            expected_prev = node.node_hash

        return len(errors) == 0, errors

    def get_node(self, node_id: str) -> Optional[AuditNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_action_trail(self, action_id: str) -> list[AuditNode]:
        """Get all nodes related to a specific action_id."""
        return [n for n in self.nodes if n.action_id == action_id]

    def get_proof_trail(self, proof_id: str) -> list[AuditNode]:
        """Get all nodes related to a specific proof_id."""
        return [n for n in self.nodes if n.proof_id == proof_id]

    def replay_from(self, since_sequence: int = 0) -> list[dict]:
        """Replay all nodes from a given sequence number."""
        return [
            n.to_dict() for n in self.nodes
            if n.sequence > since_sequence
        ]

    def get_stats(self) -> dict:
        """Return audit graph statistics."""
        by_type = {}
        for node in self.nodes:
            by_type[node.node_type] = by_type.get(node.node_type, 0) + 1

        chain_valid, errors = self.verify_chain()

        return {
            "total_nodes": len(self.nodes),
            "by_type": by_type,
            "chain_valid": chain_valid,
            "chain_errors": len(errors),
            "last_hash": self._last_hash[:16] + "...",
            "genesis": self.GENESIS_HASH[:16] + "...",
            "duration_seconds": (
                self.nodes[-1].timestamp - self.nodes[0].timestamp
                if len(self.nodes) > 1 else 0
            ),
        }


# ── Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    graph = ImmutableAuditGraph()

    # Node 1: Policy verdict
    n1 = graph.add_node(
        action_id="ACT-001",
        node_type="policy_verdict",
        payload={"verdict": "allow", "risk_score": 0.3},
        proof_id="PRF-abc123",
    )
    print(f"[NODE 1] {n1.node_id} | prev={n1.prev_hash[:8]}... | hash={n1.node_hash[:8]}...")

    # Node 2: Action executed
    n2 = graph.add_node(
        action_id="ACT-001",
        node_type="action",
        payload={"status": "executed", "simulated": True},
        proof_id="PRF-abc123",
    )
    print(f"[NODE 2] {n2.node_id} | prev={n2.prev_hash[:8]}... | hash={n2.node_hash[:8]}...")

    # Node 3: State snapshot
    n3 = graph.add_node(
        action_id="SNAP-001",
        node_type="state_snapshot",
        payload={"nodes": 5, "cpu_total": 40, "ram_gb": 80},
    )
    print(f"[NODE 3] {n3.node_id} | prev={n3.prev_hash[:8]}...")

    # Verify chain
    valid, errors = graph.verify_chain()
    print(f"\n[CHAIN] valid={valid} | errors={len(errors)}")
    print(f"Stats: {graph.get_stats()}")

    # Replay from node 1
    trail = graph.get_action_trail("ACT-001")
    print(f"\n[REPLAY] action ACT-001: {len(trail)} nodes")
    for node in trail:
        print(f"  [{node.node_type}] {node.payload}")
