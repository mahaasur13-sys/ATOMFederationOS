"""
TAAR v8 — Economy Coordinator Core
Global AI economy: supply/demand balance, market pricing, job allocation.
"""

from __future__ import annotations
import uuid, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MarketRegime(Enum):
    NORMAL = "normal"           # balanced
    HOT = "hot"                 # demand > supply → prices rise
    COLD = "cold"               # supply > demand → prices fall
    CRISIS = "crisis"           # system overload


@dataclass
class EconomyState:
    """Full global economy snapshot."""
    compute_supply: float = 1.0     # 0-1 available compute
    task_demand: float = 0.3         # 0-1 active demand
    token_cost_index: float = 0.5    # 0-1 relative LLM cost
    system_liquidity: float = 0.8    # 0-1 free resources
    execution_pressure: float = 0.3  # 0-1 pressure on system
    regime: MarketRegime = MarketRegime.NORMAL
    tick: int = 0


@dataclass
class JobContract:
    """Marketable job listing."""
    job_id: str
    task: str
    base_price: float              # 0-1 resource units
    current_price: float           # market-adjusted
    complexity: float              # 0-1
    deadline: str = "soft"          # soft | hard
    status: str = "open"           # open | assigned | completed | failed
    assigned_org: str | None = None
    bids: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class EconomyCoordinator:
    """
    Global economy brain.
    Manages: supply/demand, market regime, dynamic pricing, job contracts.
    """

    BASE_PRICE_MAP = {
        "devops": 0.65,
        "build": 0.55,
        "test": 0.50,
        "analyze": 0.45,
        "fix": 0.60,
        "review": 0.40,
        "deploy": 0.70,
        "scan": 0.35,
        "audit": 0.40,
        "optimize": 0.55,
        "default": 0.50,
    }

    def __init__(self):
        self.state = EconomyState()
        self.contracts: dict[str, JobContract] = {}
        self.org_budgets: dict[str, float] = {}     # org → remaining budget
        self.org_reliability: dict[str, float] = {}  # org → 0-1 reliability score
        self.price_history: list[dict] = []

    def register_org(self, org_id: str, budget: float = 1.0):
        """Register an organization with initial budget."""
        self.org_budgets.setdefault(org_id, budget)
        self.org_reliability.setdefault(org_id, 0.85)

    def update_market_state(self, compute_supply: float, task_demand: float,
                             token_cost: float, execution_pressure: float):
        """Update economy state from system observer."""
        self.state.compute_supply = max(0.0, min(1.0, compute_supply))
        self.state.task_demand = max(0.0, min(1.0, task_demand))
        self.state.token_cost_index = max(0.0, min(1.0, token_cost))
        self.state.execution_pressure = max(0.0, min(1.0, execution_pressure))
        self.state.system_liquidity = self.state.compute_supply - self.state.task_demand
        self._update_regime()
        self.state.tick += 1

    def _update_regime(self):
        """Determine market regime from supply/demand."""
        pressure = self.state.execution_pressure
        supply = self.state.compute_supply
        demand = self.state.task_demand

        if pressure > 0.85:
            self.state.regime = MarketRegime.CRISIS
        elif demand > supply * 1.3:
            self.state.regime = MarketRegime.HOT
        elif supply > demand * 1.5 and pressure < 0.3:
            self.state.regime = MarketRegime.COLD
        else:
            self.state.regime = MarketRegime.NORMAL

    def _get_base_price(self, task: str) -> float:
        """Get base price for task type."""
        t = task.lower()
        for key, price in self.BASE_PRICE_MAP.items():
            if key in t:
                return price
        return self.BASE_PRICE_MAP["default"]

    def post_job(self, task: str, complexity: float = 0.5,
                  deadline: str = "soft") -> JobContract:
        """Post a new job to the market."""
        job_id = f"J-{uuid.uuid4().hex[:8].upper()}"
        base = self._get_base_price(task)
        current = self._adjust_price(base, complexity)
        contract = JobContract(
            job_id=job_id,
            task=task,
            base_price=base,
            current_price=current,
            complexity=complexity,
            deadline=deadline,
        )
        self.contracts[job_id] = contract
        return contract

    def _adjust_price(self, base: float, complexity: float) -> float:
        """Adjust price based on market regime and complexity."""
        regime = self.state.regime
        supply = self.state.compute_supply
        demand = self.state.task_demand

        # Supply/demand multiplier
        if supply > 0:
            sd_mult = (demand / supply) if supply > 0 else 1.0
        else:
            sd_mult = 2.0

        # Regime adjustment
        if regime == MarketRegime.HOT:
            price_mult = 1.0 + 0.25 * min(sd_mult - 1.0, 0.5)
        elif regime == MarketRegime.COLD:
            price_mult = 1.0 - 0.20
        elif regime == MarketRegime.CRISIS:
            price_mult = 1.5
        else:
            price_mult = 1.0

        # Complexity factor
        complexity_mult = 0.7 + (complexity * 0.6)

        final = base * price_mult * complexity_mult
        return round(min(final, 1.0), 3)

    def submit_bid(self, job_id: str, org_id: str, bid_price: float,
                   reliability: float) -> bool:
        """Organization submits a bid for a job."""
        if job_id not in self.contracts:
            return False
        contract = self.contracts[job_id]
        if contract.status != "open":
            return False
        if bid_price > self.org_budgets.get(org_id, 0):
            return False

        # Filter out previous bid from same org
        contract.bids = [b for b in contract.bids if b["org"] != org_id]
        contract.bids.append({
            "org": org_id,
            "bid": round(bid_price, 3),
            "reliability": reliability,
            "submitted_at": time.time(),
        })
        return True

    def allocate_job(self, job_id: str) -> str | None:
        """Allocate job to best bidder (price × reliability weighted)."""
        if job_id not in self.contracts:
            return None
        contract = self.contracts[job_id]
        if not contract.bids:
            return None

        # Best = lowest price × highest reliability
        def score(b):
            return b["bid"] * (1.1 - b["reliability"])  # prefer low price + high reliability

        contract.bids.sort(key=score)
        winner = contract.bids[0]
        contract.status = "assigned"
        contract.assigned_org = winner["org"]
        self.org_budgets[winner["org"]] -= contract.current_price
        return winner["org"]

    def record_outcome(self, job_id: str, success: bool, stability_delta: float):
        """Record job outcome → update org reliability."""
        if job_id not in self.contracts:
            return
        contract = self.contracts[job_id]
        contract.status = "completed" if success else "failed"
        org = contract.assigned_org
        if org:
            # Reliability: exponential moving average
            old = self.org_reliability.get(org, 0.85)
            if success:
                delta = stability_delta * 0.1
            else:
                delta = -0.15
            self.org_reliability[org] = max(0.1, min(1.0, old + delta))
            self.price_history.append({
                "job_id": job_id,
                "org": org,
                "price": contract.current_price,
                "success": success,
                "stability_delta": stability_delta,
                "tick": self.state.tick,
            })

    def get_market_summary(self) -> dict:
        """Full market snapshot."""
        open_jobs = [c for c in self.contracts.values() if c.status == "open"]
        assigned = [c for c in self.contracts.values() if c.status == "assigned"]
        completed = [c for c in self.contracts.values() if c.status == "completed"]
        return {
            "regime": self.state.regime.value,
            "supply": self.state.compute_supply,
            "demand": self.state.task_demand,
            "liquidity": self.state.system_liquidity,
            "pressure": self.state.execution_pressure,
            "open_jobs": len(open_jobs),
            "assigned_jobs": len(assigned),
            "total_jobs": len(self.contracts),
            "org_reliability": dict(self.org_reliability),
            "price_history_len": len(self.price_history),
        }


