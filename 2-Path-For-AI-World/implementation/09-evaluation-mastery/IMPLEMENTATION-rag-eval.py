"""
RAG Evaluation System
======================
Complete evaluation system for Retrieval-Augmented Generation pipelines.
Covers retrieval metrics, context metrics, answer metrics, citation metrics,
LLM-as-judge, batch evaluation, comparison, and regression detection.
"""

import json
import math
import hashlib
import statistics
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable
from enum import Enum
from collections import defaultdict
import random


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class RetrievalResult:
    """A single retrieval result."""
    doc_id: str
    chunk_id: str
    score: float
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RAGInput:
    """Input to a RAG system for evaluation."""
    query: str
    retrieved_documents: list[dict]  # [{doc_id, chunk_id, content, score}]
    generated_answer: str
    citations: list[str] = field(default_factory=list)  # doc_ids cited
    latency_ms: float = 0.0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    config_id: str = ""


@dataclass
class RAGGroundTruth:
    """Ground truth for a RAG evaluation example."""
    query: str
    relevant_doc_ids: list[str]  # All relevant documents
    relevance_grades: dict = field(default_factory=dict)  # doc_id -> grade (0-3)
    reference_answer: str = ""
    required_citations: list[str] = field(default_factory=list)
    should_abstain: bool = False
    key_claims: list[str] = field(default_factory=list)  # Claims that must be in answer


@dataclass 
class MetricResult:
    """Result of a single metric computation."""
    name: str
    value: float
    confidence_interval: Optional[tuple] = None
    details: dict = field(default_factory=dict)


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    config_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    num_examples: int = 0
    metrics: dict = field(default_factory=dict)
    slice_metrics: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ============================================================
# RETRIEVAL METRICS
# ============================================================

