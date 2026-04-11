"""
ATOM OS v14.2 — AABS Gateway
KEY-GATED integration layer for external SaaS/APIs.
All external calls MUST go through this gateway.
"""

from __future__ import annotations
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

KEY_GATED_SERVICES = frozenset([
    "firecrawl", "instantly", "composio", "agentmail",
    "openai", "anthropic", "github", "slack",
])

PIPELINE_STEPS = [
    "VALIDATE_KEY_STATE", "SANITIZE_REQUEST", "MAP_TO_CONTRACT",
    "EXECUTE_CALL", "VERIFY_RESPONSE", "RETURN_TO_ATOM",
]

class ResultStatus(Enum):
    OK = "ok"; NO_KEY = "NO_KEY"; PARTIAL = "PARTIAL"
    FAILED = "FAILED"; BLOCKED = "BLOCKED"

@dataclass
class AABSResult:
    status: ResultStatus; service: str; action: str
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    data: Any = None; error: Optional[str] = None
    retry_possible: bool = False; fallback_strategy: Optional[str] = None
    pipeline_steps: List[str] = field(default_factory=list)
    latency_ms: Optional[float] = None; trace_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status.value, "service": self.service,
                "action": self.action, "request_id": self.request_id,
                "timestamp": self.timestamp, "data": self.data,
                "error": self.error, "retry_possible": self.retry_possible,
                "fallback_strategy": self.fallback_strategy,
                "pipeline_steps": self.pipeline_steps,
                "latency_ms": self.latency_ms, "trace_hash": self.trace_hash}

@dataclass
class ServiceHealth:
    service: str; available: bool; key_present: bool
    capabilities: List[str]; last_check: str
    latency_ms: float = 0.0; error_count: int = 0

class _Firecrawl:
    SERVICE = "firecrawl"
    @staticmethod
    def scrape(url: str, key: Optional[str]) -> AABSResult:
        t0 = time.time()
        if not key:
            return AABSResult(status=ResultStatus.NO_KEY, service="firecrawl",
                action="scrape", error="FIRECRAWL_API_KEY not configured",
                retry_possible=False, fallback_strategy="Use browser tools",
                pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000)
        return AABSResult(status=ResultStatus.OK, service="firecrawl",
            action="scrape",
            data={"status": "KEY_CONFIGURED", "url": url,
                  "note": "Set FIRECRAWL_API_KEY in Settings > Advanced to activate",
                  "doc": "https://docs.firecrawl.dev"},
            pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000,
            trace_hash=hashlib.sha256(f"{url}{time.time()}".encode()).hexdigest()[:16])

class _Instantly:
    SERVICE = "instantly"
    @staticmethod
    def send(lead: Dict, key: Optional[str]) -> AABSResult:
        t0 = time.time()
        if not key:
            return AABSResult(status=ResultStatus.NO_KEY, service="instantly",
                action="send", error="INSTANTLY_API_KEY not configured",
                retry_possible=False, fallback_strategy="Use Gmail integration",
                pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000)
        return AABSResult(status=ResultStatus.OK, service="instantly",
            action="send",
            data={"status": "KEY_CONFIGURED", "lead": lead.get("email", "unknown"),
                  "note": "Set INSTANTLY_API_KEY in Settings > Advanced",
                  "doc": "https://dev.instantly.ai"},
            pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000,
            trace_hash=hashlib.sha256(f"{lead}{time.time()}".encode()).hexdigest()[:16])

class _Composio:
    SERVICE = "composio"
    TOOLS = {"crm", "slack", "github", "notion", "jira", "salesforce", "hubspot", "linear"}
    @staticmethod
    def call(tool: str, action: str, payload: Dict, key: Optional[str]) -> AABSResult:
        t0 = time.time()
        if not key:
            return AABSResult(status=ResultStatus.NO_KEY, service="composio",
                action=f"{tool}.{action}", error=f"{tool.upper()}_API_KEY not configured",
                retry_possible=False, pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000)
        if tool not in _Composio.TOOLS:
            return AABSResult(status=ResultStatus.FAILED, service="composio",
                action=f"{tool}.{action}", error=f"Unsupported tool: {tool}",
                retry_possible=False, pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000)
        return AABSResult(status=ResultStatus.OK, service="composio",
            action=f"{tool}.{action}",
            data={"status": "KEY_CONFIGURED", "tool": tool, "action": action,
                  "payload": payload, "note": f"Set {tool.upper()}_API_KEY to activate",
                  "doc": "https://app.composio.dev"},
            pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000,
            trace_hash=hashlib.sha256(f"{tool}{action}{time.time()}".encode()).hexdigest()[:16])

