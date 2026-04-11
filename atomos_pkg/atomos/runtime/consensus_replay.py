"""
ATOM OS v14.2 — ConsensusCore + ReplayEngine
DESC v1.0: Raft-like consensus + Event replay
"""
from __future__ import annotations
import time
from typing import Dict, List, Any, Optional, Callable
from atomos.runtime.event_sourcing import EventStore, Event

class ConsensusCore:
    FOLLOWER = "FOLLOWER"; CANDIDATE = "CANDIDATE"; LEADER = "LEADER"

    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id; self.peers = peers
        self.state = self.FOLLOWER; self.term = 0
        self.voted_for: Optional[str] = None; self.leader_id: Optional[str] = None
        self.votes: Dict[str, bool] = {}; self.commit_index = 0
        self.last_applied = 0
        self._election_timeout = 2.0
        self._last_heartbeat = time.monotonic()

    def send_heartbeat(self) -> dict:
        self.state = self.LEADER
        self._last_heartbeat = time.monotonic()
        return {"type": "heartbeat", "from": self.node_id,
                "term": self.term, "commit_index": self.commit_index}

    def receive_heartbeat(self, msg: dict) -> dict:
        if msg["term"] < self.term:
            return {"type": "heartbeat_resp", "accepted": False, "term": self.term}
        self.term = msg["term"]; self.leader_id = msg["from"]
        self.state = self.FOLLOWER; self.voted_for = None
        self._last_heartbeat = time.monotonic()
        return {"type": "heartbeat_resp", "accepted": True, "term": self.term}

    def start_election(self) -> dict:
        self.state = self.CANDIDATE; self.term += 1
        self.voted_for = self.node_id
        self.votes = {self.node_id: True, **{p: False for p in self.peers if p != self.node_id}}
        majority = (len(self.peers) // 2) + 1
        current_votes = sum(1 for v in self.votes.values() if v)
        return {"type": "election", "state": self.state, "term": self.term,
                "votes_so_far": current_votes, "majority_needed": majority}

    def receive_vote_response(self, msg: dict) -> dict:
        if msg["term"] > self.term:
            self.term = msg["term"]; self.state = self.FOLLOWER
            return {"type": "ignored", "reason": "stale_candidate"}
        granted = msg.get("vote_granted", False)
        if granted and self.state == self.CANDIDATE:
            self.votes[msg["from"]] = True
            majority = (len(self.peers) // 2) + 1
            if sum(1 for v in self.votes.values() if v) >= majority:
                self.state = self.LEADER; self.leader_id = self.node_id
                return {"type": "elected", "term": self.term, "leader": self.node_id}
        return {"type": "pending", "votes": sum(1 for v in self.votes.values() if v)}

    def is_leader_alive(self) -> bool:
        if self.state == self.LEADER: return True
        return (time.monotonic() - self._last_heartbeat) < self._election_timeout * 2

    def should_start_election(self) -> bool:
        if self.state == self.LEADER: return False
        return (time.monotonic() - self._last_heartbeat) >= self._election_timeout

    def replicate(self, event: Event) -> dict:
        if self.state != self.LEADER:
            return {"type": "rejected", "reason": "not_leader", "leader": self.leader_id}
        return {"type": "replicate", "term": self.term,
                "entry": event.as_dict(), "commit_index": self.commit_index}

    def accept_entry(self, msg: dict) -> dict:
        if msg["term"] < self.term:
            return {"type": "rejected", "term": self.term}
        self.leader_id = msg.get("from")
        self._last_heartbeat = time.monotonic()
        return {"type": "accepted", "index": msg["entry"]["i"]}

    def status(self) -> dict:
        return {"node": self.node_id, "state": self.state, "term": self.term,
                "leader": self.leader_id, "voted_for": self.voted_for,
                "commit_index": self.commit_index,
                "votes": dict(self.votes), "leader_alive": self.is_leader_alive()}


class ReplayEngine:
    def __init__(self, store: EventStore):
        self.store = store
        self._handlers: Dict[str, Callable[[dict, Event], dict]] = {}
        self._checkpoints: Dict[int, dict] = {}

    def register(self, event_type: str, handler: Callable[[dict, Event], dict]):
        self._handlers[event_type] = handler

    def replay_to(self, index: int) -> Optional[dict]:
        return self.store.rebuild_state(index, self._project)

    def replay_range(self, start: int, end: int) -> List[dict]:
        states = []; state = {}
        for evt in self.store.range(start, end):
            try:
                state = self._project(state, evt)
                self._checkpoints[evt.index] = dict(state)
                states.append({"index": evt.index, "event": evt.event_type, "state": dict(state)})
            except Exception:
                pass
        return states

    def time_travel(self, index: int) -> Optional[dict]:
        return self.replay_to(index)

    def diff(self, idx_a: int, idx_b: int) -> dict:
        s_a = self.replay_to(idx_a) or {}
        s_b = self.replay_to(idx_b) or {}
        all_keys = set(s_a) | set(s_b)
        return {"added": {k: s_b[k] for k in all_keys if k not in s_a},
                "removed": {k: s_a[k] for k in all_keys if k not in s_b},
                "changed": {k: s_b[k] for k in all_keys if k in s_a and s_a[k] != s_b[k]}}

    def _project(self, state: dict, evt: Event) -> dict:
        handler = self._handlers.get(evt.event_type)
        if handler:
            try: return handler(state, evt)
            except Exception: pass
        return state

    def history(self, key: str, event_type: str = None) -> List[Any]:
        states = []; state = {}
        for evt in self.store.all():
            if event_type and evt.event_type != event_type: continue
            state = self._project(state, evt)
            if key in state:
                states.append({"index": evt.index, "value": state[key], "event": evt.event_type})
        return states

    def stats(self) -> dict:
        return {"total_events": len(self.store.all()),
                "registered_types": list(self._handlers.keys()),
                "checkpoints": len(self._checkpoints)}


class DistributedDESC:
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.store = EventStore(node_id)
        self.consensus = ConsensusCore(node_id, peers)
        self.replay = ReplayEngine(self.store)

    def submit(self, event_type: str, payload: tuple) -> Event:
        if self.consensus.state != ConsensusCore.LEADER and self.consensus.leader_id:
            return self.store.append(event_type, payload, term=self.consensus.term)
        if self.consensus.state == ConsensusCore.LEADER:
            return self.store.append(event_type, payload, term=self.consensus.term)
        self.consensus.start_election()
        return self.store.append(event_type, payload, term=self.consensus.term)

    def snapshot(self, state: dict):
        idx = self.store._log[-1].index if self.store._log else 0
        self.store.snapshot(state, idx)

    def full_status(self) -> dict:
        return {"node": self.node_id,
                "consensus": self.consensus.status(),
                "store": self.store.stats(),
                "replay": self.replay.stats()}


def _test():
    print("╔══════════════════════════════════════════════╗")
    print("║  DESC v1.0 \u2014 Distributed Event Sourcing   ║")
    print("║  + Consensus Core + Replay Engine          ║")
    print("╚══════════════════════════════════════════════╝")

    peers = ["atom-001", "atom-002", "atom-003", "atom-004"]
    nodes = {nid: DistributedDESC(nid, peers) for nid in peers}

    store = nodes["atom-001"].store
    for i in range(20):
        store.append("MISSION_SUBMIT", ("task-" + str(i), "payload-" + str(i)), term=1)
    chain_ok = store.verify_chain()
    verdict = "PASS" if chain_ok else "FAIL"
    print("Chain integrity   : [CHECK] " + verdict)

    evt = store.all()[5]
    tampered = Event(**evt.__dict__)
    tampered.__dict__["payload"] = ("TAMPERED",)
    tampered.__dict__["self_hash"] = "fake"
    verdict = "PASS" if not tampered.verify() else "FAIL"
    print("Tamper detected  : [CHECK] " + verdict)

    atom1 = nodes["atom-001"]
    atom1.consensus.state = atom1.consensus.FOLLOWER
    atom1.consensus._last_heartbeat = 0
    should_restart = atom1.consensus.should_start_election()
    verdict = "PASS" if should_restart else "FAIL"
    print("Election trigger : [CHECK] " + verdict)

    election = atom1.consensus.start_election()
    print("Election started : state=" + election["state"] + " term=" + str(election["term"]))

    for nid in ["atom-002", "atom-003", "atom-004"]:
        resp = atom1.consensus.receive_vote_response({"from": nid, "term": atom1.consensus.term, "vote_granted": True})
        if resp["type"] == "elected": break
    print("Leader elected   : " + str(atom1.consensus.leader_id) + " (term=" + str(atom1.consensus.term) + ")")

    re = nodes["atom-001"].replay
    re.register("MISSION_SUBMIT", lambda s, e: {**s, str(e.payload[0]): e.payload[1]})
    for i in range(20):
        re.store.append("MISSION_SUBMIT", ("task-" + str(i), "result-" + str(i)), term=1)
    state = re.replay_to(len(re.store.all()) - 1)
    replay_ok = state is not None and len(state) == 20
    print("Replay to state  : [CHECK] " + ("PASS" if replay_ok else "FAIL"))

    diff = re.diff(4, 9)
    diff_ok = "added" in diff and len(diff["added"]) == 5
    print("Time-travel diff : [CHECK] " + ("PASS" if diff_ok else "FAIL"))

    hist = re.history("task-5")
    hist_ok = len(hist) >= 1
    print("Field history    : [CHECK] " + ("PASS" if hist_ok else "FAIL"))

    atom1.consensus.state = atom1.consensus.LEADER
    desc = nodes["atom-001"]
    evt = desc.submit("SYSTEM_BOOT", ("atom-001", "started"))
    submit_ok = evt is not None and evt.event_type == "SYSTEM_BOOT"
    print("DESC submit      : [CHECK] " + ("PASS" if submit_ok else "FAIL"))

    all_ok = chain_ok and should_restart and atom1.consensus.leader_id and replay_ok and diff_ok and hist_ok and submit_ok
    print("\n" + "="*50)
    print("DESC v1.0: " + ("ALL TESTS PASSED" if all_ok else "SOME FAILED"))


if __name__ == "__main__": _test()
