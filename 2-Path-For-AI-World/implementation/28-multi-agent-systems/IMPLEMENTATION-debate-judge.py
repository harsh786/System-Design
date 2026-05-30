"""
Multi-Agent Systems: Debate/Judge Pattern
==========================================

Production implementation of the debate/judge pattern where proposer agents
generate competing solutions, critics identify weaknesses, and a judge
selects the best approach through structured multi-round debate.
"""

import asyncio
import uuid
import time
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field


# =============================================================================
# Core Types
# =============================================================================

class DebatePhase(Enum):
    PROPOSAL = "proposal"
    CRITIQUE = "critique"
    REBUTTAL = "rebuttal"
    JUDGMENT = "judgment"


@dataclass
class Argument:
    agent_id: str
    phase: DebatePhase
    content: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    round_number: int = 1
    timestamp: float = field(default_factory=time.time)


@dataclass
class Solution:
    proposer_id: str
    description: str
    approach: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    score: float = 0.0  # Assigned by judge


@dataclass
class JudgmentResult:
    winner: Optional[str]  # proposer_id or None (no winner)
    reasoning: str
    scores: dict[str, float] = field(default_factory=dict)  # proposer_id → score
    criteria_scores: dict = field(default_factory=dict)
    confidence: float = 0.0
    rounds_used: int = 0
    total_cost: float = 0.0


@dataclass
class DebateConfig:
    max_rounds: int = 3
    min_rounds: int = 1
    convergence_threshold: float = 0.3  # Score diff below this = converged
    max_cost: float = 0.50
    num_proposers: int = 2
    judging_criteria: list[str] = field(default_factory=lambda: [
        "correctness", "feasibility", "completeness", "efficiency", "clarity"
    ])


# =============================================================================
# Proposer Agent
# =============================================================================

class ProposerAgent:
    """Generates solutions and defends them against criticism."""

    def __init__(self, agent_id: str, perspective: str = "general"):
        self.agent_id = agent_id
        self.perspective = perspective
        self.cost = 0.0

    async def propose(self, problem: str, context: dict = None) -> Solution:
        """Generate an initial solution proposal."""
        await asyncio.sleep(0.4)  # Simulate LLM call
        
        # In production: LLM generates a solution from this agent's perspective
        solution = Solution(
            proposer_id=self.agent_id,
            description=f"Solution from {self.agent_id} ({self.perspective} perspective)",
            approach=f"Approach using {self.perspective} methodology for: {problem[:50]}",
            pros=[
                f"Pro 1: Strong {self.perspective} foundation",
                f"Pro 2: Well-established patterns",
                f"Pro 3: Good scalability characteristics",
            ],
            cons=[
                f"Con 1: May require more initial setup",
            ],
            evidence=[
                f"Evidence: {self.perspective} approach proven in similar systems",
                "Reference: Industry best practice documentation",
            ],
            confidence=0.78,
        )
        
        self.cost += 0.005
        return solution

    async def rebut(self, original_solution: Solution, 
                    critiques: list[Argument]) -> Argument:
        """Defend solution against critiques with evidence."""
        await asyncio.sleep(0.3)
        
        critique_points = [c.content for c in critiques]
        
        rebuttal = Argument(
            agent_id=self.agent_id,
            phase=DebatePhase.REBUTTAL,
            content=f"Rebuttal from {self.agent_id}: "
                   f"Addressing {len(critiques)} critiques. "
                   f"The concerns about {critique_points[0][:30] if critique_points else 'N/A'}... "
                   f"are mitigated by our approach because of established safeguards.",
            evidence=[
                "Counter-evidence: Performance benchmarks show acceptable overhead",
                "Counter-evidence: Similar systems deployed successfully at scale",
            ],
            confidence=0.72,
        )
        
        self.cost += 0.004
        return rebuttal

    async def critique_other(self, other_solution: Solution) -> Argument:
        """Critique another proposer's solution."""
        await asyncio.sleep(0.3)
        
        critique = Argument(
            agent_id=self.agent_id,
            phase=DebatePhase.CRITIQUE,
            content=f"Critique from {self.agent_id}: "
                   f"The proposed approach '{other_solution.approach[:30]}...' "
                   f"has potential issues with edge cases and may not handle "
                   f"high-load scenarios effectively.",
            evidence=[
                "Evidence: Similar approaches showed degradation under load",
                "Evidence: Edge case X not addressed in proposal",
            ],
            confidence=0.7,
        )
        
        self.cost += 0.003
        return critique


# =============================================================================
# Judge Agent
# =============================================================================

