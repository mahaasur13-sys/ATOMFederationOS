"""
ATOM OS — Memory Hierarchy (VRAM / RAM / NVMe / Remote)
Multi-tier storage with automatic tiering based on access patterns.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from atomos.core.service_registry import register


@dataclass
class MemoryStats:
    vram_mb: float = 0.0
    ram_mb: float = 0.0
    disk_mb: float = 0.0
    hits: int = 0
    misses: int = 0


class MemoryTier:
    """Single memory tier with eviction."""

    def __init__(self, name: str, max_bytes: int, storage_path: str | None = None):
        self.name = name
        self.max_bytes = max_bytes
        self.storage_path = storage_path
        self._store: dict[str, Any] = {}
        self._access_times: dict[str, float] = {}
        self._access_count: dict[str, int] = {}

    def get(self, key: str) -> Any | None:
        if key in self._store:
            self._access_times[key] = time.time()
            self._access_count[key] = self._access_count.get(key, 0) + 1
            return self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.max_bytes // 1024:
            self._evict_lru()
        self._store[key] = value
        self._access_times[key] = time.time()
        self._access_count[key] = 1

    def _evict_lru(self) -> None:
        if not self._access_times:
            return
        lru_key = min(self._access_times, key=self._access_times.get)
        del self._store[lru_key]
        del self._access_times[lru_key]
        self._access_count.pop(lru_key, None)

    def __len__(self) -> int:
        return len(self._store)


@register("memory", module_type="memory", init_order=40)
class MemoryHierarchy:
    """
    Three-tier memory: VRAM (GPU) → RAM → Disk (NVMe).
    Automatic tiering based on frequency and size.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # VRAM tier: GPU-attached (simulated, max 8GB)
        self.vram = MemoryTier("vram", 8 * 1024 * 1024)

        # RAM tier: system memory (max 32GB)
        self.ram = MemoryTier("ram", 32 * 1024 * 1024)

        # Disk tier: NVMe (max 256GB)
        self.disk = MemoryTier(
            "disk",
            256 * 1024 * 1024,
            str(self.data_dir / "memory_disk.jsonl"),
        )
        self._load_disk()

        self.stats = MemoryStats()

    def get(self, key: str) -> Any | None:
        # Try fastest tier first
        for tier, name in [(self.vram, "vram"), (self.ram, "ram"), (self.disk, "disk")]:
            val = tier.get(key)
            if val is not None:
                self.stats.hits += 1
                return val
        self.stats.misses += 1
        return None

    def set(self, key: str, value: Any, hot: bool = False) -> None:
        """Store value. hot=True = keep in RAM, else disk."""
        if hot:
            self.ram.set(key, value)
        else:
            self.disk.set(key, value)

    def _load_disk(self) -> None:
        if not Path(self.disk.storage_path).exists():
            return
        try:
            with open(self.disk.storage_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    key = entry["key"]
                    self.disk._store[key] = entry["value"]
                    self.disk._access_times[key] = entry.get("atime", 0)
        except Exception:
            pass

    def flush_to_disk(self) -> None:
        with open(self.disk.storage_path, "w") as f:
            for key, val in self.disk._store.items():
                f.write(json.dumps({
                    "key": key,
                    "value": val,
                    "atime": self.disk._access_times.get(key, 0),
                }) + "\n")

    def health(self) -> dict:
        return {
            "vram_items": len(self.vram),
            "ram_items": len(self.ram),
            "disk_items": len(self.disk),
            "hit_rate": self.stats.hits / max(1, self.stats.hits + self.stats.misses),
        }

    def shutdown(self) -> None:
        self.flush_to_disk()
