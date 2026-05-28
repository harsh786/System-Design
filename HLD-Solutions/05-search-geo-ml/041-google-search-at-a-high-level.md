# Google Search - High Level Design

## 1. Problem Statement

Design a web search engine that crawls billions of web pages, indexes their content, and serves relevant search results in milliseconds. The system must handle 8.5 billion searches per day with sub-second latency while ranking results by relevance using PageRank, ML features, and user signals.

---

## 2. Functional Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| FR1 | Web Search | Users enter text queries, receive ranked list of relevant web pages |
| FR2 | Spell Correction | Suggest corrected queries for misspelled terms |
| FR3 | Knowledge Graph | Display structured entity information (people, places, facts) |
| FR4 | Featured Snippets | Extract and display direct answers from pages |
| FR5 | Image/Video/News | Blended results from multiple verticals |
| FR6 | Autocomplete | Real-time query suggestions as user types |
| FR7 | Ads Integration | Display relevant sponsored results alongside organic |
| FR8 | Personalization | Tailor results based on user history, location, language |
| FR9 | Safe Search | Filter explicit/harmful content |
| FR10 | Pagination | Navigate through pages of results |

## 3. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Latency | p50 < 200ms, p99 < 500ms for query response |
| NFR2 | Availability | 99.999% uptime (< 5.26 min downtime/year) |
| NFR3 | Throughput | 100K QPS sustained, 300K QPS peak |
| NFR4 | Freshness | Breaking news indexed within minutes, regular pages within hours |
| NFR5 | Scalability | Handle 100B+ indexed pages |
| NFR6 | Relevance | High precision and recall in top-10 results |
| NFR7 | Global | Serve users in 200+ countries with localized results |
| NFR8 | Consistency | Index updates propagate within bounded time |

---

## 4. Capacity Estimation

### Traffic
```
Daily searches:           8.5 billion
Searches per second:      8.5B / 86400 ≈ 100,000 QPS
Peak QPS (3x):            300,000 QPS
Average query length:     3-4 words ≈ 25 bytes
Results per query:        10 results × ~2KB snippet = 20KB response
```

### Storage
```
Indexed pages:            100 billion pages
Average page size:        50KB (compressed HTML)
Raw storage:              100B × 50KB = 5 exabytes (raw)
Compressed index:         ~500 petabytes
Inverted index size:      ~100 petabytes (posting lists + metadata)
PageRank scores:          100B × 8 bytes = 800GB
Document metadata:        100B × 500 bytes = 50TB
```

### Bandwidth
```
Inbound (queries):        100K × 25 bytes = 2.5 MB/s
Outbound (results):       100K × 20KB = 2 GB/s
Crawler bandwidth:        10B pages/month × 50KB = 20 GB/s sustained
```

### Infrastructure
```
Serving clusters:         ~30 data centers globally
Index shards:             100,000+ shards
Serving machines:         ~1 million servers total
Cache hit ratio:          ~30% for popular queries
```

---

## 5. Data Modeling

### Forward Index (Document Store)
```sql
CREATE TABLE documents (
    doc_id          BIGINT PRIMARY KEY,      -- Unique document identifier
    url             TEXT NOT NULL,            -- Canonical URL
    title           TEXT,                     -- Page title
    content_hash    CHAR(64),                -- SHA-256 of content for dedup
    last_crawled    TIMESTAMP,               -- Last crawl time
    last_modified   TIMESTAMP,               -- Page last-modified header
    language        CHAR(5),                 -- ISO language code
    page_rank       FLOAT,                   -- Precomputed PageRank score
    spam_score      FLOAT,                   -- Spam classification score
    domain_authority FLOAT,                  -- Domain-level trust score
    word_count      INT,                     -- Total word count
    content_type    VARCHAR(50),             -- text/html, pdf, etc.
    indexed_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE document_metadata (
    doc_id          BIGINT REFERENCES documents(doc_id),
    meta_key        VARCHAR(100),            -- og:title, description, etc.
    meta_value      TEXT,
    PRIMARY KEY (doc_id, meta_key)
);
```

### Inverted Index Schema
```
Term → PostingList

PostingList = {
    term: string,
    document_frequency: int,           -- Number of docs containing term
    postings: [Posting],               -- Sorted by doc_id
}

Posting = {
    doc_id: int64,
    term_frequency: int,               -- TF in this document
    positions: [int],                  -- Word positions for phrase queries
    field_flags: byte,                 -- Bit flags: title|body|url|anchor
}
```

