"""
TAAR v13 — AI Management Board (Governance Layer 5)
Multi-agent voting + executive override system.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

class RiskLevel(str, Enum):
    LOW = "low"       # auto approve
    MEDIUM = "medium" # simulation required
    HIGH = "high"     # board vote required
    CRITICAL = "critical" # blocked by default

class VoteVerdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    VETOED = "vetoed"
    PENDING = "pending"
    OVERRIDE = "override"

class BoardMember:
    def __init__(self, name: str, role: str, expertise: list[str], bias: float = 0.0):
        self.name = name
        self.role = role
        self.expertise = expertise  # topics this member is strong in
        self.bias = bias            # -1.0 (very conservative) to +1.0 (aggressive)

    def evaluate(self, proposal: dict, risk: RiskLevel) -> tuple[VoteVerdict, float]:
        score = 0.5 + self.bias * 0.1
        topic = proposal.get("topic", "")
        for exp in self.expertise:
            if exp.lower() in topic.lower():
                score += 0.15  # bonus for expertise
        if risk == RiskLevel.CRITICAL:
            score *= 0.4  # much harder to approve critical
        elif risk == RiskLevel.LOW:
            score *= 1.1
        elif risk == RiskLevel.HIGH:
            score *= 0.75
        verdict = VoteVerdict.APPROVED if score >= 0.6 else VoteVerdict.REJECTED
        return verdict, min(1.0, max(0.0, score))

@dataclass
class Proposal:
    id: str
    topic: str
    action_plan: dict
    risk: RiskLevel
    proposer: str
    budget_cost: float
    expected_roi: float
    votes: list[tuple[BoardMember, VoteVerdict, float]] = field(default_factory=list)
    override: bool = False
    override_reason: str = ""
    created_at: float = field(default_factory=time.time)
    decided_at: Optional[float] = None

    def approval_rate(self) -> float:
        if not self.votes:
            return 0.0
        return sum(1 for _, v, _ in self.votes if v == VoteVerdict.APPROVED) / len(self.votes)

    def decision(self) -> VoteVerdict:
        if self.override:
            return VoteVerdict.OVERRIDE
        if self.risk == RiskLevel.LOW:
            return VoteVerdict.APPROVED
        if self.risk == RiskLevel.CRITICAL:
            return VoteVerdict.VETOED
        rate = self.approval_rate()
        if rate >= 0.6:
            return VoteVerdict.APPROVED
        elif rate <= 0.2:
            return VoteVerdict.REJECTED
        return VoteVerdict.PENDING

class GovernanceBoard:
    def __init__(self):
        self.members: list[BoardMember] = [
            BoardMember("CEO-Alpha", "Chief Executive", ["strategy", "architecture", "execution"], bias=0.1),
            BoardMember("CFO-Beta", "Chief Financial", ["cost", "budget", "roi"], bias=-0.2),
            BoardMember("CTO-Gamma", "Chief Technology", ["engineering", "code", "infrastructure"], bias=0.1),
            BoardMember("CSO-Delta", "Chief Security", ["security", "risk", "safety"], bias=-0.3),
            BoardMember("COO-Epsilon", "Chief Operations", ["devops", "deployment", "workflow"], bias=0.0),
        ]
        self.proposals: list[Proposal] = []
        self.decided: list[Proposal] = []
        self.stats = {"total": 0, "approved": 0, "rejected": 0, "vetoed": 0, "overridden": 0}

    def submit(self, topic: str, action_plan: dict, risk: RiskLevel,
               budget_cost: float, expected_roi: float, proposer: str = "CEO") -> str:
        pid = f"PROP-{len(self.proposals)+1:04d}"
        prop = Proposal(
            id=pid, topic=topic, action_plan=action_plan, risk=risk,
            budget_cost=budget_cost, expected_roi=expected_roi, proposer=proposer
        )
        self.proposals.append(prop)
        self.stats["total"] += 1
        return pid

    def vote(self, proposal_id: str) -> VoteVerdict:
        prop = next((p for p in self.proposals if p.id == proposal_id), None)
        if not prop:
            return VoteVerdict.REJECTED
        for member in self.members:
            verdict, confidence = member.evaluate({"topic": prop.topic, "risk": prop.risk}, prop.risk)
            prop.votes.append((member, verdict, confidence))
        prop.decided_at = time.time()
        decision = prop.decision()
        self.decided.append(prop)
        self.stats["approved" if decision == VoteVerdict.APPROVED else
                         "rejected" if decision == VoteVerdict.REJECTED else
                         "vetoed" if decision == VoteVerdict.VETOED else
                         "overridden"] += 1
        return decision

    def executive_override(self, proposal_id: str, reason: str) -> VoteVerdict:
        prop = next((p for p in self.proposals if p.id == proposal_id), None)
        if prop:
            prop.override = True
            prop.override_reason = reason
            prop.decided_at = time.time()
            self.decided.append(prop)
            self.stats["overridden"] += 1
            self.stats["approved"] += 1
            return VoteVerdict.OVERRIDE
        return VoteVerdict.REJECTED

    def get_report(self) -> dict:
        return {
            "total_proposals": self.stats["total"],
            "approved": self.stats["approved"],
            "rejected": self.stats["rejected"],
            "vetoed": self.stats["vetoed"],
            "overridden": self.stats["overridden"],
            "approval_rate": self.stats["approved"] / max(1, self.stats["total"]),
            "pending": len(self.proposals),
        }

if __name__ == "__main__":
    board = GovernanceBoard()
    pid1 = board.submit("Deploy new service to production", {"action": "deploy"}, RiskLevel.HIGH, 2.0, 3.5)
    pid2 = board.submit("Run ruff check on codebase", {"action": "lint"}, RiskLevel.LOW, 0.1, 10.0)
    pid3 = board.submit("Delete production database", {"action": "destroy"}, RiskLevel.CRITICAL, 999.0, 0.0)
    decisions = [board.vote(p) for p in [pid1, pid2, pid3]]
    print(f"Decisions: {[d.value for d in decisions]}")
    print(f"Report: {board.get_report()}")