class RetrievalMetrics:
    """Compute retrieval quality metrics."""
    
    @staticmethod
    def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Recall@k: fraction of relevant docs found in top-k."""
        if not relevant_ids:
            return 1.0  # No relevant docs means perfect recall vacuously
        retrieved_top_k = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_top_k & relevant_set) / len(relevant_set)
    
    @staticmethod
    def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Precision@k: fraction of top-k that are relevant."""
        if k == 0:
            return 0.0
        retrieved_top_k = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_top_k & relevant_set) / k
    
    @staticmethod
    def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
        """Mean Reciprocal Rank: 1/rank of first relevant document."""
        relevant_set = set(relevant_ids)
        for i, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in relevant_set:
                return 1.0 / i
        return 0.0
    
    @staticmethod
    def ndcg_at_k(retrieved_ids: list[str], relevance_grades: dict, k: int) -> float:
        """Normalized Discounted Cumulative Gain at k.
        
        relevance_grades: {doc_id: grade} where grade is 0-3
        """
        def dcg(ids: list[str], grades: dict, n: int) -> float:
            score = 0.0
            for i, doc_id in enumerate(ids[:n], 1):
                rel = grades.get(doc_id, 0)
                score += (2 ** rel - 1) / math.log2(i + 1)
            return score
        
        # Actual DCG
        actual_dcg = dcg(retrieved_ids, relevance_grades, k)
        
        # Ideal DCG (docs sorted by relevance)
        ideal_order = sorted(relevance_grades.keys(), 
                           key=lambda x: relevance_grades.get(x, 0), reverse=True)
        ideal_dcg = dcg(ideal_order, relevance_grades, k)
        
        if ideal_dcg == 0:
            return 0.0
        return actual_dcg / ideal_dcg
    
    @staticmethod
    def average_precision(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
        """Average Precision: area under precision-recall curve."""
        relevant_set = set(relevant_ids)
        if not relevant_set:
            return 1.0
        
        score = 0.0
        relevant_found = 0
        
        for i, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in relevant_set:
                relevant_found += 1
                score += relevant_found / i
        
        return score / len(relevant_set)
    
    @staticmethod
    def hit_rate_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Hit rate: 1 if any relevant doc in top-k, else 0."""
        retrieved_top_k = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return 1.0 if retrieved_top_k & relevant_set else 0.0


# ============================================================
# CONTEXT METRICS
# ============================================================

class ContextMetrics:
    """Metrics for evaluating retrieved context quality."""
    
    @staticmethod
    def context_precision(
        retrieved_contents: list[str],
        query: str,
        reference_answer: str,
        judge_fn: Callable
    ) -> float:
        """Context precision: fraction of retrieved chunks that are useful.
        
        Uses LLM judge to determine if each chunk is useful for answering.
        """
        if not retrieved_contents:
            return 0.0
        
        useful_count = 0
        for content in retrieved_contents:
            is_useful = judge_fn(
                query=query,
                context_chunk=content,
                reference_answer=reference_answer,
                task="context_precision"
            )
            if is_useful:
                useful_count += 1
        
        return useful_count / len(retrieved_contents)
    
    @staticmethod
    def context_recall(
        retrieved_contents: list[str],
        key_claims: list[str],
        judge_fn: Callable
    ) -> float:
        """Context recall: fraction of required claims supportable by context.
        
        Checks if the retrieved context contains information to support each key claim.
        """
        if not key_claims:
            return 1.0
        
        supported_claims = 0
        combined_context = "\n".join(retrieved_contents)
        
        for claim in key_claims:
            is_supported = judge_fn(
                context=combined_context,
                claim=claim,
                task="context_recall"
            )
            if is_supported:
                supported_claims += 1
        
        return supported_claims / len(key_claims)
    
    @staticmethod
    def context_relevance_score(
        retrieved_contents: list[str],
        query: str,
        judge_fn: Callable
    ) -> float:
        """Average relevance score (0-1) of retrieved chunks to query."""
        if not retrieved_contents:
            return 0.0
        
        scores = []
        for content in retrieved_contents:
            score = judge_fn(
                query=query,
                context_chunk=content,
                task="context_relevance"
            )
            scores.append(score)
        
        return statistics.mean(scores)


# ============================================================
# ANSWER METRICS
# ============================================================

class AnswerMetrics:
    """Metrics for evaluating generated answer quality."""
    
    @staticmethod
    def faithfulness(
        answer: str,
        context: str,
        judge_fn: Callable
    ) -> float:
        """Faithfulness: fraction of claims in answer supported by context.
        
        This is the #1 RAG metric. Measures hallucination.
        """
        # Step 1: Extract claims from answer
        claims = judge_fn(answer=answer, task="extract_claims")
        if not claims:
            return 1.0  # No claims = vacuously faithful
        
        # Step 2: Check each claim against context
        supported = 0
        claim_details = []
        for claim in claims:
            is_supported = judge_fn(
                context=context,
                claim=claim,
                task="verify_claim"
            )
            if is_supported:
                supported += 1
            claim_details.append({"claim": claim, "supported": is_supported})
        
        return supported / len(claims)
    
    @staticmethod
    def groundedness(
        answer: str,
        context: str,
        citations: list[str],
        judge_fn: Callable
    ) -> float:
        """Groundedness: fraction of assertive sentences with citation support."""
        # Extract assertive sentences (not questions, not hedges)
        sentences = judge_fn(answer=answer, task="extract_assertive_sentences")
        if not sentences:
            return 1.0
        
        grounded = 0
        for sentence in sentences:
            has_grounding = judge_fn(
                sentence=sentence,
                context=context,
                citations=citations,
                task="check_grounding"
            )
            if has_grounding:
                grounded += 1
        
        return grounded / len(sentences)
    
    @staticmethod
    def answer_relevance(
        answer: str,
        query: str,
        judge_fn: Callable
    ) -> float:
        """Answer relevance: does the answer address the question asked?"""
        return judge_fn(
            query=query,
            answer=answer,
            task="answer_relevance"
        )
    
    @staticmethod
    def answer_correctness(
        answer: str,
        reference_answer: str,
        judge_fn: Callable
    ) -> dict:
        """Answer correctness: factual overlap with reference answer.
        
        Returns precision, recall, and F1 of factual claims.
        """
        # Extract claims from both
        answer_claims = judge_fn(answer=answer, task="extract_claims")
        reference_claims = judge_fn(answer=reference_answer, task="extract_claims")
        
        if not reference_claims:
            return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
        if not answer_claims:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        
        # Check overlap (semantic, not exact)
        correct_in_answer = 0
        for claim in answer_claims:
            matches_reference = judge_fn(
                claim=claim,
                reference_claims=reference_claims,
                task="claim_matches_any"
            )
            if matches_reference:
                correct_in_answer += 1
        
        covered_in_reference = 0
        for claim in reference_claims:
            matches_answer = judge_fn(
                claim=claim,
                reference_claims=answer_claims,
                task="claim_matches_any"
            )
            if matches_answer:
                covered_in_reference += 1
        
        precision = correct_in_answer / len(answer_claims) if answer_claims else 0
        recall = covered_in_reference / len(reference_claims) if reference_claims else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {"precision": precision, "recall": recall, "f1": f1}
    
    @staticmethod
    def abstention_accuracy(
        should_abstain: bool,
        did_abstain: bool
    ) -> dict:
        """Check if abstention behavior is correct."""
        correct = should_abstain == did_abstain
        category = ""
        if should_abstain and did_abstain:
            category = "true_abstention"
        elif should_abstain and not did_abstain:
            category = "false_answer"  # Hallucination risk!
        elif not should_abstain and did_abstain:
            category = "false_abstention"  # Over-refusal
        else:
            category = "true_answer"
        
        return {"correct": correct, "category": category}


# ============================================================
# CITATION METRICS
# ============================================================

class CitationMetrics:
    """Metrics for evaluating citation quality."""
    
    @staticmethod
    def citation_precision(
        provided_citations: list[str],
        correct_citations: list[str]
    ) -> float:
        """Citation precision: fraction of provided citations that are correct."""
        if not provided_citations:
            return 1.0  # No citations provided = vacuously precise (debatable)
        correct_set = set(correct_citations)
        correct_count = sum(1 for c in provided_citations if c in correct_set)
        return correct_count / len(provided_citations)
    
    @staticmethod
    def citation_recall(
        provided_citations: list[str],
        required_citations: list[str]
    ) -> float:
        """Citation recall: fraction of required citations that were provided."""
        if not required_citations:
            return 1.0
        provided_set = set(provided_citations)
        found_count = sum(1 for c in required_citations if c in provided_set)
        return found_count / len(required_citations)
    
    @staticmethod
    def citation_f1(
        provided_citations: list[str],
        correct_citations: list[str]
    ) -> float:
        """F1 of citation precision and recall."""
        p = CitationMetrics.citation_precision(provided_citations, correct_citations)
        r = CitationMetrics.citation_recall(provided_citations, correct_citations)
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


# ============================================================
# LLM-AS-JUDGE
# ============================================================

class LLMJudge:
    """LLM-as-judge implementation with calibration."""
    
    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        num_samples: int = 1,  # For self-consistency
        position_debias: bool = True,
        llm_client: Optional[object] = None
    ):
        self.model = model
        self.temperature = temperature
        self.num_samples = num_samples
        self.position_debias = position_debias
        self.llm_client = llm_client
        self.calibration_data: list[dict] = []
    
    def judge(self, task: str, **kwargs) -> float | bool | list:
        """Route to appropriate judge prompt based on task."""
        prompt = self._build_prompt(task, **kwargs)
        
        if self.num_samples == 1:
            return self._call_llm(prompt, task)
        
        # Self-consistency: multiple samples, majority vote
        results = [self._call_llm(prompt, task) for _ in range(self.num_samples)]
        if isinstance(results[0], bool):
            return sum(results) > len(results) / 2
        elif isinstance(results[0], (int, float)):
            return statistics.median(results)
        return results[0]  # For list types, return first
    
    def pairwise_compare(
        self,
        query: str,
        answer_a: str,
        answer_b: str,
        context: str = ""
    ) -> dict:
        """Pairwise comparison with position debiasing."""
        # First order: A then B
        result_ab = self._pairwise_single(query, answer_a, answer_b, context)
        
        if not self.position_debias:
            return result_ab
        
        # Second order: B then A (swap)
        result_ba = self._pairwise_single(query, answer_b, answer_a, context)
        # Flip the result
        result_ba_flipped = "B" if result_ba["winner"] == "A" else "A" if result_ba["winner"] == "B" else "tie"
        
        # Combine
        if result_ab["winner"] == result_ba_flipped:
            return {"winner": result_ab["winner"], "confidence": "high", "consistent": True}
        else:
            return {"winner": "tie", "confidence": "low", "consistent": False}
    
    def calibrate(self, calibration_examples: list[dict]) -> dict:
        """Calibrate judge against human labels.
        
        calibration_examples: [{input: ..., human_label: ..., judge_label: ...}]
        """
        self.calibration_data = calibration_examples
        
        agreements = 0
        total = len(calibration_examples)
        
        for example in calibration_examples:
            judge_result = self.judge(**example["input"])
            example["judge_label"] = judge_result
            if judge_result == example["human_label"]:
                agreements += 1
        
        agreement_rate = agreements / total if total > 0 else 0
        
        # Cohen's kappa (simplified for binary)
        # pe = expected agreement by chance
        human_pos = sum(1 for e in calibration_examples if e["human_label"]) / total
        judge_pos = sum(1 for e in calibration_examples if e["judge_label"]) / total
        pe = human_pos * judge_pos + (1 - human_pos) * (1 - judge_pos)
        kappa = (agreement_rate - pe) / (1 - pe) if pe < 1 else 1.0
        
        return {
            "agreement_rate": agreement_rate,
            "cohens_kappa": kappa,
            "total_examples": total,
            "recommendation": (
                "Excellent (κ≥0.8)" if kappa >= 0.8
                else "Good (κ≥0.6)" if kappa >= 0.6
                else "Fair (κ≥0.4)" if kappa >= 0.4
                else "Poor (κ<0.4) — do not use as sole evaluator"
            )
        }
    
    def _build_prompt(self, task: str, **kwargs) -> str:
        """Build judge prompt for a specific task."""
        prompts = {
            "extract_claims": f"""Extract all factual claims from the following text. 
Return as a JSON list of strings. Each claim should be atomic (one fact).

Text: {kwargs.get('answer', '')}

Claims (JSON list):""",
            
            "verify_claim": f"""Does the following context support this claim? Answer YES or NO only.

Context: {kwargs.get('context', '')}

Claim: {kwargs.get('claim', '')}

Answer:""",
            
            "context_precision": f"""Is this context chunk useful for answering the given query?
Answer YES or NO only.

Query: {kwargs.get('query', '')}
Context chunk: {kwargs.get('context_chunk', '')}
Reference answer: {kwargs.get('reference_answer', '')}

Answer:""",
            
            "context_recall": f"""Does the context contain information that supports this claim?
Answer YES or NO only.

Context: {kwargs.get('context', '')}
Claim: {kwargs.get('claim', '')}

Answer:""",
            
            "context_relevance": f"""Rate the relevance of this context chunk to the query.
Score from 0.0 (irrelevant) to 1.0 (highly relevant). Return only the number.

Query: {kwargs.get('query', '')}
Context chunk: {kwargs.get('context_chunk', '')}

Score:""",
            
            "answer_relevance": f"""Rate how well the answer addresses the question.
Score from 0.0 (completely irrelevant) to 1.0 (perfectly addresses the question).
Return only the number.

Question: {kwargs.get('query', '')}
Answer: {kwargs.get('answer', '')}

Score:""",
            
            "extract_assertive_sentences": f"""Extract all assertive factual sentences from this text.
Exclude questions, hedged statements, and opinions. Return as a JSON list.

Text: {kwargs.get('answer', '')}

Sentences:""",
            
            "check_grounding": f"""Is this sentence grounded in the provided context and citations?
Answer YES or NO only.

Sentence: {kwargs.get('sentence', '')}
Context: {kwargs.get('context', '')}

Answer:""",
            
            "claim_matches_any": f"""Does this claim semantically match any of the reference claims?
Answer YES or NO only.

Claim: {kwargs.get('claim', '')}
Reference claims: {json.dumps(kwargs.get('reference_claims', []))}

Answer:"""
        }
        
        return prompts.get(task, f"Unknown task: {task}")
    
    def _call_llm(self, prompt: str, task: str):
        """Call LLM and parse response. Stub for integration."""
        # In production, this calls your LLM client
        # Here we return a placeholder
        if self.llm_client:
            response = self.llm_client.complete(prompt, model=self.model, temperature=self.temperature)
            return self._parse_response(response, task)
        
        # Stub response for demonstration
        if task in ("verify_claim", "context_precision", "context_recall", "check_grounding", "claim_matches_any"):
            return True
        elif task in ("context_relevance", "answer_relevance"):
            return 0.8
        elif task in ("extract_claims", "extract_assertive_sentences"):
            return ["claim1", "claim2"]
        return None
    
    def _parse_response(self, response: str, task: str):
        """Parse LLM response based on expected format."""
        response = response.strip()
        if task in ("verify_claim", "context_precision", "context_recall", "check_grounding", "claim_matches_any"):
            return response.upper().startswith("YES")
        elif task in ("context_relevance", "answer_relevance"):
            try:
                return float(response)
            except ValueError:
                return 0.5
        elif task in ("extract_claims", "extract_assertive_sentences"):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return [response]
        return response
    
    def _pairwise_single(self, query: str, answer_a: str, answer_b: str, context: str) -> dict:
        """Single pairwise comparison (without position debiasing)."""
        prompt = f"""Which answer better addresses the question? Consider accuracy, completeness, and helpfulness.
Answer with ONLY "A", "B", or "TIE".

Question: {query}
{"Context: " + context if context else ""}

Answer A: {answer_a}

Answer B: {answer_b}

Winner:"""
        
        if self.llm_client:
            response = self.llm_client.complete(prompt, model=self.model, temperature=self.temperature)
            winner = response.strip().upper()
        else:
            winner = "A"  # Stub
        
        if "A" in winner:
            return {"winner": "A"}
        elif "B" in winner:
            return {"winner": "B"}
        return {"winner": "tie"}


# ============================================================
# BATCH EVALUATOR
# ============================================================

class RAGEvaluator:
    """Batch RAG evaluation with full metric computation."""
    
    def __init__(self, judge: Optional[LLMJudge] = None):
        self.judge = judge or LLMJudge()
        self.retrieval_metrics = RetrievalMetrics()
        self.context_metrics = ContextMetrics()
        self.answer_metrics = AnswerMetrics()
        self.citation_metrics = CitationMetrics()
    
    def evaluate_single(self, rag_input: RAGInput, ground_truth: RAGGroundTruth) -> dict:
        """Evaluate a single RAG example across all metrics."""
        results = {}
        
        # Retrieval metrics
        retrieved_ids = [doc["doc_id"] for doc in rag_input.retrieved_documents]
        relevant_ids = ground_truth.relevant_doc_ids
        
        for k in [1, 3, 5, 10]:
            if k <= len(retrieved_ids):
                results[f"recall@{k}"] = self.retrieval_metrics.recall_at_k(retrieved_ids, relevant_ids, k)
                results[f"precision@{k}"] = self.retrieval_metrics.precision_at_k(retrieved_ids, relevant_ids, k)
        
        results["mrr"] = self.retrieval_metrics.mrr(retrieved_ids, relevant_ids)
        
        if ground_truth.relevance_grades:
            results["ndcg@10"] = self.retrieval_metrics.ndcg_at_k(
                retrieved_ids, ground_truth.relevance_grades, 10
            )
        
        results["average_precision"] = self.retrieval_metrics.average_precision(retrieved_ids, relevant_ids)
        
        # Context metrics (using judge)
        retrieved_contents = [doc.get("content", "") for doc in rag_input.retrieved_documents]
        combined_context = "\n".join(retrieved_contents)
        
        results["context_precision"] = self.context_metrics.context_precision(
            retrieved_contents, rag_input.query, ground_truth.reference_answer, self.judge.judge
        )
        
        if ground_truth.key_claims:
            results["context_recall"] = self.context_metrics.context_recall(
                retrieved_contents, ground_truth.key_claims, self.judge.judge
            )
        
        # Answer metrics
        results["faithfulness"] = self.answer_metrics.faithfulness(
            rag_input.generated_answer, combined_context, self.judge.judge
        )
        
        results["answer_relevance"] = self.answer_metrics.answer_relevance(
            rag_input.generated_answer, rag_input.query, self.judge.judge
        )
        
        if ground_truth.reference_answer:
            correctness = self.answer_metrics.answer_correctness(
                rag_input.generated_answer, ground_truth.reference_answer, self.judge.judge
            )
            results["answer_correctness_f1"] = correctness["f1"]
            results["answer_correctness_precision"] = correctness["precision"]
            results["answer_correctness_recall"] = correctness["recall"]
        
        # Abstention
        did_abstain = self._detect_abstention(rag_input.generated_answer)
        abstention = self.answer_metrics.abstention_accuracy(ground_truth.should_abstain, did_abstain)
        results["abstention_correct"] = 1.0 if abstention["correct"] else 0.0
        results["abstention_category"] = abstention["category"]
        
        # Citation metrics
        if ground_truth.required_citations:
            results["citation_precision"] = self.citation_metrics.citation_precision(
                rag_input.citations, ground_truth.required_citations
            )
            results["citation_recall"] = self.citation_metrics.citation_recall(
                rag_input.citations, ground_truth.required_citations
            )
            results["citation_f1"] = self.citation_metrics.citation_f1(
                rag_input.citations, ground_truth.required_citations
            )
        
        # Cost/latency
        results["latency_ms"] = rag_input.latency_ms
        results["total_tokens"] = rag_input.total_tokens
        results["cost_usd"] = rag_input.cost_usd
        
        return results
    
    def evaluate_batch(
        self,
        inputs: list[RAGInput],
        ground_truths: list[RAGGroundTruth],
        slices: Optional[dict] = None  # {example_idx: {slice_key: slice_value}}
    ) -> EvaluationReport:
        """Evaluate a batch of RAG examples."""
        assert len(inputs) == len(ground_truths), "Inputs and ground truths must match"
        
        all_results = []
        failures = []
        
        for i, (inp, gt) in enumerate(zip(inputs, ground_truths)):
            try:
                result = self.evaluate_single(inp, gt)
                result["_index"] = i
                all_results.append(result)
            except Exception as e:
                failures.append({"index": i, "query": inp.query, "error": str(e)})
        
        # Aggregate metrics
        report = EvaluationReport(
            config_id=inputs[0].config_id if inputs else "unknown",
            num_examples=len(inputs),
            failures=failures
        )
        
        # Compute aggregate metrics with confidence intervals
        metric_names = set()
        for r in all_results:
            metric_names.update(k for k in r.keys() if k != "_index" and isinstance(r[k], (int, float)))
        
        for metric in metric_names:
            values = [r[metric] for r in all_results if metric in r and isinstance(r[metric], (int, float))]
            if values:
                report.metrics[metric] = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "n": len(values),
                    "ci_95": self._bootstrap_ci(values) if len(values) >= 20 else None
                }
        
        # Slice-based metrics
        if slices:
            report.slice_metrics = self._compute_slice_metrics(all_results, slices)
        
        return report
    
    def _compute_slice_metrics(self, results: list[dict], slices: dict) -> dict:
        """Compute metrics per slice."""
        slice_groups = defaultdict(list)
        
        for result in results:
            idx = result["_index"]
            if idx in slices:
                for slice_key, slice_value in slices[idx].items():
                    slice_groups[f"{slice_key}:{slice_value}"].append(result)
        
        slice_metrics = {}
        for slice_name, slice_results in slice_groups.items():
            slice_metrics[slice_name] = {}
            for metric in ["faithfulness", "answer_relevance", "recall@5", "mrr"]:
                values = [r[metric] for r in slice_results if metric in r]
                if values:
                    slice_metrics[slice_name][metric] = {
                        "mean": statistics.mean(values),
                        "n": len(values)
                    }
        
        return slice_metrics
    
    def _detect_abstention(self, answer: str) -> bool:
        """Detect if the answer is an abstention."""
        abstention_phrases = [
            "i don't have enough information",
            "i cannot answer",
            "i'm not able to",
            "the provided context doesn't",
            "there is no information",
            "i don't know",
            "cannot be determined from",
        ]
        answer_lower = answer.lower()
        return any(phrase in answer_lower for phrase in abstention_phrases)
    
    def _bootstrap_ci(self, values: list[float], confidence: float = 0.95, n_bootstrap: int = 1000) -> tuple:
        """Compute bootstrap confidence interval."""
        n = len(values)
        bootstrap_means = []
        
        for _ in range(n_bootstrap):
            sample = random.choices(values, k=n)
            bootstrap_means.append(statistics.mean(sample))
        
        bootstrap_means.sort()
        alpha = 1 - confidence
        lower_idx = int(alpha / 2 * n_bootstrap)
        upper_idx = int((1 - alpha / 2) * n_bootstrap)
        
        return (bootstrap_means[lower_idx], bootstrap_means[upper_idx])


# ============================================================
# COMPARISON AND REGRESSION DETECTION
# ============================================================

class RAGComparison:
    """Compare RAG configurations and detect regressions."""
    
    @staticmethod
    def compare_configs(report_a: EvaluationReport, report_b: EvaluationReport) -> dict:
        """Compare two configurations across all metrics."""
        comparison = {
            "config_a": report_a.config_id,
            "config_b": report_b.config_id,
            "metrics": {}
        }
        
        all_metrics = set(report_a.metrics.keys()) | set(report_b.metrics.keys())
        
        for metric in all_metrics:
            a_val = report_a.metrics.get(metric, {}).get("mean")
            b_val = report_b.metrics.get(metric, {}).get("mean")
            
            if a_val is not None and b_val is not None:
                delta = b_val - a_val
                pct_change = (delta / a_val * 100) if a_val != 0 else float('inf')
                
                comparison["metrics"][metric] = {
                    "config_a": a_val,
                    "config_b": b_val,
                    "delta": delta,
                    "pct_change": pct_change,
                    "significant": abs(pct_change) > 2.0  # Simplified threshold
                }
        
        return comparison
    
    @staticmethod
    def detect_regression(
        current: EvaluationReport,
        baseline: EvaluationReport,
        thresholds: dict = None
    ) -> dict:
        """Detect statistically significant regressions."""
        default_thresholds = {
            "faithfulness": -0.02,      # Max 2% drop
            "answer_relevance": -0.03,
            "recall@5": -0.05,
            "mrr": -0.05,
            "abstention_correct": -0.05,
            "citation_f1": -0.05,
        }
        thresholds = thresholds or default_thresholds
        
        regressions = []
        
        for metric, max_drop in thresholds.items():
            current_val = current.metrics.get(metric, {}).get("mean")
            baseline_val = baseline.metrics.get(metric, {}).get("mean")
            
            if current_val is None or baseline_val is None:
                continue
            
            delta = current_val - baseline_val
            if delta < max_drop:
                regressions.append({
                    "metric": metric,
                    "baseline": baseline_val,
                    "current": current_val,
                    "delta": delta,
                    "threshold": max_drop,
                    "severity": "critical" if delta < max_drop * 2 else "warning"
                })
        
        return {
            "has_regression": len(regressions) > 0,
            "regressions": regressions,
            "recommendation": "BLOCK" if any(r["severity"] == "critical" for r in regressions)
                            else "WARN" if regressions else "PASS"
        }
    
    @staticmethod
    def paired_significance_test(values_a: list[float], values_b: list[float]) -> dict:
        """Paired bootstrap significance test."""
        assert len(values_a) == len(values_b)
        n = len(values_a)
        
        observed_diff = statistics.mean(values_b) - statistics.mean(values_a)
        
        # Bootstrap test
        n_bootstrap = 10000
        count_extreme = 0
        
        for _ in range(n_bootstrap):
            # Randomly swap pairs
            diffs = []
            for a, b in zip(values_a, values_b):
                if random.random() < 0.5:
                    diffs.append(b - a)
                else:
                    diffs.append(a - b)
            boot_diff = statistics.mean(diffs)
            if abs(boot_diff) >= abs(observed_diff):
                count_extreme += 1
        
        p_value = count_extreme / n_bootstrap
        
        return {
            "observed_difference": observed_diff,
            "p_value": p_value,
            "significant_at_05": p_value < 0.05,
            "significant_at_01": p_value < 0.01,
            "n": n
        }


# ============================================================
# REPORT GENERATION
# ============================================================

class ReportGenerator:
    """Generate human-readable evaluation reports."""
    
    @staticmethod
    def generate_markdown(report: EvaluationReport, baseline: Optional[EvaluationReport] = None) -> str:
        """Generate markdown evaluation report."""
        lines = [
            f"# RAG Evaluation Report",
            f"",
            f"**Config**: {report.config_id}",
            f"**Timestamp**: {report.timestamp}",
            f"**Examples**: {report.num_examples}",
            f"**Failures**: {len(report.failures)}",
            f"",
            f"## Metrics Summary",
            f"",
            f"| Metric | Mean | Median | Std | 95% CI |",
            f"|--------|------|--------|-----|--------|",
        ]
        
        # Sort metrics by category
        for metric, values in sorted(report.metrics.items()):
            if isinstance(values, dict) and "mean" in values:
                ci = f"[{values['ci_95'][0]:.3f}, {values['ci_95'][1]:.3f}]" if values.get("ci_95") else "N/A"
                delta_str = ""
                if baseline and metric in baseline.metrics:
                    delta = values["mean"] - baseline.metrics[metric]["mean"]
                    delta_str = f" ({'↑' if delta > 0 else '↓'}{abs(delta):.3f})"
                lines.append(
                    f"| {metric} | {values['mean']:.4f}{delta_str} | "
                    f"{values['median']:.4f} | {values.get('std', 0):.4f} | {ci} |"
                )
        
        # Slice metrics
        if report.slice_metrics:
            lines.extend(["", "## Slice Analysis", ""])
            for slice_name, metrics in report.slice_metrics.items():
                lines.append(f"### {slice_name}")
                for metric, vals in metrics.items():
                    lines.append(f"- {metric}: {vals['mean']:.4f} (n={vals['n']})")
                lines.append("")
        
        # Failures
        if report.failures:
            lines.extend(["", "## Failures", ""])
            for failure in report.failures[:10]:
                lines.append(f"- **{failure['query'][:50]}...**: {failure['error']}")
        
        return "\n".join(lines)


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    # Create judge
    judge = LLMJudge(model="gpt-4o", num_samples=1)
    
    # Create evaluator
    evaluator = RAGEvaluator(judge=judge)
    
    # Example evaluation
    rag_input = RAGInput(
        query="What is the refund policy for enterprise customers?",
        retrieved_documents=[
            {"doc_id": "policy-42", "chunk_id": "c1", "content": "Enterprise customers get 30-day refunds.", "score": 0.95},
            {"doc_id": "faq-12", "chunk_id": "c2", "content": "General FAQ about returns.", "score": 0.72},
        ],
        generated_answer="Enterprise customers can request a full refund within 30 days of purchase.",
        citations=["policy-42"],
        latency_ms=1200,
        total_tokens=850,
        cost_usd=0.003,
        config_id="rag-v2.1"
    )
    
    ground_truth = RAGGroundTruth(
        query="What is the refund policy for enterprise customers?",
        relevant_doc_ids=["policy-42"],
        relevance_grades={"policy-42": 3, "faq-12": 1},
        reference_answer="Enterprise customers may request a full refund within 30 days.",
        required_citations=["policy-42"],
        should_abstain=False,
        key_claims=["30-day refund window", "full refund"]
    )
    
    # Run evaluation
    results = evaluator.evaluate_single(rag_input, ground_truth)
    print(json.dumps(results, indent=2, default=str))