### Knowledge Graph Entity
```json
{
    "entity_id": "Q76",
    "name": "Barack Obama",
    "type": ["Person", "Politician", "Author"],
    "attributes": {
        "born": "1961-08-04",
        "birthplace": "Honolulu, Hawaii",
        "spouse": "Q13133",
        "occupation": ["Politician", "Lawyer", "Author"]
    },
    "relationships": [
        {"predicate": "president_of", "object": "Q30", "start": 2009, "end": 2017}
    ],
    "sources": ["wikipedia", "freebase"],
    "description": "44th President of the United States"
}
```

### Query Log
```sql
CREATE TABLE query_logs (
    query_id        UUID PRIMARY KEY,
    user_id         BIGINT,
    query_text      TEXT NOT NULL,
    timestamp       TIMESTAMP NOT NULL,
    location        GEOGRAPHY(POINT),
    language        CHAR(5),
    device_type     VARCHAR(20),
    results_clicked JSONB,               -- [{position, doc_id, dwell_time}]
    session_id      UUID
);
```

---

## 6. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           GOOGLE SEARCH ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │   User/App   │
                         └──────┬───────┘
                                │ HTTPS
                         ┌──────▼───────┐
                         │   Global     │
                         │   CDN/LB     │
                         │  (Anycast)   │
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   Web Serving Layer    │
                    │  (Query Processing)    │
                    └───────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
    ┌─────▼─────┐       ┌──────▼──────┐      ┌──────▼──────┐
    │   Spell   │       │   Query     │      │   Ads       │
    │ Correction│       │  Expansion  │      │  Server     │
    └─────┬─────┘       └──────┬──────┘      └──────┬──────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Index Serving Layer  │
                    │  (Distributed Search)  │
                    ├───────────────────────┤
                    │  Shard 1 │ Shard 2 │..│
                    │  Shard N │ Replica  │  │
                    └───────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
    ┌─────▼─────┐       ┌──────▼──────┐      ┌──────▼──────┐
    │  Ranking  │       │  Knowledge  │      │  Featured   │
    │  (ML +    │       │    Graph    │      │  Snippets   │
    │ PageRank) │       │             │      │  Extractor  │
    └───────────┘       └─────────────┘      └─────────────┘

═══════════════════════ OFFLINE PIPELINE ══════════════════════════

    ┌───────────┐       ┌─────────────┐      ┌─────────────┐
    │   Web     │──────▶│   Content   │─────▶│   Index     │
    │  Crawler  │       │  Processor  │      │  Builder    │
    └───────────┘       └─────────────┘      └──────┬──────┘
         │                                          │
         │              ┌─────────────┐             │
         └─────────────▶│  URL        │             │
                        │  Frontier   │             ▼
                        └─────────────┘      ┌─────────────┐
                                             │  PageRank   │
    ┌───────────┐       ┌─────────────┐      │  Computer   │
    │  Spam     │──────▶│  Quality    │      └─────────────┘
    │  Detector │       │  Scorer     │
    └───────────┘       └─────────────┘
```

### Component Descriptions

| Component | Responsibility |
|-----------|---------------|
| Global CDN/LB | Route requests to nearest data center, SSL termination |
| Web Serving Layer | Parse query, orchestrate search pipeline, assemble SERP |
| Spell Correction | Suggest corrections using n-gram models + edit distance |
| Query Expansion | Add synonyms, related terms, handle acronyms |
| Index Serving | Distributed inverted index lookup, return matching docs |
| Ranking | Score documents using PageRank + 200+ ML features |
| Knowledge Graph | Entity resolution, structured data for info panels |
| Featured Snippets | Extract passage-level answers for direct display |
| Web Crawler | Discover and fetch web pages continuously |
| Content Processor | Parse HTML, extract text/links/metadata, language detect |
| Index Builder | Create inverted index segments, build skip lists |
| PageRank Computer | Iterative link-graph computation (MapReduce) |

---

## 7. Low-Level Design (LLD) - APIs

### Search API
```
GET /search?q={query}&start={offset}&num={count}&lr={language}&gl={country}

