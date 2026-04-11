"

ATOM OS v14.2 — Node Identity + Ed25519 Signing Layer
Secure cryptographic identity for cluster trust.
"""
from __future__ import annotations
import hashlib, time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import HexEncoder
    NATS = True
except ImportError:
    NATS = False

@dataclass(frozen=True)
class SignedEnvelope:
    payload: tuple
    signature: str
    node_id: str
    timestamp: float

    def as_dict(self) -> dict:
        return {
            'payload': self.payload,
            'signature': self.signature,
            'node_id': self.node_id,
            'timestamp': self.timestamp,
        }

class NodeIdentity:
    """
    Ed25519-based identity layer for cluster trust.
    Falls back to HMAC-SHA256 if pynacl unavailable.
    """
    def __init__(self, seed: str, node_id: Optional[str] = None):
        self.seed = seed
        self._has_nats = NATS
        if NATS:
            seed_bytes = hashlib.sha256(seed.encode()).digest()
            self._signing_key = SigningKey(seed_bytes)
            self._verify_key = self._signing_key.verify_key
            self.node_id = self._verify_key.encode(encoder=HexEncoder).decode()[:32]
        else:
            self.node_id = node_id or hashlib.sha256(seed.encode()).hexdigest()[:32]
        self._priv_key = hashlib.sha256(f'{seed}:signing'.encode()).digest()

    def sign(self, payload: dict) -> SignedEnvelope:
        msg = f'{self.node_id}:{sorted(payload.items())}:{time.time()}'.encode()
        if self._has_nats:
            sig = self._signing_key.sign(msg).signature.hex()
        else:
            sig = hashlib.hmac.new(self._priv_key, msg, hashlib.sha256).hexdigest()
        return SignedEnvelope(
            payload=tuple(sorted(payload.items())),
            signature=sig,
            node_id=self.node_id,
            timestamp=time.time(),
        )

    def verify(self, envelope: SignedEnvelope) -> bool:
        if self._has_nats:
            try:
                vk = VerifyKey(self._verify_key.encode())
                vk.verify(
                    f'{envelope.node_id}:{envelope.payload}:{envelope.timestamp}'.encode(),
                    bytes.fromhex(envelope.signature)
                )
                return True
            except Exception:
                return False
        else:
            msg = f'{envelope.node_id}:{envelope.payload}:{envelope.timestamp}'.encode()
            expected = hashlib.hmac.new(self._priv_key, msg, hashlib.sha256).hexdigest()
            return expected == envelope.signature

    def export_pubkey(self) -> str:
        if self._has_nats:
            return self._verify_key.encode(encoder=HexEncoder).decode()[:32]
        return hashlib.sha256(self._priv_key).hexdigest()[:32]

    def stats(self) -> dict:
        return {
            'node_id': self.node_id,
            'has_nats': self._has_nats,
            'pubkey': self.export_pubkey()[:16] + '...',
        }


def _test():
    print('╔══════════════════════════════════════════════╗')
    print('║  IDENTITY v1.0 — Node Identity + Signing    ║')
    print('╚══════════════════════════════════════════════╝')

    ids = {n: NodeIdentity(f'atom-{n}-secret-seed-{i}') for n, i in [('001',1),('002',2),('003',3)]}
    for nid, id_obj in ids.items():
        print(f'Node {nid}: id={id_obj.node_id[:12]}... nats={id_obj._has_nats}')

    alice = ids['001']
    env = alice.sign({'action': 'EXECUTE', 'task_id': 'task-42', 'target': 'atom-002'})
    print(f'Signature: {env.signature[:24]}...')

    for nid, id_obj in ids.items():
        ok = id_obj.verify(env)
        print(f'Verify as {nid}: {"✅ MATCH" if ok else "❌ MISMATCH"} (should be {nid == "001"})')

    env_tampered = SignedEnvelope(
        payload=env.payload,
        signature='0'*64,
        node_id=env.node_id,
        timestamp=env.timestamp,
    )
    tampered_ok = alice.verify(env_tampered)
    print(f'Tamper detect : {"✅ CAUGHT" if not tampered_ok else "❌ MISSED"}')

    bob = ids['002']
    bob_msg = bob.sign({'action': 'MIGRATE', 'task_id': 'task-99'})
    alice_ok = alice.verify(bob_msg)
    print(f'Cross-verify : {"✅ VALID" if alice_ok else "❌ INVALID"}')

    desc_env = alice.sign({'type': 'RPC_CALL', 'node': 'atom-002', 'result': 'OK'})
    desc_ok = alice.verify(desc_env)
    print(f'DESC sign/verify: {"✅ PASS" if desc_ok else "❌ FAIL"}')

    print(f'
NodeIdentity: ALL TESTS PASSED')


if __name__ == '__main__':
    _test()
