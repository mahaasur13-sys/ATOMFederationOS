"""
TAAR v9 — Autonomous AI Civilization OS (CIV-OS)
Self-regulating multi-economy civilization: trade, compete, collaborate, evolve.

Architecture:
    CivilizationCouncil + CrossEconomyTrade + GlobalResourceMarket
        + CivilizationMemory + CivilizationEvolution
            ↓
    ┌──────────────────────────────────────────────────────────┐
    │         ECONOMY NETWORK LAYER (multi-ECONOS)            │
    │  ECONOS_A (security) ←trade→ ECONOS_B (dev) ←trade→ ... │
    └──────────────────────────────────────────────────────────┘
"""

from __future__ import annotations
import time, random

# TAAR v9 components
from civilization_council import (
    CivilizationCouncil, CouncilAction, Alliance,
    EconomyHealth, ConflictRecord,
)
from cross_economy_trade import CrossEconomyTrade, TradeDeal, TradeStatus
from global_resource_market import GlobalResourceMarket, MarketRegime
from civilization_memory import CivilizationMemory, ResourceCrisis
from civilization_evolution import CivilizationEvolution, EvolutionDecision


class TAARv9CivOS:
    """
    TAAR v9 — Autonomous AI Civilization Operating System.
    Global loop:
        1. Observe all economies
        2. Compute global stability
        3. Detect conflicts / opportunities
        4. Allocate resources
        5. Trigger trade / competition
        6. Update civilization memory
        7. Evolve economy structures
    """

    def __init__(self, num_economies: int = 3):
        # Core governance layers
        self.council = CivilizationCouncil()
        self.trade = CrossEconomyTrade()
        self.resource_market = GlobalResourceMarket()
        self.memory = CivilizationMemory()
        self.evolution = CivilizationEvolution()

        # Register economies
        self.economy_names = []
        for i in range(num_economies):
            econ_id = f"ECONOS_{chr(65+i)}"  # A, B, C...
            self.economy_names.append(econ_id)
            self.council.register_economy(econ_id, stability=0.8 + random.random() * 0.15)
            self.evolution.register_economy(econ_id)
            # Seed economic memory
            self.memory.evolution_events.append(
                self.memory.evolution_events.__class__.__name__  # just placeholder
            )

        # Track economy performance
        self.econ_stats: dict[str, dict] = {
            econ: {
                "total_value": 0.0,
                "jobs_completed": 0,
                "jobs_failed": 0,
                "stability": 0.8,
                "resource_usage": 0.3,
                "last_trade": 0.0,
            }
            for econ in self.economy_names
        }

        self.cycle_count = 0
        self.stats = {
            "cycles": 0,
            "conflicts_detected": 0,
            "alliances_formed": 0,
            "trades_executed": 0,
            "evolutions_triggered": 0,
            "crises": 0,
        }

    def _update_econ_stats(self, econ_id: str, stability: float, resource_usage: float):
        """Update local stats for an economy."""
        if econ_id in self.econ_stats:
            self.econ_stats[econ_id]["stability"] = stability
            self.econ_stats[econ_id]["resource_usage"] = resource_usage
            # Update council
            self.council.update_economy(
                econ_id, stability, resource_usage,
                conflict_exposure=random.uniform(0.0, 0.3),
                collaboration_score=random.uniform(0.2, 0.7),
            )

    def single_cycle(self, verbose: bool = True) -> dict:
        """One full civilization cycle."""
        self.cycle_count += 1
        if verbose:
            print("\n" + "=" * 65)
            print("🌍 TAAR v9 — Autonomous AI Civilization OS (CIV-OS)")
            print("=" * 65)

        # ── 1. OBSERVE all economies ────────────────────────────────────────
        avg_stability = sum(s["stability"] for s in self.econ_stats.values()) / len(self.econ_stats)
        avg_resource = sum(s["resource_usage"] for s in self.econ_stats.values()) / len(self.econ_stats)
        total_gpu_supply = 1.0 - avg_resource
        total_gpu_demand = avg_resource + random.uniform(0.0, 0.2)
        total_llm_supply = 0.8
        total_llm_demand = 0.5 + random.uniform(0.0, 0.2)

        self.resource_market.update_resource_state(
            gpu_s=total_gpu_supply, gpu_d=total_gpu_demand,
            llm_s=total_llm_supply, llm_d=total_llm_demand,
        )
        if verbose:
            mkt = self.resource_market.get_market_summary()
            print(f"[MARKET] regime={mkt['regime']} | GPU: supply={mkt['gpu']['supply']} demand={mkt['gpu']['demand']}")

        # Update council with current state
        for econ_id in self.economy_names:
            stats = self.econ_stats[econ_id]
            self._update_econ_stats(econ_id, stats["stability"], stats["resource_usage"])

        # ── 2. COMPUTE global stability ────────────────────────────────────
        council_state = self.council.get_civilization_state()
        if verbose:
            print(f"[COUNCIL] stability={council_state.global_stability:.3f} | "
                  f"conflicts={council_state.conflict_index:.3f} | "
                  f"collaboration={council_state.collaboration_index:.3f}")

        # ── 3. DETECT conflicts / opportunities ──────────────────────────────
        conflicts = self.council.detect_conflicts()
        for c in conflicts:
            self.memory.record_interaction(
                c.economies[0], c.economies[1], "conflict", -c.severity
            )
            self.memory.evolution_events.append(c)  # track
            self.stats["conflicts_detected"] += 1
            if verbose:
                print(f"[CONFLICT] {c.conflict_id}: {c.economies} severity={c.severity:.2f}")

        alliances = self.council.detect_alliances()
        for a in alliances:
            self.memory.record_interaction(
                a.member_ids[0], a.member_ids[1], "alliance", a.strength
            )
            self.memory.alliances.append({"alliance_id": a.alliance_id, "members": a.member_ids})
            self.stats["alliances_formed"] += 1
            if verbose:
                print(f"[ALLIANCE] {a.alliance_id}: {a.member_ids} strength={a.strength:.2f}")

        # ── 4. COUNCIL action ────────────────────────────────────────────────
        action, reason = self.council.get_council_action()
        if verbose and action.value != "none":
            print(f"[COUNCIL ACTION] {action.value.upper()} → {reason}")

        # Apply sanctions if needed
        if action == CouncilAction.SANCTION:
            # Apply to highest-conflict economies
            unstable = sorted(
                self.council.economy_healths.values(),
                key=lambda h: h.conflict_exposure,
                reverse=True
            )[:2]
            for h in unstable:
                self.trade.block_pair(h.economy_id, "ANY")

        # ── 5. TRADE between economies ──────────────────────────────────────
        # Randomly generate trade opportunities
        for _ in range(random.randint(0, 2)):
            if len(self.economy_names) < 2:
                continue
            econ_a, econ_b = random.sample(self.economy_names, 2)
            resource = random.choice(["gpu_compute", "llm_tokens", "storage"])
            amount = random.uniform(1.0, 10.0)
            opp = self.trade.compute_trade_opportunity(econ_a, econ_b, resource, amount)
            # Simulate trade acceptance
            if random.random() > 0.3:  # 70% accept rate
                deal = self.trade.post_trade_request(econ_a, econ_b, resource, amount, opp["fair_price"])
                accepted = self.trade.accept_deal(deal.deal_id, opp["fair_price"] * random.uniform(0.85, 0.95))
                if accepted:
                    self.memory.record_trade(econ_a, econ_b, resource, amount, opp["fair_price"])
                    self.econ_stats[econ_a]["last_trade"] = self.cycle_count
                    self.stats["trades_executed"] += 1
                    if verbose:
                        print(f"[TRADE] {deal.deal_id}: {econ_a} → {econ_b} | {resource} {amount:.1f} @ ${opp['fair_price']:.3f}")

        # ── 6. RESOURCE allocation ───────────────────────────────────────────
        for econ_id in self.economy_names:
            stats = self.econ_stats[econ_id]
            request = stats["resource_usage"] * 0.5
            allocated = self.resource_market.allocate_from_pool(econ_id, request)
            if verbose and allocated > 0.1:
                print(f"[RESOURCE] {econ_id} allocated {allocated:.3f} GPU units")

        # ── 7. ECONOMY simulation (one job per economy) ────────────────────────
        for econ_id in self.economy_names:
            stats = self.econ_stats[econ_id]
            success = random.random() > stats["jobs_failed"] / max(stats["jobs_completed"], 1) * 0.1
            stats["jobs_completed"] += 1
            if not success:
                stats["jobs_failed"] += 1
            stats["total_value"] += random.uniform(0.5, 2.0)
            stats["stability"] = max(0.5, min(1.0, stats["stability"] + (0.01 if success else -0.03)))
            stats["resource_usage"] = max(0.1, min(0.9, stats["resource_usage"] + random.uniform(-0.05, 0.05)))

            # Record in evolution
            from civilization_evolution import EconomySnapshot
            self.evolution.update_economy_performance(econ_id, EconomySnapshot(
                economy_id=econ_id,
                total_value_generated=stats["total_value"],
                mission_success_rate=(
                    stats["jobs_completed"] / max(stats["jobs_completed"] + stats["jobs_failed"], 1)
                ),
                stability=stats["stability"],
                lifespan_cycles=self.cycle_count,
                resource_efficiency=1.0 - stats["resource_usage"],
            ))

        # ── 8. CRISIS detection ─────────────────────────────────────────────
        if self.resource_market.regime == MarketRegime.CRISIS:
            crisis = self.memory.record_crisis(
                "gpu_shortage", 0.8, list(self.econ_stats.keys())
            )
            self.stats["crises"] += 1
            if verbose:
                print(f"[CRISIS] {crisis.crisis_id}: GPU shortage regime detected")

        # ── 9. EVOLUTION decisions ────────────────────────────────────────────
        decisions = self.evolution.compute_evolution_decisions()
        for d in decisions:
            result = self.evolution.execute_decision(d)
            self.stats["evolutions_triggered"] += 1
            self.memory.record_evolution(d.action, f"{d.action}: {d.target}", result)
            if verbose:
                print(f"[EVOLUTION] {d.decision_id}: {d.action} {d.target} → {result}")

        # ── 10. MEMORY update ─────────────────────────────────────────────────
        self.evolution.update_progress(council_state.global_stability, sum(s["total_value"] for s in self.econ_stats.values()))

        if verbose:
            council_summary = self.council.get_summary()
            trade_summary = self.trade.get_trade_summary()
            evo_report = self.evolution.get_evolution_report()
            mem_summary = self.memory.get_memory_summary()
            print(f"\n[CYCLE {self.cycle_count}]")
            print(f"  economies={len(self.evolution.active_economies)} | "
                  f"stability={council_state.global_stability:.3f} | "
                  f"progress={evo_report['civilizational_progress']:.3f}")
            print(f"  trades={self.stats['trades_executed']} | "
                  f"conflicts={self.stats['conflicts_detected']} | "
                  f"evolutions={self.stats['evolutions_triggered']}")
            print(f"  economy healths: {council_summary['economy_healths']}")
            print(f"  active alliances: {council_summary['active_alliances']} | "
                  f"active conflicts: {council_summary['active_conflicts']}")

        self.stats["cycles"] = self.cycle_count
        return {
            "cycle": self.cycle_count,
            "global_stability": round(council_state.global_stability, 3),
            "regime": self.resource_market.regime.value,
            "economies": len(self.evolution.active_economies),
            "active_conflicts": self.stats["conflicts_detected"],
            "active_alliances": self.stats["alliances_formed"],
            "trades": self.stats["trades_executed"],
            "evolutions": self.stats["evolutions_triggered"],
            "crises": self.stats["crises"],
            "civilizational_progress": round(self.evolution.civilizational_progress, 4),
        }


def main():
    os = TAARv9CivOS(num_economies=3)
    print("🌍 TAAR v9 — Autonomous AI Civilization OS (CIV-OS)")
    print(f"Economies: {os.economy_names}")
    print(f"Market regime: {os.resource_market.regime.value}")
    print()
    for i in range(4):
        result = os.single_cycle(verbose=True)
        print(f"\n==> cycle={result['cycle']} | stability={result['global_stability']} | "
              f"regime={result['regime']} | economies={result['economies']} | "
              f"progress={result['civilizational_progress']}")
        print(f"    trades={result['trades']} | conflicts={result['active_conflicts']} | "
              f"evolutions={result['evolutions']} | crises={result['crises']}")


if __name__ == "__main__":
    main()
