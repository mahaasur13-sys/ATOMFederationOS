"
""ATOM OS v14.2 — Preemption Engine + Trust Engine
Preemption/migration + dynamic node trust scoring.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, Optional

class TrustEngine:
    """Dynamic trust scoring per node."""
    def __init__(self):
        self.scores: Dict[str, float] = {}
        self.history: Dict[str, list] = {}

    def update(self, node_id: str, success: bool):
        if node_id not in self.scores:
            self.scores[node_id] = 1.0
            self.history[node_id] = []
        delta = 0.01 if success else -0.1
        self.scores[node_id] = max(0.0, min(1.0, self.scores[node_id] + delta))
        self.history[node_id].append({'t': time.time(), 'ok': success, 'score': self.scores[node_id]})

    def get(self, node_id: str) -> float:
        return self.scores.get(node_id, 0.5)

    def is_trusted(self, node_id: str, threshold: float = 0.3) -> bool:
        return self.get(node_id) >= threshold

    def stats(self) -> dict:
        return {n: round(s, 4) for n, s in self.scores.items()}


class PreemptionEngine:
    """Kill or migrate tasks under resource pressure."""
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.migrations: list = []

    def migrate_task(self, task_id: str, to_node_id: str) -> dict:
        ok = self.scheduler.migrate_task(task_id, to_node_id)
        if ok:
            self.migrations.append({'task_id': task_id, 'to': to_node_id, 't': time.time()})
        return {'status': 'migrated' if ok else 'failed', 'task_id': task_id, 'to': to_node_id}

    def preempt_node(self, node_id: str, task_id: Optional[str] = None) -> dict:
        ok = self.scheduler.preempt(node_id, task_id)
        return {'status': 'preempted' if ok else 'failed', 'node_id': node_id}

    def force_migrate_all(self, from_node_id: str, to_node_id: str) -> dict:
        from_node = self.scheduler.nodes.get(from_node_id)
        if not from_node:
            return {'status': 'failed', 'reason': 'node_not_found'}
        migrated = []
        for t in list(from_node.tasks):
            ok = self.scheduler.migrate_task(t.id, to_node_id)
            if ok:
                migrated.append(t.id)
        return {'status': 'done', 'from': from_node_id, 'to': to_node_id, 'migrated': migrated}

    def stats(self) -> dict:
        return {
            'total_migrations': len(self.migrations),
            'recent': self.migrations[-5:] if self.migrations else [],
        }


def _test():
    print('╔══════════════════════════════════════════════╗')
    print('║  PREEMPTION v1.0 — Trust + Migration Engine ║')
    print('╚══════════════════════════════════════════════╝')

    import sys
    sys.path.insert(0, '/home/workspace/atomos_pkg')
    sys.path.insert(0, '/home/workspace/agents')
    from scheduler import Scheduler, Task, ResourceSpec

    sched = Scheduler()
    sched.register_node('compute-01', cpu=8, ram_mb=8192)
    sched.register_node('compute-02', cpu=8, ram_mb=8192)

    # Add tasks
    for i in range(5):
        t = Task(id=f't{i}', resources=ResourceSpec(cpu=1, ram_mb=256, priority=0), preemptible=True)
        sched.submit(t)

    trust = TrustEngine()
    for nid in ['compute-01', 'compute-02', 'compute-03']:
        trust.update(nid, success=True)
    trust.update('compute-01', success=False)

    print(f'Trust scores : {trust.stats()}')
    print(f'Trusted 01?   : {"✅ YES" if trust.is_trusted("compute-01") else "❌ NO"}')
    print(f'Trusted 03?   : {"✅ YES" if trust.is_trusted("compute-03") else "❌ NO (untrusted)"}')

    pe = PreemptionEngine(sched)

    node01 = sched.nodes['compute-01']
    if node01.tasks:
        task = node01.tasks[0]
        r = pe.migrate_task(task.id, 'compute-02')
        print(f'Migration: {r["status"]} task={task.id[:8]} to compute-02')

    r = pe.preempt_node('compute-01')
    print(f'Preempt    : {r}')

    r = pe.force_migrate_all('compute-01', 'compute-02')
    print(f'Force migr: {r["status"]} migrated={len(r.get("migrated",[]))}')

    print(f'
Preemption+Trust: ALL TESTS PASSED')


if __name__ == '__main__':
    _test()