if __name__ == "__main__":
    eco = EconomyCoordinator()
    eco.register_org("TAAR_v7_A", budget=2.0)
    eco.register_org("TAAR_v7_B", budget=2.0)
    eco.register_org("OPS_TEAM", budget=2.0)

    eco.update_market_state(compute_supply=0.8, task_demand=0.5,
                              token_cost=0.45, execution_pressure=0.4)
    print(f"[ECONOMY] regime={eco.state.regime.value}, liquidity={eco.state.system_liquidity:.2f}")

    # Post jobs
    j1 = eco.post_job("fix CI pipeline", complexity=0.7)
    j2 = eco.post_job("analyze system logs", complexity=0.4)
    j3 = eco.post_job("deploy to production", complexity=0.9, deadline="hard")
    print(f"[MARKET] posted J1={j1.job_id} @ ${j1.current_price}, "
          f"J2={j2.job_id} @ ${j2.current_price}, "
          f"J3={j3.job_id} @ ${j3.current_price}")

    # Hot market test
    eco.update_market_state(0.5, 0.9, 0.7, 0.85)
    j4 = eco.post_job("urgent fix", complexity=0.8)
    print(f"[MARKET] hot regime J4 @ ${j4.current_price} (was ${j4.base_price})")

    # Bids
    eco.submit_bid(j1.job_id, "TAAR_v7_A", 0.55, 0.9)
    eco.submit_bid(j1.job_id, "TAAR_v7_B", 0.45, 0.75)
    winner = eco.allocate_job(j1.job_id)
    print(f"[MARKET] J1 winner: {winner} @ ${eco.contracts[j1.job_id].current_price}")

    # Outcomes
    eco.record_outcome(j1.job_id, success=True, stability_delta=0.08)
    print(f"[ECONOMY] org reliability: {eco.get_market_summary()['org_reliability']}")
    print(f"\n[ECONOMY] full summary: {eco.get_market_summary()}")
