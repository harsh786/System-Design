"""
==============================================================================
PROJECT 3: Evaluation Platform
==============================================================================
A comprehensive platform for evaluating AI systems:
- Golden dataset management with versioning and tagging
- Retrieval metrics (Precision@K, Recall@K, MRR, NDCG, MAP)
- RAG metrics (Faithfulness, Relevance, Groundedness)
- Agent trajectory evaluation (task completion, efficiency, cost)
- LLM-as-Judge with calibration against human labels
- Human review queue with inter-annotator agreement
- CI/CD gate integration with regression detection
- Dashboard data generation and reporting

Demonstrates: ML evaluation rigor, statistical testing, CI/CD integration,
and systematic quality management for AI systems.
==============================================================================
"""

import asyncio
import hashlib
import json
import logging
import math
import random
import statistics
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np

# ==============================================================================
# DOMAIN MODELS
# ==============================================================================

class MetricType(Enum):
    RETRIEVAL = "retrieval"
    RAG = "rag"
    AGENT = "agent"
    SYSTEM = "system"


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class EvalStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GateDecision(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class GoldenExample:
    """A single golden evaluation example."""
    example_id: str
    query: str
    expected_answer: Optional[str] = None
    relevant_doc_ids: List[str] = field(default_factory=list)
    expected_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    version: int = 1


@dataclass
class GoldenDataset:
    """A versioned collection of golden evaluation examples."""
    dataset_id: str
    name: str
    description: str
    examples: List[GoldenExample] = field(default_factory=list)
    version: int = 1
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""

    @property
    def size(self) -> int:
        return len(self.examples)

    def get_by_difficulty(self, difficulty: Difficulty) -> List[GoldenExample]:
        return [e for e in self.examples if e.difficulty == difficulty]

    def get_by_tag(self, tag: str) -> List[GoldenExample]:
        return [e for e in self.examples if tag in e.tags]


@dataclass
class EvalResult:
    """Result of evaluating a single example."""
    example_id: str
    metrics: Dict[str, float]
    predicted_answer: Optional[str] = None
    retrieved_doc_ids: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost: float = 0.0
    error: Optional[str] = None


@dataclass
class EvalRun:
    """A complete evaluation run."""
    run_id: str
    dataset_id: str
    model_version: str
    config: Dict[str, Any] = field(default_factory=dict)
    results: List[EvalResult] = field(default_factory=list)
    aggregate_metrics: Dict[str, float] = field(default_factory=dict)
    status: EvalStatus = EvalStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    triggered_by: str = ""  # "ci", "manual", "scheduled"


@dataclass
class RegressionReport:
    """Report comparing two evaluation runs for regression detection."""
    current_run_id: str
    baseline_run_id: str
    regressions: List[Dict[str, Any]] = field(default_factory=list)
    improvements: List[Dict[str, Any]] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)
    gate_decision: GateDecision = GateDecision.PASS
    confidence_level: float = 0.95
    summary: str = ""


@dataclass
class HumanReviewItem:
    """An item in the human review queue."""
    review_id: str
    example_id: str
    query: str
    predicted_answer: str
    llm_judge_score: float
    llm_judge_rationale: str
    human_score: Optional[float] = None
    human_rationale: Optional[str] = None
    reviewer: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)


# ==============================================================================
# GOLDEN DATASET MANAGER
# ==============================================================================

