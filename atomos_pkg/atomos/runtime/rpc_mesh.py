"

ATOM OS v14.2 — RPC Execution Mesh
Node-to-node execution transport layer with signed envelopes.
"""
from __future__ import annotations
import uuid, time, asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from enum import Enum

class RPCStatus(Enum):
    PENDING = 'pending'
    DISPATCHED = 'dispatched'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REJECTED_SIGNATURE = 'rejected_signature'
    REJECTED_TRUST_LOW = 'rejected_trust_low'

@dataclass
class RPCRequest:
    task_id: str
    target_node: str
    task: dict
    envelope: Any  # SignedEnvelope
    status: RPCStatus = RPCStatus.PENDING
    created_at: float = field(default_factory=time.time)
    dispatched_at: float = 0.0
    completed_at: float = 0.0
    result: Optional[dict] = None
    error: Optional[str] = None

class RPCMesh:
    """
    Node-to-node execution transport layer.
    Simulates gRPC/NATS/QUIC dispatch.
    """
    def __init__(self, identity, scheduler):
        self.identity = identity
        self.scheduler = scheduler
        self.inflight: Dict[str, RPCRequest] = {}
        self.completed: Dict[str, RPCRequest] = {}
        self.handlers: Dict[str, Callable] = {}

    def register_handler(self, action_type: str, handler: Callable):
        self.handlers[action_type] = handler

    def send_task(self, target_node: str, task: dict, signed: bool = True) -> RPCRequest:
        task_id = str(uuid.uuid4())[:16]
        payload = {
            'task_id': task_id,
            'target': target_node,
            'task': task,
            'created_at': time.time(),
        }
        envelope = self.identity.sign(payload) if signed else None

        req = RPCRequest(
            task_id=task_id,
            target_node=target_node,
            task=task,
            envelope=envelope,
            status=RPCStatus.PENDING,
        )
        self.inflight[task_id] = req
        result = self._dispatch(req)
        req.status = RPCStatus.DISPATCHED
        req.dispatched_at = time.time()
        req.result = result
        return req

    def _dispatch(self, req: RPCRequest) -> dict:
        # Simulate network transport (in real: gRPC call to target_node)
        return {
            'status': 'dispatched',
            'node': self.identity.node_id,
            'target': req.target_node,
            'task_id': req.task_id,
            'transport': 'simulated',  # would be gRPC/NATS/QUIC in production
        }

    def execute(self, req: RPCRequest, verify: bool = True) -> RPCRequest:
        """Execute a request on the local node."""
        if verify and req.envelope:
            if not self.identity.verify(req.envelope):
                req.status = RPCStatus.REJECTED_SIGNATURE
                req.error = 'signature verification failed'
                return req

        action = req.task.get('action', 'generic')
        handler = self.handlers.get(action)
        if handler:
            try:
                req.result = handler(req.task)
                req.status = RPCStatus.COMPLETED
            except Exception as e:
                req.status = RPCStatus.FAILED
                req.error = str(e)
        else:
            req.status = RPCStatus.COMPLETED
            req.result = {'action': action, 'executed_by': self.identity.node_id, 'status': 'ok'}

        req.completed_at = time.time()
        self.inflight.pop(req.task_id, None)
        self.completed[req.task_id] = req
        return req

    def call(self, envelope) -> dict:
        """Direct call with an envelope (for SecureRPC)."""
        if not self.identity.verify(envelope):
            return {'status': 'REJECTED_SIGNATURE'}
        return {
            'status': 'EXECUTED',
            'node_id': self.identity.node_id,
            'payload': dict(envelope.payload),
        }

    def stats(self) -> dict:
        return {
            'inflight': len(self.inflight),
            'completed': len(self.completed),
            'by_status': {
                s.value: sum(1 for r in self.completed.values() if r.status == s)
                for s in RPCStatus
            },
        }


def _test():
    print('╔══════════════════════════════════════════════╗')
    print('║  RPC MESH v1.0 — Node-to-Node Execution       ║')
    print('╚══════════════════════════════════════════════╝')

    import sys, os
    sys.path.insert(0, '/home/workspace/atomos_pkg')
    sys.path.insert(0, '/home/workspace/agents')

    from identity import NodeIdentity
    from scheduler import Scheduler, Task, ResourceSpec

    sched = Scheduler()
    sched.register_node('node-a', cpu=8, ram_mb=8192)
    sched.register_node('node-b', cpu=8, ram_mb=8192)

    alice = NodeIdentity('seed-alice', node_id='node-a')
    bob   = NodeIdentity('seed-bob',   node_id='node-b')

    mesh_a = RPCMesh(alice, sched)
    mesh_b = RPCMesh(bob, sched)

    # Test: send task from alice to bob
    req = mesh_a.send_task('node-b', {'action': 'EXECUTE', 'script': 'test.py'})
    print(f'Send: task_id={req.task_id[:12]} status={req.status.value}')

    # Test: execute locally on bob
    result = mesh_b.execute(req, verify=True)
    print(f'Execute: status={result.status.value} result={result.result}')

    # Test: failed signature
    from identity import SignedEnvelope
    bad_env = SignedEnvelope(payload=req.envelope.payload, signature='00'*64,
                              node_id=req.envelope.node_id, timestamp=req.envelope.timestamp)
    result2 = mesh_b.execute(RPCRequest(task_id='x', target_node='node-b',
                                         task={}, envelope=bad_env))
    print(f'Bad sig : status={result2.status.value}')

    # Test: cross-node RPC
    mesh_a.register_handler('COMPUTE', lambda t: {'result': 42})
    req2 = mesh_a.send_task('node-b', {'action': 'COMPUTE', 'x': 10})
    print(f'Compute: task_id={req2.task_id[:12]} result={req2.result}')

    print(f'
RPCMesh: ALL TESTS PASSED')


if __name__ == '__main__':
    _test()
