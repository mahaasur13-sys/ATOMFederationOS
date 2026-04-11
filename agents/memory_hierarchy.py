"""
TAAR v2.1 — Memory Hierarchy Layer (Greenboost Abstraction)
Tiered memory: VRAM → RAM → NVMe
Automatic offload, compression, and eviction.
"""

from __future__ import annotations

import os
import json
import time
import mmap
import shutil
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Literal


# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────

# /dev/shm is a tmpfs (RAM-backed) — typically 50% of RAM
RAM_TMP_DIR = Path("/dev/shm/taar")
# NVMe swap/cache
NVME_CACHE_DIR = Path("/home/workspace/.taar_cache")
# In-process compressed store (RAM)
COMPRESS_THRESHOLD_MB = 256   # Compress if stored object > 256MB
RAM_BUDGET_MB = 512           # Max RAM for TAAR memory subsystem


# ─────────────────────────────────────────
# Tier definitions
# ─────────────────────────────────────────

@dataclass
class MemoryStats:
    ram_used_mb: int = 0
    ram_free_mb: int = 0
    vram_used_mb: int = 0
    vram_free_mb: int = 0
    nvme_cached_mb: int = 0
    active_tier: str = "ram"     # ram | vram | nvme
    pressure: str = "low"         # low | medium | high | critical


@dataclass
class MemoryEntry:
    key: str
    data: Any
    tier: str = "ram"
    size_bytes: int = 0
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    access_count: int = 0
    compressed: bool = False
    pinned: bool = False

    def touch(self):
        self.last_access = time.time()
        self.access_count += 1


# ─────────────────────────────────────────
# RAM tier — in-memory LRU dict
# ─────────────────────────────────────────

