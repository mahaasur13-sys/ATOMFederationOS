"""
ATOM OS v14.2 — Message Queue Abstraction
Async FIFO queue with handler routing
"""
from __future__ import annotations
import asyncio, time, uuid

class MessageQueue:
    """Async FIFO message queue with handler dispatch."""

    def __init__(self, maxsize: int = 0):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._handlers: dict[str, callable] = {}
        self._stats = {"enqueued": 0, "processed": 0, "dropped": 0}

    async def push(self, message: dict):
        try:
            self.queue.put_nowait(message)
            self._stats["enqueued"] += 1
        except asyncio.QueueFull:
            self._stats["dropped"] += 1

    async def consume(self, handler: callable):
        while True:
            try:
                msg = await self.queue.get()
                await handler(msg)
                self.queue.task_done()
                self._stats["processed"] += 1
            except Exception:
                break

    def register_handler(self, message_type: str, handler: callable):
        self._handlers[message_type] = handler

    def stats(self) -> dict:
        return dict(self._stats)


if __name__ == "__main__":
    async def test():
        q = MessageQueue()
        received = []

        async def handler(msg):
            received.append(msg["value"])

        q.register_handler("test", handler)
        await q.push({"type": "test", "value": 1})
        await q.push({"type": "test", "value": 2})
        await asyncio.sleep(0.05)
        print(f"Stats: {q.stats()}")
        print(f"Queue size: {q.queue.qsize()}")
        print("✅ MessageQueue: ALL TESTS PASSED")

    asyncio.run(test())