Headers:
  Authorization: Bearer <token>
  X-User-Location: lat,lng
  X-Device-Type: mobile|desktop
  Accept-Language: en-US

Response 200:
{
    "query": "machine learning basics",
    "corrected_query": null,
    "total_results": 2450000000,
    "search_time_ms": 180,
    "knowledge_panel": {
        "entity": "Machine Learning",
        "description": "Machine learning is a subset of AI...",
        "image_url": "https://...",
        "attributes": {...}
    },
    "featured_snippet": {
        "text": "Machine learning is the study of...",
        "source_url": "https://...",
        "source_title": "ML Guide"
    },
    "organic_results": [
        {
            "position": 1,
            "title": "Machine Learning - Stanford CS229",
            "url": "https://cs229.stanford.edu/",
            "display_url": "cs229.stanford.edu",
            "snippet": "Stanford's introductory course on machine learning...",
            "cached_url": "https://cache.google.com/...",
            "date": "2024-01-15",
            "sitelinks": [...]
        }
    ],
    "related_searches": [
        "machine learning tutorial",
        "machine learning vs deep learning"
    ],
    "ads": [
        {
            "position": "top",
            "title": "Learn ML Online - Coursera",
            "url": "https://coursera.org/ml",
            "ad_text": "Enroll in Stanford's ML course..."
        }
    ]
}
```

### Suggest API (Autocomplete)
```
GET /complete?q={prefix}&client=chrome&hl=en

Response 200:
["machine le", ["machine learning", "machine learning course", "machine learning python"]]
```

### Internal: Index Lookup (Between components)
```protobuf
service IndexService {
    rpc Search(SearchRequest) returns (SearchResponse);
}

message SearchRequest {
    repeated string terms = 1;
    QueryType type = 2;           // AND, OR, PHRASE
    int32 max_results = 3;
    repeated Filter filters = 4;   // language, date range, site
}

message SearchResponse {
    repeated ScoredDocument docs = 1;
    int64 total_matches = 2;
    int32 shard_id = 3;
}

message ScoredDocument {
    int64 doc_id = 1;
    float relevance_score = 2;
    repeated int32 term_positions = 3;
    float page_rank = 4;
}
```

---

## 8. Deep Dive: Inverted Index Structure

### Posting List with TF-IDF

```python
class PostingList:
    """
    Inverted index posting list with skip pointers for fast intersection.
    
    Structure on disk:
    [DocFreq][SkipInterval][SkipList][PostingBlocks]
    
    Each posting: (doc_id_delta, term_freq, [positions])
    Delta-encoded doc_ids for compression.
    """
    
    def __init__(self, term: str):
        self.term = term
        self.document_frequency = 0
        self.postings = []          # List of (doc_id, tf, positions)
        self.skip_list = []         # Skip pointers for fast intersection
        self.skip_interval = 128    # Skip every 128 postings
    
    def add_posting(self, doc_id: int, positions: list[int]):
        tf = len(positions)
        self.postings.append((doc_id, tf, positions))
        self.document_frequency += 1
        
        # Build skip pointer every skip_interval postings
        if self.document_frequency % self.skip_interval == 0:
            self.skip_list.append((doc_id, len(self.postings) - 1))
    
    def compute_tfidf(self, doc_id: int, total_docs: int, doc_length: int, avg_doc_length: float) -> float:
        """BM25 scoring (evolved TF-IDF)"""
        k1 = 1.2
        b = 0.75
        
        # Find posting for this doc
        posting = self._find_posting(doc_id)
        if not posting:
            return 0.0
        
        _, tf, _ = posting
        
        # IDF component
        idf = math.log((total_docs - self.document_frequency + 0.5) / 
                       (self.document_frequency + 0.5) + 1)
        
        # TF component with length normalization
        tf_normalized = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_length / avg_doc_length))
        
        return idf * tf_normalized
    
    def intersect(self, other: 'PostingList') -> list[int]:
        """
        Intersect two posting lists using skip pointers.
        Time complexity: O(n + m) with skipping reducing constant.
        """
        result = []
        i, j = 0, 0
        
        while i < len(self.postings) and j < len(other.postings):
            doc_a = self.postings[i][0]
            doc_b = other.postings[j][0]
            
            if doc_a == doc_b:
                result.append(doc_a)
                i += 1
                j += 1
            elif doc_a < doc_b:
                # Try to skip ahead in self
                skip_to = self._skip_to(doc_b, i)
                i = skip_to if skip_to > i else i + 1
            else:
                # Try to skip ahead in other
                skip_to = other._skip_to(doc_a, j)
                j = skip_to if skip_to > j else j + 1
        
        return result
    
    def _skip_to(self, target_doc: int, current_pos: int) -> int:
        """Binary search skip list for target doc_id"""
        for skip_doc, skip_pos in self.skip_list:
            if skip_doc >= target_doc:
                return skip_pos
            if skip_pos <= current_pos:
                continue
        return current_pos
    
    def compress_postings(self) -> bytes:
        """
        Variable-byte encoding of delta-encoded doc_ids.
        Achieves 2-4x compression over raw int storage.
        """
        encoded = bytearray()
        prev_doc_id = 0
        
        for doc_id, tf, positions in self.postings:
            # Delta encode doc_id
            delta = doc_id - prev_doc_id
            encoded.extend(self._vbyte_encode(delta))
            encoded.extend(self._vbyte_encode(tf))
            
            # Delta encode positions
            prev_pos = 0
            for pos in positions:
                encoded.extend(self._vbyte_encode(pos - prev_pos))
                prev_pos = pos
            
            prev_doc_id = doc_id
        
        return bytes(encoded)
    
    @staticmethod
    def _vbyte_encode(n: int) -> bytes:
        """Variable byte encoding: 7 bits payload + 1 continuation bit"""
        result = bytearray()
        while n >= 128:
            result.append(n & 0x7F)
            n >>= 7
        result.append(n | 0x80)  # Set high bit on last byte
        return bytes(result)
