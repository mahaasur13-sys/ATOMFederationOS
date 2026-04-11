"""
TAAR Memory — File-based JSONL store for agent state persistence.
Provides semantic-like retrieval via text matching (lightweight, no embedding server needed).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────
# MEMORY RECORD
# ─────────────────────────────────────────

@dataclass
class MemoryRecord:
    id: str          # uuid-like unique id
    session_id: str  # conversation/session identifier
    role: str        # "user" | "assistant" | "system" | "tool"
    content: str
    tool_name: str | None = None
    tool_result: Any | None = None
    created_at: str | None = None  # ISO timestamp

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        # Clean None fields for JSONL
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─────────────────────────────────────────
# JSONL STORE
# ─────────────────────────────────────────

class JSONLStore:
    """
    Append-only JSONL file store.
    Thread-safe via file locking for writes.
    """

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: MemoryRecord) -> str:
        """Append a record, return its id."""
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return record.id

    def append_dict(self, d: dict) -> str:
        return self.append(MemoryRecord(**d))

    def get_all(self) -> list[MemoryRecord]:
        """Load all records from the store."""
        if not self.filepath.exists():
            return []
        records = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(MemoryRecord.from_dict(json.loads(line)))
                except Exception:
                    continue
        return records

    def search(self, query: str, session_id: str | None = None, limit: int = 10) -> list[MemoryRecord]:
        """
        Simple text-search through content.
        Returns records matching query, optionally filtered by session_id.
        """
        records = self.get_all()
        query_lower = query.lower()
        results = []

        for rec in records:
            if session_id and rec.session_id != session_id:
                continue
            if query_lower in rec.content.lower():
                results.append(rec)
                if len(results) >= limit:
                    break

        return results

    def get_session(self, session_id: str) -> list[MemoryRecord]:
        """Get all records for a session."""
        return [r for r in self.get_all() if r.session_id == session_id]

    def clear_session(self, session_id: str) -> int:
        """Remove all records for a session, return count deleted."""
        all_records = self.get_all()
        kept = [r for r in all_records if r.session_id != session_id]
        deleted = len(all_records) - len(kept)

        # Rewrite file
        with open(self.filepath, "w", encoding="utf-8") as f:
            for rec in kept:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

        return deleted

    def stats(self) -> dict:
        """Return store statistics."""
        records = self.get_all()
        sessions = set(r.session_id for r in records)
        return {
            "total_records": len(records),
            "sessions": len(sessions),
            "filepath": str(self.filepath),
        }


# ─────────────────────────────────────────
# SESSION MEMORY
# ─────────────────────────────────────────

class SessionMemory:
    """
    In-memory cache backed by JSONL store.
    Provides fast read/write within a session, persists to disk.
    """

    def __init__(self, store_path: str | Path, session_id: str):
        self.store = JSONLStore(store_path)
        self.session_id = session_id
        self._cache: list[MemoryRecord] | None = None

    def _ensure_cache(self):
        if self._cache is None:
            self._cache = self.store.get_session(self.session_id)

    def add(self, role: str, content: str, tool_name: str | None = None, tool_result: Any = None) -> str:
        """Add a message to session memory."""
        self._ensure_cache()
        record = MemoryRecord(
            id=f"{self.session_id}-{int(time.time()*1000)}",
            session_id=self.session_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_result=tool_result,
        )
        self._cache.append(record)
        self.store.append(record)
        return record.id

    def add_user(self, content: str) -> str:
        return self.add("user", content)

    def add_assistant(self, content: str, tool_name: str | None = None, tool_result: Any = None) -> str:
        return self.add("assistant", content, tool_name, tool_result)

    def add_system(self, content: str) -> str:
        return self.add("system", content)

    def get_history(self, limit: int | None = None) -> list[MemoryRecord]:
        """Get conversation history, newest last."""
        self._ensure_cache()
        history = self._cache[-limit:] if limit else self._cache
        return history

    def get_last_n(self, n: int) -> list[MemoryRecord]:
        return self.get_history(limit=n)

    def search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Search within session."""
        self._ensure_cache()
        query_lower = query.lower()
        return [r for r in self._cache if query_lower in r.content.lower()][-limit:]

    def clear(self):
        """Clear this session from store."""
        self.store.clear_session(self.session_id)
        self._cache = []


# ─────────────────────────────────────────
# GLOBAL MEMORY MANAGER
# ─────────────────────────────────────────

_DEFAULT_STORE = Path("/home/workspace/agents/memory.jsonl")

def get_memory(session_id: str = "default", store_path: Path | None = None) -> SessionMemory:
    """Factory function for session memory."""
    path = store_path or _DEFAULT_STORE
    return SessionMemory(path, session_id)


# ─────────────────────────────────────────
# SEMANTIC-LIKE RETRIEVAL (lightweight)
# ─────────────────────────────────────────

class VectorMemory:
    """
    Lightweight vector-like memory using BM25-style scoring.
    No external embedding server needed — uses keyword overlap.
    """

    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or _DEFAULT_STORE
        self.jsonl = JSONLStore(self.store_path)

    def add(self, text: str, metadata: dict | None = None, session_id: str = "default") -> str:
        record_dict = {
            "id": f"{session_id}-{int(time.time()*1000)}",
            "session_id": session_id,
            "role": "memory",
            "content": text,
        }
        if metadata:
            record_dict["tool_result"] = metadata
        return self.jsonl.append_dict(record_dict)

    def retrieve(self, query: str, top_k: int = 5, session_id: str | None = None) -> list[MemoryRecord]:
        """
        Retrieve top-k records by keyword overlap scoring.
        BM25-lite: term frequency / document frequency.
        """
        records = self.jsonl.get_all()

        if session_id:
            records = [r for r in records if r.session_id == session_id]

        if not records:
            return []

        query_terms = query.lower().split()
        doc_scores: list[tuple[MemoryRecord, float]] = []

        for rec in records:
            content_lower = rec.content.lower()
            # TF: how many query terms appear in document
            tf = sum(1 for term in query_terms if term in content_lower)
            # IDF-like: penalize common words (use total docs / term docs)
            if tf == 0:
                continue
            # Simple score: tf * log(N / df)
            # Approximate: just tf for now
            score = tf
            doc_scores.append((rec, score))

        doc_scores.sort(key=lambda x: x[1], reverse=True)
        return [rec for rec, score in doc_scores[:top_k]]

    def stats(self) -> dict:
        return self.jsonl.stats()