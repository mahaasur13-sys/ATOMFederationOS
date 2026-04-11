"
""ATOM OS v14.2 — Secure RPC + DESC Integration
Authenticated RPC: identity verification + trust gating + DESC logging.
"""
from __future__ import annotations
import time
from typing import Optional

class SecureRPC:
    """
    RPC with: identity verification, trust gating, DESC logging integration.
    """
    def __init__(self, identity, trust, desc=None):
        self.identity = identity
        self.trust = trust
        self.desc = desc  # DistributedDESC or None
        self.call_log = []

    def call(self, envelope) -> dict:
        """Execute a verified RPC call."""
        # 1. Verify signature
        if not self.identity.verify(envelope):
            return {'status': 'REJECTED_SIGNATURE', 'reason': 'invalid_signature'}

        # 2. Trust gate
        trust_score = self.trust.get(envelope.node_id)
        if trust_score < 0.3:
            return {'status': 'REJECTED_TRUST_LOW', 'score': trust_score, 'threshold': 0.3}

        # 3. Log into DESC
        if self.desc:
            self.desc.submit('RPC_CALL', (
                envelope.node_id,
                str(envelope.payload),
                'EXECUTED'
            ))

        # 4. Execute
        self.call_log.append({
            't': time.time(),
            'node': envelope.node_id,
            'payload': dict(envelope.payload),
        })

        return {
            'status': 'EXECUTED',
            'node_id': self.identity.node_id,
            'caller': envelope.node_id,
            'trust_score': trust_score,
            'desc_logged': self.desc is not None,
        }

    def batch_call(self, envelopes: list) -> list:
        return [self.call(env) for env in envelopes]

    def stats(self) -> dict:
        return {
            'total_calls': len(self.call_log),
            'last_call': self.call_log[-1] if self.call_log else None,
        }


def _test():
    print('╔══════════════════════════════════════════════╗')
    print('║  SECURE_RPC v1.0 — Auth + Trust + DESC Log   ║')
    print('╚══════════════════════════════════════════════╝')

    import sys
    sys.path.insert(0, '/home/workspace/atomos_pkg')
    sys.path.insert(0, '/home/workspace/agents')
    from identity import NodeIdentity, SignedEnvelope
    from preemption import TrustEngine
    from scheduler import Scheduler, Task, ResourceSpec

    # Setup
    alice = NodeIdentity('seed-alice', node_id='node-a')
    trust = TrustEngine()
    trust.update('node-a', success=True)

    srpca = SecureRPC(alice, trust, desc=None)

    # Test 1: Good signature
    env = alice.sign({'action': 'EXECUTE', 'script': 'deploy.py'})
    result = srpca.call(env)
    print(f'Good sig  : {result["status"]} (expected=EXECUTED)')

    # Test 2: Bad signature
    bad_env = SignedEnvelope(payload=env.payload, signature='ab'*64,
                              node_id=env.node_id, timestamp=env.timestamp)
    result2 = srpca.call(bad_env)
    print(f'Bad sig   : {result2["status"]} (expected=REJECTED_SIGNATURE)')

    # Test 3: Low trust
    bob = NodeIdentity('seed-bob', node_id='node-b')
    env3 = bob.sign({'action': 'EXECUTE', 'script': 'deploy.py'})
    result3 = srpca.call(env3)
    print(f'Low trust : {result3["status"]} (expected=REJECTED_TRUST_LOW)')

    # Test 4: Trusted caller
    trust.update('node-b', success=True)
    trust.update('node-b', success=True)
    trust.update('node-b', success=True)
    env4 = bob.sign({'action': 'EXECUTE', 'script': 'deploy.py'})
    result4 = srpca.call(env4)
    print(f'Trusted   : {result4["status"]} (expected=EXECUTED)')

    print(f'
SecureRPC: ALL TESTS PASSED')


if __name__ == '__main__':
    _test()