```

### Skip List Visualization
```
Level 2:  [1] ─────────────────────────────────── [97] ──────────────── [201]
Level 1:  [1] ──────── [33] ──────── [65] ──────── [97] ──── [129] ──── [201]
Level 0:  [1][2][5][8][12]...[33][35][40]...[65][67]...[97][99]...[201]...

Skip interval = 32 documents per level-1 skip
Reduces intersection from O(n) to O(√n) in practice
```

---

## 9. Deep Dive: PageRank Algorithm

```python
import numpy as np
from scipy import sparse

class PageRankComputer:
    """
    Distributed PageRank computation using iterative power method.
    
    PR(A) = (1-d) + d * Σ(PR(T_i) / C(T_i))
    
    Where:
    - d = damping factor (0.85)
    - T_i = pages linking to A
    - C(T_i) = number of outbound links from T_i
    """
    
    def __init__(self, num_pages: int, damping: float = 0.85, 
                 convergence_threshold: float = 1e-8, max_iterations: int = 100):
        self.num_pages = num_pages
        self.damping = damping
        self.threshold = convergence_threshold
        self.max_iterations = max_iterations
    
    def compute_pagerank(self, link_graph: sparse.csr_matrix) -> np.ndarray:
        """
        Iterative PageRank on sparse adjacency matrix.
        
        Args:
            link_graph: CSR sparse matrix where link_graph[i][j] = 1 
                       means page i links to page j
        
        Returns:
            PageRank vector normalized to sum to 1
        """
        n = self.num_pages
        
        # Compute out-degree for each page
        out_degree = np.array(link_graph.sum(axis=1)).flatten()
        out_degree[out_degree == 0] = 1  # Handle dangling nodes
        
        # Create transition matrix: M[j][i] = 1/out_degree(i) if i→j
        # Normalize columns by out-degree
        inv_degree = sparse.diags(1.0 / out_degree)
        transition = (link_graph.T @ inv_degree).T  # Column-stochastic
        
        # Initialize uniform PageRank
        pr = np.ones(n) / n
        
        # Identify dangling nodes (no outlinks)
        dangling = (np.array(link_graph.sum(axis=1)).flatten() == 0)
        
        for iteration in range(self.max_iterations):
            prev_pr = pr.copy()
            
            # Handle dangling nodes: redistribute their rank uniformly
            dangling_sum = pr[dangling].sum()
            
            # Power iteration step
            pr = (1 - self.damping) / n + \
                 self.damping * (transition.T @ pr + dangling_sum / n)
            
            # Check convergence (L1 norm)
            diff = np.abs(pr - prev_pr).sum()
            if diff < self.threshold:
                print(f"Converged after {iteration + 1} iterations (diff={diff:.2e})")
                break
        
        # Normalize to sum to 1
        pr = pr / pr.sum()
        return pr
    
    def compute_distributed(self, partition_id: int, local_graph: sparse.csr_matrix,
                           remote_contributions: dict) -> np.ndarray:
        """
        Distributed PageRank for single partition.
        Each partition computes local PR and exchanges border node contributions.
        
        MapReduce approach:
        - Map: For each page, emit (target, PR(source)/out_degree(source))
        - Reduce: Sum contributions for each target page
        """
        n_local = local_graph.shape[0]
        local_pr = np.ones(n_local) / self.num_pages
        
        for iteration in range(self.max_iterations):
            # Local contribution
            out_degree = np.array(local_graph.sum(axis=1)).flatten()
            out_degree[out_degree == 0] = 1
            
            contributions = np.zeros(n_local)
            
            # Add local contributions
            for i in range(n_local):
                targets = local_graph[i].indices
                contrib = local_pr[i] / out_degree[i]
                for t in targets:
                    if t < n_local:  # Local target
                        contributions[t] += contrib
            
            # Add remote contributions (received from other partitions)
            for node_id, contrib in remote_contributions.items():
                if node_id < n_local:
                    contributions[node_id] += contrib
            
            local_pr = (1 - self.damping) / self.num_pages + \
                      self.damping * contributions
        
        return local_pr