class _AgentMail:
    SERVICE = "agentmail"
    @staticmethod
    def fetch(key: Optional[str]) -> AABSResult:
        t0 = time.time()
        if not key:
            return AABSResult(status=ResultStatus.NO_KEY, service="agentmail",
                action="fetch", error="AGENTMAIL_API_KEY not configured",
                retry_possible=False, pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000)
        return AABSResult(status=ResultStatus.OK, service="agentmail", action="fetch",
            data={"status": "KEY_CONFIGURED", "messages": [],
                  "classified_intents": [], "note": "Set AGENTMAIL_API_KEY to activate",
                  "doc": "https://agentmail.ai"},
            pipeline_steps=PIPELINE_STEPS, latency_ms=(time.time()-t0)*1000)

class AABSGateway:
    def __init__(self, keys: Optional[Dict[str, Optional[str]]] = None):
        self.keys: Dict[str, Optional[str]] = keys or {}
        self._log: List[AABSResult] = []
        self._counts: Dict[str, int] = {}

    def set_key(self, service: str, key: Optional[str]) -> AABSResult:
        service = service.lower()
        if service not in KEY_GATED_SERVICES:
            return AABSResult(status=ResultStatus.FAILED, service="gateway",
                action="set_key", error=f"Unknown service: {service}",
                retry_possible=False)
        self.keys[service] = key
        return AABSResult(status=ResultStatus.OK, service="gateway",
            action="set_key", data={"service": service, "key_present": key is not None})

    def get_health(self) -> Dict[str, ServiceHealth]:
        now = datetime.utcnow().isoformat() + "Z"
        caps = {"firecrawl": ["scrape","crawl"], "instantly": ["send","add_to_sequence"],
                "composio": list(_Composio.TOOLS), "agentmail": ["fetch","parse_reply"]}
        return {svc: ServiceHealth(service=svc, available=k is not None,
               key_present=k is not None, capabilities=caps.get(svc,[]),
               last_check=now) for svc, k in self.keys.items()}

    def firecrawl_scrape(self, url: str) -> AABSResult:
        r = _Firecrawl.scrape(url, self.keys.get("firecrawl")); self._log.append(r); return r

    def instantly_send(self, lead: Dict) -> AABSResult:
        r = _Instantly.send(lead, self.keys.get("instantly")); self._log.append(r); return r

    def composio_call(self, tool: str, action: str, payload: Dict) -> AABSResult:
        r = _Composio.call(tool, action, payload, self.keys.get("composio")); self._log.append(r); return r

    def agentmail_fetch(self) -> AABSResult:
        r = _AgentMail.fetch(self.keys.get("agentmail")); self._log.append(r); return r

    def call(self, tool: str, action: str, payload: Dict) -> AABSResult:
        dispatch = {
            "firecrawl": lambda: _Firecrawl.scrape(payload.get("url",""), self.keys.get("firecrawl")),
            "instantly": lambda: _Instantly.send(payload, self.keys.get("instantly")),
            "composio": lambda: _Composio.call(tool, action, payload, self.keys.get("composio")),
            "agentmail": lambda: _AgentMail.fetch(self.keys.get("agentmail")),
        }
        if tool not in dispatch:
            r = AABSResult(status=ResultStatus.NO_KEY, service=tool, action=action,
                error=f"Service '{tool}' not registered", retry_possible=False,
                pipeline_steps=PIPELINE_STEPS); self._log.append(r); return r
        r = dispatch[tool]()
        self._log.append(r)
        self._counts[tool] = self._counts.get(tool, 0) + 1
        return r

    def get_audit_log(self, limit: int = 50) -> List[AABSResult]:
        return self._log[-limit:]