class JudgeAgent:
    """
    Evaluates solutions and debate arguments to select the best approach.
    Does NOT generate solutions — only evaluates.
    """

    def __init__(self, criteria: list[str]):
        self.criteria = criteria
        self.cost = 0.0

    async def judge(self, solutions: list[Solution],
                    debate_history: list[Argument],
                    round_number: int) -> JudgmentResult:
        """
        Evaluate solutions based on debate evidence and criteria.
        """
        await asyncio.sleep(0.5)  # Simulate LLM evaluation
        
        scores = {}
        criteria_scores = {}
        
        for solution in solutions:
            # Score each criterion (in production: LLM evaluates each)
            sol_criteria = {}
            for criterion in self.criteria:
                # Simulated scoring based on evidence and arguments
                base_score = solution.confidence
                
                # Boost from evidence
                evidence_boost = min(0.1, len(solution.evidence) * 0.02)
                
                # Penalty from unaddressed critiques
                critiques_against = [
                    a for a in debate_history
                    if a.phase == DebatePhase.CRITIQUE and a.agent_id != solution.proposer_id
                ]
                rebuttals = [
                    a for a in debate_history
                    if a.phase == DebatePhase.REBUTTAL and a.agent_id == solution.proposer_id
                ]
                
                unaddressed_penalty = max(0, (len(critiques_against) - len(rebuttals)) * 0.05)
                
                score = min(1.0, max(0.0, base_score + evidence_boost - unaddressed_penalty))
                sol_criteria[criterion] = score
            
            criteria_scores[solution.proposer_id] = sol_criteria
            scores[solution.proposer_id] = sum(sol_criteria.values()) / len(self.criteria)
        
        # Determine winner
        if scores:
            best_proposer = max(scores, key=scores.get)
            score_diff = max(scores.values()) - min(scores.values())
            
            # Only declare winner if meaningful difference
            if score_diff < 0.05:
                winner = None
                reasoning = "Solutions are too close in quality to declare a clear winner."
            else:
                winner = best_proposer
                reasoning = (f"Selected {best_proposer} (score: {scores[best_proposer]:.3f}) "
                           f"based on superior {self.criteria[0]} and evidence quality.")
        else:
            winner = None
            reasoning = "No valid solutions to judge."
        
        self.cost += 0.008
        
        return JudgmentResult(
            winner=winner,
            reasoning=reasoning,
            scores=scores,
            criteria_scores=criteria_scores,
            confidence=0.75 + (score_diff * 0.2 if scores else 0),
            rounds_used=round_number,
        )

    async def should_continue_debate(self, current_judgment: JudgmentResult,
                                     round_number: int, 
                                     config: DebateConfig) -> bool:
        """Decide if more debate rounds would be productive."""
        if round_number >= config.max_rounds:
            return False
        if round_number < config.min_rounds:
            return True
        
        # Continue if scores are too close (need more differentiation)
        if current_judgment.scores:
            score_range = max(current_judgment.scores.values()) - min(current_judgment.scores.values())
            if score_range < config.convergence_threshold:
                return True
        
        # Continue if confidence is low
        if current_judgment.confidence < 0.7:
            return True
        
        return False


# =============================================================================
# Debate Orchestrator
# =============================================================================

