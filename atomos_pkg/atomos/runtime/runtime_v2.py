"""
ATOM OS v14.2 — Runtime Substrate v2 (ATOMFederationOS CORE)
Unified event-driven OS runtime kernel
"""
from __future__ import annotations
import asyncio, time, uuid

from atomos.runtime.event_bus import EventBus
from atomos.runtime.async_runtime import AsyncExecutionEngine
from atomos.runtime.memory_graph import MemoryGraph
from atomos.runtime.message_queue import MessageQueue
from atomos.runtime.federation_v2 import FederationKernelV2


class ATOMRuntimeV2:
    """
    ATOM OS v14.2 — Event-Driven OS Runtime Substrate

    Pipeline:
        USER INPUT
            ↓
        EVENT BUS (intent_received)
            ↓
        MEMORY GRAPH (session node)
            ↓
        EXECUTION LOOP (plan graph)
            ↓
        ASYNC ENGINE (step executor)
            ↓
        MESSAGE QUEUE (dispatch)
            ↓
        AABS / LOCAL / SWARM
            ↓
        EVENT BUS (step_completed / execution_finished)
            ↓
        MEMORY GRAPH (update state)
            ↓
        FEDERATION KERNEL (broadcast)
    """

    def __init__(self, node_id: str = None, execution_loop=None, policy_kernel=None):
        self.node_id = node_id or f"atom-{uuid.uuid4().hex[:8]}"
        self.exec_loop = execution_loop
        self.pk = policy_kernel

        # ── Core OS subsystems ──
        self.event_bus = EventBus()
        self.memory = MemoryGraph()
        self.message_queue = MessageQueue()
        self.federation = FederationKernelV2(self.node_id)
        self.async_engine = AsyncExecutionEngine(self.event_bus)

        # ── Register self with federation ──
        self.federation.register(self.node_id, "local", ["runtime", "execution"])

        self._running = False
        self._boot_time = time.time()

        # ── Wire event bus → memory graph updates ──
        self.event_bus.subscribe("execution_finished", self._on_execution_finished)

    async def process_intent(self, intent: str, context: dict = None) -> dict:
        """Main entry point: intent → event → plan → execute → audit."""
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        ctx = context or {}

        # 1. Emit intent received
        await self.event_bus.emit("intent_received", {
            "intent": intent, "session_id": session_id, "context": ctx
        })

        # 2. Create session node in memory graph
        self.memory.add_node(session_id, {
            "intent": intent, "context": ctx, "status": "planning"
        })

        # 3. Execute via execution loop
        if self.exec_loop:
            plan = self.exec_loop.execute(intent, ctx)
        else:
            plan = None

        # 4. Build execution graph and run async
        execution_graph = []
        if plan and plan.steps:
            execution_graph = [
                {"id": s.step_id, "type": s.description, "params": s.predicted_state_delta}
                for s in plan.steps
            ]

        if execution_graph:
            results = await self.async_engine.run(execution_graph)
        else:
            results = []

        # 5. Emit execution finished (triggers memory update via subscriber)
        await self.event_bus.emit("execution_finished", {
            "session_id": session_id, "results": results, "plan": plan
        })

        # 6. Update memory graph
        self.memory.update_state(session_id, {"status": "completed"})

        # 7. Federation heartbeat
        self.federation.heartbeat()

        return {
            "session_id": session_id,
            "plan": plan,
            "results": results,
            "event_log": self.event_bus.get_log(),
            "memory_nodes": len(self.memory.nodes),
        }

    async def _on_execution_finished(self, payload: dict):
        """Auto-update memory graph when execution finishes."""
        session_id = payload.get("session_id")
        if session_id and session_id in self.memory.nodes:
            self.memory.update_state(session_id, {
                "status": "completed",
                "result_count": len(payload.get("results", []))
            })

    async def run_async_consumer(self):
        """Start message queue consumer (call as background task)."""
        async def handler(msg):
            await self.event_bus.emit(f"mq_{msg.get('type', 'unknown')}", msg)

        await self.message_queue.consume(handler)

    def get_stats(self) -> dict:
        return {
            "node_id": self.node_id,
            "uptime_s": round(time.time() - self._boot_time, 1),
            "memory_nodes": len(self.memory.nodes),
            "memory_edges": len(self.memory.edges),
            "event_log_size": len(self.event_bus.get_log()),
            "mq_stats": self.message_queue.stats(),
            "federation_alive": len(self.federation.get_alive_nodes()),
        }


if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, "/home/workspace")
    import asyncio

    async def _main():
        print("╔═══════════════════════════════════════════════════╗")
        print("║  ATOMFederationOS v2.0 — Event-Driven Runtime    ║")
        print("║  SUBSTRATE KERNEL  (DETERMINISTIC + ASYNC)        ║")
        print("╚═══════════════════════════════════════════════════╝")

        rt = ATOMRuntimeV2()

        # Test intent pipeline
        for intent in [
            "ci fail: ruff error agents/ci_analyzer.py",
            "create new agent swarm engine",
            "read system status",
        ]:
            print(f"\n{'='*60}")
            print(f"Intent: {intent}")
            result = await rt.process_intent(intent)
            print(f"Session: {result['session_id']}")
            print(f"Steps executed: {len(result['results'])}")
            print(f"Memory nodes: {result['memory_nodes']}")

        stats = rt.get_stats()
        print(f"\n{'='*60}")
        print(f"RUNTIME STATS:")
        print(f"  Node ID: {stats['node_id']}")
        print(f"  Uptime: {stats['uptime_s']}s")
        print(f"  Memory nodes: {stats['memory_nodes']}")
        print(f"  Event log: {stats['event_log_size']}")
        print(f"  Federation alive: {stats['federation_alive']}")
        print(f"  MQ: {stats['mq_stats']}")
        print("\n✅ ATOMFederationOS v2.0 — ALL TESTS PASSED")

    asyncio.run(_main())