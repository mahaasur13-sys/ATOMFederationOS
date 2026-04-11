"""
TAAR v8 — Autonomous AI Economy OS (ECONOS)
Self-regulating economy: organizations compete, bid, execute, evolve.

Architecture:
    EconomyCoordinator → TaskMarket → ResourceLedger → ValueEvaluator → EconomicMemory
                    ↕
              TAAR_v7_ORG nodes (DEV/OPS/PLANNER/QA)
"""

from __future__ import annotations
import uuid, time
from dataclasses import dataclass

# TAAR v8 components
from economy_coordinator import EconomyCoordinator, EconomyState, MarketRegime
from task_market import TaskMarket, MarketJob
from resource_ledger import ResourceLedger
from value_evaluator import ValueEvaluator
from economic_memory import EconomicMemory
from system_observer import SystemObserver


# ─── Organization definitions ─────────────────────────────────────────────────

@dataclass
class AIOrganization:
    """An autonomous AI organization (TAAR v7 instance)."""
    org_id: str
    role: str           # dev | ops | planner | qa
    budget: float
    capacity: float    # 0-1 current capacity
    registered_in_market: bool = False


class TAARv8EconomyOS:
    """
    TAAR v8 — Autonomous AI Economy Operating System.
    Global economy loop: observe → post jobs → collect bids → allocate → execute → evaluate → ledger.
    """

    ORG_ROLES = {
        "DEV_ORG":    "dev",
        "OPS_ORG":    "ops",
        "PLANNER_ORG": "planner",
        "QA_ORG":     "qa",
        "SECURITY_ORG": "security",
    }

    def __init__(self):
        # Core engine components
        self.coordinator = EconomyCoordinator()
        self.market = TaskMarket()
        self.ledger = ResourceLedger()
        self.evaluator = ValueEvaluator()
        self.memory = EconomicMemory()
        self.observer = SystemObserver()

        # Register organizations
        self.orgs: dict[str, AIOrganization] = {}
        for org_id, role in self.ORG_ROLES.items():
            org = AIOrganization(org_id=org_id, role=role, budget=3.0, capacity=1.0)
            self.orgs[org_id] = org
            self.coordinator.register_org(org_id, budget=3.0)
            self.market.register_org(org_id, reputation=0.8, capacity=1.0)
            self.ledger.register_node(org_id)

        self.cycle_count = 0
        self.stats = {
            "cycles": 0, "jobs_posted": 0, "jobs_completed": 0,
            "jobs_failed": 0, "total_value_generated": 0.0,
            "avg_market_price": 0.0,
        }

    def _generate_missions(self, state) -> list[str]:
        """Generate mission tasks based on system state."""
        missions = []
        pressure = state.gpu_pressure if hasattr(state, 'gpu_pressure') else state.execution_pressure
        if pressure > 0.5:
            missions.append("fix critical CI pipeline failure")
            missions.append("optimize GPU memory usage")
        if state.memory_pressure > 40:
            missions.append("clean up episodic memory")
        if self.cycle_count % 3 == 0:
            missions.append("audit workspace security")
        if not missions:
            missions = [
                "scan workspace for unused files",
                "analyze system performance logs",
                "review code quality metrics",
            ]
        return missions

    def _execute_org_mission(self, org: AIOrganization, task: str) -> dict:
        """Simulate org executing a task. Returns result dict."""
        start = time.time()
        # Simulate execution (in real: spawn subprocess with mission_controller)
        complexity = self.market.estimate_complexity(task)
        duration = 0.05 + (complexity * 0.2)
        time.sleep(min(duration, 0.3))
        success = (complexity < 0.85)  # high-complexity sometimes fails
        stability_delta = 0.05 if success else -0.08
        gpu_used = complexity * 2.0
        llm_tokens = int(complexity * 10000)
        compute_s = complexity * 5.0
        cost = gpu_used * 0.05 + llm_tokens * 0.0001 + compute_s * 0.01
        return {
            "success": success,
            "stability_delta": stability_delta,
            "gpu_used": gpu_used,
            "llm_tokens": llm_tokens,
            "compute_s": compute_s,
            "resource_cost": cost,
            "duration_s": time.time() - start,
        }

    def single_cycle(self, verbose: bool = True) -> dict:
        """One full economic cycle."""
        self.cycle_count += 1
        if verbose:
            print("\n" + "=" * 60)
            print("TAAR v8 — Autonomous AI Economy OS (ECONOS)")
            print("=" * 60)

        # 1. OBSERVE system
        state = self.observer.observe()
        supply = state.compute if hasattr(state, 'compute') else 1.0 - state.gpu_pressure
        demand = state.task_failure_rate if hasattr(state, 'task_failure_rate') else 0.4
        token_cost = state.memory_pressure / 100.0
        pressure = state.gpu_pressure if hasattr(state, 'gpu_pressure') else 0.3

        self.coordinator.update_market_state(
            compute_supply=supply,
            task_demand=demand,
            token_cost=token_cost,
            execution_pressure=pressure,
        )
        eco_state: EconomyState = self.coordinator.state

        if verbose:
            print(f"[ECONOMY] regime={eco_state.regime.value} | "
                  f"supply={eco_state.compute_supply:.2f} | demand={eco_state.task_demand:.2f} | "
                  f"liquidity={eco_state.system_liquidity:.2f}")

        # 2. GENERATE missions → post to market
        missions = self._generate_missions(state)
        contracts = []
        for task in missions:
            contract = self.coordinator.post_job(task, complexity=0.5 + (hash(task) % 40) / 100)
            contracts.append(contract)
        self.stats["jobs_posted"] += len(contracts)
        if verbose:
            print(f"[MARKET] posted {len(contracts)} jobs: "
                  f"{[c.job_id for c in contracts]}")

        # 3. BIDS — orgs bid on jobs
        for contract in contracts:
            for org_id, org in self.orgs.items():
                if org.budget >= contract.current_price * 0.5:
                    self.coordinator.submit_bid(
                        contract.job_id, org_id,
                        bid_price=contract.current_price * 0.9,
                        reliability=0.75 + hash(org_id) % 25 / 100,
                    )
                    self.market.submit_bid(
                        contract.job_id, org_id,
                        price=contract.current_price * 0.85,
                    )

        # 4. ALLOCATE jobs
        allocated = []
        for contract in contracts:
            winner = self.coordinator.allocate_job(contract.job_id)
            if winner:
                allocated.append((contract, winner))
                if verbose:
                    print(f"[MARKET] {contract.job_id} → {winner} @ ${contract.current_price}")

        # 5. EXECUTE allocated jobs
        job_results = []
        for contract, winner_org_id in allocated:
            org = self.orgs.get(winner_org_id)
            if not org:
                continue
            result = self._execute_org_mission(org, contract.task)
            job_results.append((contract, winner_org_id, result))

            # 6. RECORD in ledger
            self.ledger.record_job(
                winner_org_id, contract.job_id, result["success"],
                result["gpu_used"], result["llm_tokens"], result["compute_s"],
            )
            org.budget -= contract.current_price
            org.capacity = max(0.0, org.capacity - contract.complexity * 0.2)

            # 7. EVALUATE
            eval_record = self.evaluator.evaluate_job(
                contract.job_id, winner_org_id, result["success"],
                result["stability_delta"], result["resource_cost"],
            )
            if verbose:
                grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "💀"}
                emoji = grade_emoji.get(eval_record.grade, "⚪")
                print(f"  {emoji} {contract.job_id} [{eval_record.grade}] {contract.task[:40]} "
                      f"| cost=${result['resource_cost']:.4f} | Δstab={result['stability_delta']:+.2f}")

            # 8. RECORD outcome
            self.coordinator.record_outcome(
                contract.job_id, result["success"], result["stability_delta"],
            )
            self.market.record_result(
                contract.job_id, result["success"],
                result["stability_delta"], eval_record.value_score,
            )
            self.memory.record_job(
                contract.job_id, contract.task, contract.current_price,
                winner_org_id, result["success"], contract.complexity,
            )
            self.memory.update_org_performance(
                winner_org_id,
                success_rate=1.0 if result["success"] else 0.0,
                stability_delta=result["stability_delta"],
                total_cost=result["resource_cost"],
                value_score=eval_record.value_score,
            )
            if result["success"]:
                self.stats["jobs_completed"] += 1
            else:
                self.stats["jobs_failed"] += 1
            self.stats["total_value_generated"] += eval_record.value_score

        # 9. RECORD market regime
        self.memory.record_market_fluctuation(
            eco_state.regime.value, eco_state.compute_supply,
            eco_state.task_demand, eco_state.token_cost_index,
        )

        # 10. Economic intelligence
        market_summary = self.coordinator.get_market_summary()
        econ_stats = self.memory.get_economic_stats()
        sys_report = self.ledger.get_system_report()
        top_orgs = self.evaluator.get_top_orgs(n=3)

        if verbose:
            print(f"\n[ECONOMY] cycle={self.cycle_count}")
            print(f"  org reliability: {market_summary['org_reliability']}")
            print(f"  ledger: {sys_report}")
            print(f"  top orgs: {[(o.entity_id, o.grade, round(o.value, 2)) for o in top_orgs]}")
            print(f"  market: {market_summary}")

        # 11. Market dynamics adjustment
        if eco_state.regime == MarketRegime.HOT:
            print(f"  📈 HOT market — demand>{eco_state.compute_supply:.2f} supply, prices rising")
        elif eco_state.regime == MarketRegime.COLD:
            print(f"  📉 COLD market — supply>demand, lowering prices to attract jobs")
        elif eco_state.regime == MarketRegime.CRISIS:
            print(f"  🚨 CRISIS — system overloaded, emergency pricing")

        self.stats["cycles"] += 1
        self.stats["avg_market_price"] = (
            sum(c.current_price for c in contracts) / len(contracts)
            if contracts else 0
        )

        return {
            "cycle": self.cycle_count,
            "regime": eco_state.regime.value,
            "jobs_allocated": len(allocated),
            "jobs_completed": self.stats["jobs_completed"],
            "jobs_failed": self.stats["jobs_failed"],
            "total_value": round(self.stats["total_value_generated"], 3),
            "top_orgs": [(o.entity_id, o.grade, round(o.value, 2)) for o in top_orgs],
            "ledger": sys_report,
            "econ_stats": econ_stats,
        }


def main():
    os = TAARv8EconomyOS()
    print("TAAR v8 — Autonomous AI Economy OS (ECONOS)")
    print(f"Organizations: {list(os.orgs.keys())}")
    print()
    for i in range(3):
        result = os.single_cycle(verbose=True)
        print(f"\n[RESULT] cycle={result['cycle']} | "
              f"regime={result['regime']} | "
              f"completed={result['jobs_completed']}/{result['jobs_completed']+result['jobs_failed']} | "
              f"value={result['total_value']}")


if __name__ == "__main__":
    main()