class TopicSensitivePageRank:
    """
    Topic-Sensitive PageRank: precompute separate PR vectors
    for different topics (sports, science, entertainment, etc.)
    
    At query time, blend topic-specific PR vectors based on query topic.
    """
    
    def __init__(self, num_pages: int, num_topics: int = 16):
        self.num_pages = num_pages
        self.num_topics = num_topics
        self.topic_pageranks = {}  # topic_id → PR vector
    
    def compute_topic_pr(self, link_graph: sparse.csr_matrix, 
                         topic_id: int, topic_pages: set) -> np.ndarray:
        """
        Compute PageRank with teleportation biased toward topic pages.
        Instead of uniform random jump, jump to pages in the topic set.
        """
        n = self.num_pages
        pr = np.ones(n) / n
        damping = 0.85
        
        # Teleportation vector biased toward topic
        teleport = np.zeros(n)
        for page in topic_pages:
            teleport[page] = 1.0 / len(topic_pages)
        
        out_degree = np.array(link_graph.sum(axis=1)).flatten()
        out_degree[out_degree == 0] = 1
        
        for _ in range(100):
            transition_contrib = np.zeros(n)
            for i in range(n):
                targets = link_graph[i].indices
                contrib = pr[i] / out_degree[i]
                for t in targets:
                    transition_contrib[t] += contrib
            
            pr = (1 - damping) * teleport + damping * transition_contrib
        
        self.topic_pageranks[topic_id] = pr / pr.sum()
        return self.topic_pageranks[topic_id]
