"""ATOM OS — Boot Log"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class BootEntry:
    service_id: str
    status: str      # ok | skipped | failed
    note: str = ""


@dataclass
class BootLog:
    entries: list[BootEntry] = field(default_factory=list)

    def add(self, service_id: str, status: str, note: str = "") -> None:
        self.entries.append(BootEntry(service_id, status, note))

    @property
    def all_ok(self) -> bool:
        return all(e.status == "ok" for e in self.entries)
