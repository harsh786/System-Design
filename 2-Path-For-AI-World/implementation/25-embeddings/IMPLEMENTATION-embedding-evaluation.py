"""
Embedding Evaluation Framework - Comprehensive evaluation of embedding models.

Features:
- Custom evaluation dataset creation
- Recall@k measurement
- MRR (Mean Reciprocal Rank) computation
- nDCG (Normalized Discounted Cumulative Gain) computation
- Cross-model comparison
- Domain-specific evaluation
- Multilingual evaluation
- Adversarial query evaluation
- Statistical significance testing
- Evaluation report generation
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class EvalQuery:
    """A single evaluation query with relevance judgments."""
    query_id: str
    query_text: str
    relevant_doc_ids: list[str]  # Ordered by relevance (most relevant first)
    category: str = "general"  # general, paraphrase, multi_hop, adversarial, etc.
    language: str = "en"
    difficulty: str = "medium"  # easy, medium, hard


@dataclass
class EvalDocument:
    """A document in the evaluation corpus."""
    doc_id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalDataset:
    """Complete evaluation dataset."""
    name: str
    queries: list[EvalQuery]
    documents: list[EvalDocument]
    description: str = ""
    version: str = "1.0"

    def get_category_queries(self, category: str) -> list[EvalQuery]:
        return [q for q in self.queries if q.category == category]

    @property
    def categories(self) -> list[str]:
        return list(set(q.category for q in self.queries))

    def save(self, path: str):
        data = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "queries": [
                {
                    "query_id": q.query_id,
                    "query_text": q.query_text,
                    "relevant_doc_ids": q.relevant_doc_ids,
                    "category": q.category,
                    "language": q.language,
                    "difficulty": q.difficulty,
                }
                for q in self.queries
            ],
            "documents": [
                {"doc_id": d.doc_id, "text": d.text, "metadata": d.metadata}
                for d in self.documents
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str) -> "EvalDataset":
        data = json.loads(Path(path).read_text())
        queries = [EvalQuery(**q) for q in data["queries"]]
        documents = [EvalDocument(**d) for d in data["documents"]]
        return cls(
            name=data["name"],
            queries=queries,
            documents=documents,
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
        )


@dataclass
class ModelEvalResult:
    """Evaluation results for a single model."""
    model_name: str
    recall_at_k: dict[int, float]  # {1: 0.45, 5: 0.78, 10: 0.89, ...}
    mrr: float
    ndcg_at_k: dict[int, float]
    per_category_recall: dict[str, dict[int, float]]
    per_category_mrr: dict[str, float]
    latency_ms: float
    total_queries: int
    per_query_scores: list[dict]  # For statistical testing


# =============================================================================
# Evaluation Dataset Builder
# =============================================================================

class EvalDatasetBuilder:
    """Helper to build evaluation datasets from various sources."""

    def __init__(self, name: str, description: str = ""):
        self._name = name
        self._description = description
        self._queries: list[EvalQuery] = []
        self._documents: list[EvalDocument] = []
        self._doc_ids: set = set()

    def add_document(self, doc_id: str, text: str, **metadata) -> "EvalDatasetBuilder":
        if doc_id not in self._doc_ids:
            self._documents.append(EvalDocument(doc_id=doc_id, text=text, metadata=metadata))
            self._doc_ids.add(doc_id)
        return self

    def add_query(
        self,
        query_id: str,
        query_text: str,
        relevant_doc_ids: list[str],
        category: str = "general",
        language: str = "en",
        difficulty: str = "medium",
    ) -> "EvalDatasetBuilder":
        self._queries.append(
            EvalQuery(
                query_id=query_id,
                query_text=query_text,
                relevant_doc_ids=relevant_doc_ids,
                category=category,
                language=language,
                difficulty=difficulty,
            )
        )
        return self

    def add_exact_term_queries(self, queries: list[dict]) -> "EvalDatasetBuilder":
        """Add queries that test exact term matching."""
        for i, q in enumerate(queries):
            self.add_query(
                query_id=f"exact_{i}",
                query_text=q["query"],
                relevant_doc_ids=q["relevant_docs"],
                category="exact_term",
                difficulty="easy",
            )
        return self

    def add_paraphrase_queries(self, queries: list[dict]) -> "EvalDatasetBuilder":
        """Add queries expressed differently from document text."""
        for i, q in enumerate(queries):
            self.add_query(
                query_id=f"paraphrase_{i}",
                query_text=q["query"],
                relevant_doc_ids=q["relevant_docs"],
                category="paraphrase",
                difficulty="medium",
            )
        return self

    def add_adversarial_queries(self, queries: list[dict]) -> "EvalDatasetBuilder":
        """Add adversarial queries (negation, misleading terms)."""
        for i, q in enumerate(queries):
            self.add_query(
                query_id=f"adversarial_{i}",
                query_text=q["query"],
                relevant_doc_ids=q["relevant_docs"],
                category="adversarial",
                difficulty="hard",
            )
        return self

    def add_no_answer_queries(self, queries: list[str]) -> "EvalDatasetBuilder":
        """Add queries with no relevant documents."""
        for i, q in enumerate(queries):
            self.add_query(
                query_id=f"no_answer_{i}",
                query_text=q,
                relevant_doc_ids=[],
                category="no_answer",
                difficulty="hard",
            )
        return self

    def add_multilingual_queries(self, queries: list[dict]) -> "EvalDatasetBuilder":
        """Add queries in non-English languages."""
        for i, q in enumerate(queries):
            self.add_query(
                query_id=f"multilingual_{i}",
                query_text=q["query"],
                relevant_doc_ids=q["relevant_docs"],
                category="multilingual",
                language=q.get("language", "unknown"),
                difficulty="medium",
            )
        return self

    def from_llm_generation(self, documents: list[dict], llm_client) -> "EvalDatasetBuilder":
        """
        Generate evaluation queries from documents using an LLM.

        Each document gets:
        - 1 exact match query
        - 1 paraphrase query
        - 1 adversarial query
        """
        prompt_template = """Given this document, generate evaluation queries.

