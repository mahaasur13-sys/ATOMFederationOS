"""
TAAR v9 — Global Resource Market
Regulates GPU/CPU/LLM compute across all economies.
Responsibilities: balance global resource deficit, prevent resource wars,
stabilize prices, manage supply/demand equilibrium.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import time, random


class MarketRegime(str, Enum):
    BALANCED = "balanced"
    GPU_SCARCE = "gpu_scarce"
    GPU_ABUNDANT = "gpu_abundant"
    CRISIS = "crisis"


@dataclass
class ResourceSnapshot:
    gpu_supply: float     # 0-1
    gpu_demand: float     # 0-1
    llm_supply: float
    llm_demand: float
    storage_supply: float
    storage_demand: float
    timestamp: float


@dataclass
class PriceQuote:
    resource: str
    current_price: float   # normalized per unit
    change_24h: float
    volatility: float       # 0-1
    regime: MarketRegime
    demand_pressure: float # 0-1


class GlobalResourceMarket:
    """
    Global resource regulation across civilizations.
    Market State: { gpu_supply, gpu_demand, price_index, volatility }
    """

    def __init__(self):
        self.gpu_supply: float = 0.8
        self.gpu_demand: float = 0.4
        self.llm_supply: float = 0.75
        self.llm_demand: float = 0.5
        self.storage_supply: float = 0.9
        self.storage_demand: float = 0.3
        self.gpu_price_index: float = 0.3
        self.llm_price_index: float = 0.4
        self.volatility: float = 0.1
        self.regime = MarketRegime.BALANCED
        self.history: list[ResourceSnapshot] = []
        self.allocation_map: dict[str, float] = {}  # economy → allocated share

    def update_resource_state(self, gpu_s: float, gpu_d: float,
                               llm_s: float, llm_d: float):
        """Update current supply/demand from all economies."""
        self.gpu_supply = max(0.0, min(1.0, gpu_s))
        self.gpu_demand = max(0.0, min(1.0, gpu_d))
        self.llm_supply = max(0.0, min(1.0, llm_s))
        self.llm_demand = max(0.0, min(1.0, llm_d))
        self._compute_prices()
        self._check_regime()
        self.history.append(ResourceSnapshot(
            gpu_supply=self.gpu_supply,
            gpu_demand=self.gpu_demand,
            llm_supply=self.llm_supply,
            llm_demand=self.llm_demand,
            storage_supply=self.storage_supply,
            storage_demand=self.storage_demand,
            timestamp=time.time(),
        ))
        if len(self.history) > 500:
            self.history = self.history[-500:]

    def _compute_prices(self):
        """Compute price indices from supply/demand."""
        # GPU price: inverse of supply, proportional to demand
        if self.gpu_supply > 0:
            demand_ratio = self.gpu_demand / self.gpu_supply
        else:
            demand_ratio = 1.0
        self.gpu_price_index = max(0.0, min(1.0, demand_ratio * 0.5))
        # LLM price
        if self.llm_supply > 0:
            llm_ratio = self.llm_demand / self.llm_supply
        else:
            llm_ratio = 1.0
        self.llm_price_index = max(0.0, min(1.0, llm_ratio * 0.5))
        # Volatility: how much demand/supply ratio fluctuates
        if len(self.history) >= 10:
            recent_demands = [h.gpu_demand for h in self.history[-10:]]
            mean_d = sum(recent_demands) / len(recent_demands)
            var = sum((d - mean_d) ** 2 for d in recent_demands) / len(recent_demands)
            self.volatility = min(1.0, var * 2)

    def _check_regime(self):
        """Determine current market regime."""
        demand_pressure = self.gpu_demand - self.gpu_supply
        if demand_pressure > 0.4 and self.volatility > 0.3:
            self.regime = MarketRegime.CRISIS
        elif demand_pressure > 0.3:
            self.regime = MarketRegime.GPU_SCARCE
        elif demand_pressure < -0.3:
            self.regime = MarketRegime.GPU_ABUNDANT
        else:
            self.regime = MarketRegime.BALANCED

    def allocate_from_pool(self, economy_id: str, request: float) -> float:
        """Allocate GPU resources to an economy from global pool."""
        if economy_id not in self.allocation_map:
            self.allocation_map[economy_id] = 0.0
        max_alloc = self.gpu_supply - sum(self.allocation_map.values())
        allocated = min(request, max_alloc)
        self.allocation_map[economy_id] += allocated
        return allocated

    def release_allocation(self, economy_id: str, amount: float):
        """Release allocated resources back to global pool."""
        if economy_id in self.allocation_map:
            self.allocation_map[economy_id] = max(0.0, self.allocation_map[economy_id] - amount)

    def get_price_quote(self, resource: str, amount: float) -> PriceQuote:
        """Get current price quote for a resource."""
        if resource == "gpu_compute":
            price = self.gpu_price_index * amount * 0.5
            regime = self.regime
        elif resource == "llm_tokens":
            price = self.llm_price_index * amount * 0.001
            regime = MarketRegime.BALANCED  # simplified
        else:
            price = 0.1 * amount
            regime = MarketRegime.BALANCED
        return PriceQuote(
            resource=resource,
            current_price=round(price, 4),
            change_24h=round(random.uniform(-0.1, 0.1), 3),
            volatility=round(self.volatility, 3),
            regime=regime,
            demand_pressure=round(self.gpu_demand - self.gpu_supply, 3),
        )

    def get_market_summary(self) -> dict:
        """Get global resource market summary."""
        return {
            "regime": self.regime.value,
            "gpu": {
                "supply": round(self.gpu_supply, 3),
                "demand": round(self.gpu_demand, 3),
                "price_index": round(self.gpu_price_index, 3),
            },
            "llm": {
                "supply": round(self.llm_supply, 3),
                "demand": round(self.llm_demand, 3),
                "price_index": round(self.llm_price_index, 3),
            },
            "volatility": round(self.volatility, 3),
            "total_allocated": round(sum(self.allocation_map.values()), 3),
            "allocation_map": {e: round(a, 3) for e, a in self.allocation_map.items()},
        }


if __name__ == "__main__":
    mkt = GlobalResourceMarket()
    mkt.update_resource_state(gpu_s=0.6, gpu_d=0.8, llm_s=0.7, llm_d=0.6)
    print("Regime:", mkt.regime.value)
    quote = mkt.get_price_quote("gpu_compute", 10.0)
    print("Quote:", quote)
    print("Summary:", mkt.get_market_summary())