class RAMStore:
    """In-process memory store with LRU eviction."""

    def __init__(self, max_mb: int = RAM_BUDGET_MB):
        self.max_bytes = max_mb * 1024 * 1024
        self._data: dict[str, MemoryEntry] = {}
        self._current_bytes = 0

    def __setitem__(self, key: str, value: Any, size_bytes: int = 0) -> bool:
        # Estimate size if not provided
        if size_bytes == 0:
            size_bytes = len(json.dumps(value).encode()) if isinstance(value, (dict, list, str)) else 1024

        # Evict if needed
        while self._current_bytes + size_bytes > self.max_bytes and self._data:
            self._evict_lru()

        if size_bytes > self.max_bytes:
            return False  # Won't fit even after eviction

        # Remove existing
        if key in self._data:
            self._current_bytes -= self._data[key].size_bytes

        self._data[key] = MemoryEntry(key=key, data=value, size_bytes=size_bytes)
        self._current_bytes += size_bytes
        return True

    def __getitem__(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        entry.touch()
        return entry.data

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __delitem__(self, key: str):
        if key in self._data:
            self._current_bytes -= self._data[key].size_bytes
            del self._data[key]

    def _evict_lru(self):
        """Evict least-recently used non-pinned entry."""
        if not self._data:
            return
        lru_key = min(
            (k for k, e in self._data.items() if not e.pinned),
            key=lambda k: self._data[k].last_access,
            default=None,
        )
        if lru_key:
            del self[lru_key]

    def keys(self):
        return self._data.keys()

    def get_stats(self) -> dict:
        return {
            "entries": len(self._data),
            "used_bytes": self._current_bytes,
            "max_bytes": self.max_bytes,
            "util_pct": round(100 * self._current_bytes / self.max_bytes, 1),
        }

    def clear(self):
        self._data.clear()
        self._current_bytes = 0


# ─────────────────────────────────────────
# NVMe tier — disk-backed JSONL
# ─────────────────────────────────────────

class NVMeStore:
    """Persistent JSONL store on NVMe. Write-once, read-many."""

    def __init__(self, cache_dir: Path = NVME_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = cache_dir / "nvme_index.json"
        self._index: dict[str, dict] = self._load_index()

    def _load_index(self) -> dict:
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_index(self):
        with open(self.index_file, "w") as f:
            json.dump(self._index, f)

    def _chunk_path(self, key: str) -> Path:
        h = hashlib.md5(key.encode()).hexdigest()[:8]
        return self.cache_dir / f"{h}.jsonl"

    def __setitem__(self, key: str, value: Any) -> bool:
        try:
            chunk_path = self._chunk_path(key)
            record = {
                "key": key,
                "data": value,
                "ts": time.time(),
            }
            with open(chunk_path, "a") as f:
                f.write(json.dumps(record) + "\n")

            self._index[key] = {
                "chunk": str(chunk_path),
                "size_bytes": len(json.dumps(record).encode()),
                "ts": time.time(),
            }
            self._save_index()
            return True
        except (IOError, TypeError):
            return False

    def __getitem__(self, key: str) -> Any | None:
        if key not in self._index:
            return None
        chunk_path = self._index[key]["chunk"]
        if not Path(chunk_path).exists():
            return None
        try:
            with open(chunk_path) as f:
                for line in f:
                    rec = json.loads(line)
                    if rec["key"] == key:
                        return rec["data"]
        except (json.JSONDecodeError, IOError):
            pass
        return None

    def __contains__(self, key: str) -> bool:
        return key in self._index and Path(self._index[key]["chunk"]).exists()

    def __delitem__(self, key: str):
        if key in self._index:
            p = Path(self._index[key]["chunk"])
            if p.exists():
                p.unlink()
            del self._index[key]
            self._save_index()

    def get_stats(self) -> dict:
        total_size = sum(e["size_bytes"] for e in self._index.values())
        return {
            "entries": len(self._index),
            "total_bytes": total_size,
            "cache_dir": str(self.cache_dir),
        }

    def clear(self):
        for key in list(self._index.keys()):
            del self[key]


# ─────────────────────────────────────────
# Memory Hierarchy — GreenBoost
# ─────────────────────────────────────────

class MemoryHierarchy:
    """
    Tiered memory system:
      1. RAM  — fast, in-process, LRU-evicted
      2. NVMe — slow, persistent, disk-backed

    Auto-tiering: RAM → NVMe on overflow.
    Manual pin: prevents eviction.
    """

    def __init__(
        self,
        ram_max_mb: int = RAM_BUDGET_MB,
        cache_dir: Path = NVME_CACHE_DIR,
        vram_free_mb_fn: callable | None = None,
    ):
        self.ram = RAMStore(max_mb=ram_max_mb)
        self.nvme = NVMeStore(cache_dir=cache_dir)
        self.vram_free_fn = vram_free_mb_fn or (lambda: 0)

    # ── Core API ─────────────────────────

    def set(self, key: str, value: Any, *, tier: str | None = None, pin: bool = False) -> bool:
        """
        Store value. Auto-tier if not specified.
        Returns False if all tiers failed.
        """
        size = len(json.dumps(value).encode()) if isinstance(value, (dict, list, str)) else 1024

        # Check VRAM availability
        vram_free = self.vram_free_fn()
        if tier is None:
            # Auto-select tier
            if vram_free >= (size / 1024) + 512:
                tier = "vram"
            elif self.ram.get_stats()["util_pct"] < 90:
                tier = "ram"
            else:
                tier = "nvme"

        if tier == "vram" and vram_free < size / 1024:
            tier = "ram"

        if tier == "ram":
            ok = self.ram.__setitem__(key, value, size)
            if not ok:
                # RAM full — spill to NVMe
                tier = "nvme"
                ok = self.nvme.__setitem__(key, value)

        elif tier == "nvme":
            ok = self.nvme.__setitem__(key, value)
        else:
            ok = False

        if ok and pin:
            # Pin in RAM if there
            if key in self.ram:
                self.ram._data[key].pinned = True

        return ok

    def get(self, key: str) -> Any | None:
        """Get value. Checks RAM first, then NVMe."""
        val = self.ram[key]
        if val is not None:
            return val
        val = self.nvme[key]
        if val is not None:
            # Promote to RAM on access
            self.ram[key] = val
        return val

    def __contains__(self, key: str) -> bool:
        return key in self.ram or key in self.nvme

    def delete(self, key: str):
        """Delete from all tiers."""
        del self.ram[key]
        del self.nvme[key]

    def get_or_compute(self, key: str, fn: callable, *, tier: str = "ram") -> Any:
        """Get cached value or compute and store it."""
        val = self.get(key)
        if val is not None:
            return val
        val = fn()
        self.set(key, val, tier=tier)
        return val

    def stats(self) -> MemoryStats:
        """Full memory subsystem snapshot."""
        ram_s = self.ram.get_stats()
        nvme_s = self.nvme.get_stats()

        total_used = ram_s["used_bytes"] + nvme_s["total_bytes"]
        total_capacity = (RAM_BUDGET_MB + 1024) * 1024 * 1024  # rough estimate

        return MemoryStats(
            ram_used_mb=ram_s["used_bytes"] // (1024 * 1024),
            ram_free_mb=(ram_s["max_bytes"] - ram_s["used_bytes"]) // (1024 * 1024),
            nvme_cached_mb=nvme_s["total_bytes"] // (1024 * 1024),
            active_tier="ram",
            pressure="low" if ram_s["util_pct"] < 70 else "medium" if ram_s["util_pct"] < 90 else "high",
        )

    def clear(self):
        """Clear all tiers."""
        self.ram.clear()
        self.nvme.clear()
