"""
ATOM OS v14.2 — Event Bus
In-memory pub/sub for async event-driven OS
"""
from __future__ import annotations
from collections import defaultdict
import asyncio, time

class EventBus:
    """Pub/sub event system for ATOM OS runtime."""

    def __init__(self):
        self.subscribers: dict[str, list] = defaultdict(list)
        self._event_log: list[dict] = []

    def subscribe(self, event_type: str, handler):
        self.subscribers[event_type].append(handler)

    async def emit(self, event_type: str, payload: dict):
        entry = {"type": event_type, "payload": payload, "ts": time.time()}
        self._event_log.append(entry)
        if event_type not in self.subscribers:
            return
        tasks = [handler(payload) for handler in self.subscribers[event_type]]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_log(self, limit: int = 50) -> list[dict]:
        return self._event_log[-limit:]


if __name__ == "__main__":
    async def test():
        bus = EventBus()
        received = []

        async def handler(payload):
            received.append(payload.get("value"))

        bus.subscribe("test_event", handler)
        await bus.emit("test_event", {"value": 42})
        await bus.emit("test_event", {"value": 100})

        print(f"Event log size: {len(bus.get_log())}")
        print(f"Handler received: {received}")
        assert received == [42, 100], f"Expected [42, 100], got {received}"
        print("✅ EventBus: ALL TESTS PASSED")

    asyncio.run(test())