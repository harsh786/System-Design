"""
Embedding Fine-Tuning - Domain adaptation for embedding models.

Features:
- Training data preparation (positive pairs, hard negatives)
- Contrastive learning setup (InfoNCE / Multiple Negatives Ranking Loss)
- Fine-tuning with sentence-transformers
- Evaluation during training
- Domain adaptation strategies
- Hard negative mining
- Model export and serving
- Before/after comparison
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Training Data Structures
# =============================================================================

@dataclass
class TrainingPair:
    """A single training example."""
    query: str
    positive: str  # Relevant document
    hard_negatives: list[str] = field(default_factory=list)  # Similar but irrelevant
    metadata: dict = field(default_factory=dict)


@dataclass
class TrainingDataset:
    """Complete training dataset for embedding fine-tuning."""
    pairs: list[TrainingPair]
    name: str = "training_data"
    version: str = "1.0"

    @property
    def size(self) -> int:
        return len(self.pairs)

    def split(self, train_ratio: float = 0.9) -> tuple["TrainingDataset", "TrainingDataset"]:
        """Split into train/val sets."""
        shuffled = self.pairs.copy()
        random.shuffle(shuffled)
        split_idx = int(len(shuffled) * train_ratio)
        return (
            TrainingDataset(pairs=shuffled[:split_idx], name=f"{self.name}_train"),
            TrainingDataset(pairs=shuffled[split_idx:], name=f"{self.name}_val"),
        )

    def save(self, path: str):
        data = {
            "name": self.name,
            "version": self.version,
            "pairs": [
                {
                    "query": p.query,
                    "positive": p.positive,
                    "hard_negatives": p.hard_negatives,
                    "metadata": p.metadata,
                }
                for p in self.pairs
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str) -> "TrainingDataset":
        data = json.loads(Path(path).read_text())
        pairs = [TrainingPair(**p) for p in data["pairs"]]
        return cls(pairs=pairs, name=data.get("name", ""), version=data.get("version", "1.0"))


# =============================================================================
# Training Data Preparation
# =============================================================================

class TrainingDataPreparer:
    """
    Prepare training data from various sources.

    Sources:
    - Query logs with clicked documents
    - Manually annotated pairs
    - LLM-generated synthetic pairs
    - Cross-encoder scored pairs
    """

    def __init__(self):
        self._pairs: list[TrainingPair] = []

    def from_query_clicks(self, click_data: list[dict]) -> "TrainingDataPreparer":
        """
        Create pairs from search click logs.

        Expected format: [{"query": "...", "clicked_doc": "...", "shown_docs": [...]}]
        """
        for item in click_data:
            # Clicked doc = positive
            # Other shown but not clicked = potential hard negatives
            negatives = [d for d in item.get("shown_docs", []) if d != item["clicked_doc"]]
            self._pairs.append(
                TrainingPair(
                    query=item["query"],
                    positive=item["clicked_doc"],
                    hard_negatives=negatives[:5],
                    metadata={"source": "click_log"},
                )
            )
        return self

    def from_qa_pairs(self, qa_pairs: list[dict]) -> "TrainingDataPreparer":
        """
        Create pairs from question-answer data.

        Expected format: [{"question": "...", "answer": "...", "context": "..."}]
        """
        for item in qa_pairs:
            self._pairs.append(
                TrainingPair(
                    query=item["question"],
                    positive=item.get("context", item["answer"]),
                    metadata={"source": "qa_pairs"},
                )
            )
        return self

    def from_llm_generation(
        self, documents: list[str], llm_client, queries_per_doc: int = 3
    ) -> "TrainingDataPreparer":
        """
        Generate synthetic training pairs using an LLM.

        For each document, generate multiple queries that the document answers.
        """
        prompt = """Given this document, generate {n} diverse search queries that this document would answer.
Return as JSON array of strings.

Document: {doc}

