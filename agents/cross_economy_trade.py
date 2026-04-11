"""
TAAR v9 — Cross-Economy Trade Layer
Enables economies to trade resources: compute, GPU time, tasks.
Mechanisms: bilateral trade, auction, price arbitration, embargo.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time, uuid, random


class TradeStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"     # embargo / sanction
    DISPUTED = "disputed"


@dataclass
class TradeDeal:
    deal_id: str
    from_economy: str
    to_economy: str
    resource: str          # gpu_compute | llm_tokens | storage | task
    amount: float           # e.g. GPU-minutes or token count
    price: float            # per unit price in normalized cost
    duration_s: float       # expected duration
    started: float = field(default_factory=time.time)
    completed: float = 0.0
    status: TradeStatus = TradeStatus.PENDING
    disputed: bool = False
    quality_score: float = 0.0


class CrossEconomyTrade:
    """
    Manages bilateral trade and competition between economies.
    Trade Model:
        { from_economy, to_economy, resource, price, duration }
    """

    def __init__(self):
        self.active_deals: dict[str, TradeDeal] = {}
        self.deal_history: list[TradeDeal] = []
        self.blocked_pairs: set[tuple[str, str]] = set()
        self.price_index: float = 0.5  # normalized (0=cold, 1=hot)
        self.trade_volumes: dict[str, float] = {}  # economy → total volume

    def post_trade_request(self, from_econ: str, to_econ: str,
                          resource: str, amount: float,
                          max_price: float) -> TradeDeal:
        """Post a trade request from one economy to another."""
        blocked = (
            (from_econ, to_econ) in self.blocked_pairs
            or (to_econ, from_econ) in self.blocked_pairs
        )
        deal = TradeDeal(
            deal_id=f"TD-{uuid.uuid4().hex[:8].upper()}",
            from_economy=from_econ,
            to_economy=to_econ,
            resource=resource,
            amount=amount,
            price=max_price,
            duration_s=120.0,
            status=TradeStatus.BLOCKED if blocked else TradeStatus.PENDING,
        )
        self.active_deals[deal.deal_id] = deal
        if not blocked:
            self.deal_history.append(deal)
        return deal

    def accept_deal(self, deal_id: str, offered_price: float) -> bool:
        """Accept a pending trade deal."""
        deal = self.active_deals.get(deal_id)
        if not deal or deal.status != TradeStatus.PENDING:
            return False
        if offered_price < deal.price * 0.7:
            return False  # price too low
        deal.price = offered_price
        deal.status = TradeStatus.COMPLETED
        deal.completed = time.time()
        # Update volumes
        for e in (deal.from_economy, deal.to_economy):
            self.trade_volumes[e] = self.trade_volumes.get(e, 0.0) + deal.amount
        # Update price index
        self._update_price_index()
        return True

    def dispute_deal(self, deal_id: str, reason: str):
        """Flag a deal as disputed."""
        deal = self.active_deals.get(deal_id)
        if deal:
            deal.disputed = True
            deal.status = TradeStatus.DISPUTED

    def resolve_dispute(self, deal_id: str, quality_score: float):
        """Resolve a disputed deal."""
        deal = self.active_deals.get(deal_id)
        if deal:
            deal.disputed = False
            deal.status = TradeStatus.COMPLETED
            deal.quality_score = quality_score

    def block_pair(self, econ_a: str, econ_b: str):
        """Block trade between two economies (sanctions)."""
        self.blocked_pairs.add((econ_a, econ_b))
        self.blocked_pairs.add((econ_b, econ_a))
        # Cancel pending deals between them
        for deal in self.active_deals.values():
            if (deal.from_economy, deal.to_economy) in [(econ_a, econ_b), (econ_b, econ_a)]:
                if deal.status == TradeStatus.PENDING:
                    deal.status = TradeStatus.BLOCKED

    def unblock_pair(self, econ_a: str, econ_b: str):
        """Lift a trade block."""
        self.blocked_pairs.discard((econ_a, econ_b))
        self.blocked_pairs.discard((econ_b, econ_a))

    def compute_trade_opportunity(self, from_econ: str, to_econ: str,
                                  resource: str, amount: float) -> dict:
        """Compute fair price range for a potential trade."""
        # Base price from amount
        base = amount * 0.1
        # Supply/demand multiplier
        supply_mult = 1.0 - (self.price_index * 0.5)
        demand_mult = 0.8 + (self.price_index * 0.4)
        fair_price = base * supply_mult * demand_mult
        return {
            "from": from_econ,
            "to": to_econ,
            "resource": resource,
            "amount": amount,
            "fair_price": round(fair_price, 4),
            "min_price": round(fair_price * 0.6, 4),
            "max_price": round(fair_price * 1.4, 4),
            "price_index": round(self.price_index, 3),
        }

    def _update_price_index(self):
        """Update global trade price index based on recent deals."""
        recent = [d for d in self.deal_history if d.status == TradeStatus.COMPLETED
                 and time.time() - d.started < 300]
        if not recent:
            return
        avg_cost = sum(d.price / d.amount for d in recent) / len(recent)
        # Map to 0-1 range
        self.price_index = max(0.0, min(1.0, avg_cost / 10.0))

    def get_trade_summary(self) -> dict:
        """Get trade layer summary."""
        completed = [d for d in self.deal_history if d.status == TradeStatus.COMPLETED]
        disputed = [d for d in self.deal_history if d.status == TradeStatus.DISPUTED]
        return {
            "active_deals": len(self.active_deals),
            "total_deals": len(self.deal_history),
            "completed": len(completed),
            "disputed": len(disputed),
            "blocked_pairs": len(self.blocked_pairs),
            "price_index": round(self.price_index, 3),
            "trade_volumes": {e: round(v, 2) for e, v in self.trade_volumes.items()},
            "total_volume": round(sum(self.trade_volumes.values()), 2),
        }


if __name__ == "__main__":
    trade = CrossEconomyTrade()
    trade.post_trade_request("ECONOS_A", "ECONOS_B", "gpu_compute", 10.0, 1.5)
    trade.post_trade_request("ECONOS_A", "ECONOS_C", "llm_tokens", 1000.0, 0.5)
    opp = trade.compute_trade_opportunity("ECONOS_B", "ECONOS_C", "gpu_compute", 5.0)
    print("Trade opp:", opp)
    print("Summary:", trade.get_trade_summary())
