"""
Multi-Vector Search: Parent-Child Hierarchical Retrieval

Demonstrates how embedding documents at multiple granularities
(section summaries + individual chunks) improves search precision.
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass, field


# --- Data Models ---

@dataclass
class Chunk:
    id: str
    parent_id: str
    text: str
    position: int  # Position within parent


@dataclass
class Section:
    id: str
    title: str
    summary: str
    chunks: List[Chunk] = field(default_factory=list)


# --- Simulated Embeddings ---

SEMANTIC_CLUSTERS = {
    "ml": ["machine", "learning", "model", "training", "algorithm", "prediction", "classification"],
    "dl": ["neural", "network", "deep", "layer", "activation", "backpropagation", "gradient"],
    "nlp": ["language", "text", "token", "embedding", "transformer", "attention", "bert"],
    "infra": ["kubernetes", "docker", "container", "deploy", "cluster", "pod", "service"],
    "db": ["database", "query", "index", "table", "sql", "nosql", "schema"],
    "acme": ["monitoring", "logging", "metrics", "alert", "dashboard", "trace", "observability"],
}


def embed_text(text: str, dim: int = 128) -> np.ndarray:
    """Create a simulated embedding with semantic clustering."""
    np.random.seed(hash(text) % 2**31)
    vec = np.random.randn(dim) * 0.3
    
    words = set(text.lower().split())
    
    for cluster_idx, (cluster_name, keywords) in enumerate(SEMANTIC_CLUSTERS.items()):
        overlap = len(words & set(keywords))
        if overlap > 0:
            # Add strong signal in cluster-specific dimensions
            start_dim = cluster_idx * 20
            for d in range(start_dim, min(start_dim + 20, dim)):
                vec[d] += overlap * 0.8
    
    # Normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


# --- Document Corpus ---

def create_corpus() -> List[Section]:
    """Create a multi-section document corpus."""
    sections = [
        Section(
            id="sec_ml_basics",
            title="Machine Learning Fundamentals",
            summary="Introduction to machine learning algorithms including supervised and unsupervised learning approaches",
            chunks=[
                Chunk("ch_ml_1", "sec_ml_basics", "supervised learning uses labeled data for training classification and regression models", 0),
                Chunk("ch_ml_2", "sec_ml_basics", "unsupervised learning discovers patterns in data without labels using clustering", 1),
                Chunk("ch_ml_3", "sec_ml_basics", "model evaluation uses metrics like accuracy precision recall and f1 score", 2),
                Chunk("ch_ml_4", "sec_ml_basics", "feature engineering transforms raw data into meaningful input for algorithms", 3),
            ]
        ),
        Section(
            id="sec_deep_learning",
            title="Deep Learning Architectures",
            summary="Deep neural network architectures including CNNs RNNs and transformers for complex pattern recognition",
            chunks=[
                Chunk("ch_dl_1", "sec_deep_learning", "convolutional neural networks use filters for image classification tasks", 0),
                Chunk("ch_dl_2", "sec_deep_learning", "recurrent neural networks process sequential data with hidden state memory", 1),
                Chunk("ch_dl_3", "sec_deep_learning", "transformer architecture uses self attention mechanism for parallel processing", 2),
                Chunk("ch_dl_4", "sec_deep_learning", "gradient descent optimization with backpropagation updates network weights", 3),
                Chunk("ch_dl_5", "sec_deep_learning", "batch normalization and dropout prevent overfitting in deep networks", 4),
            ]
        ),
        Section(
            id="sec_nlp",
            title="Natural Language Processing",
            summary="NLP techniques for text understanding including embeddings tokenization and language models",
            chunks=[
                Chunk("ch_nlp_1", "sec_nlp", "word embeddings map text tokens to dense vector representations", 0),
                Chunk("ch_nlp_2", "sec_nlp", "tokenization breaks text into subword units for language model input", 1),
                Chunk("ch_nlp_3", "sec_nlp", "bert uses masked language modeling for bidirectional text understanding", 2),
                Chunk("ch_nlp_4", "sec_nlp", "attention mechanism computes relevance weights between all token pairs", 3),
                Chunk("ch_nlp_5", "sec_nlp", "fine tuning adapts pretrained language models to specific downstream tasks", 4),
            ]
        ),
        Section(
            id="sec_kubernetes",
            title="Kubernetes Operations",
            summary="Container orchestration with Kubernetes including deployment scaling and service management",
            chunks=[
                Chunk("ch_k8s_1", "sec_kubernetes", "pods are the smallest deployable units in kubernetes cluster", 0),
                Chunk("ch_k8s_2", "sec_kubernetes", "deployment controllers manage pod replicas and rolling updates", 1),
                Chunk("ch_k8s_3", "sec_kubernetes", "services provide stable network endpoints for pod discovery", 2),
                Chunk("ch_k8s_4", "sec_kubernetes", "horizontal pod autoscaler adjusts replicas based on cpu memory metrics", 3),
                Chunk("ch_k8s_5", "sec_kubernetes", "ingress routes external traffic to internal kubernetes services", 4),
            ]
        ),
        Section(
            id="sec_databases",
            title="Database Design",
            summary="Database design patterns including SQL NoSQL indexing and query optimization strategies",
            chunks=[
                Chunk("ch_db_1", "sec_databases", "relational database schema design with normalization reduces data redundancy", 0),
                Chunk("ch_db_2", "sec_databases", "index structures btree and hash improve query lookup performance", 1),
                Chunk("ch_db_3", "sec_databases", "nosql databases like mongodb store documents with flexible schema", 2),
                Chunk("ch_db_4", "sec_databases", "query optimization involves analyzing execution plans and adding indexes", 3),
                Chunk("ch_db_5", "sec_databases", "database replication provides high availability and read scaling", 4),
            ]
        ),
        Section(
            id="sec_monitoring",
            title="Observability and Monitoring",
            summary="System monitoring with metrics logging distributed tracing and alerting dashboards",
            chunks=[
                Chunk("ch_mon_1", "sec_monitoring", "prometheus collects time series metrics from application endpoints", 0),
                Chunk("ch_mon_2", "sec_monitoring", "distributed tracing follows requests across microservice boundaries", 1),
                Chunk("ch_mon_3", "sec_monitoring", "structured logging with correlation ids enables request tracking", 2),
                Chunk("ch_mon_4", "sec_monitoring", "alerting rules trigger notifications based on metric threshold breaches", 3),
                Chunk("ch_mon_5", "sec_monitoring", "grafana dashboards visualize system health and performance metrics", 4),
            ]
        ),
    ]
    return sections


# --- Search Implementations ---

class FlatSearch:
    """Standard flat search across all chunks."""
    
    def __init__(self, sections: List[Section]):
        self.chunks: List[Chunk] = []
        self.chunk_vectors: List[np.ndarray] = []
        
        for section in sections:
            for chunk in section.chunks:
                self.chunks.append(chunk)
                self.chunk_vectors.append(embed_text(chunk.text))
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        query_vec = embed_text(query)
        scores = []
        for i, (chunk, vec) in enumerate(zip(self.chunks, self.chunk_vectors)):
            sim = cosine_similarity(query_vec, vec)
            scores.append((chunk, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class HierarchicalSearch:
    """Parent-child hierarchical search."""
    
    def __init__(self, sections: List[Section]):
        self.sections = sections
        self.parent_vectors: Dict[str, np.ndarray] = {}
        self.child_vectors: Dict[str, np.ndarray] = {}
        self.section_map: Dict[str, Section] = {}
        
        for section in sections:
            # Parent: embed the summary
            self.parent_vectors[section.id] = embed_text(section.summary)
            self.section_map[section.id] = section
            
            # Children: embed each chunk
            for chunk in section.chunks:
                self.child_vectors[chunk.id] = embed_text(chunk.text)
    
    def search(self, query: str, top_k_parents: int = 3, top_k_children: int = 2) -> List[Tuple[Chunk, float, str]]:
        """
        Two-stage search:
        1. Find top-K parent sections
        2. Within each, find top-K children
        
        Returns: [(chunk, score, parent_title), ...]
        """
        query_vec = embed_text(query)
        
        # Stage 1: Parent search
        parent_scores = []
        for sec_id, vec in self.parent_vectors.items():
            sim = cosine_similarity(query_vec, vec)
            parent_scores.append((sec_id, sim))
        parent_scores.sort(key=lambda x: x[1], reverse=True)
        top_parents = parent_scores[:top_k_parents]
        
        # Stage 2: Child search within top parents
        results = []
        for sec_id, parent_score in top_parents:
            section = self.section_map[sec_id]
            child_scores = []
            for chunk in section.chunks:
                vec = self.child_vectors[chunk.id]
                sim = cosine_similarity(query_vec, vec)
                child_scores.append((chunk, sim))
            child_scores.sort(key=lambda x: x[1], reverse=True)
            
            for chunk, child_score in child_scores[:top_k_children]:
                # Combined score: weighted parent + child
                combined = 0.3 * parent_score + 0.7 * child_score
                results.append((chunk, combined, section.title))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k_parents * top_k_children]


# --- Main Demo ---

def main():
    print("=" * 70)
    print("Multi-Vector Search: Flat vs Hierarchical (Parent-Child)")
    print("=" * 70)
    
    # Create corpus
    sections = create_corpus()
    
    total_chunks = sum(len(s.chunks) for s in sections)
    print(f"\n  Corpus: {len(sections)} sections, {total_chunks} total chunks")
    print(f"\n  Sections:")
    for s in sections:
        print(f"    [{s.id}] {s.title} ({len(s.chunks)} chunks)")
    
    # Build indexes
    flat_search = FlatSearch(sections)
    hierarchical_search = HierarchicalSearch(sections)
    
    # Test queries
    queries = [
        ("attention mechanism transformer architecture", "NLP + Deep Learning overlap"),
        ("kubernetes pod scaling deployment", "Infrastructure specific"),
        ("database index query performance", "Database specific"),
        ("neural network training gradient", "Deep learning specific"),
        ("text embedding token vector representation", "NLP specific"),
        ("monitoring metrics alerting dashboard", "Observability specific"),
    ]
    
    print("\n\n" + "=" * 70)
    print("SEARCH COMPARISON")
    print("=" * 70)
    
    flat_precision_scores = []
    hier_precision_scores = []
    
    for query, description in queries:
        print(f"\n{'─' * 70}")
        print(f"Query: \"{query}\"")
        print(f"Type:  {description}")
        print(f"{'─' * 70}")
        
        # Flat search
        flat_results = flat_search.search(query, top_k=5)
        
        # Hierarchical search
        hier_results = hierarchical_search.search(query, top_k_parents=2, top_k_children=3)
        
        print(f"\n  FLAT SEARCH (all {total_chunks} chunks equally):")
        flat_sections = set()
        for chunk, score in flat_results:
            section_name = next(s.title for s in sections if s.id == chunk.parent_id)
            flat_sections.add(chunk.parent_id)
            print(f"    score={score:.3f} [{chunk.parent_id}] {chunk.text[:55]}...")
        
        print(f"\n  HIERARCHICAL SEARCH (parents first → children within):")
        hier_sections = set()
        for chunk, score, parent_title in hier_results[:5]:
            hier_sections.add(chunk.parent_id)
            print(f"    score={score:.3f} [{chunk.parent_id}] {chunk.text[:55]}...")
        
        # Measure: how many unique sections in results?
        print(f"\n  Sections in results: flat={len(flat_sections)}, hierarchical={len(hier_sections)}")
        
        # For focused queries, fewer sections = more precise
        # (results are concentrated in the relevant section)
        flat_precision_scores.append(1.0 / len(flat_sections) if flat_sections else 0)
        hier_precision_scores.append(1.0 / len(hier_sections) if hier_sections else 0)
    
    # --- Summary ---
    print("\n\n" + "=" * 70)
    print("SUMMARY: Flat vs Hierarchical Search")
    print("=" * 70)
    
    print(f"""
  ┌─────────────────────────────────────────────────────────────┐
  │ Architecture Comparison                                     │
  ├───────────────────┬──────────────────┬──────────────────────┤
  │ Metric            │ Flat Search      │ Hierarchical Search  │
  ├───────────────────┼──────────────────┼──────────────────────┤
  │ Vectors stored    │ {total_chunks:<16} │ {total_chunks + len(sections):<20} │
  │ Search space      │ All {total_chunks} chunks   │ {len(sections)} parents → children │
  │ Avg focus score   │ {np.mean(flat_precision_scores):<16.3f} │ {np.mean(hier_precision_scores):<20.3f} │
  │ Storage overhead  │ 1x (baseline)    │ ~1.2x (+ parent vecs)│
  │ Latency           │ O(N)             │ O(P) + O(C/P)        │
  └───────────────────┴──────────────────┴──────────────────────┘

  Key observations:

  1. FOCUSED RESULTS: Hierarchical search concentrates results within
     the most relevant section, avoiding cross-section noise.

  2. CONTEXTUAL RELEVANCE: By filtering at the parent level first,
     child results come from contextually appropriate sections.

  3. SCALABILITY: For large corpora (1M+ chunks), searching 1000 
     parents then 50 children is much faster than searching 1M chunks.

  4. EXPLAINABILITY: Can show users "Found in section: {title}"
     which helps them understand why a result was returned.

  When to use hierarchical:
    - Documents have clear section structure
    - Users need passage-level results WITH document context
    - Corpus is large (parent filtering reduces search space)
    - Precision matters more than recall

  When flat is better:
    - Short documents (no meaningful hierarchy)
    - Maximum recall needed (don't want to miss anything)
    - Simple architecture preferred
""")


if __name__ == "__main__":
    main()