class DebateOrchestrator:
    """
    Orchestrates the full debate protocol between proposers and judge.
    """

    def __init__(self, config: DebateConfig = None):
        self.config = config or DebateConfig()
        self.proposers: list[ProposerAgent] = []
        self.judge: Optional[JudgeAgent] = None
        self.debate_history: list[Argument] = []
        self.solutions: list[Solution] = []

    def setup(self, proposers: list[ProposerAgent], judge: JudgeAgent):
        self.proposers = proposers
        self.judge = judge

    async def run_debate(self, problem: str, context: dict = None) -> dict:
        """Run the full debate protocol."""
        start_time = time.time()
        self.debate_history = []
        self.solutions = []
        total_cost = 0.0
        
        print(f"\n  [Debate] Problem: {problem[:60]}...")
        print(f"  [Debate] Proposers: {len(self.proposers)}, Max rounds: {self.config.max_rounds}")
        print(f"  [Debate] Criteria: {', '.join(self.config.judging_criteria)}")
        
        # Phase 1: Initial Proposals (parallel)
        print(f"\n  --- Round 1: Proposals ---")
        proposal_tasks = [p.propose(problem, context) for p in self.proposers]
        self.solutions = await asyncio.gather(*proposal_tasks)
        
        for sol in self.solutions:
            print(f"    [{sol.proposer_id}] {sol.approach[:60]}...")
            self.debate_history.append(Argument(
                agent_id=sol.proposer_id,
                phase=DebatePhase.PROPOSAL,
                content=sol.description,
                evidence=sol.evidence,
                confidence=sol.confidence,
                round_number=1,
            ))
        
        # Multi-round debate
        current_judgment = None
        for round_num in range(1, self.config.max_rounds + 1):
            # Cost check
            current_cost = sum(p.cost for p in self.proposers) + (self.judge.cost if self.judge else 0)
            if current_cost > self.config.max_cost:
                print(f"\n  [Debate] Cost limit reached (${current_cost:.3f}), ending debate")
                break
            
            # Phase 2: Cross-critique
            print(f"\n  --- Round {round_num}: Critiques ---")
            for i, proposer in enumerate(self.proposers):
                # Each proposer critiques the others
                for j, other_solution in enumerate(self.solutions):
                    if i != j:
                        critique = await proposer.critique_other(other_solution)
                        critique.round_number = round_num
                        self.debate_history.append(critique)
                        print(f"    [{proposer.agent_id}] critiques [{other_solution.proposer_id}]: "
                              f"{critique.content[:60]}...")
            
            # Phase 3: Rebuttals
            print(f"\n  --- Round {round_num}: Rebuttals ---")
            for i, proposer in enumerate(self.proposers):
                # Get critiques against this proposer
                critiques_against = [
                    a for a in self.debate_history
                    if a.phase == DebatePhase.CRITIQUE 
                    and a.agent_id != proposer.agent_id
                    and a.round_number == round_num
                ]
                
                if critiques_against:
                    rebuttal = await proposer.rebut(self.solutions[i], critiques_against)
                    rebuttal.round_number = round_num
                    self.debate_history.append(rebuttal)
                    print(f"    [{proposer.agent_id}] rebuts: {rebuttal.content[:60]}...")
            
            # Phase 4: Intermediate judgment
            print(f"\n  --- Round {round_num}: Judgment ---")
            current_judgment = await self.judge.judge(
                self.solutions, self.debate_history, round_num
            )
            
            print(f"    Scores: {', '.join(f'{k}: {v:.3f}' for k, v in current_judgment.scores.items())}")
            print(f"    Current leader: {current_judgment.winner or 'Too close to call'}")
            print(f"    Judge confidence: {current_judgment.confidence:.2f}")
            
            # Check if more rounds needed
            if not await self.judge.should_continue_debate(
                current_judgment, round_num, self.config
            ):
                print(f"\n  [Debate] Converged after {round_num} rounds")
                break
        
        # Final judgment
        total_cost = sum(p.cost for p in self.proposers) + self.judge.cost
        current_judgment.total_cost = total_cost
        
        elapsed = time.time() - start_time
        
        print(f"\n  {'─' * 50}")
        print(f"  [VERDICT] Winner: {current_judgment.winner or 'No clear winner'}")
        print(f"  [VERDICT] Reasoning: {current_judgment.reasoning}")
        print(f"  [VERDICT] Confidence: {current_judgment.confidence:.2f}")
        print(f"  [VERDICT] Rounds: {current_judgment.rounds_used}")
        print(f"  [VERDICT] Cost: ${total_cost:.4f}")
        print(f"  [VERDICT] Time: {elapsed:.2f}s")
        
        return {
            "judgment": current_judgment,
            "solutions": self.solutions,
            "debate_history": self.debate_history,
            "total_rounds": current_judgment.rounds_used,
            "total_cost": total_cost,
            "elapsed_time": elapsed,
            "criteria_breakdown": current_judgment.criteria_scores,
        }


# =============================================================================
# Demo
# =============================================================================

async def main():
    print("=" * 70)
    print("DEBATE/JUDGE PATTERN DEMO")
    print("=" * 70)
    
    # Setup debate
    config = DebateConfig(
        max_rounds=2,
        min_rounds=1,
        convergence_threshold=0.15,
        max_cost=0.30,
        num_proposers=2,
        judging_criteria=["correctness", "feasibility", "performance", "maintainability"],
    )
    
    proposers = [
        ProposerAgent("proposer-A", perspective="simplicity-first"),
        ProposerAgent("proposer-B", perspective="performance-first"),
    ]
    
    judge = JudgeAgent(criteria=config.judging_criteria)
    
    orchestrator = DebateOrchestrator(config=config)
    orchestrator.setup(proposers, judge)
    
    # Run debate
    result = await orchestrator.run_debate(
        problem="Design a caching strategy for a high-traffic API that serves "
               "both real-time and batch queries with varying staleness tolerance",
        context={"scale": "10k rps", "data_size": "50GB"}
    )
    
    # Print detailed criteria breakdown
    print(f"\n{'=' * 70}")
    print("CRITERIA BREAKDOWN")
    print(f"{'=' * 70}")
    for proposer_id, criteria in result["criteria_breakdown"].items():
        print(f"\n  {proposer_id}:")
        for criterion, score in criteria.items():
            bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
            print(f"    {criterion:15s} [{bar}] {score:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
