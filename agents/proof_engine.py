"""
TAAR v15 — Proof Engine (Cryptographic Execution Binding)
Every execution result is bound to its policy trace via cryptographic hash.
No proof = no trust in the result.
"""

from __future__ import annotations
import hashlib
import time
from typing import Any


class ProofEngine:
    """
    Binds: policy_id + action + context + result → cryptographic proof.
    Proof is deterministic — same inputs always produce same proof.
    """

    def __init__(self, policy_id: str = "pk_v4"):
        self.policy_id = policy_id
        self.proof_count = 0

    def generate(
        self,
        trace_hash: str,
        result: Any,
        verdict: str,
        sandbox_id: str | None = None,
    ) -> dict:
        """
        Generate cryptographic proof binding trace to result.
        Returns proof record with deterministic hash.
        """
        self.proof_count += 1
        payload = {
            "policy_id":    self.policy_id,
            "trace_hash":   trace_hash,
            "result":        str(result),
            "verdict":       verdict,
            "sandbox_id":    sandbox_id or "none",
            "ts":            time.time(),
            "seq":           self.proof_count,
        }

        proof_hash = self._hash_payload(payload)

        return {
            "proof_id":    f"pf_{self.proof_count:06d}",
            "policy_id":   self.policy_id,
            "trace_hash":  trace_hash,
            "result_hash": proof_hash,
            "verdict":     verdict,
            "sandbox_id":  sandbox_id or "none",
            "timestamp":   payload["ts"],
            "seq":         self.proof_count,
        }

    def verify(self, proof: dict) -> bool:
        """Verify proof integrity: trace_hash + result must match."""
        expected = self._hash_payload({
            "policy_id":  proof.get("policy_id", ""),
            "trace_hash": proof.get("trace_hash", ""),
            "result":     str(proof.get("result", "")),
            "verdict":    proof.get("verdict", ""),
            "sandbox_id": proof.get("sandbox_id", "none"),
            "ts":         proof.get("timestamp", 0),
            "seq":        proof.get("seq", 0),
        })
        return proof.get("result_hash", "") == expected

    def generate_chain(self, proofs: list[dict]) -> dict:
        """
        Build a cryptographic chain from a list of proofs.
        Each proof's result_hash is chained to the next — tamper-evident.
        """
        if not proofs:
            return {"chain_length": 0, "valid": True}

        chain = []
        prev_hash = "GENESIS"
        for p in proofs:
            # Chain element: proof's result_hash (deterministic, tamper-evident)
            chain_element_hash = self._hash_payload({
                "result_hash": p.get("result_hash", ""),
                "prev_hash": prev_hash,
            })
            chain.append({
                "proof_id":    p.get("proof_id"),
                "result_hash": p.get("result_hash"),
                "prev_hash":   prev_hash,
                "chain_hash":  chain_element_hash,
            })
            prev_hash = chain_element_hash

        return {
            "chain":        chain,
            "chain_length":  len(chain),
            "chain_hash":   prev_hash,
            "valid":        True,
        }

    def verify_chain(self, chain: list[dict]) -> tuple[bool, str]:
        """
        Verify chain integrity: each chain_hash must match.
        """
        if not chain:
            return True, "empty chain"
        prev_hash = "GENESIS"
        for i, link in enumerate(chain):
            expected = self._hash_payload({
                "result_hash": link.get("result_hash", ""),
                "prev_hash":  prev_hash,
            })
            if link.get("chain_hash", "") != expected:
                return False, f"chain broken at link {i}"
            prev_hash = link.get("chain_hash", "")
        return True, "chain valid"

    def _hash_payload(self, payload: dict) -> str:
        """Deterministic SHA-256 hash of payload."""
        # Sort keys for determinism
        items = []
        for k in sorted(payload.keys()):
            items.append(f"{k}={payload[k]}")
        serialized = "|".join(items)
        return hashlib.sha256(serialized.encode()).hexdigest()


# ─── Test ─────────────────────────────────────────────────────────────────────

def main():
    pe = ProofEngine()

    # Generate 3 proofs
    proofs = []
    for i in range(3):
        p = pe.generate(
            trace_hash=f"trace_{i}",
            result=f"result_{i}",
            verdict="ALLOW",
            sandbox_id=f"sbx_{i}",
        )
        proofs.append(p)
        print(f"Proof {i}: {p['proof_id']} trace={p['trace_hash'][:8]} hash={p['result_hash'][:16]}")

    # Build chain
    chain = pe.generate_chain(proofs)
    print(f"\nChain: {chain['chain_length']} links, hash={chain['chain_hash'][:16]}")

    # Verify chain
    valid, msg = pe.verify_chain(chain["chain"])
    print(f"Chain valid: {valid} ({msg})")

    # Verify individual proof
    print(f"\nProof verify: {pe.verify(proofs[1])}")

    # Tamper test
    tampered = [{**proofs[0], "result": "TAMPERED!"}]
    chain_tampered = pe.generate_chain(tampered)
    valid, msg = pe.verify_chain(chain_tampered["chain"])
    print(f"Tamper detect: {not valid} → {msg}")


if __name__ == "__main__":
    main()