Document: {text}

Generate exactly 3 queries in JSON format:
1. An exact term query (uses key terms from the document)
2. A paraphrase query (asks the same thing differently)
3. An adversarial query (tries to trick a retrieval system)

Output format:
{{"exact": "...", "paraphrase": "...", "adversarial": "..."}}"""

        for doc in documents:
            self.add_document(doc["id"], doc["text"])

            # Call LLM to generate queries
            response = llm_client.generate(
                prompt_template.format(text=doc["text"][:500])
            )
            try:
                generated = json.loads(response)
                self.add_query(
                    f"gen_exact_{doc['id']}", generated["exact"],
                    [doc["id"]], category="exact_term"
                )
                self.add_query(
                    f"gen_para_{doc['id']}", generated["paraphrase"],
                    [doc["id"]], category="paraphrase"
                )
                self.add_query(
                    f"gen_adv_{doc['id']}", generated["adversarial"],
                    [doc["id"]], category="adversarial"
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse LLM output for doc {doc['id']}: {e}")

        return self

    def build(self) -> EvalDataset:
        return EvalDataset(
            name=self._name,
            queries=self._queries,
            documents=self._documents,
            description=self._description,
        )


# =============================================================================
# Core Metrics
# =============================================================================

class RetrievalMetrics:
    """Compute standard IR metrics."""

    @staticmethod
    def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Fraction of relevant documents retrieved in top-k."""
        if not relevant_ids:
            return 1.0  # No relevant docs = trivially correct
        retrieved_top_k = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_top_k & relevant_set) / len(relevant_set)

    @staticmethod
    def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Fraction of top-k that are relevant."""
        if k == 0:
            return 0.0
        retrieved_top_k = retrieved_ids[:k]
        relevant_set = set(relevant_ids)
        return sum(1 for doc in retrieved_top_k if doc in relevant_set) / k

    @staticmethod
    def reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
        """1/rank of the first relevant document."""
        relevant_set = set(relevant_ids)
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_set:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """
        Normalized Discounted Cumulative Gain at k.
        Uses binary relevance (relevant=1, not relevant=0).
        """
        relevant_set = set(relevant_ids)

        # DCG
        dcg = 0.0
        for i, doc_id in enumerate(retrieved_ids[:k]):
            if doc_id in relevant_set:
                dcg += 1.0 / np.log2(i + 2)  # +2 because i is 0-indexed

        # Ideal DCG
        ideal_relevant = min(len(relevant_ids), k)
        idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_relevant))

        if idcg == 0:
            return 1.0  # No relevant docs
        return dcg / idcg

    @staticmethod
    def average_precision(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
        """Average precision for a single query."""
        relevant_set = set(relevant_ids)
        if not relevant_set:
            return 1.0

        num_relevant_seen = 0
        precision_sum = 0.0

        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_set:
                num_relevant_seen += 1
                precision_sum += num_relevant_seen / (i + 1)

        return precision_sum / len(relevant_set)


# =============================================================================
# Embedding Evaluator
# =============================================================================

class EmbeddingEvaluator:
    """
    Evaluate embedding models on a standard evaluation dataset.

    Usage:
        evaluator = EmbeddingEvaluator(dataset)
        result = await evaluator.evaluate_model(embedding_fn, model_name="openai-3-large")
    """

    def __init__(self, dataset: EvalDataset, k_values: list[int] = None):
        self.dataset = dataset
        self.k_values = k_values or [1, 3, 5, 10, 20, 50, 100]
        self._doc_embeddings: Optional[dict[str, np.ndarray]] = None
        self._metrics = RetrievalMetrics()

    async def evaluate_model(
        self,
        embed_fn,  # async fn(texts: list[str]) -> list[list[float]]
        model_name: str,
        batch_size: int = 100,
    ) -> ModelEvalResult:
        """
        Evaluate a single embedding model.

        Args:
            embed_fn: Async function that takes list of texts and returns embeddings.
            model_name: Name for this model in results.
            batch_size: Batch size for embedding generation.
        """
        start_time = time.monotonic()

        # Embed all documents
        logger.info(f"Embedding {len(self.dataset.documents)} documents with {model_name}...")
        doc_texts = [d.text for d in self.dataset.documents]
        doc_embeddings = await self._batch_embed(embed_fn, doc_texts, batch_size)
        doc_id_to_embedding = {
            self.dataset.documents[i].doc_id: doc_embeddings[i]
            for i in range(len(self.dataset.documents))
        }

        # Build document matrix for fast similarity computation
        doc_ids = [d.doc_id for d in self.dataset.documents]
        doc_matrix = np.array([doc_id_to_embedding[did] for did in doc_ids])

        # Embed all queries
        logger.info(f"Embedding {len(self.dataset.queries)} queries...")
        query_texts = [q.query_text for q in self.dataset.queries]
        query_embeddings = await self._batch_embed(embed_fn, query_texts, batch_size)

        # Compute metrics per query
        per_query_scores = []
        category_scores: dict[str, list[dict]] = {}

        for i, query in enumerate(self.dataset.queries):
            query_vec = np.array(query_embeddings[i])

            # Compute similarities (dot product for normalized vectors)
            similarities = doc_matrix @ query_vec
            ranked_indices = np.argsort(similarities)[::-1]
            retrieved_ids = [doc_ids[idx] for idx in ranked_indices]

            # Compute metrics
            query_metrics = {
                "query_id": query.query_id,
                "category": query.category,
                "recall": {},
                "ndcg": {},
            }

            for k in self.k_values:
                query_metrics["recall"][k] = self._metrics.recall_at_k(
                    retrieved_ids, query.relevant_doc_ids, k
                )
                query_metrics["ndcg"][k] = self._metrics.ndcg_at_k(
                    retrieved_ids, query.relevant_doc_ids, k
                )

            query_metrics["mrr"] = self._metrics.reciprocal_rank(
                retrieved_ids, query.relevant_doc_ids
            )
            query_metrics["ap"] = self._metrics.average_precision(
                retrieved_ids, query.relevant_doc_ids
            )

            per_query_scores.append(query_metrics)

            # Group by category
            if query.category not in category_scores:
                category_scores[query.category] = []
            category_scores[query.category].append(query_metrics)

        # Aggregate metrics
        recall_at_k = {}
        ndcg_at_k = {}
        for k in self.k_values:
            recall_at_k[k] = np.mean([s["recall"][k] for s in per_query_scores])
            ndcg_at_k[k] = np.mean([s["ndcg"][k] for s in per_query_scores])

        mrr = np.mean([s["mrr"] for s in per_query_scores])

        # Per-category metrics
        per_category_recall = {}
        per_category_mrr = {}
        for category, scores in category_scores.items():
            per_category_recall[category] = {
                k: np.mean([s["recall"][k] for s in scores]) for k in self.k_values
            }
            per_category_mrr[category] = np.mean([s["mrr"] for s in scores])

        latency_ms = (time.monotonic() - start_time) * 1000

        return ModelEvalResult(
            model_name=model_name,
            recall_at_k=recall_at_k,
            mrr=mrr,
            ndcg_at_k=ndcg_at_k,
            per_category_recall=per_category_recall,
            per_category_mrr=per_category_mrr,
            latency_ms=latency_ms,
            total_queries=len(self.dataset.queries),
            per_query_scores=per_query_scores,
        )

    async def _batch_embed(self, embed_fn, texts: list[str], batch_size: int) -> list:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await embed_fn(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings


# =============================================================================
# Cross-Model Comparison
# =============================================================================

class ModelComparator:
    """Compare multiple embedding models with statistical significance."""

    def __init__(self, results: list[ModelEvalResult]):
        self.results = {r.model_name: r for r in results}

    def comparison_table(self, metric: str = "recall", k: int = 10) -> str:
        """Generate comparison table."""
        lines = [
            f"{'Model':<30} {'Recall@1':<10} {'Recall@5':<10} {'Recall@10':<10} {'MRR':<10} {'nDCG@10':<10}"
        ]
        lines.append("-" * 80)

        for name, result in sorted(self.results.items(), key=lambda x: x[1].mrr, reverse=True):
            lines.append(
                f"{name:<30} "
                f"{result.recall_at_k.get(1, 0):<10.4f} "
                f"{result.recall_at_k.get(5, 0):<10.4f} "
                f"{result.recall_at_k.get(10, 0):<10.4f} "
                f"{result.mrr:<10.4f} "
                f"{result.ndcg_at_k.get(10, 0):<10.4f}"
            )

        return "\n".join(lines)

    def statistical_significance(
        self, model_a: str, model_b: str, metric: str = "mrr", alpha: float = 0.05
    ) -> dict:
        """
        Paired t-test between two models on per-query scores.

        Returns dict with t-statistic, p-value, and whether difference is significant.
        """
        result_a = self.results[model_a]
        result_b = self.results[model_b]

        if metric == "mrr":
            scores_a = [s["mrr"] for s in result_a.per_query_scores]
            scores_b = [s["mrr"] for s in result_b.per_query_scores]
        elif metric.startswith("recall@"):
            k = int(metric.split("@")[1])
            scores_a = [s["recall"][k] for s in result_a.per_query_scores]
            scores_b = [s["recall"][k] for s in result_b.per_query_scores]
        else:
            raise ValueError(f"Unknown metric: {metric}")

        t_stat, p_value = stats.ttest_rel(scores_a, scores_b)

        # Bootstrap confidence interval for the difference
        differences = np.array(scores_a) - np.array(scores_b)
        bootstrap_means = []
        for _ in range(1000):
            sample = np.random.choice(differences, size=len(differences), replace=True)
            bootstrap_means.append(np.mean(sample))

        ci_lower = np.percentile(bootstrap_means, 2.5)
        ci_upper = np.percentile(bootstrap_means, 97.5)

        return {
            "model_a": model_a,
            "model_b": model_b,
            "metric": metric,
            "mean_a": np.mean(scores_a),
            "mean_b": np.mean(scores_b),
            "difference": np.mean(scores_a) - np.mean(scores_b),
            "t_statistic": t_stat,
            "p_value": p_value,
            "significant": p_value < alpha,
            "confidence_interval_95": (ci_lower, ci_upper),
            "alpha": alpha,
        }

    def category_comparison(self) -> str:
        """Compare models across categories."""
        categories = set()
        for result in self.results.values():
            categories.update(result.per_category_recall.keys())

        lines = [f"\n{'Category':<20} " + " ".join(f"{m:<20}" for m in self.results.keys())]
        lines.append("-" * (20 + 20 * len(self.results)))

        for category in sorted(categories):
            values = []
            for name, result in self.results.items():
                r10 = result.per_category_recall.get(category, {}).get(10, 0)
                values.append(f"{r10:<20.4f}")
            lines.append(f"{category:<20} " + " ".join(values))

        return "\n".join(lines)


# =============================================================================
# Evaluation Report Generator
# =============================================================================

class EvalReportGenerator:
    """Generate comprehensive evaluation reports."""

    def __init__(self, comparator: ModelComparator, dataset: EvalDataset):
        self._comparator = comparator
        self._dataset = dataset

    def generate_report(self, output_path: str):
        """Generate full markdown evaluation report."""
        lines = [
            f"# Embedding Evaluation Report",
            f"",
            f"## Dataset: {self._dataset.name}",
            f"- **Queries:** {len(self._dataset.queries)}",
            f"- **Documents:** {len(self._dataset.documents)}",
            f"- **Categories:** {', '.join(self._dataset.categories)}",
            f"- **Version:** {self._dataset.version}",
            f"",
            f"## Overall Results",
            f"```",
            self._comparator.comparison_table(),
            f"```",
            f"",
            f"## Per-Category Results (Recall@10)",
            f"```",
            self._comparator.category_comparison(),
            f"```",
            f"",
        ]

        # Statistical significance between all pairs
        model_names = list(self._comparator.results.keys())
        if len(model_names) >= 2:
            lines.append("## Statistical Significance (MRR, paired t-test)")
            lines.append("")
            for i in range(len(model_names)):
                for j in range(i + 1, len(model_names)):
                    sig = self._comparator.statistical_significance(
                        model_names[i], model_names[j]
                    )
                    status = "SIGNIFICANT" if sig["significant"] else "NOT significant"
                    lines.append(
                        f"- **{model_names[i]}** vs **{model_names[j]}**: "
                        f"diff={sig['difference']:.4f}, p={sig['p_value']:.4f} ({status})"
                    )
            lines.append("")

        # Recommendations
        lines.append("## Recommendation")
        best_model = max(
            self._comparator.results.values(), key=lambda r: r.mrr
        )
        lines.append(f"Best overall model: **{best_model.model_name}** (MRR={best_model.mrr:.4f})")

        Path(output_path).write_text("\n".join(lines))
        logger.info(f"Report saved to {output_path}")

    def generate_json_report(self, output_path: str):
        """Generate machine-readable JSON report."""
        report = {
            "dataset": {
                "name": self._dataset.name,
                "num_queries": len(self._dataset.queries),
                "num_documents": len(self._dataset.documents),
                "categories": self._dataset.categories,
            },
            "results": {},
        }

        for name, result in self._comparator.results.items():
            report["results"][name] = {
                "recall_at_k": result.recall_at_k,
                "mrr": result.mrr,
                "ndcg_at_k": result.ndcg_at_k,
                "per_category_recall": result.per_category_recall,
                "per_category_mrr": result.per_category_mrr,
                "latency_ms": result.latency_ms,
            }

        Path(output_path).write_text(json.dumps(report, indent=2, default=str))


# =============================================================================
# Example Usage
# =============================================================================

async def example_evaluation():
    """Example: evaluate two models and compare."""

    # 1. Build evaluation dataset
    builder = EvalDatasetBuilder("my-domain-eval", "Evaluation for our product search")

    # Add documents
    for i in range(100):
        builder.add_document(f"doc_{i}", f"Document {i} content about various topics...")

    # Add queries of different types
    builder.add_exact_term_queries([
        {"query": "RFC 7231 HTTP semantics", "relevant_docs": ["doc_0"]},
        {"query": "CUDA toolkit 12.0 installation", "relevant_docs": ["doc_1"]},
    ])
    builder.add_paraphrase_queries([
        {"query": "How to stop my program from crashing?", "relevant_docs": ["doc_2"]},
        {"query": "Ways to make API calls faster", "relevant_docs": ["doc_3"]},
    ])
    builder.add_adversarial_queries([
        {"query": "I do NOT want Python information", "relevant_docs": ["doc_4"]},
    ])
    builder.add_no_answer_queries([
        "What is the price of quantum computing as a service?",
    ])

    dataset = builder.build()
    dataset.save("eval_dataset_v1.json")

    # 2. Evaluate models
    evaluator = EmbeddingEvaluator(dataset)

    # Mock embedding functions for demonstration
    async def mock_embed_model_a(texts):
        return [np.random.randn(768).tolist() for _ in texts]

    async def mock_embed_model_b(texts):
        return [np.random.randn(1024).tolist() for _ in texts]

    result_a = await evaluator.evaluate_model(mock_embed_model_a, "model-a-768d")
    result_b = await evaluator.evaluate_model(mock_embed_model_b, "model-b-1024d")

    # 3. Compare
    comparator = ModelComparator([result_a, result_b])
    print(comparator.comparison_table())
    print()

    sig = comparator.statistical_significance("model-a-768d", "model-b-1024d")
    print(f"Statistical significance: p={sig['p_value']:.4f}, significant={sig['significant']}")

    # 4. Generate report
    report_gen = EvalReportGenerator(comparator, dataset)
    report_gen.generate_report("eval_report.md")
    report_gen.generate_json_report("eval_report.json")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_evaluation())