class GoldenDatasetManager:
    """CRUD operations for golden evaluation datasets with versioning."""

    def __init__(self):
        self._datasets: Dict[str, GoldenDataset] = {}
        self._history: Dict[str, List[GoldenDataset]] = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    def create_dataset(
        self, name: str, description: str, tags: List[str] = None,
        created_by: str = ""
    ) -> GoldenDataset:
        """Create a new golden dataset."""
        dataset = GoldenDataset(
            dataset_id=f"ds_{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            tags=tags or [],
            created_by=created_by,
        )
        self._datasets[dataset.dataset_id] = dataset
        self.logger.info(f"Created dataset: {dataset.dataset_id} ({name})")
        return dataset

    def add_example(
        self, dataset_id: str, example: GoldenExample
    ) -> GoldenDataset:
        """Add an example to a dataset, creating a new version."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        # Save current version to history
        self._history[dataset_id].append(
            GoldenDataset(**asdict(dataset))
        )

        # Add example and bump version
        dataset.examples.append(example)
        dataset.version += 1
        dataset.updated_at = datetime.utcnow()

        return dataset

    def remove_example(self, dataset_id: str, example_id: str) -> GoldenDataset:
        """Remove an example from a dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        self._history[dataset_id].append(GoldenDataset(**asdict(dataset)))

        dataset.examples = [e for e in dataset.examples if e.example_id != example_id]
        dataset.version += 1
        dataset.updated_at = datetime.utcnow()

        return dataset

    def get_dataset(self, dataset_id: str, version: Optional[int] = None) -> Optional[GoldenDataset]:
        """Get a dataset, optionally at a specific version."""
        if version is not None:
            history = self._history.get(dataset_id, [])
            for ds in history:
                if ds.version == version:
                    return ds
            return None

        return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all datasets with summary info."""
        return [
            {
                "dataset_id": ds.dataset_id,
                "name": ds.name,
                "size": ds.size,
                "version": ds.version,
                "tags": ds.tags,
                "updated_at": ds.updated_at.isoformat(),
            }
            for ds in self._datasets.values()
        ]

    def get_stratified_sample(
        self, dataset_id: str, n: int, by: str = "difficulty"
    ) -> List[GoldenExample]:
        """Get a stratified sample from the dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []

        if by == "difficulty":
            groups = defaultdict(list)
            for ex in dataset.examples:
                groups[ex.difficulty].append(ex)

            # Sample proportionally from each group
            sample = []
            per_group = max(1, n // len(groups))
            for difficulty, examples in groups.items():
                k = min(per_group, len(examples))
                sample.extend(random.sample(examples, k))

            return sample[:n]

        return random.sample(dataset.examples, min(n, len(dataset.examples)))


# ==============================================================================
# RETRIEVAL METRICS
# ==============================================================================

class RetrievalMetricsComputer:
    """Compute standard information retrieval metrics."""

    def compute_all(
        self, retrieved_ids: List[str], relevant_ids: Set[str], k: int = 10
    ) -> Dict[str, float]:
        """Compute all retrieval metrics."""
        return {
            "precision_at_k": self.precision_at_k(retrieved_ids, relevant_ids, k),
            "recall_at_k": self.recall_at_k(retrieved_ids, relevant_ids, k),
            "mrr": self.mrr(retrieved_ids, relevant_ids),
            "ndcg_at_k": self.ndcg_at_k(retrieved_ids, relevant_ids, k),
            "map": self.average_precision(retrieved_ids, relevant_ids),
            "hit_rate_at_k": self.hit_rate(retrieved_ids, relevant_ids, k),
        }

    def precision_at_k(
        self, retrieved: List[str], relevant: Set[str], k: int
    ) -> float:
        retrieved_at_k = retrieved[:k]
        if not retrieved_at_k:
            return 0.0
        hits = sum(1 for doc in retrieved_at_k if doc in relevant)
        return hits / len(retrieved_at_k)

    def recall_at_k(
        self, retrieved: List[str], relevant: Set[str], k: int
    ) -> float:
        if not relevant:
            return 0.0
        retrieved_at_k = set(retrieved[:k])
        hits = len(retrieved_at_k & relevant)
        return hits / len(relevant)

    def mrr(self, retrieved: List[str], relevant: Set[str]) -> float:
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                return 1.0 / (i + 1)
        return 0.0

    def ndcg_at_k(
        self, retrieved: List[str], relevant: Set[str], k: int
    ) -> float:
        dcg = sum(
            (1.0 if doc in relevant else 0.0) / math.log2(i + 2)
            for i, doc in enumerate(retrieved[:k])
        )
        ideal_hits = min(len(relevant), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
        return dcg / idcg if idcg > 0 else 0.0

    def average_precision(
        self, retrieved: List[str], relevant: Set[str]
    ) -> float:
        if not relevant:
            return 0.0
        hits = 0
        sum_precisions = 0.0
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                hits += 1
                sum_precisions += hits / (i + 1)
        return sum_precisions / len(relevant)

    def hit_rate(
        self, retrieved: List[str], relevant: Set[str], k: int
    ) -> float:
        return 1.0 if any(doc in relevant for doc in retrieved[:k]) else 0.0


# ==============================================================================
# RAG METRICS
# ==============================================================================

class RAGMetricsComputer:
    """
    Compute RAG-specific quality metrics.
    Uses LLM-as-judge for semantic evaluation.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def compute_all(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        reference_answer: Optional[str] = None,
    ) -> Dict[str, float]:
        """Compute all RAG metrics."""
        faithfulness = await self.faithfulness(answer, contexts)
        answer_relevance = await self.answer_relevance(query, answer)
        context_relevance = await self.context_relevance(query, contexts)
        groundedness = await self.groundedness(answer, contexts)

        metrics = {
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_relevance": context_relevance,
            "groundedness": groundedness,
        }

        if reference_answer:
            metrics["answer_similarity"] = await self.answer_similarity(
                answer, reference_answer
            )
            metrics["answer_correctness"] = await self.answer_correctness(
                answer, reference_answer
            )

        return metrics

    async def faithfulness(self, answer: str, contexts: List[str]) -> float:
        """
        Measure if the answer is faithful to the provided contexts.
        No hallucinated information beyond what's in the sources.
        """
        # Extract claims from answer
        claims = self._extract_claims(answer)
        if not claims:
            return 1.0

        # Check each claim against contexts
        all_context = " ".join(contexts).lower()
        supported = 0

        for claim in claims:
            claim_words = set(claim.lower().split())
            context_words = set(all_context.split())
            overlap = len(claim_words & context_words) / max(len(claim_words), 1)
            if overlap > 0.4:
                supported += 1

        return supported / len(claims)

    async def answer_relevance(self, query: str, answer: str) -> float:
        """Measure if the answer addresses the query."""
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())

        # Remove stopwords for meaningful comparison
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'what', 'how', 'why',
                     'when', 'where', 'which', 'who', 'do', 'does', 'did'}
        query_meaningful = query_words - stopwords
        answer_meaningful = answer_words - stopwords

        if not query_meaningful:
            return 0.5

        overlap = len(query_meaningful & answer_meaningful) / len(query_meaningful)
        # Scale: some overlap is expected even for irrelevant answers
        return min(overlap * 1.5, 1.0)

    async def context_relevance(self, query: str, contexts: List[str]) -> float:
        """Measure if retrieved contexts are relevant to the query."""
        if not contexts:
            return 0.0

        query_words = set(query.lower().split())
        scores = []

        for context in contexts:
            context_words = set(context.lower().split())
            overlap = len(query_words & context_words) / max(len(query_words), 1)
            scores.append(min(overlap * 2, 1.0))

        return sum(scores) / len(scores)

    async def groundedness(self, answer: str, contexts: List[str]) -> float:
        """
        Measure how well each statement in the answer is grounded in context.
        Similar to faithfulness but more granular.
        """
        sentences = [s.strip() for s in answer.split('.') if len(s.strip()) > 10]
        if not sentences:
            return 1.0

        all_context = " ".join(contexts).lower()
        grounded_count = 0

        for sentence in sentences:
            # Check if sentence content appears in contexts
            words = set(sentence.lower().split())
            context_words = set(all_context.split())
            overlap = len(words & context_words) / max(len(words), 1)
            if overlap > 0.35:
                grounded_count += 1

        return grounded_count / len(sentences)

    async def answer_similarity(self, answer: str, reference: str) -> float:
        """Semantic similarity between answer and reference."""
        answer_words = set(answer.lower().split())
        ref_words = set(reference.lower().split())
        if not ref_words:
            return 0.0
        intersection = answer_words & ref_words
        union = answer_words | ref_words
        return len(intersection) / max(len(union), 1)

    async def answer_correctness(self, answer: str, reference: str) -> float:
        """
        Correctness combines factual accuracy with completeness.
        Factual: claims in answer match reference
        Complete: reference claims are covered in answer
        """
        answer_claims = set(self._extract_claims(answer))
        ref_claims = set(self._extract_claims(reference))

        if not ref_claims:
            return 0.5

        # Precision: fraction of answer claims in reference
        precision = sum(
            1 for c in answer_claims
            if any(self._claim_overlap(c, r) > 0.5 for r in ref_claims)
        ) / max(len(answer_claims), 1)

        # Recall: fraction of reference claims in answer
        recall = sum(
            1 for r in ref_claims
            if any(self._claim_overlap(r, c) > 0.5 for c in answer_claims)
        ) / len(ref_claims)

        # F1
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _extract_claims(self, text: str) -> List[str]:
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 15]
        return sentences

    def _claim_overlap(self, claim_a: str, claim_b: str) -> float:
        words_a = set(claim_a.lower().split())
        words_b = set(claim_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / max(len(words_a | words_b), 1)


# Need re for _extract_claims
import re


# ==============================================================================
# AGENT TRAJECTORY METRICS
# ==============================================================================

class AgentTrajectoryEvaluator:
    """Evaluate agent execution trajectories for quality and efficiency."""

    def evaluate_trajectory(
        self,
        expected_tools: List[Dict[str, Any]],
        actual_tools: List[Dict[str, Any]],
        task_completed: bool,
        total_cost: float,
        total_latency_ms: float,
    ) -> Dict[str, float]:
        """Evaluate an agent's execution trajectory."""
        return {
            "task_completion": 1.0 if task_completed else 0.0,
            "tool_accuracy": self._tool_accuracy(expected_tools, actual_tools),
            "tool_precision": self._tool_precision(expected_tools, actual_tools),
            "tool_recall": self._tool_recall(expected_tools, actual_tools),
            "trajectory_efficiency": self._efficiency(expected_tools, actual_tools),
            "cost_efficiency": self._cost_efficiency(total_cost),
            "latency_score": self._latency_score(total_latency_ms),
            "redundancy_score": self._redundancy(actual_tools),
        }

    def _tool_accuracy(
        self, expected: List[Dict], actual: List[Dict]
    ) -> float:
        """Exact match of tool sequence."""
        if not expected:
            return 1.0 if not actual else 0.5

        # Check if tools were called in correct order with correct params
        matches = 0
        for exp in expected:
            for act in actual:
                if (exp.get("tool") == act.get("tool") and
                    exp.get("key_params") == act.get("key_params")):
                    matches += 1
                    break

        return matches / len(expected)

    def _tool_precision(self, expected: List[Dict], actual: List[Dict]) -> float:
        """Fraction of actual tool calls that were necessary."""
        if not actual:
            return 1.0
        expected_tools = {e.get("tool") for e in expected}
        correct = sum(1 for a in actual if a.get("tool") in expected_tools)
        return correct / len(actual)

    def _tool_recall(self, expected: List[Dict], actual: List[Dict]) -> float:
        """Fraction of expected tool calls that were made."""
        if not expected:
            return 1.0
        actual_tools = {a.get("tool") for a in actual}
        found = sum(1 for e in expected if e.get("tool") in actual_tools)
        return found / len(expected)

    def _efficiency(self, expected: List[Dict], actual: List[Dict]) -> float:
        """How close to optimal path (fewer steps = better)."""
        if not expected:
            return 1.0
        optimal_steps = len(expected)
        actual_steps = len(actual)
        if actual_steps == 0:
            return 0.0
        return min(optimal_steps / actual_steps, 1.0)

    def _cost_efficiency(self, cost: float) -> float:
        """Score based on cost (lower is better)."""
        # Budget thresholds
        if cost <= 0.01:
            return 1.0
        elif cost <= 0.05:
            return 0.8
        elif cost <= 0.10:
            return 0.6
        elif cost <= 0.25:
            return 0.4
        else:
            return 0.2

    def _latency_score(self, latency_ms: float) -> float:
        """Score based on latency (lower is better)."""
        if latency_ms <= 1000:
            return 1.0
        elif latency_ms <= 3000:
            return 0.8
        elif latency_ms <= 5000:
            return 0.6
        elif latency_ms <= 10000:
            return 0.4
        else:
            return 0.2

    def _redundancy(self, actual: List[Dict]) -> float:
        """Penalize repeated identical tool calls."""
        if not actual:
            return 1.0
        unique = len(set(json.dumps(a, sort_keys=True) for a in actual))
        return unique / len(actual)


# ==============================================================================
# LLM-AS-JUDGE
# ==============================================================================

class LLMJudge:
    """
    LLM-based evaluation with configurable rubrics and calibration.
    Includes inter-rater agreement tracking with human labels.
    """

    def __init__(self):
        self._rubrics: Dict[str, Dict[str, Any]] = {}
        self._calibration_data: List[Dict[str, float]] = []
        self.logger = logging.getLogger(__name__)
        self._register_default_rubrics()

    def _register_default_rubrics(self):
        """Register default evaluation rubrics."""
        self._rubrics["helpfulness"] = {
            "name": "Helpfulness",
            "scale": (1, 5),
            "criteria": [
                "1: Not helpful at all, irrelevant or harmful",
                "2: Minimally helpful, misses key points",
                "3: Somewhat helpful, addresses the question partially",
                "4: Helpful, addresses the question well with minor gaps",
                "5: Very helpful, comprehensive and accurate",
            ],
        }
        self._rubrics["faithfulness"] = {
            "name": "Faithfulness",
            "scale": (1, 5),
            "criteria": [
                "1: Contains fabricated information not in sources",
                "2: Mostly fabricated with some source material",
                "3: Mix of grounded and ungrounded claims",
                "4: Mostly grounded with minor unsupported claims",
                "5: Fully grounded in provided sources",
            ],
        }
        self._rubrics["coherence"] = {
            "name": "Coherence",
            "scale": (1, 5),
            "criteria": [
                "1: Incoherent, contradictory",
                "2: Poorly organized, hard to follow",
                "3: Somewhat organized, occasional confusion",
                "4: Well organized, clear flow",
                "5: Excellently organized, clear and logical",
            ],
        }

    async def judge(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        rubric_name: str = "helpfulness",
    ) -> Dict[str, Any]:
        """
        Judge an answer using LLM with specified rubric.
        Returns score, rationale, and confidence.
        """
        rubric = self._rubrics.get(rubric_name)
        if not rubric:
            raise ValueError(f"Unknown rubric: {rubric_name}")

        # In production: call LLM with rubric prompt
        # Simulated: heuristic scoring
        score = await self._simulate_judge(query, answer, contexts, rubric)

        rationale = self._generate_rationale(score, rubric_name)

        return {
            "rubric": rubric_name,
            "score": score,
            "max_score": rubric["scale"][1],
            "normalized_score": score / rubric["scale"][1],
            "rationale": rationale,
            "confidence": 0.8,  # In production: from LLM logprobs
        }

    async def judge_pairwise(
        self,
        query: str,
        answer_a: str,
        answer_b: str,
        contexts: List[str],
    ) -> Dict[str, Any]:
        """Pairwise comparison of two answers."""
        score_a = await self._simulate_judge(
            query, answer_a, contexts, self._rubrics["helpfulness"]
        )
        score_b = await self._simulate_judge(
            query, answer_b, contexts, self._rubrics["helpfulness"]
        )

        if score_a > score_b:
            winner = "A"
        elif score_b > score_a:
            winner = "B"
        else:
            winner = "tie"

        return {
            "winner": winner,
            "score_a": score_a,
            "score_b": score_b,
            "margin": abs(score_a - score_b),
            "confidence": min(abs(score_a - score_b) / 2, 1.0),
        }

    def calibrate(self, llm_scores: List[float], human_scores: List[float]):
        """Calibrate LLM judge against human labels."""
        if len(llm_scores) != len(human_scores) or not llm_scores:
            return

        for llm_s, human_s in zip(llm_scores, human_scores):
            self._calibration_data.append({"llm": llm_s, "human": human_s})

        # Compute agreement metrics
        agreement = self._compute_agreement(llm_scores, human_scores)
        self.logger.info(f"Judge calibration - Cohen's kappa: {agreement['cohens_kappa']:.3f}")

    def _compute_agreement(
        self, scores_a: List[float], scores_b: List[float]
    ) -> Dict[str, float]:
        """Compute inter-rater agreement metrics."""
        n = len(scores_a)
        if n == 0:
            return {"cohens_kappa": 0.0, "pearson": 0.0, "mse": 0.0}

        # Pearson correlation
        mean_a = sum(scores_a) / n
        mean_b = sum(scores_b) / n
        cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(scores_a, scores_b)) / n
        std_a = (sum((a - mean_a)**2 for a in scores_a) / n) ** 0.5
        std_b = (sum((b - mean_b)**2 for b in scores_b) / n) ** 0.5
        pearson = cov / (std_a * std_b) if std_a * std_b > 0 else 0.0

        # MSE
        mse = sum((a - b)**2 for a, b in zip(scores_a, scores_b)) / n

        # Simplified Cohen's kappa (treat as ordinal)
        # Round to nearest integer for agreement calculation
        agreements = sum(1 for a, b in zip(scores_a, scores_b) if round(a) == round(b))
        po = agreements / n
        pe = 0.2  # Expected agreement by chance for 5-point scale
        kappa = (po - pe) / (1 - pe) if pe < 1 else 0.0

        return {"cohens_kappa": kappa, "pearson": pearson, "mse": mse}

    async def _simulate_judge(
        self, query: str, answer: str, contexts: List[str], rubric: Dict
    ) -> float:
        """Simulate LLM judge scoring."""
        await asyncio.sleep(0.02)

        # Heuristic scoring based on text properties
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        context_words = set(" ".join(contexts).lower().split())

        # Relevance signal
        relevance = len(query_words & answer_words) / max(len(query_words), 1)
        # Grounding signal
        grounding = len(answer_words & context_words) / max(len(answer_words), 1)
        # Length signal (not too short, not too long)
        length_score = min(len(answer.split()) / 50, 1.0)

        raw_score = 0.4 * relevance + 0.4 * grounding + 0.2 * length_score
        # Map to rubric scale
        min_score, max_score = rubric["scale"]
        score = min_score + raw_score * (max_score - min_score)
        return round(score, 1)

    def _generate_rationale(self, score: float, rubric_name: str) -> str:
        """Generate explanation for the score."""
        if score >= 4:
            return f"The answer scores well on {rubric_name}: comprehensive, accurate, and well-structured."
        elif score >= 3:
            return f"The answer partially addresses the question but has gaps in {rubric_name}."
        else:
            return f"The answer has significant issues with {rubric_name}: key information missing or inaccurate."


# ==============================================================================
# HUMAN REVIEW QUEUE
# ==============================================================================

class HumanReviewQueue:
    """Queue for human evaluation to calibrate LLM judges."""

    def __init__(self, sample_rate: float = 0.1):
        self._queue: List[HumanReviewItem] = []
        self._completed: List[HumanReviewItem] = []
        self.sample_rate = sample_rate

    def should_sample(self) -> bool:
        """Determine if this example should go to human review."""
        return random.random() < self.sample_rate

    def enqueue(
        self, example_id: str, query: str, predicted_answer: str,
        llm_score: float, llm_rationale: str
    ) -> str:
        """Add item to review queue."""
        item = HumanReviewItem(
            review_id=f"rev_{uuid.uuid4().hex[:8]}",
            example_id=example_id,
            query=query,
            predicted_answer=predicted_answer,
            llm_judge_score=llm_score,
            llm_judge_rationale=llm_rationale,
        )
        self._queue.append(item)
        return item.review_id

    def get_next(self, reviewer: str) -> Optional[HumanReviewItem]:
        """Get next item for a reviewer."""
        for item in self._queue:
            if item.status == "pending":
                item.status = "assigned"
                item.reviewer = reviewer
                return item
        return None

    def submit_review(
        self, review_id: str, score: float, rationale: str
    ):
        """Submit a human review."""
        for item in self._queue:
            if item.review_id == review_id:
                item.human_score = score
                item.human_rationale = rationale
                item.status = "completed"
                self._completed.append(item)
                self._queue.remove(item)
                return
        raise ValueError(f"Review not found: {review_id}")

    def get_agreement_stats(self) -> Dict[str, float]:
        """Compute agreement between LLM judge and human reviewers."""
        if not self._completed:
            return {"count": 0, "agreement": 0.0}

        llm_scores = [item.llm_judge_score for item in self._completed]
        human_scores = [item.human_score for item in self._completed]

        # Exact agreement (within 0.5)
        agreements = sum(
            1 for l, h in zip(llm_scores, human_scores)
            if abs(l - h) <= 0.5
        )

        return {
            "count": len(self._completed),
            "exact_agreement": agreements / len(self._completed),
            "mean_llm": sum(llm_scores) / len(llm_scores),
            "mean_human": sum(human_scores) / len(human_scores),
            "mean_abs_diff": sum(abs(l-h) for l, h in zip(llm_scores, human_scores)) / len(llm_scores),
        }


# ==============================================================================
# REGRESSION DETECTION
# ==============================================================================

class RegressionDetector:
    """
    Detect statistically significant regressions between eval runs.
    Uses bootstrap confidence intervals and hypothesis testing.
    """

    def __init__(self, confidence_level: float = 0.95, min_effect_size: float = 0.02):
        self.confidence_level = confidence_level
        self.min_effect_size = min_effect_size

    def detect(
        self, current_run: EvalRun, baseline_run: EvalRun
    ) -> RegressionReport:
        """Compare two runs and detect regressions."""
        regressions = []
        improvements = []
        unchanged = []

        # Compare each metric
        current_metrics = current_run.aggregate_metrics
        baseline_metrics = baseline_run.aggregate_metrics

        all_metrics = set(current_metrics.keys()) | set(baseline_metrics.keys())

        for metric_name in all_metrics:
            current_val = current_metrics.get(metric_name, 0.0)
            baseline_val = baseline_metrics.get(metric_name, 0.0)

            # Compute per-example scores for significance testing
            current_scores = [r.metrics.get(metric_name, 0.0) for r in current_run.results]
            baseline_scores = [r.metrics.get(metric_name, 0.0) for r in baseline_run.results]

            # Bootstrap confidence interval for the difference
            diff = current_val - baseline_val
            is_significant = self._is_significant(current_scores, baseline_scores)

            result = {
                "metric": metric_name,
                "current": current_val,
                "baseline": baseline_val,
                "diff": diff,
                "diff_pct": (diff / max(baseline_val, 0.001)) * 100,
                "significant": is_significant,
            }

            if is_significant and diff < -self.min_effect_size:
                regressions.append(result)
            elif is_significant and diff > self.min_effect_size:
                improvements.append(result)
            else:
                unchanged.append(metric_name)

        # Gate decision
        if any(r["significant"] for r in regressions):
            gate_decision = GateDecision.FAIL
        elif regressions:
            gate_decision = GateDecision.WARN
        else:
            gate_decision = GateDecision.PASS

        summary = self._build_summary(regressions, improvements, unchanged)

        return RegressionReport(
            current_run_id=current_run.run_id,
            baseline_run_id=baseline_run.run_id,
            regressions=regressions,
            improvements=improvements,
            unchanged=unchanged,
            gate_decision=gate_decision,
            confidence_level=self.confidence_level,
            summary=summary,
        )

    def _is_significant(
        self, current: List[float], baseline: List[float]
    ) -> bool:
        """Test if difference is statistically significant using bootstrap."""
        if len(current) < 5 or len(baseline) < 5:
            return False

        # Bootstrap the difference in means
        n_bootstrap = 1000
        observed_diff = np.mean(current) - np.mean(baseline)

        boot_diffs = []
        combined = current + baseline
        n_current = len(current)

        rng = np.random.RandomState(42)
        for _ in range(n_bootstrap):
            sample = rng.choice(combined, size=len(combined), replace=True)
            boot_current = sample[:n_current]
            boot_baseline = sample[n_current:]
            boot_diffs.append(np.mean(boot_current) - np.mean(boot_baseline))

        # Two-tailed test
        alpha = 1 - self.confidence_level
        lower = np.percentile(boot_diffs, (alpha / 2) * 100)
        upper = np.percentile(boot_diffs, (1 - alpha / 2) * 100)

        # Significant if observed diff outside bootstrap CI under null
        return observed_diff < lower or observed_diff > upper

    def _build_summary(
        self, regressions: List[Dict], improvements: List[Dict],
        unchanged: List[str]
    ) -> str:
        parts = []
        if regressions:
            metrics = [r["metric"] for r in regressions]
            parts.append(f"REGRESSIONS in: {', '.join(metrics)}")
        if improvements:
            metrics = [i["metric"] for i in improvements]
            parts.append(f"Improvements in: {', '.join(metrics)}")
        parts.append(f"{len(unchanged)} metrics unchanged")
        return "; ".join(parts)


# ==============================================================================
# CI/CD GATE
# ==============================================================================

class CIGate:
    """
    CI/CD quality gate that blocks deployments on quality regressions.
    Integrates with regression detector and configurable thresholds.
    """

    def __init__(self):
        self._thresholds: Dict[str, float] = {
            "faithfulness": 0.85,
            "answer_relevance": 0.80,
            "precision_at_k": 0.70,
            "recall_at_k": 0.60,
            "mrr": 0.65,
            "task_completion": 0.90,
        }
        self._regression_tolerance: float = 0.05  # 5% regression tolerance
        self.logger = logging.getLogger(__name__)

    def set_threshold(self, metric: str, threshold: float):
        """Set quality threshold for a metric."""
        self._thresholds[metric] = threshold

    def evaluate(
        self, eval_run: EvalRun, regression_report: Optional[RegressionReport] = None
    ) -> Dict[str, Any]:
        """
        Evaluate an eval run against CI gates.
        Returns pass/fail decision with details.
        """
        failures = []
        warnings = []

        # Check absolute thresholds
        for metric, threshold in self._thresholds.items():
            value = eval_run.aggregate_metrics.get(metric)
            if value is not None and value < threshold:
                failures.append({
                    "type": "threshold",
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "message": f"{metric}: {value:.3f} < {threshold:.3f}",
                })

        # Check regression
        if regression_report:
            if regression_report.gate_decision == GateDecision.FAIL:
                for reg in regression_report.regressions:
                    if reg["significant"]:
                        failures.append({
                            "type": "regression",
                            "metric": reg["metric"],
                            "diff_pct": reg["diff_pct"],
                            "message": f"{reg['metric']} regressed {reg['diff_pct']:.1f}%",
                        })
            elif regression_report.gate_decision == GateDecision.WARN:
                for reg in regression_report.regressions:
                    warnings.append({
                        "type": "regression_warn",
                        "metric": reg["metric"],
                        "diff_pct": reg["diff_pct"],
                    })

        # Decision
        if failures:
            decision = GateDecision.FAIL
        elif warnings:
            decision = GateDecision.WARN
        else:
            decision = GateDecision.PASS

        result = {
            "decision": decision.value,
            "failures": failures,
            "warnings": warnings,
            "metrics_checked": len(self._thresholds),
            "run_id": eval_run.run_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.logger.info(f"CI Gate decision: {decision.value} ({len(failures)} failures)")
        return result


# ==============================================================================
# EVALUATION ORCHESTRATOR
# ==============================================================================

class EvaluationPlatform:
    """
    Main orchestrator for the evaluation platform.
    Coordinates datasets, metrics, judges, and CI gates.
    """

    def __init__(self):
        self.dataset_manager = GoldenDatasetManager()
        self.retrieval_metrics = RetrievalMetricsComputer()
        self.rag_metrics = RAGMetricsComputer()
        self.trajectory_evaluator = AgentTrajectoryEvaluator()
        self.llm_judge = LLMJudge()
        self.human_review = HumanReviewQueue(sample_rate=0.1)
        self.regression_detector = RegressionDetector()
        self.ci_gate = CIGate()

        self._runs: Dict[str, EvalRun] = {}
        self.logger = logging.getLogger(__name__)

    async def run_evaluation(
        self,
        dataset_id: str,
        model_version: str,
        system_under_test: Callable,
        config: Dict[str, Any] = None,
        triggered_by: str = "manual",
    ) -> EvalRun:
        """Execute a full evaluation run."""
        dataset = self.dataset_manager.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        run = EvalRun(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            dataset_id=dataset_id,
            model_version=model_version,
            config=config or {},
            status=EvalStatus.RUNNING,
            started_at=datetime.utcnow(),
            triggered_by=triggered_by,
        )

        self.logger.info(
            f"Starting eval run {run.run_id}: {dataset.size} examples, "
            f"model={model_version}"
        )

        # Evaluate each example
        for example in dataset.examples:
            try:
                result = await self._evaluate_example(example, system_under_test)
                run.results.append(result)
            except Exception as e:
                run.results.append(EvalResult(
                    example_id=example.example_id,
                    metrics={},
                    error=str(e),
                ))

        # Aggregate metrics
        run.aggregate_metrics = self._aggregate_metrics(run.results)
        run.status = EvalStatus.COMPLETED
        run.completed_at = datetime.utcnow()

        self._runs[run.run_id] = run

        self.logger.info(
            f"Eval run {run.run_id} completed: "
            f"{len([r for r in run.results if not r.error])}/{len(run.results)} succeeded"
        )

        return run

    async def _evaluate_example(
        self, example: GoldenExample, system_under_test: Callable
    ) -> EvalResult:
        """Evaluate a single example."""
        start = time.time()

        # Call system under test
        response = await system_under_test(example.query)
        latency_ms = (time.time() - start) * 1000

        predicted_answer = response.get("answer", "")
        retrieved_ids = response.get("retrieved_doc_ids", [])
        contexts = response.get("contexts", [])

        metrics = {}

        # Retrieval metrics
        if example.relevant_doc_ids:
            retrieval_m = self.retrieval_metrics.compute_all(
                retrieved_ids, set(example.relevant_doc_ids), k=10
            )
            metrics.update(retrieval_m)

        # RAG metrics
        if predicted_answer and contexts:
            rag_m = await self.rag_metrics.compute_all(
                query=example.query,
                answer=predicted_answer,
                contexts=contexts,
                reference_answer=example.expected_answer,
            )
            metrics.update(rag_m)

        # LLM judge
        judge_result = await self.llm_judge.judge(
            example.query, predicted_answer, contexts, "helpfulness"
        )
        metrics["judge_helpfulness"] = judge_result["normalized_score"]

        # Human review sampling
        if self.human_review.should_sample():
            self.human_review.enqueue(
                example.example_id, example.query, predicted_answer,
                judge_result["score"], judge_result["rationale"]
            )

        return EvalResult(
            example_id=example.example_id,
            metrics=metrics,
            predicted_answer=predicted_answer,
            retrieved_doc_ids=retrieved_ids,
            latency_ms=latency_ms,
            tokens_used=response.get("tokens_used", 0),
            cost=response.get("cost", 0.0),
        )

    def _aggregate_metrics(self, results: List[EvalResult]) -> Dict[str, float]:
        """Aggregate per-example metrics into run-level metrics."""
        if not results:
            return {}

        valid_results = [r for r in results if not r.error]
        if not valid_results:
            return {}

        # Collect all metric names
        all_metrics: Dict[str, List[float]] = defaultdict(list)
        for result in valid_results:
            for metric, value in result.metrics.items():
                all_metrics[metric].append(value)

        # Compute mean for each metric
        aggregated = {}
        for metric, values in all_metrics.items():
            aggregated[metric] = sum(values) / len(values)

        # Add system metrics
        latencies = [r.latency_ms for r in valid_results]
        aggregated["avg_latency_ms"] = sum(latencies) / len(latencies)
        aggregated["p95_latency_ms"] = sorted(latencies)[int(len(latencies) * 0.95)]
        aggregated["total_cost"] = sum(r.cost for r in valid_results)
        aggregated["error_rate"] = len(results) - len(valid_results) / max(len(results), 1)

        return aggregated

    async def compare_runs(
        self, current_run_id: str, baseline_run_id: str
    ) -> RegressionReport:
        """Compare two runs for regression detection."""
        current = self._runs.get(current_run_id)
        baseline = self._runs.get(baseline_run_id)

        if not current or not baseline:
            raise ValueError("Run not found")

        return self.regression_detector.detect(current, baseline)

    async def check_ci_gate(
        self, run_id: str, baseline_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check CI gate for a given run."""
        run = self._runs.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        regression_report = None
        if baseline_run_id:
            baseline = self._runs.get(baseline_run_id)
            if baseline:
                regression_report = self.regression_detector.detect(run, baseline)

        return self.ci_gate.evaluate(run, regression_report)

    def generate_report(self, run_id: str) -> Dict[str, Any]:
        """Generate a comprehensive evaluation report."""
        run = self._runs.get(run_id)
        if not run:
            return {"error": "Run not found"}

        # Per-difficulty breakdown
        dataset = self.dataset_manager.get_dataset(run.dataset_id)
        difficulty_breakdown = {}
        if dataset:
            for difficulty in Difficulty:
                examples = dataset.get_by_difficulty(difficulty)
                example_ids = {e.example_id for e in examples}
                difficulty_results = [
                    r for r in run.results if r.example_id in example_ids
                ]
                if difficulty_results:
                    difficulty_breakdown[difficulty.value] = self._aggregate_metrics(
                        difficulty_results
                    )

        # Failure analysis
        failures = [r for r in run.results if r.error]
        low_scores = [
            r for r in run.results
            if r.metrics.get("faithfulness", 1.0) < 0.5
        ]

        return {
            "run_id": run.run_id,
            "model_version": run.model_version,
            "dataset": run.dataset_id,
            "status": run.status.value,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "aggregate_metrics": run.aggregate_metrics,
            "difficulty_breakdown": difficulty_breakdown,
            "total_examples": len(run.results),
            "successful": len(run.results) - len(failures),
            "failures": len(failures),
            "low_quality_answers": len(low_scores),
            "human_review_stats": self.human_review.get_agreement_stats(),
        }


# ==============================================================================
# DEMONSTRATION
# ==============================================================================

async def main():
    """Demonstrate the Evaluation Platform."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    platform = EvaluationPlatform()

    logger.info("=" * 60)
    logger.info("Evaluation Platform - Demonstration")
    logger.info("=" * 60)

    # --- 1. Create golden dataset ---
    logger.info("\n--- Creating Golden Dataset ---")
    dataset = platform.dataset_manager.create_dataset(
        name="RAG Quality Benchmark v1",
        description="Golden dataset for RAG system evaluation",
        tags=["rag", "production", "v1"],
        created_by="eval_team",
    )

    examples = [
        GoldenExample(
            example_id="ex_001",
            query="What is retrieval-augmented generation?",
            expected_answer="RAG combines retrieval systems with generative models to produce grounded answers.",
            relevant_doc_ids=["doc_rag_intro", "doc_rag_arch"],
            difficulty=Difficulty.EASY,
            tags=["definition", "rag"],
        ),
        GoldenExample(
            example_id="ex_002",
            query="How does hybrid retrieval improve over dense-only search?",
            expected_answer="Hybrid retrieval combines dense vectors with sparse BM25, improving recall for keyword-heavy queries while maintaining semantic understanding.",
            relevant_doc_ids=["doc_hybrid", "doc_bm25", "doc_dense"],
            difficulty=Difficulty.MEDIUM,
            tags=["retrieval", "hybrid"],
        ),
        GoldenExample(
            example_id="ex_003",
            query="Compare the tradeoffs of pgvector vs Qdrant for ACL-filtered retrieval at scale",
            expected_answer="pgvector offers operational simplicity with PostgreSQL but struggles with complex filtered queries at scale. Qdrant provides native filtering with payload indices but adds operational overhead.",
            relevant_doc_ids=["doc_pgvector", "doc_qdrant", "doc_acl"],
            difficulty=Difficulty.HARD,
            tags=["vector_db", "comparison", "acl"],
        ),
        GoldenExample(
            example_id="ex_004",
            query="What chunking strategy works best for technical documentation?",
            expected_answer="Recursive chunking with structure awareness works best, respecting heading boundaries and keeping code blocks intact.",
            relevant_doc_ids=["doc_chunking"],
            difficulty=Difficulty.MEDIUM,
            tags=["chunking", "strategy"],
        ),
        GoldenExample(
            example_id="ex_005",
            query="Explain the reranking step in a RAG pipeline and when to skip it",
            expected_answer="Reranking uses cross-encoders to rescore initial retrieval results for higher precision. Skip when latency budget is <100ms or when retrieval quality is already high (MRR > 0.9).",
            relevant_doc_ids=["doc_reranking", "doc_latency"],
            difficulty=Difficulty.HARD,
            tags=["reranking", "optimization"],
        ),
    ]

    for ex in examples:
        platform.dataset_manager.add_example(dataset.dataset_id, ex)

    logger.info(f"  Created dataset: {dataset.name} ({len(examples)} examples)")

    # --- 2. Run evaluation (simulated system under test) ---
    logger.info("\n--- Running Evaluation ---")

    async def mock_system(query: str) -> Dict[str, Any]:
        """Simulated RAG system responses."""
        await asyncio.sleep(0.02)
        return {
            "answer": f"Based on my analysis, {query.lower().rstrip('?')} involves several key concepts that are well-documented in the literature.",
            "retrieved_doc_ids": ["doc_rag_intro", "doc_hybrid", "doc_chunking"],
            "contexts": [
                "RAG combines retrieval with generation for grounded answers.",
                "Hybrid retrieval uses both dense and sparse methods.",
                "Chunking strategies affect retrieval quality significantly.",
            ],
            "tokens_used": 250,
            "cost": 0.005,
        }

    run = await platform.run_evaluation(
        dataset_id=dataset.dataset_id,
        model_version="rag-v2.1.0",
        system_under_test=mock_system,
        triggered_by="demonstration",
    )

    logger.info(f"  Run completed: {run.run_id}")
    logger.info(f"  Aggregate metrics:")
    for metric, value in sorted(run.aggregate_metrics.items()):
        logger.info(f"    {metric}: {value:.3f}")

    # --- 3. Run baseline for comparison ---
    logger.info("\n--- Running Baseline Evaluation ---")

    async def mock_baseline(query: str) -> Dict[str, Any]:
        await asyncio.sleep(0.02)
        return {
            "answer": f"The answer to your question is complex and involves multiple factors.",
            "retrieved_doc_ids": ["doc_rag_intro"],
            "contexts": ["RAG is a technique for grounding LLM outputs."],
            "tokens_used": 150,
            "cost": 0.003,
        }

    baseline_run = await platform.run_evaluation(
        dataset_id=dataset.dataset_id,
        model_version="rag-v2.0.0",
        system_under_test=mock_baseline,
        triggered_by="demonstration",
    )

    # --- 4. Regression detection ---
    logger.info("\n--- Regression Detection ---")
    regression_report = await platform.compare_runs(run.run_id, baseline_run.run_id)
    logger.info(f"  Gate decision: {regression_report.gate_decision.value}")
    logger.info(f"  Summary: {regression_report.summary}")
    if regression_report.improvements:
        for imp in regression_report.improvements:
            logger.info(f"  Improvement: {imp['metric']} +{imp['diff_pct']:.1f}%")

    # --- 5. CI Gate ---
    logger.info("\n--- CI Gate Check ---")
    gate_result = await platform.check_ci_gate(run.run_id, baseline_run.run_id)
    logger.info(f"  Decision: {gate_result['decision']}")
    if gate_result['failures']:
        for f in gate_result['failures']:
            logger.info(f"  FAIL: {f['message']}")
    if gate_result['warnings']:
        for w in gate_result['warnings']:
            logger.info(f"  WARN: {w['metric']}")

    # --- 6. Generate report ---
    logger.info("\n--- Evaluation Report ---")
    report = platform.generate_report(run.run_id)
    logger.info(f"  Total examples: {report['total_examples']}")
    logger.info(f"  Successful: {report['successful']}")
    logger.info(f"  Failures: {report['failures']}")
    logger.info(f"  Low quality: {report['low_quality_answers']}")

    logger.info("\n" + "=" * 60)
    logger.info("Demonstration complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
