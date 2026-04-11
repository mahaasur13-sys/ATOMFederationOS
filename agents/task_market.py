"""
TAAR v8 — Task Market Engine
Broadcasts jobs → collects bids → allocates to best org.
"""

from __future__ import annotations
import uuid, time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bid:
    org_id: str
    price: float
    reliability: float
    submitted_at: float = field(default_factory=time.time)


@dataclass
class MarketJob:
    """A job listed on the task market."""
    job_id: str
    task: str
    complexity: float
    deadline: str
    base_price: float
    current_price: float
    status: str = "open"
    bids: list[Bid] = field(default_factory=list)
    winner: str | None = None
    result: dict | None = None
    created_at: float = field(default_factory=time.time)


class TaskMarket:
    """
    Job exchange: converts tasks to market jobs, collects org bids,
    allocates to best performer based on price × reliability.
    """

    COMPLEXITY_KEYWORDS = {
        # High (0.7-1.0)
        "production": 0.85, "deploy": 0.80, "critical": 0.90,
        "security": 0.85, "migrate": 0.80, "refactor": 0.75,
        "cluster": 0.80, "distributed": 0.80, "kubernetes": 0.85,
        # Medium (0.4-0.7)
        "ci": 0.55, "build": 0.55, "test": 0.50, "pipeline": 0.60,
        "fix": 0.65, "debug": 0.60, "optimize": 0.60, "integration": 0.60,
        "mission": 0.60, "autonomous": 0.65,
        # Low (0.1-0.4)
        "scan": 0.30, "review": 0.35, "audit": 0.35, "analyze": 0.40,
        "report": 0.30, "query": 0.20, "list": 0.15,
    }

    def __init__(self):
        self.jobs: dict[str, MarketJob] = {}
        self.orgs: dict[str, dict] = {}  # org_id → metadata

    def register_org(self, org_id: str, reputation: float = 0.8,
                      capacity: float = 1.0):
        """Register an org in the market."""
        self.orgs[org_id] = {
            "reputation": reputation,
            "capacity": capacity,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "total_earned": 0.0,
        }

    def estimate_complexity(self, task: str) -> float:
        """Auto-estimate task complexity from keywords."""
        t = task.lower()
        scores = []
        for kw, score in self.COMPLEXITY_KEYWORDS.items():
            if kw in t:
                scores.append(score)
        if not scores:
            return 0.50  # default medium
        return round(sum(scores) / len(scores), 3)

    def publish_job(self, task: str, base_price: float | None = None,
                     deadline: str = "soft") -> MarketJob:
        """Publish a job to the market."""
        job_id = f"MJ-{uuid.uuid4().hex[:8].upper()}"
        complexity = self.estimate_complexity(task)
        price = base_price if base_price else self._compute_price(complexity)
        job = MarketJob(
            job_id=job_id,
            task=task,
            complexity=complexity,
            deadline=deadline,
            base_price=price,
            current_price=price,
        )
        self.jobs[job_id] = job
        return job

    def _compute_price(self, complexity: float) -> float:
        """Compute base price from complexity."""
        return round(0.3 + (complexity * 0.5), 3)

    def submit_bid(self, job_id: str, org_id: str, price: float) -> bool:
        """Org submits a bid. Returns True if accepted."""
        if job_id not in self.jobs:
            return False
        job = self.jobs[job_id]
        if job.status != "open":
            return False
        org = self.orgs.get(org_id, {})
        reliability = org.get("reputation", 0.5)
        if price > (org.get("capacity", 1.0) * 2.0):
            return False  # org can't afford it

        job.bids = [b for b in job.bids if b.org_id != org_id]
        job.bids.append(Bid(org_id=org_id, price=price, reliability=reliability))
        return True

    def allocate(self, job_id: str) -> str | None:
        """Allocate job to lowest price × highest reliability."""
        if job_id not in self.jobs:
            return None
        job = self.jobs[job_id]
        if not job.bids or job.status != "open":
            return None

        def merit(b: Bid):
            return b.price * (1.1 - b.reliability)

        job.bids.sort(key=merit)
        winner = job.bids[0]
        job.winner = winner.org_id
        job.status = "assigned"
        org = self.orgs.get(winner.org_id, {})
        org["capacity"] = max(0.0, org.get("capacity", 1.0) - job.complexity * 0.3)
        return winner.org_id

    def record_result(self, job_id: str, success: bool,
                      stability_delta: float, value_score: float):
        """Record execution result → update org reputation."""
        if job_id not in self.jobs:
            return
        job = self.jobs[job_id]
        job.status = "completed" if success else "failed"
        org_id = job.winner
        if not org_id:
            return
        org = self.orgs.get(org_id, {})
        rep = org.get("reputation", 0.8)
        if success:
            rep_delta = stability_delta * 0.15
            org["jobs_completed"] = org.get("jobs_completed", 0) + 1
            org["total_earned"] = org.get("total_earned", 0.0) + job.current_price
        else:
            rep_delta = -0.20
            org["jobs_failed"] = org.get("jobs_failed", 0) + 1
        org["reputation"] = max(0.1, min(1.0, rep + rep_delta))

    def get_market_stats(self) -> dict:
        """Market statistics."""
        total = len(self.jobs)
        by_status = {"open": 0, "assigned": 0, "completed": 0, "failed": 0}
        for j in self.jobs.values():
            by_status[j.status] = by_status.get(j.status, 0) + 1
        avg_price = sum(j.current_price for j in self.jobs.values()) / total if total else 0
        return {
            "total_jobs": total,
            "by_status": by_status,
            "avg_price": round(avg_price, 3),
            "registered_orgs": len(self.orgs),
        }


if __name__ == "__main__":
    mkt = TaskMarket()
    mkt.register_org("DEV_TEAM", reputation=0.9)
    mkt.register_org("OPS_TEAM", reputation=0.75)
    mkt.register_org("QA_TEAM", reputation=0.85)

    # Publish
    j1 = mkt.publish_job("fix critical CI pipeline failure in production")
    j2 = mkt.publish_job("scan all workspace files for secrets")
    j3 = mkt.publish_job("deploy update to kubernetes cluster")
    print(f"[MARKET] published 3 jobs: complexity={j1.complexity}, {j2.complexity}, {j3.complexity}")

    # Bids
    mkt.submit_bid(j1.job_id, "DEV_TEAM", 0.60)
    mkt.submit_bid(j1.job_id, "OPS_TEAM", 0.45)
    winner = mkt.allocate(j1.job_id)
    print(f"[MARKET] j1 allocated to: {winner}")

    # Results
    mkt.record_result(j1.job_id, success=True, stability_delta=0.12, value_score=0.85)
    mkt.record_result(j2.job_id, success=True, stability_delta=0.03, value_score=0.60)
    print(f"[MARKET] org stats: DEV={mkt.orgs['DEV_TEAM']['reputation']:.2f}, "
          f"OPS={mkt.orgs['OPS_TEAM']['reputation']:.2f}")
    print(f"[MARKET] stats: {mkt.get_market_stats()}")