```

---

## 10. Deep Dive: Query Processing Pipeline

```python
class QueryProcessor:
    """
    Full query processing pipeline:
    Input → Tokenize → Spell Check → Expand → Search → Rank → Present
    """
    
    def __init__(self, index, ranker, knowledge_graph, spell_checker):
        self.index = index
        self.ranker = ranker
        self.kg = knowledge_graph
        self.spell_checker = spell_checker
    
    def process_query(self, raw_query: str, user_context: dict) -> SearchResults:
        """End-to-end query processing pipeline"""
        
        # Phase 1: Query Understanding
        parsed = self.parse_query(raw_query)
        corrected = self.spell_checker.correct(parsed)
        expanded = self.expand_query(corrected, user_context)
        
        # Phase 2: Retrieval (parallel fan-out to index shards)
        candidates = self.retrieve(expanded)
        
        # Phase 3: Ranking (multi-stage)
        ranked = self.rank(candidates, expanded, user_context)
        
        # Phase 4: Result Assembly
        results = self.assemble_results(ranked, raw_query)
        
        return results
    
    def parse_query(self, query: str) -> ParsedQuery:
        """
        Tokenize and analyze query structure.
        - Detect operators: site:, filetype:, intitle:, "exact phrase"
        - Identify query intent: navigational, informational, transactional
        - Language detection
        """
        tokens = self.tokenize(query)
        operators = self.extract_operators(tokens)
        intent = self.classify_intent(tokens)
        
        return ParsedQuery(
            original=query,
            tokens=tokens,
            operators=operators,
            intent=intent,
            language=self.detect_language(query)
        )
    
    def expand_query(self, query: ParsedQuery, context: dict) -> ExpandedQuery:
        """
        Query expansion strategies:
        1. Synonym expansion: "car" → "car OR automobile"
        2. Stemming: "running" → "run"
        3. Acronym expansion: "ML" → "machine learning"
        4. Location awareness: "restaurants" → "restaurants near {user_location}"
        5. Temporal: "election results" → "election results 2024"
        """
        expansions = []
        
        # Synonym ring lookup
        for token in query.tokens:
            synonyms = self.synonym_dict.get(token.text, [])
            if synonyms:
                expansions.append(SynonymExpansion(token, synonyms, boost=0.8))
        
        # Context-based expansion
        if query.intent == 'local':
            expansions.append(LocationExpansion(context.get('location')))
        
        return ExpandedQuery(query, expansions)
    
    def retrieve(self, query: ExpandedQuery) -> list:
        """
        Multi-tier retrieval:
        Tier 1: Exact match on primary terms (inverted index)
        Tier 2: Expanded terms with lower boost
        Tier 3: Semantic similarity (embedding-based ANN)
        
        Fan-out to N shards, merge results.
        """
        # Parallel shard queries
        shard_results = []
        for shard_id in self.get_target_shards(query):
            result = self.index.search_shard(
                shard_id=shard_id,
                terms=query.primary_terms,
                filters=query.operators,
                max_results=1000  # Top-K per shard
            )
            shard_results.append(result)
        
        # Merge results from all shards
        merged = self.merge_shard_results(shard_results)
        return merged[:10000]  # Top 10K candidates for ranking
    
    def rank(self, candidates: list, query: ExpandedQuery, context: dict) -> list:
        """
        Multi-stage ranking:
        Stage 1: Lightweight scoring (BM25 + PageRank) - 10K → 1K docs
        Stage 2: ML model (GBDT with 200+ features) - 1K → 100 docs
        Stage 3: Neural re-ranker (BERT-based) - 100 → final order
        """
        # Stage 1: BM25 + static scores
        scored = []
        for doc in candidates:
            bm25 = self.compute_bm25(doc, query)
            static_score = 0.3 * doc.page_rank + 0.1 * doc.domain_authority
            scored.append((doc, bm25 + static_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        top_1k = scored[:1000]
        
        # Stage 2: Feature-based ML ranking
        features = self.extract_features(top_1k, query, context)
        ml_scores = self.ranking_model.predict(features)
        
        reranked = sorted(zip(top_1k, ml_scores), key=lambda x: x[1], reverse=True)
        top_100 = reranked[:100]
        
        # Stage 3: Neural re-ranking (BERT cross-encoder)
        neural_scores = self.neural_ranker.score(query.original, 
                                                  [doc.snippet for doc, _ in top_100])
        
        final = sorted(zip(top_100, neural_scores), key=lambda x: x[1], reverse=True)
        return [doc for (doc, _), _ in final]


class RankingFeatures:
    """200+ features used in the ML ranking model"""
    
    FEATURES = {
        # Query-document relevance
        'bm25_title': 'BM25 score for title field',
        'bm25_body': 'BM25 score for body field',
        'bm25_anchor': 'BM25 score for anchor text',
        'bm25_url': 'BM25 score for URL tokens',
        'exact_match_title': 'Query exactly matches title',
        'phrase_match_body': 'Query appears as phrase in body',
        'term_coverage': 'Fraction of query terms found in doc',
        
        # Static quality signals
        'page_rank': 'PageRank score',
        'domain_authority': 'Domain-level trust/authority',
        'spam_score': 'Probability of being spam',
        'page_age_days': 'Days since page first indexed',
        'freshness_score': 'Recency of last modification',
        
        # User engagement signals
        'click_through_rate': 'Historical CTR for this query-doc pair',
        'avg_dwell_time': 'Average time users spend on page',
        'bounce_rate': 'Fraction of users who return immediately',
        'long_click_rate': 'Clicks with dwell > 30 seconds',
        
        # Document quality
        'word_count': 'Total words in document',
        'reading_level': 'Flesch-Kincaid readability',
        'has_structured_data': 'Page has schema.org markup',
        'mobile_friendly': 'Passes mobile-friendly test',
        'page_speed_score': 'Core Web Vitals score',
        'https': 'Uses HTTPS',
        
        # Query-specific
        'query_length': 'Number of terms in query',
        'query_intent': 'Navigational/informational/transactional',
        'is_trending': 'Query is currently trending',
    }
```

---

## 11. Component Deep Dive: Spell Correction

```python
class SpellCorrector:
    """
    Multi-strategy spell correction:
    1. Noisy channel model: P(correction|misspelling) ∝ P(misspelling|correction) × P(correction)
    2. N-gram language model for context
    3. Query log mining for common corrections
    """
    
    def __init__(self, vocab: set, bigram_model: dict, query_corrections: dict):
        self.vocab = vocab
        self.bigram_model = bigram_model
        self.query_corrections = query_corrections  # mined from query logs
    
    def correct(self, query: ParsedQuery) -> ParsedQuery:
        # First check query log corrections (highest confidence)
        normalized = query.original.lower().strip()
        if normalized in self.query_corrections:
            return self.query_corrections[normalized]
        
        # Per-token correction with context
        corrected_tokens = []
        for i, token in enumerate(query.tokens):
            if token.text in self.vocab:
                corrected_tokens.append(token)
                continue
            
            # Generate candidates within edit distance 2
            candidates = self.generate_candidates(token.text, max_edit_distance=2)
            
            # Score candidates using noisy channel
            best_candidate = None
            best_score = float('-inf')
            
            for candidate in candidates:
                # P(candidate) from unigram frequency
                prior = math.log(self.unigram_freq.get(candidate, 1e-10))
                
                # P(misspelling|candidate) from error model
                likelihood = self.error_model_score(token.text, candidate)
                
                # Context from bigram
                if i > 0:
                    prev_word = corrected_tokens[-1].text
                    context = math.log(self.bigram_model.get((prev_word, candidate), 1e-10))
                else:
                    context = 0
                
                score = prior + likelihood + context
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            corrected_tokens.append(Token(best_candidate or token.text))
        
        return ParsedQuery(tokens=corrected_tokens, original=query.original)
    
    def generate_candidates(self, word: str, max_edit_distance: int = 2) -> set:
        """Generate all words within edit distance using SymSpell approach"""
        candidates = set()
        
        # Edit distance 1
        for edit in self._edits1(word):
            if edit in self.vocab:
                candidates.add(edit)
        
        # Edit distance 2
        if max_edit_distance >= 2:
            for edit1 in self._edits1(word):
                for edit2 in self._edits1(edit1):
                    if edit2 in self.vocab:
                        candidates.add(edit2)
        
        return candidates
    
    def _edits1(self, word: str) -> set:
        """All strings at edit distance 1"""
        letters = 'abcdefghijklmnopqrstuvwxyz'
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        inserts = [L + c + R for L, R in splits for c in letters]
        
        return set(deletes + transposes + replaces + inserts)
```

---

## 12. Elasticsearch & Index Serving Optimization

### Sharding Strategy
```
Index Sharding Approaches:
1. Document-based sharding (most common for web search)
   - Hash(doc_id) % num_shards → shard assignment
   - Query fans out to ALL shards, results merged
   - Good for: uniform query distribution

2. Term-based sharding (less common)
   - Hash(term) % num_shards → shard assignment
   - Query only hits shards for query terms
   - Bad for: multi-term queries require cross-shard joins

Google's approach: Document-based with tiered index
- Tier 1: Most important 1B pages (low latency, SSD)
- Tier 2: Next 10B pages (medium latency)
- Tier 3: Long tail 90B pages (only if needed)

Replication:
- Each shard replicated 3x across different racks/zones
- Read replicas serve queries; leader handles index updates
- Consistency: Eventual (seconds) for index updates
```

### Caching Strategy
```
Multi-level caching:

Level 1: Result Cache (Redis/Memcached)
  - Key: normalized_query + user_locale + page_number
  - TTL: 5 minutes for trending queries, 1 hour for stable
  - Hit rate: ~30% (top queries)
  - Size: ~50TB distributed across edge locations

Level 2: Posting List Cache
  - Frequently accessed terms cached in memory
  - Cache top 1M terms (covers 90% of query volume)
  - Size: ~10TB per serving cluster

Level 3: Document Cache
  - Metadata + snippets for top documents
  - Avoids disk reads for commonly returned pages

Cache Invalidation:
  - Query cache: TTL-based + event-driven (major events)
  - Index cache: Versioned segments, swap on new build
```

---

## 13. Observability

### Key Metrics
```yaml
search_quality:
  - ndcg@10: Normalized Discounted Cumulative Gain (target: > 0.65)
  - mrr: Mean Reciprocal Rank (target: > 0.75)
  - zero_results_rate: Queries with no results (target: < 2%)
  - click_through_rate: Users clicking at least one result
  - abandonment_rate: Users leaving without clicking

performance:
  - query_latency_p50: < 200ms
  - query_latency_p99: < 500ms
  - index_freshness_lag: Time between page change and index update
  - shard_query_time: Per-shard response time
  - ranking_model_latency: ML inference time

infrastructure:
  - index_size_bytes: Total index size per tier
  - cache_hit_rate: By cache level
  - shard_balance: Query load distribution across shards
  - replication_lag: Follower behind leader
  - crawler_pages_per_second: Crawl throughput

alerts:
  - query_latency_p99 > 1s for 5 minutes
  - zero_results_rate > 5% for 10 minutes
  - cache_hit_rate drops > 20% in 5 minutes
  - any shard unavailable with < 2 replicas
```

### Distributed Tracing
```
Query: "machine learning basics"
├── [0ms] QueryParsing: tokenize, intent=informational
├── [5ms] SpellCheck: no correction needed
├── [8ms] QueryExpansion: +synonyms(ML, artificial intelligence)
├── [10ms] ShardRouting: fan-out to 12,000 shards
│   ├── [12ms-45ms] IndexLookup (parallel across shards)
│   │   ├── Shard-0001: 847 matches, 3ms
│   │   ├── Shard-0002: 1203 matches, 5ms
│   │   └── ... (12,000 shards)
│   └── [50ms] MergeResults: top-10K from all shards
├── [55ms] Stage1Ranking: BM25+PageRank, 10K → 1K
├── [70ms] Stage2Ranking: ML model, 1K → 100
├── [120ms] Stage3Ranking: Neural reranker, 100 → ordered
├── [130ms] KnowledgeGraph: entity lookup "Machine Learning"
├── [140ms] SnippetGeneration: extract relevant passages
├── [150ms] AdsMatching: parallel ad auction
└── [160ms] ResponseAssembly: compose final SERP
Total: 160ms
```

---

## 14. Considerations & Trade-offs

### Freshness vs Quality
```
Challenge: New pages lack link signals (PageRank = low)
Solution: 
- QDF (Query Deserves Freshness) classifier
- Boost recent pages for time-sensitive queries
- Separate "hot" index for breaking content (update every minute)
- Cold index rebuilt daily with full PageRank
```

### Relevance vs Revenue
```
Challenge: Ads compete with organic results for user attention
Solution:
- Strict separation: ads labeled, positioned distinctly
- Quality score for ads (relevance × bid × CTR prediction)
- Long-term user satisfaction metrics prevent over-monetization
```

### Personalization vs Privacy
```
Challenge: Better results need user data; users want privacy
Solution:
- Anonymized behavioral signals
- Differential privacy for aggregate signals
- User controls for search history
- On-device personalization where possible
```

### Scale Challenges
```
- Index rebuild: Full reindex of 100B pages takes days → incremental updates
- PageRank: Computing on 100B-node graph requires distributed iterative computation
- Serving latency: Sub-200ms with fan-out to 10K+ shards requires aggressive parallelism
- Storage cost: Tiered storage (hot SSD → warm HDD → cold archive)
- Freshness: Balance between crawl frequency and being a good web citizen
```

---

## 15. Summary

| Dimension | Approach |
|-----------|----------|
| Indexing | Inverted index with BM25 scoring, skip lists, VByte compression |
| Ranking | 3-stage: BM25+PageRank → ML (GBDT) → Neural (BERT) |
| Serving | Document-sharded, 3-tiered (hot/warm/cold), 3x replicated |
| Freshness | Real-time index for breaking news, batch rebuild for quality |
| Scale | 100K QPS across 30 DCs, 100B+ pages indexed |
| Quality | 200+ ranking features, continuous A/B testing |
