"""
TAAR v8 — Economic Memory Graph
Stores: jobs_history, bids_history, org_performance,
market_fluctuations, resource_price_history.
Drives long-term economic intelligence.
"""

from __future__ import annotations
import json, time, uuid
from pathlib import Path
from typing import Any


class EconomicMemory:
    """
    Persistent economic memory graph.
    Stores and queries: jobs, bids, org performance, market trends.
    """

    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or "/tmp/economic_memory.jsonl"
        self.jobs_history: list[dict] = []
        self.bids_history: list[dict] = []
        self.org_performance: dict[str, dict] = {}
        self.market_fluctuations: list[dict] = []
        self.resource_price_history: list[dict] = []
        self._load()

    def _load(self):
        """Load from disk."""
        p = Path(self.storage_path)
        if p.exists():
            try:
                with open(p) as f:
                    data = json.load(f)
                    self.jobs_history = data.get("jobs_history", [])
                    self.bids_history = data.get("bids_history", [])
                    self.org_performance = data.get("org_performance", {})
                    self.market_fluctuations = data.get("market_fluctuations", [])
                    self.resource_price_history = data.get("resource_price_history", [])
            except Exception:
                pass

    def _save(self):
        """Persist to disk."""
        try:
            with open(self.storage_path, "w") as f:
                json.dump({
                    "jobs_history": self.jobs_history,
                    "bids_history": self.bids_history,
                    "org_performance": self.org_performance,
                    "market_fluctuations": self.market_fluctuations,
                    "resource_price_history": self.resource_price_history,
                }, f, indent=2)
        except Exception:
            pass

    def record_job(self, job_id: str, task: str, price: float,
                   winner: str | None, success: bool, complexity: float):
        """Record completed job."""
        self.jobs_history.append({
            "job_id": job_id,
            "task": task,
            "price": price,
            "winner": winner,
            "success": success,
            "complexity": complexity,
            "timestamp": time.time(),
        })
        if len(self.jobs_history) > 10000:
            self.jobs_history = self.jobs_history[-5000:]
        self._save()

    def record_bid(self, job_id: str, org_id: str, price: float, reliability: float):
        """Record a bid event."""
        self.bids_history.append({
            "job_id": job_id,
            "org_id": org_id,
            "price": price,
            "reliability": reliability,
            "timestamp": time.time(),
        })
        if len(self.bids_history) > 20000:
            self.bids_history = self.bids_history[-10000:]
        self._save()

    def update_org_performance(self, org_id: str, success_rate: float,
                               stability_delta: float, total_cost: float,
                               value_score: float):
        """Update org's economic performance profile."""
        current = self.org_performance.get(org_id, {
            "jobs_completed": 0, "jobs_failed": 0,
            "avg_success_rate": 0.0, "avg_stability_delta": 0.0,
            "total_cost": 0.0, "total_value": 0.0,
        })
        n = current["jobs_completed"] + current["jobs_failed"]
        current["jobs_completed"] += 1
        current["avg_success_rate"] = (
            (current["avg_success_rate"] * n + success_rate) / (n + 1)
        )
        current["avg_stability_delta"] = (
            (current["avg_stability_delta"] * n + stability_delta) / (n + 1)
        )
        current["total_cost"] += total_cost
        current["total_value"] += value_score
        self.org_performance[org_id] = current
        self._save()

    def record_market_fluctuation(self, regime: str, supply: float,
                                   demand: float, avg_price: float):
        """Record market regime change."""
        self.market_fluctuations.append({
            "regime": regime,
            "supply": supply,
            "demand": demand,
            "avg_price": avg_price,
            "timestamp": time.time(),
        })
        if len(self.market_fluctuations) > 5000:
            self.market_fluctuations = self.market_fluctuations[-2000:]
        self._save()

    def record_resource_price(self, resource_type: str, price: float):
        """Record resource price point."""
        self.resource_price_history.append({
            "resource_type": resource_type,
            "price": price,
            "timestamp": time.time(),
        })
        self._save()

    def get_trend(self, metric: str, window: int = 20) -> dict:
        """Compute trend for a metric over recent window."""
        if metric == "job_prices":
            data = [j["price"] for j in self.jobs_history[-window:]]
        elif metric == "success_rate":
            data = [j["success"] for j in self.jobs_history[-window:]]
        elif metric == "market_fluctuation":
            data = [float(m["regime"] == "hot") for m in self.market_fluctuations[-window:]]
        else:
            data = []
        if not data:
            return {"trend": "neutral", "value": 0.0}
        avg = sum(data) / len(data)
        if len(data) >= 2:
            slope = data[-1] - data[0]
            direction = "rising" if slope > 0.05 else "falling" if slope < -0.05 else "stable"
        else:
            direction = "stable"
        return {"trend": direction, "value": round(avg, 4), "samples": len(data)}

    def get_economic_stats(self) -> dict:
        """Full economic intelligence summary."""
        total_jobs = len(self.jobs_history)
        success_rate = (
            sum(1 for j in self.jobs_history if j["success"]) / total_jobs
            if total_jobs > 0 else 0.0
        )
        completed_jobs = [j for j in self.jobs_history if j.get("winner")]
        return {
            "total_jobs_recorded": total_jobs,
            "total_bids_recorded": len(self.bids_history),
            "orgs_tracked": len(self.org_performance),
            "avg_success_rate": round(success_rate, 3),
            "avg_job_price": round(
                sum(j["price"] for j in self.jobs_history) / total_jobs
                if total_jobs > 0 else 0.0, 3
            ),
            "regimes_recorded": len(self.market_fluctuations),
            "resource_prices_recorded": len(self.resource_price_history),
        }


if __name__ == "__main__":
    em = EconomicMemory("/tmp/taar_v8_test_mem.jsonl")
    em.record_market_fluctuation("normal", 0.8, 0.4, 0.50)
    em.record_market_fluctuation("hot", 0.5, 0.9, 0.72)
    em.update_org_performance("DEV_TEAM", 0.95, 0.12, 0.45, 2.1)
    em.update_org_performance("OPS_TEAM", 0.70, 0.05, 0.60, 1.2)
    em.record_job("MJ-001", "fix CI", 0.65, "DEV_TEAM", True, 0.6)
    em.record_job("MJ-002", "deploy", 0.80, "OPS_TEAM", True, 0.85)
    em.record_job("MJ-003", "scan", 0.30, "QA_TEAM", False, 0.35)
    print(f"[MEMORY] stats: {em.get_economic_stats()}")
    print(f"[MEMORY] job_prices trend: {em.get_trend('job_prices')}")
    print(f"[MEMORY] success_rate trend: {em.get_trend('success_rate')}")
    print(f"[MEMORY] DEV_TEAM perf: {em.org_performance.get('DEV_TEAM')}")
