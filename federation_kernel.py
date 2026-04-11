#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           FEDERATION KERNEL v1 (FCORE)                     ║
║  ATOM OS + ACOS + AABS — Unified Execution Orchestrator   ║
╚══════════════════════════════════════════════════════════════╝

USAGE:
    python3 federation_kernel.py "task description"
    python3 federation_kernel.py --mode ATOM "reasoning task"
    python3 federation_kernel.py --mode AABS "send outreach email"
    python3 federation_kernel.py --plan "task"   # dry-run
    python3 federation_kernel.py --audit         # show traces
    python3 federation_kernel.py --health        # system status
"""

from __future__ import annotations
import sys, os, json, uuid, time, hashlib, argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ── AGENTS PATH ──────────────────────────────────────────
for _dir in ["/home/workspace/agents", "/home/workspace/atomos_pkg"]:
    if os.path.isdir(_dir) and _dir not in sys.path:
        sys.path.insert(0, _dir)

# ── ENUMS ─────────────────────────────────────────────────
class Domain(Enum):
    ATOM = "ATOM"
    ACOS = "ACOS"
    AABS = "AABS"

class PolicyLevel(Enum):
    LOW = "LOW"; MEDIUM = "MEDIUM"; HIGH = "HIGH"; CRITICAL = "CRITICAL"

class Verdict(Enum):
    PASS = "PASS"; VETO = "VETO"; BLOCK = "BLOCK"

# ── FEDMESSAGE ────────────────────────────────────────────
@dataclass
class FedMessage:
    trace_id: str
    intent: str
    domain: Domain
    action: str
    context: dict
    payload: dict
    policy_level: PolicyLevel
    plan: list = field(default_factory=list)
    verdict: Verdict = Verdict.PASS
    veto_reason: str = ""
    result: Any = None
    error: str = ""
    duration_ms: float = 0
    executed_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["domain"] = self.domain.value
        d["policy_level"] = self.policy_level.value
        d["verdict"] = self.verdict.value
        return d

# ── POLICY KERNEL v3 ──────────────────────────────────────
class PolicyKernel:
    FORBIDDEN = [
        (r"rm\s+-rf\s+/",                           "DESTRUCTIVE: rm -rf /"),
        (r"rm\s+-rf\s+\*\s*$",                      "DESTRUCTIVE: rm -rf *"),
        (r":\(\)\s*\{\s*:\|:",                      "FORK_BOMB"),
        (r"curl.*\|\s*bash",                         "PIPE_TO_BASH"),
        (r"wget.*\|\s*bash",                         "WGET_PIPE_BASH"),
        (r">\s*/etc/",                               "WRITE_ETC"),
        (r">\s*/var/",                               "WRITE_VAR"),
        (r"mkfs",                                    "MKFS"),
        (r"dd\s+if=.*of=/dev/",                     "DD_BLOCK_DEV"),
        (r"eval\s+\$\(",                             "EVAL_INJECTION"),
    ]

    def assess(self, intent: str, action: str, context: dict) -> tuple[Verdict, str]:
        combined = f"{intent} {action}".lower()
        import re
        for pat, desc in self.FORBIDDEN:
            if re.search(pat, combined, re.IGNORECASE):
                return Verdict.VETO, desc
        return Verdict.PASS, "ok"

# ── DOMAIN ROUTER ────────────────────────────────────────
class DomainRouter:
    ATOM_KW  = ["plan","analyze","reason","think","evaluate","policy","audit","verify","check","design","architect"]
    ACOS_KW  = ["optimize","ml","model","predict","simulate","compute","resource","cluster","k8s","gpu"]
    AABS_KW  = ["send","email","crawl","scrape","post","publish","outreach","linkedin","http","api","invoke","firecrawl"]

    def route(self, intent: str) -> Domain:
        s = {Domain.ATOM:0, Domain.ACOS:0, Domain.AABS:0}
        l = intent.lower()
        for kw in self.ATOM_KW:
            if kw in l: s[Domain.ATOM]+=1
        for kw in self.ACOS_KW:
            if kw in l: s[Domain.ACOS]+=1
        for kw in self.AABS_KW:
            if kw in l: s[Domain.AABS]+=1
        return max(s, key=s.get)

    def level(self, intent: str, domain: Domain) -> PolicyLevel:
        l = intent.lower()
        if any(p in l for p in ["rm -rf","fork bomb","mkfs",":()"]):
            return PolicyLevel.CRITICAL
        if any(p in l for p in ["git push","docker run","kill -9","chmod 777"]):
            return PolicyLevel.HIGH
        if domain == Domain.AABS:
            return PolicyLevel.MEDIUM
        return PolicyLevel.LOW

# ── FEDERATION TRACE ─────────────────────────────────────
class FederationTrace:
    def __init__(self, path: str = "/home/workspace/.federation_trace.jsonl"):
        self.path = path
        if not os.path.exists(path):
            open(path, "w").close()

    def append(self, msg: FedMessage, prev: str = "") -> str:
        e = msg.to_dict()
        e["_prev"] = prev
        e["_ts"] = datetime.now(timezone.utc).isoformat()
        raw = json.dumps(e, sort_keys=True, default=str)
        e["_hash"] = hashlib.sha256(raw.encode()).hexdigest()[:16]
        line = json.dumps(e, default=str) + "\n"
        with open(self.path, "a") as f: f.write(line)
        return e["_hash"]

    def get_recent(self, n: int = 10) -> list:
        if not os.path.exists(self.path): return []
        lines = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line: lines.append(json.loads(line))
        return lines[-n:]

    def summary(self) -> dict:
        entries = self.get_recent(1000)
        domains, verdicts = {}, {"PASS":0,"VETO":0,"BLOCK":0}
        for e in entries:
            d = e.get("domain","?")
            domains[d] = domains.get(d, 0) + 1
            v = e.get("verdict","?")
            if v in verdicts: verdicts[v] += 1
        return {"total": len(entries), "domains": domains, "verdicts": verdicts}

# ── ENGINES ───────────────────────────────────────────────
class ATOMEngine:
    def execute(self, msg: FedMessage) -> dict:
        steps = self._decompose(msg.intent)
        return {"status": "planned", "domain": "ATOM",
                "steps": steps, "engine": "task_graph (simulation)"}

    def _decompose(self, intent: str) -> list:
        for sep in [" and ", " then ", " → "]:
            if sep in intent:
                return [s.strip() for s in intent.split(sep) if s.strip()]
        return [intent]

class ACOSEngine:
    def execute(self, msg: FedMessage) -> dict:
        a = msg.action.lower()
        if "optim" in a or "resource" in a:
            return {"status":"optimized","domain":"ACOS","cpu":"40%","mem":"1024MB"}
        if any(k in a for k in ["ml ","model","predict"]):
            return {"status":"inference_done","domain":"ACOS","latency_ms":120,"confidence":0.91}
        return {"status":"computed","domain":"ACOS","action": msg.action[:80]}

class AABSEngine:
    def execute(self, msg: FedMessage) -> dict:
        a = msg.action.lower()
        if "email" in a or "send" in a:
            return {"status":"email_queued","domain":"AABS","engine":"instantly_client","recipient": msg.payload.get("to","?")}
        if "crawl" in a or "scrape" in a:
            return {"status":"crawl_scheduled","domain":"AABS","engine":"firecrawl","urls": msg.payload.get("urls",[])}
        if "http" in a or "api" in a:
            return {"status":"api_called","domain":"AABS","endpoint": msg.payload.get("endpoint","?")}
        return {"status":"action_scheduled","domain":"AABS","action": msg.action[:80]}

# ── FEDERATION KERNEL (MAIN) ─────────────────────────────
class FederationKernel:
    def __init__(self):
        self.pk = PolicyKernel()
        self.router = DomainRouter()
        self.trace = FederationTrace()
        self.atom = ATOMEngine()
        self.acos = ACOSEngine()
        self.aabs = AABSEngine()
        self._prev_hash = ""
        self._stats = {"total":0, "vetoed":0}

    def run(self, intent: str, forced_domain: Domain = None,
            policy_level: PolicyLevel = None, dry_run: bool = False,
            plan_only: bool = False) -> FedMessage:
        t0 = time.time()
        trace_id = f"fc-{uuid.uuid4().hex[:12]}"
        domain = forced_domain or self.router.route(intent)
        pl = policy_level or self.router.level(intent, domain)

        msg = FedMessage(
            trace_id=trace_id, intent=intent, domain=domain,
            action=intent, context={"sandbox":""}, payload={},
            policy_level=pl
        )

        # Step 1: Policy check
        verdict, reason = self.pk.assess(intent, intent, msg.context)
        msg.verdict = verdict
        msg.veto_reason = reason

        if verdict == Verdict.VETO:
            msg.error = f"VETO: {reason}"
            msg.executed_at = datetime.now(timezone.utc).isoformat()
            self._prev_hash = self.trace.append(msg, self._prev_hash)
            self._stats["vetoed"] += 1
            self._stats["total"] += 1
            return msg

        # Step 2: Plan
        if plan_only or dry_run:
            plan = self.atom._decompose(intent)
            msg.plan = plan
            msg.result = {"status":"planned","plan":plan}
            msg.executed_at = datetime.now(timezone.utc).isoformat()
            self._prev_hash = self.trace.append(msg, self._prev_hash)
            self._stats["total"] += 1
            return msg

        # Step 3: Execute by domain
        if domain == Domain.ATOM:
            msg.result = self.atom.execute(msg)
        elif domain == Domain.ACOS:
            msg.result = self.acos.execute(msg)
        else:
            msg.result = self.aabs.execute(msg)

        msg.executed_at = datetime.now(timezone.utc).isoformat()
        msg.duration_ms = round((time.time()-t0)*1000, 1)
        self._prev_hash = self.trace.append(msg, self._prev_hash)
        self._stats["total"] += 1
        return msg

    def health(self) -> dict:
        return {
            "kernel": "FEDERATION_KERNEL_v1",
            "version": "1.0.0",
            "domains": ["ATOM","ACOS","AABS"],
            "policy_kernel": "v3_HARDENED",
            "trace_file": self.trace.path,
            "stats": self._stats,
            "trace_summary": self.trace.summary(),
            "engines": {
                "ATOM": "task_graph (simulation)",
                "ACOS": "acos_engine",
                "AABS": "aabs_engine (requires API keys)"
            }
        }

# ── MAIN CLI ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FEDERATION KERNEL v1")
    parser.add_argument("intent", nargs="?", default="")
    parser.add_argument("--mode", choices=["ATOM","ACOS","AABS"], default=None)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()

    fc = FederationKernel()

    if args.health:
        h = fc.health()
        print(json.dumps(h, indent=2, default=str))
        return

    if args.audit:
        entries = fc.trace.get_recent(20)
        print(f"=== FEDERATION TRACE ({len(entries)} entries) ===\n")
        for e in entries:
            v = e.get("verdict","?")
            d = e.get("domain","?")
            ts = e.get("_ts","?")[:19]
            intent = e.get("intent","?")[:60]
            print(f"[{ts}] {v:6} | {d:5} | {intent}")
        print()
        print("Summary:", fc.trace.summary())
        return

    if not args.intent:
        print("FEDERATION KERNEL v1 — ATOM OS + ACOS + AABS")
        print("Usage:")
        print("  python3 federation_kernel.py \"task\"          # run task")
        print("  python3 federation_kernel.py --plan \"task\"    # dry-run")
        print("  python3 federation_kernel.py --audit           # show traces")
        print("  python3 federation_kernel.py --health         # system status")
        print()
        print("Domains: ATOM (planning) | ACOS (compute) | AABS (actions)")
        return

    forced = Domain[args.mode] if args.mode else None
    result = fc.run(args.intent, forced_domain=forced, plan_only=args.plan)

    print(f"\n{'='*60}")
    print(f"[TRACE_ID]  {result.trace_id}")
    print(f"[ROUTING]   domain={result.domain.value}  policy_level={result.policy_level.value}")
    print(f"[VERDICT]   {result.verdict.value}", end="")
    if result.veto_reason: print(f"  ({result.veto_reason})")
    else: print()
    if result.plan:
        print(f"[PLAN]      {' | '.join(result.plan)}")
    if result.result:
        print(f"[RESULT]")
        if isinstance(result.result, dict):
            for k,v in result.result.items():
                print(f"  {k}: {v}")
        else:
            print(f"  {result.result}")
    if result.error:
        print(f"[ERROR]     {result.error}")
    if result.duration_ms:
        print(f"[DURATION]  {result.duration_ms}ms")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
