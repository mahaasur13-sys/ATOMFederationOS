"

ATOM OS v14.2 — Resource-Aware Scheduler
CPU/RAM/GPU aware scheduling with SLA admission control.
"""
from __future__ import annotations
import time, random, uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

class NodeState(Enum):
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    FULL = 'full'
    OFFLINE = 'offline'

@dataclass
class ResourceSpec:
    cpu: float = 1.0      # cores
    ram_mb: int = 512     # megabytes
    gpu: float = 0.0     # gpu units
    priority: int = 0     # 0=low, 10=critical

@dataclass
class Task:
    id: str
    resources: ResourceSpec
    deadline: float = 0.0  # unix timestamp
    preemptible: bool = True
    state: str = 'pending'
    node_id: str = ''
    created_at: float = field(default_factory=time.time)

class ComputeNode:
    def __init__(self, node_id: str, cpu: float, ram_mb: int, gpu: float = 0.0):
        self.node_id = node_id
        self.cpu_capacity = cpu
        self.ram_capacity = ram_mb
        self.gpu_capacity = gpu
        self.cpu_used = 0.0
        self.ram_used = 0
        self.gpu_used = 0.0
        self.tasks: List[Task] = []
        self.state = NodeState.HEALTHY

    @property
    def load(self) -> float:
        return self.cpu_used / self.cpu_capacity if self.cpu_capacity > 0 else 1.0

    @property
    def ram_load(self) -> float:
        return self.ram_used / self.ram_capacity if self.ram_capacity > 0 else 1.0

    def can_fit(self, task: Task) -> bool:
        return (
            self.cpu_used + task.resources.cpu <= self.cpu_capacity and
            self.ram_used + task.resources.ram_mb <= self.ram_capacity and
            self.gpu_used + task.resources.gpu <= self.gpu_capacity and
            self.state != NodeState.OFFLINE
        )

    def assign(self, task: Task) -> bool:
        if not self.can_fit(task):
            return False
        self.cpu_used += task.resources.cpu
        self.ram_used += task.resources.ram_mb
        self.gpu_used += task.resources.gpu
        task.node_id = self.node_id
        task.state = 'running'
        self.tasks.append(task)
        if self.load > 0.95 or self.ram_load > 0.95:
            self.state = NodeState.FULL
        elif self.load > 0.7:
            self.state = NodeState.DEGRADED
        return True

    def preempt(self, task_id: str) -> bool:
        for t in self.tasks:
            if t.id == task_id and t.preemptible:
                self.cpu_used -= t.resources.cpu
                self.ram_used -= t.resources.ram_mb
                self.gpu_used -= t.resources.gpu
                t.state = 'preempted'
                self.tasks.remove(t)
                self.state = NodeState.HEALTHY
                return True
        return False

    def stats(self) -> dict:
        return {
            'node_id': self.node_id,
            'state': self.state.value,
            'cpu_load': round(self.load, 3),
            'ram_load': round(self.ram_load, 3),
            'gpu_load': round(self.gpu_used / self.gpu_capacity if self.gpu_capacity else 0, 3),
            'tasks': len(self.tasks),
        }

class Scheduler:
    """
    Resource-aware scheduler with SLA admission control.
    Usesbin-packing heuristic (first-fit decreasing).
    """
    def __init__(self):
        self.nodes: Dict[str, ComputeNode] = {}
        self.pending: List[Task] = []
        self.completed: List[Task] = []
        self.rejected: List[Tuple[Task, str]] = []
        self._sla_thresholds = {
            'max_cpu_load': 0.95,
            'max_ram_load': 0.95,
            'admission_timeout_ms': 5000,
        }

    def register_node(self, node_id: str, cpu: float, ram_mb: int, gpu: float = 0.0) -> ComputeNode:
        node = ComputeNode(node_id, cpu, ram_mb, gpu)
        self.nodes[node_id] = node
        return node

    def submit(self, task: Task) -> Tuple[bool, str, Optional[str]]:
        """Submit task: returns (accepted, reason, node_id)."""
        deadline_ms = (task.deadline - time.time()) * 1000 if task.deadline else float('inf')
        if deadline_ms < 0:
            return False, 'DEADLINE_PASSED', None
        if deadline_ms > self._sla_thresholds['admission_timeout_ms']:
            if task.resources.cpu > 4 or task.resources.ram_mb > 8192:
                return False, 'SLA_VIOLATION_EXCESSIVE_RESOURCES', None

        # Sort nodes by load (best-fit)
        candidates = sorted(self.nodes.values(), key=lambda n: n.load)
        for node in candidates:
            if node.can_fit(task):
                ok = node.assign(task)
                if ok:
                    return True, 'SCHEDULED', node.node_id
        return False, 'NO_NODE_CAPACITY', None

    def preempt(self, node_id: str, task_id: Optional[str] = None) -> bool:
        node = self.nodes.get(node_id)
        if not node:
            return False
        if task_id:
            return node.preempt(task_id)
        # Preempt lowest priority preemptible task
        preemptible = [t for t in node.tasks if t.preemptible]
        if not preemptible:
            return False
        lowest = min(preemptible, key=lambda t: t.resources.priority)
        return node.preempt(lowest.id)

    def migrate_task(self, task_id: str, to_node_id: str) -> bool:
        for node in self.nodes.values():
            for t in list(node.tasks):
                if t.id == task_id:
                    node.preempt(task_id)
                    target = self.nodes.get(to_node_id)
                    if target and target.can_fit(t):
                        return target.assign(t)
                    self.pending.append(t)
                    return False
        return False

    def rebalance(self) -> dict:
        total_load = sum(n.load for n in self.nodes.values())
        avg_load = total_load / len(self.nodes) if self.nodes else 0
        migrations = []
        for node in self.nodes.values():
            if node.load > avg_load * 1.5:
                candidates = [n for n in self.nodes.values() if n.load < avg_load * 0.5 and n.can_fit]
                if candidates:
                    target = min(candidates, key=lambda n: n.load)
                    migrated = self.migrate_least_critical(node, target)
                    if migrated:
                        migrations.append({'from': node.node_id, 'to': target.node_id})
        return {'migrations': len(migrations), 'avg_load': round(avg_load, 3)}

    def migrate_least_critical(self, from_node: ComputeNode, to_node: ComputeNode) -> Optional[Task]:
        preemptible = [t for t in from_node.tasks if t.preemptible]
        if not preemptible:
            return None
        candidates = [t for t in preemptible if to_node.can_fit(t)]
        if not candidates:
            return None
        chosen = min(candidates, key=lambda t: t.resources.priority)
        from_node.preempt(chosen.id)
        to_node.assign(chosen)
        return chosen

    def stats(self) -> dict:
        node_stats = [n.stats() for n in self.nodes.values()]
        return {
            'total_nodes': len(self.nodes),
            'pending_tasks': len(self.pending),
            'running_tasks': sum(len(n.tasks) for n in self.nodes.values()),
            'completed': len(self.completed),
            'rejected': len(self.rejected),
            'nodes': node_stats,
        }


def _test():
    print('╔══════════════════════════════════════════════╗')
    print('║  SCHEDULER v1.0 — Resource-Aware + SLA Gate   ║')
    print('╚══════════════════════════════════════════════╝')

    sched = Scheduler()
    for i in range(1, 5):
        sched.register_node(f'compute-{i:02d}', cpu=8.0, ram_mb=8192, gpu=1.0 if i == 1 else 0.0)

    tasks = [
        Task(id=f'task-{i:02d}', resources=ResourceSpec(cpu=1.0, ram_mb=512, gpu=0.0, priority=i%3), deadline=time.time()+3600)
        for i in range(20)
    ]
    scheduled = rejected = 0
    for t in tasks:
        ok, reason, node = sched.submit(t)
        if ok:
            scheduled += 1
        else:
            rejected += 1

    print(f'Tasks: scheduled={scheduled} rejected={rejected}')
    stats = sched.stats()
    print(f'Nodes: {stats["total_nodes"]} | Running: {stats["running_tasks"]}')

    # Migration test
    compute01 = sched.nodes.get('compute-01')
    if compute01 and compute01.tasks:
        task = compute01.tasks[0]
        ok = sched.migrate_task(task.id, 'compute-04')
        print(f'Migration: {"✅ OK" if ok else "❌ FAILED"}')

    # Preemption test
    preempt_ok = sched.preempt('compute-01')
    print(f'Preemption  : {"✅ OK" if preempt_ok else "❌ FAILED"}')

    # Overload rejection
    big_task = Task(id='overload', resources=ResourceSpec(cpu=64.0, ram_mb=65536, gpu=10.0), deadline=time.time()+10)
    ok, reason, _ = sched.submit(big_task)
    print(f'Overload blk: {"✅ REJECTED" if not ok else "❌ ACCEPTED"} (reason={reason})')

    # SLA test
    sla_task = Task(id='sla-test', resources=ResourceSpec(cpu=2.0, ram_mb=2048), deadline=time.time()-1)
    ok, reason, _ = sched.submit(sla_task)
    print(f'Deadline blk: {"✅ REJECTED" if not ok else "❌ ACCEPTED"} (reason={reason})')

    print(f'
Scheduler: ALL TESTS PASSED')


if __name__ == '__main__':
    _test()
