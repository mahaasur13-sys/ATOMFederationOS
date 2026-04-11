"""
ATOM OS v14.2 — Distributed Event Sourcing + Consensus Core
DESC v1.0: EventStore + ConsensusCore + ReplayEngine
"""
from __future__ import annotations
import time, hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

# =========================================================
# EVENT MODEL (IMMUTABLE)
# =========================================================

@dataclass(frozen=True)
class Event:
    version:    str
    node_id:    str
    term:       int
    index:      int
    event_type: str
    payload:    tuple
    timestamp:  float
    prev_hash:  str
    self_hash:  str = field(default="", compare=False)

    def __post_init__(self):
        if not self.self_hash:
            raw = f"{self.version}{self.node_id}{self.term}{self.index}{self.event_type}{self.payload}{self.timestamp}{self.prev_hash}"
            object.__setattr__(self, 'self_hash', hashlib.sha256(raw.encode()).hexdigest()[:32])

    def verify(self) -> bool:
        raw = f"{self.version}{self.node_id}{self.term}{self.index}{self.event_type}{self.payload}{self.timestamp}{self.prev_hash}"
        return self.self_hash == hashlib.sha256(raw.encode()).hexdigest()[:32]

    def as_dict(self) -> dict:
        return {"v": self.version, "n": self.node_id, "t": self.term,
                "i": self.index, "et": self.event_type,
                "p": self.payload, "ts": self.timestamp,
                "ph": self.prev_hash, "sh": self.self_hash}

# =========================================================
# EVENT STORE (Append-only CRDT log)
# =========================================================

class EventStore:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._log: List[Event] = []
        self._index: Dict[int, Event] = {}
        self._by_type: Dict[str, List[Event]] = defaultdict(list)
        self._snapshots: Dict[int, dict] = {}

    def append(self, event_type: str, payload: tuple, term: int = 0) -> Event:
        prev = self._log[-1] if self._log else None
        prev_hash = prev.self_hash if prev else "GENESIS"
        idx = len(self._log)
        evt = Event(version="1.0", node_id=self.node_id, term=term, index=idx,
                     event_type=event_type, payload=payload, timestamp=time.time(),
                     prev_hash=prev_hash)
        self._log.append(evt)
        self._index[idx] = evt
        self._by_type[event_type].append(evt)
        return evt

    def get(self, index: int) -> Optional[Event]:
        return self._index.get(index)

    def range(self, start: int, end: int) -> List[Event]:
        return [e for _, e in sorted(self._index.items()) if start <= _ <= end]

    def of_type(self, event_type: str) -> List[Event]:
        return list(self._by_type.get(event_type, []))

    def all(self) -> List[Event]:
        return list(self._log)

    def verify_chain(self) -> bool:
        for i, evt in enumerate(self._log):
            if not evt.verify():
                return False
            if i > 0 and evt.prev_hash != self._log[i-1].self_hash:
                return False
        return True

    def snapshot(self, state: dict, until_index: int):
        self._snapshots[until_index] = dict(state)

    def rebuild_state(self, until_index: int, projector: Callable[[dict, Event], dict]) -> Optional[dict]:
        if until_index < 0:
            return None
        if until_index in self._snapshots:
            state = dict(self._snapshots[until_index])
            events = self.range(until_index + 1, until_index)
        else:
            state = {}
            events = self.range(0, until_index)
        for evt in events:
            try:
                state = projector(state, evt)
            except Exception:
                pass
        return state

    def stats(self) -> dict:
        return {"node": self.node_id, "total_events": len(self._log),
                "by_type": {k: len(v) for k, v in self._by_type.items()},
                "chain_valid": self.verify_chain()}
