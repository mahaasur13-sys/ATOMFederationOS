"""
TAAR v6 — Policy Consensus Engine
Nodes propose policy updates → aggregator merges weights → conflicts resolved by stability.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class PolicyVote:
    node_id: str
    param: str
    proposed_value: float
    reason: str
    stability_delta: float  # expected stability improvement
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConsensusDecision:
    param: str
    agreed_value: float
    voters: list[str]
    method: str  # "unanimous" | "majority" | "stability_weighted"
    confidence: float  # 0-1
    reason: str


class PolicyConsensusEngine:
    """
    Consensus-driven policy evolution.
    Rule: IF node policies conflict → choose policy with highest system stability gain.
    """

    def __init__(self):
        self._pending_votes: list[PolicyVote] = []
        self._decisions: list[ConsensusDecision] = []
        self._node_policies: dict[str, dict[str, float]] = {}  # node_id → {param: value}

    def submit_vote(self, vote: PolicyVote):
        self._pending_votes.append(vote)
        # Update node's local policy
        if vote.node_id not in self._node_policies:
            self._node_policies[vote.node_id] = {}
        self._node_policies[vote.node_id][vote.param] = vote.proposed_value

    def resolve(self) -> list[ConsensusDecision]:
        """Aggregate pending votes into consensus decisions."""
        decisions = []
        # Group votes by param
        by_param: dict[str, list[PolicyVote]] = {}
        for v in self._pending_votes:
            by_param.setdefault(v.param, []).append(v)
        self._pending_votes.clear()

        for param, votes in by_param.items():
            if not votes:
                continue
            # Strategy: stability_weighted — pick voter with highest expected stability_delta
            if len(votes) == 1:
                v = votes[0]
                decisions.append(ConsensusDecision(
                    param=param,
                    agreed_value=v.proposed_value,
                    voters=[v.node_id],
                    method="single",
                    confidence=0.5,
                    reason=f"Only vote: {v.reason}",
                ))
            else:
                # Pick the vote with highest stability improvement
                best = max(votes, key=lambda v: v.stability_delta)
                voters = [v.node_id for v in votes]
                decisions.append(ConsensusDecision(
                    param=param,
                    agreed_value=best.proposed_value,
                    voters=voters,
                    method="stability_weighted",
                    confidence=min(len(votes) / 5.0, 1.0),
                    reason=f"Best stability delta: {best.reason}",
                ))

            self._decisions.append(decisions[-1])

        return decisions

    def get_global_policy(self) -> dict[str, float]:
        """Merge all node policies into a global view (median per param)."""
        all_params: dict[str, list[float]] = {}
        for node_policy in self._node_policies.values():
            for param, value in node_policy.items():
                all_params.setdefault(param, []).append(value)
        return {param: (sum(vals) / len(vals)) for param, vals in all_params.items()}

    def get_decision_history(self) -> list[ConsensusDecision]:
        return list(self._decisions)

    def get_stats(self) -> dict:
        return {
            "pending_votes": len(self._pending_votes),
            "total_decisions": len(self._decisions),
            "nodes_participating": len(self._node_policies),
            "global_policy": self.get_global_policy(),
        }