Queries:"""

        for doc in documents:
            try:
                response = llm_client.generate(
                    prompt.format(n=queries_per_doc, doc=doc[:1000])
                )
                queries = json.loads(response)
                for query in queries:
                    self._pairs.append(
                        TrainingPair(
                            query=query,
                            positive=doc,
                            metadata={"source": "llm_synthetic"},
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to generate queries for doc: {e}")

        return self

    def build(self) -> TrainingDataset:
        logger.info(f"Built training dataset with {len(self._pairs)} pairs")
        return TrainingDataset(pairs=self._pairs)


# =============================================================================
# Hard Negative Mining
# =============================================================================

class HardNegativeMiner:
    """
    Mine hard negatives using the current embedding model.

    Hard negatives are documents that are similar to the query (high embedding similarity)
    but are NOT relevant. These are the most informative negatives for training.
    """

    def __init__(self, embed_fn, corpus_embeddings: np.ndarray, corpus_texts: list[str]):
        """
        Args:
            embed_fn: Function to embed texts.
            corpus_embeddings: Pre-computed embeddings for all documents.
            corpus_texts: Corresponding document texts.
        """
        self._embed_fn = embed_fn
        self._corpus_embeddings = corpus_embeddings  # (N, dim)
        self._corpus_texts = corpus_texts

    def mine(
        self,
        dataset: TrainingDataset,
        num_negatives: int = 5,
        min_rank: int = 5,
        max_rank: int = 100,
    ) -> TrainingDataset:
        """
        Add hard negatives to training pairs.

        Strategy: For each query, find documents ranked between min_rank and max_rank
        that are NOT in the positive set. These are "hard" because the model currently
        thinks they're relevant, but they're not.
        """
        logger.info(f"Mining hard negatives for {len(dataset.pairs)} pairs...")

        enriched_pairs = []
        for pair in dataset.pairs:
            query_embedding = self._embed_fn([pair.query])[0]
            query_vec = np.array(query_embedding)

            # Compute similarities
            similarities = self._corpus_embeddings @ query_vec
            ranked_indices = np.argsort(similarities)[::-1]

            # Get hard negatives (documents ranked min_rank to max_rank)
            hard_negs = []
            for idx in ranked_indices[min_rank:max_rank]:
                candidate = self._corpus_texts[idx]
                # Skip if it's the positive document
                if candidate == pair.positive:
                    continue
                hard_negs.append(candidate)
                if len(hard_negs) >= num_negatives:
                    break

            enriched_pairs.append(
                TrainingPair(
                    query=pair.query,
                    positive=pair.positive,
                    hard_negatives=hard_negs,
                    metadata={**pair.metadata, "negatives_mined": True},
                )
            )

        logger.info(f"Hard negative mining complete. Avg negatives per pair: "
                    f"{np.mean([len(p.hard_negatives) for p in enriched_pairs]):.1f}")
        return TrainingDataset(pairs=enriched_pairs, name=dataset.name + "_with_negatives")


# =============================================================================
# Fine-Tuning Engine
# =============================================================================

@dataclass
class FinetuneConfig:
    """Configuration for embedding fine-tuning."""
    base_model: str = "BAAI/bge-large-en-v1.5"
    output_dir: str = "./finetuned_model"
    epochs: int = 3
    batch_size: int = 32
    learning_rate: float = 2e-5
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    max_seq_length: int = 512
    loss_type: str = "mnrl"  # mnrl, infonce, triplet, cosine
    use_hard_negatives: bool = True
    evaluation_steps: int = 500
    save_steps: int = 1000
    fp16: bool = True
    gradient_accumulation_steps: int = 1
    matryoshka_dims: Optional[list[int]] = None  # [256, 512, 768, 1024]


class EmbeddingFinetuner:
    """
    Fine-tune embedding models using sentence-transformers.

    Supports:
    - Multiple Negatives Ranking Loss (MNRL)
    - InfoNCE loss
    - Triplet loss
    - Matryoshka Representation Learning
    """

    def __init__(self, config: FinetuneConfig):
        self.config = config
        self._model = None
        self._training_history: list[dict] = []

    def prepare_model(self):
        """Load base model for fine-tuning."""
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading base model: {self.config.base_model}")
        self._model = SentenceTransformer(self.config.base_model)
        self._model.max_seq_length = self.config.max_seq_length
        logger.info(f"Model loaded. Dimensions: {self._model.get_sentence_embedding_dimension()}")

    def train(self, train_data: TrainingDataset, val_data: Optional[TrainingDataset] = None):
        """
        Run fine-tuning.

        This creates the appropriate loss function and trains the model.
        """
        from sentence_transformers import InputExample, losses
        from sentence_transformers.evaluation import InformationRetrievalEvaluator
        from torch.utils.data import DataLoader

        if self._model is None:
            self.prepare_model()

        # Convert to InputExamples
        train_examples = self._make_examples(train_data)
        train_dataloader = DataLoader(
            train_examples, shuffle=True, batch_size=self.config.batch_size
        )

        # Create loss
        loss = self._create_loss()

        # Create evaluator
        evaluator = None
        if val_data:
            evaluator = self._create_evaluator(val_data)

        # Train
        logger.info(f"Starting training: {len(train_examples)} examples, {self.config.epochs} epochs")
        warmup_steps = int(
            len(train_dataloader) * self.config.epochs * self.config.warmup_ratio
        )

        self._model.fit(
            train_objectives=[(train_dataloader, loss)],
            epochs=self.config.epochs,
            warmup_steps=warmup_steps,
            evaluator=evaluator,
            evaluation_steps=self.config.evaluation_steps,
            output_path=self.config.output_dir,
            save_best_model=True,
            use_amp=self.config.fp16,
            optimizer_params={"lr": self.config.learning_rate},
            weight_decay=self.config.weight_decay,
        )

        logger.info(f"Training complete. Model saved to {self.config.output_dir}")

    def _make_examples(self, dataset: TrainingDataset) -> list:
        """Convert training pairs to sentence-transformers InputExamples."""
        from sentence_transformers import InputExample

        examples = []
        for pair in dataset.pairs:
            if self.config.use_hard_negatives and pair.hard_negatives:
                # With hard negatives: (query, positive, negative)
                for neg in pair.hard_negatives:
                    examples.append(InputExample(texts=[pair.query, pair.positive, neg]))
            else:
                # Pairs only: (query, positive)
                examples.append(InputExample(texts=[pair.query, pair.positive]))

        return examples

    def _create_loss(self):
        """Create the appropriate loss function."""
        from sentence_transformers import losses

        if self.config.loss_type == "mnrl":
            loss = losses.MultipleNegativesRankingLoss(self._model)
        elif self.config.loss_type == "triplet":
            loss = losses.TripletLoss(self._model)
        elif self.config.loss_type == "cosine":
            loss = losses.CosineSimilarityLoss(self._model)
        else:
            loss = losses.MultipleNegativesRankingLoss(self._model)

        # Wrap with Matryoshka loss if configured
        if self.config.matryoshka_dims:
            loss = losses.MatryoshkaLoss(
                self._model, loss, matryoshka_dims=self.config.matryoshka_dims
            )
            logger.info(f"Using Matryoshka loss with dims: {self.config.matryoshka_dims}")

        return loss

    def _create_evaluator(self, val_data: TrainingDataset):
        """Create IR evaluator for validation during training."""
        from sentence_transformers.evaluation import InformationRetrievalEvaluator

        queries = {}
        corpus = {}
        relevant_docs = {}

        for i, pair in enumerate(val_data.pairs):
            qid = f"q_{i}"
            did = f"d_{i}"
            queries[qid] = pair.query
            corpus[did] = pair.positive
            relevant_docs[qid] = {did: 1}

            # Add negatives to corpus
            for j, neg in enumerate(pair.hard_negatives):
                neg_id = f"d_{i}_neg_{j}"
                corpus[neg_id] = neg

        return InformationRetrievalEvaluator(
            queries=queries,
            corpus=corpus,
            relevant_docs=relevant_docs,
            name="val",
            mrr_at_k=[10],
            ndcg_at_k=[10],
            accuracy_at_k=[1, 5, 10],
        )

    def export_model(self, output_path: Optional[str] = None) -> str:
        """Export the fine-tuned model for serving."""
        path = output_path or self.config.output_dir
        if self._model:
            self._model.save(path)
        logger.info(f"Model exported to {path}")
        return path


# =============================================================================
# Before/After Comparison
# =============================================================================

class BeforeAfterComparison:
    """Compare base model vs fine-tuned model on evaluation data."""

    def __init__(self, base_model_name: str, finetuned_model_path: str):
        self._base_name = base_model_name
        self._finetuned_path = finetuned_model_path

    def compare(self, eval_pairs: list[TrainingPair], top_k: int = 10) -> dict:
        """
        Run comparison between base and fine-tuned model.

        Returns metrics for both models.
        """
        from sentence_transformers import SentenceTransformer

        logger.info("Loading models for comparison...")
        base_model = SentenceTransformer(self._base_name)
        tuned_model = SentenceTransformer(self._finetuned_path)

        # Embed all documents (positives + negatives from eval set)
        all_docs = []
        doc_to_idx = {}
        for pair in eval_pairs:
            if pair.positive not in doc_to_idx:
                doc_to_idx[pair.positive] = len(all_docs)
                all_docs.append(pair.positive)
            for neg in pair.hard_negatives:
                if neg not in doc_to_idx:
                    doc_to_idx[neg] = len(all_docs)
                    all_docs.append(neg)

        logger.info(f"Embedding {len(all_docs)} documents with both models...")
        base_doc_embs = base_model.encode(all_docs, normalize_embeddings=True)
        tuned_doc_embs = tuned_model.encode(all_docs, normalize_embeddings=True)

        # Evaluate
        base_mrr_scores = []
        tuned_mrr_scores = []

        for pair in eval_pairs:
            query = pair.query
            positive_idx = doc_to_idx[pair.positive]

            # Base model
            base_query_emb = base_model.encode([query], normalize_embeddings=True)[0]
            base_sims = base_doc_embs @ base_query_emb
            base_rank = np.argsort(base_sims)[::-1]
            base_pos_rank = np.where(base_rank == positive_idx)[0][0] + 1
            base_mrr_scores.append(1.0 / base_pos_rank)

            # Fine-tuned model
            tuned_query_emb = tuned_model.encode([query], normalize_embeddings=True)[0]
            tuned_sims = tuned_doc_embs @ tuned_query_emb
            tuned_rank = np.argsort(tuned_sims)[::-1]
            tuned_pos_rank = np.where(tuned_rank == positive_idx)[0][0] + 1
            tuned_mrr_scores.append(1.0 / tuned_pos_rank)

        results = {
            "base_model": {
                "name": self._base_name,
                "mrr": float(np.mean(base_mrr_scores)),
                "recall_at_1": float(np.mean([1 if s == 1.0 else 0 for s in base_mrr_scores])),
            },
            "finetuned_model": {
                "path": self._finetuned_path,
                "mrr": float(np.mean(tuned_mrr_scores)),
                "recall_at_1": float(np.mean([1 if s == 1.0 else 0 for s in tuned_mrr_scores])),
            },
            "improvement": {
                "mrr_delta": float(np.mean(tuned_mrr_scores) - np.mean(base_mrr_scores)),
                "mrr_pct_improvement": float(
                    (np.mean(tuned_mrr_scores) - np.mean(base_mrr_scores))
                    / max(np.mean(base_mrr_scores), 0.001) * 100
                ),
            },
            "num_eval_pairs": len(eval_pairs),
        }

        logger.info(f"Base MRR: {results['base_model']['mrr']:.4f}")
        logger.info(f"Tuned MRR: {results['finetuned_model']['mrr']:.4f}")
        logger.info(f"Improvement: {results['improvement']['mrr_pct_improvement']:.1f}%")

        return results


# =============================================================================
# Domain Adaptation Strategies
# =============================================================================

class DomainAdaptationStrategy:
    """
    Strategies for adapting embeddings to specific domains.

    Approaches (in order of complexity):
    1. Prefix-based (add "query: " or "passage: " - no training needed)
    2. Fine-tune last N layers only (cheaper, less catastrophic forgetting)
    3. Full fine-tune with domain data
    4. Continue pre-training on domain corpus, then fine-tune
    """

    @staticmethod
    def strategy_prefix_tuning(model_name: str, query_prefix: str, doc_prefix: str) -> dict:
        """Strategy 1: Use input prefixes (no training)."""
        return {
            "strategy": "prefix_tuning",
            "description": "Add task-specific prefixes to inputs. No training required.",
            "model": model_name,
            "query_template": f"{query_prefix}{{query}}",
            "doc_template": f"{doc_prefix}{{document}}",
            "example_models": ["intfloat/e5-large-v2", "BAAI/bge-large-en-v1.5"],
            "effort": "none",
            "expected_improvement": "0-5%",
        }

    @staticmethod
    def strategy_last_layers(
        base_model: str, freeze_layers: int, train_data_size: int
    ) -> dict:
        """Strategy 2: Fine-tune only last N layers."""
        return {
            "strategy": "last_layer_finetune",
            "description": "Freeze early layers, fine-tune last layers only.",
            "base_model": base_model,
            "freeze_layers": freeze_layers,
            "trainable_params_pct": f"~{100 // (freeze_layers + 1)}%",
            "min_data_needed": 1000,
            "your_data_size": train_data_size,
            "sufficient_data": train_data_size >= 1000,
            "effort": "low",
            "expected_improvement": "5-10%",
            "risk_of_forgetting": "low",
        }

    @staticmethod
    def strategy_full_finetune(base_model: str, train_data_size: int) -> dict:
        """Strategy 3: Full fine-tuning."""
        return {
            "strategy": "full_finetune",
            "description": "Fine-tune all model parameters with contrastive learning.",
            "base_model": base_model,
            "min_data_needed": 10000,
            "your_data_size": train_data_size,
            "sufficient_data": train_data_size >= 10000,
            "effort": "medium",
            "expected_improvement": "10-20%",
            "risk_of_forgetting": "medium",
            "mitigation": "Use regularization, keep learning rate low, evaluate on general benchmarks",
        }

    @staticmethod
    def strategy_continued_pretraining(
        base_model: str, domain_corpus_size: int, train_data_size: int
    ) -> dict:
        """Strategy 4: Continue pre-training + fine-tuning."""
        return {
            "strategy": "continued_pretraining",
            "description": "First do unsupervised pre-training on domain text, then supervised fine-tuning.",
            "base_model": base_model,
            "phase_1": {
                "type": "masked_language_modeling",
                "data": "unlabeled domain corpus",
                "corpus_size": domain_corpus_size,
                "min_corpus": 100000,
            },
            "phase_2": {
                "type": "contrastive_finetuning",
                "data": "labeled query-document pairs",
                "data_size": train_data_size,
            },
            "effort": "high",
            "expected_improvement": "15-30%",
            "risk_of_forgetting": "high",
            "best_for": "highly specialized domains (medical, legal, scientific)",
        }

    @classmethod
    def recommend(cls, domain: str, labeled_pairs: int, unlabeled_docs: int) -> dict:
        """Recommend the best strategy based on available resources."""
        if labeled_pairs < 100:
            return cls.strategy_prefix_tuning(
                "BAAI/bge-large-en-v1.5", "Represent this query: ", "Represent this document: "
            )
        elif labeled_pairs < 5000:
            return cls.strategy_last_layers("BAAI/bge-large-en-v1.5", freeze_layers=20, train_data_size=labeled_pairs)
        elif labeled_pairs < 50000 or unlabeled_docs < 100000:
            return cls.strategy_full_finetune("BAAI/bge-large-en-v1.5", labeled_pairs)
        else:
            return cls.strategy_continued_pretraining(
                "BAAI/bge-large-en-v1.5", unlabeled_docs, labeled_pairs
            )


# =============================================================================
# Example Usage
# =============================================================================

def example_fine_tuning_workflow():
    """Complete fine-tuning workflow example."""

    # 1. Prepare training data
    preparer = TrainingDataPreparer()
    preparer.from_query_clicks([
        {
            "query": "how to handle database timeouts",
            "clicked_doc": "Database connection pools should have timeout...",
            "shown_docs": [
                "Database connection pools should have timeout...",
                "Database indexing improves query performance...",
                "Timeout errors in distributed systems...",
            ],
        },
        {
            "query": "kubernetes pod restart policy",
            "clicked_doc": "RestartPolicy applies to all containers in a Pod...",
            "shown_docs": [
                "RestartPolicy applies to all containers in a Pod...",
                "Kubernetes deployment strategies include rolling...",
            ],
        },
    ])

    dataset = preparer.build()
    train_data, val_data = dataset.split(train_ratio=0.9)

    print(f"Training pairs: {train_data.size}")
    print(f"Validation pairs: {val_data.size}")

    # 2. Get strategy recommendation
    strategy = DomainAdaptationStrategy.recommend(
        domain="devops", labeled_pairs=train_data.size, unlabeled_docs=1000
    )
    print(f"\nRecommended strategy: {strategy['strategy']}")
    print(f"Expected improvement: {strategy.get('expected_improvement', 'N/A')}")

    # 3. Configure fine-tuning
    config = FinetuneConfig(
        base_model="BAAI/bge-large-en-v1.5",
        output_dir="./models/finetuned-devops-embedding",
        epochs=3,
        batch_size=32,
        learning_rate=2e-5,
        loss_type="mnrl",
        use_hard_negatives=True,
        matryoshka_dims=[256, 512, 768, 1024],
    )

    # 4. Fine-tune (would require GPU in practice)
    # finetuner = EmbeddingFinetuner(config)
    # finetuner.train(train_data, val_data)
    # finetuner.export_model()

    # 5. Compare before/after
    # comparison = BeforeAfterComparison("BAAI/bge-large-en-v1.5", config.output_dir)
    # results = comparison.compare(val_data.pairs)
    # print(json.dumps(results, indent=2))

    print("\n[Fine-tuning would run here with GPU. See config above.]")
    print(f"Model would be saved to: {config.output_dir}")


if __name__ == "__main__":
    example_fine_tuning_workflow()
