# Autocomplete / Typeahead System Design

## 1. Problem Statement

Design a real-time autocomplete system that suggests query completions as users type, handling 10 billion keystrokes per day. The system must return suggestions within 100ms, support personalized and trending results, filter offensive content, and work across multiple languages.

---

## 2. Functional Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| FR1 | Prefix Matching | Return top-K suggestions matching user's typed prefix |
| FR2 | Frequency Ranking | Rank suggestions by popularity/relevance |
| FR3 | Personalization | Boost suggestions from user's search history |
| FR4 | Trending Queries | Surface currently trending/breaking queries |
| FR5 | Multi-language | Support 100+ languages with proper tokenization |
| FR6 | Offensive Filtering | Block suggestions for offensive/harmful content |
| FR7 | Entity Awareness | Recognize entities (people, places, brands) in suggestions |
| FR8 | Real-time Updates | New trending queries appear within minutes |
| FR9 | Deletion | Users can remove items from personal suggestions |
| FR10 | Context Awareness | Consider time, location, device for relevance |

## 3. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Latency | p99 < 100ms end-to-end |
| NFR2 | Availability | 99.99% uptime |
| NFR3 | Throughput | 120K RPS sustained (10B keystrokes/day) |
| NFR4 | Freshness | Trending queries surface within 5 minutes |
| NFR5 | Scalability | Handle 2x traffic spikes (events, elections) |
| NFR6 | Global | Serve from edge locations worldwide |
| NFR7 | Accuracy | Top-5 suggestions contain user's intended query > 70% of time |

---

## 4. Capacity Estimation

### Traffic
```
Daily keystrokes:          10 billion
Average query length:      4 words × 5 chars = 20 keystrokes per query
Unique queries per day:    500 million (10B / 20)
Keystrokes per second:     10B / 86400 ≈ 115,740 RPS
Peak (3x):                 ~350K RPS
Average prefix length:     8 characters (users don't wait for full completion)
Suggestions per request:   10
```

### Storage
```
Unique suggestions stored: 100 million (after dedup + filtering)
Average suggestion length: 30 bytes
Suggestion metadata:       50 bytes (frequency, freshness, category)
Raw suggestion data:       100M × 80 bytes = 8 GB
Trie structure overhead:   ~3x raw = 24 GB
Per-user personalization:  1B users × 100 recent queries × 30 bytes = 3 TB
Trending data (hot):       1M trending queries × 100 bytes = 100 MB
```

### Bandwidth
```
Request size:              ~50 bytes (prefix + metadata)
Response size:             10 suggestions × 50 bytes = 500 bytes
Inbound:                   120K × 50 bytes = 6 MB/s
Outbound:                  120K × 500 bytes = 60 MB/s
```

### Infrastructure
```
Serving nodes:             ~200 nodes (600K suggestions/s per node)
Memory per node:           32 GB (full trie fits in memory)
Replication factor:        3
Total serving machines:    600 (200 × 3 replicas)
Edge cache nodes:          ~500 (CDN edge locations)
```

---

## 5. Data Modeling

### Suggestion Entry
```sql
CREATE TABLE suggestions (
    suggestion_id    BIGINT PRIMARY KEY,
    text             VARCHAR(200) NOT NULL,
    normalized_text  VARCHAR(200) NOT NULL,     -- Lowercase, no diacritics
    language         CHAR(5) NOT NULL,
    frequency        BIGINT DEFAULT 0,          -- Global search frequency
    freshness_score  FLOAT DEFAULT 0.0,         -- Decay-weighted recency
    category         VARCHAR(50),               -- entity type: person, place, etc.
    is_offensive     BOOLEAN DEFAULT FALSE,
    entity_id        VARCHAR(100),              -- Link to knowledge graph
    last_updated     TIMESTAMP,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_suggestions_prefix ON suggestions USING btree(normalized_text text_pattern_ops);
CREATE INDEX idx_suggestions_freq ON suggestions(language, frequency DESC);
```

### User History
```sql
CREATE TABLE user_search_history (
    user_id          BIGINT NOT NULL,
    query_text       VARCHAR(200) NOT NULL,
    search_count     INT DEFAULT 1,
    last_searched    TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, query_text)
) PARTITION BY HASH(user_id);
```

### Trending Queries
```sql
CREATE TABLE trending_queries (
    query_text       VARCHAR(200) PRIMARY KEY,
    language         CHAR(5) NOT NULL,
    region           VARCHAR(10),
    current_qps      FLOAT,                    -- Queries per second right now
    baseline_qps     FLOAT,                    -- Historical average
    trend_score      FLOAT,                    -- current / baseline ratio
    started_trending TIMESTAMP,
    category         VARCHAR(50)
);
```

### Trie Node (In-Memory Structure)
```json
{
    "char": "m",
    "children": {
        "a": { "char": "a", "children": {...}, "top_suggestions": [...] },
        "e": { "char": "e", "children": {...}, "top_suggestions": [...] }
    },
    "is_terminal": false,
    "top_suggestions": [
        {"text": "machine learning", "score": 98500},
        {"text": "minecraft", "score": 87200},
        {"text": "maps", "score": 82100}
    ]
}
```

---

## 6. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AUTOCOMPLETE SYSTEM ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

     User types "mach"
          │
          ▼
┌──────────────────┐
│   CDN / Edge     │──── Cache hit? Return immediately (p50 < 20ms)
│   (Cloudflare)   │
└────────┬─────────┘
         │ Cache miss
         ▼
┌──────────────────┐         ┌──────────────────┐
│   API Gateway    │────────▶│   Rate Limiter   │
│   (Load Balance) │         │   (Token Bucket) │
└────────┬─────────┘         └──────────────────┘
         │
         ▼
┌──────────────────┐         ┌──────────────────┐
│  Suggestion      │────────▶│  Personalization │
│  Service         │         │  Service         │
│  (Trie Lookup)   │◀────────│  (User History)  │
└────────┬─────────┘         └──────────────────┘
         │
         ├────────────────────────────┐
         ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│  Global Trie     │         │  Trending        │
│  (In-Memory)     │         │  Service         │
│  Sharded by      │         │  (Real-time)     │
│  prefix range    │         └────────┬─────────┘
└──────────────────┘                  │
                                      ▼
                             ┌──────────────────┐
                             │  Kafka + Flink   │
                             │  (Stream Proc.)  │
                             └────────┬─────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │  Query Logs      │
                             │  (Click Stream)  │
                             └──────────────────┘

═══════════════════════ OFFLINE PIPELINE ═══════════════════════════

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Query Log       │────▶│  Aggregation     │────▶│  Trie Builder    │
│  Store (HDFS)    │     │  (Spark Daily)   │     │  (Serialize +    │
└──────────────────┘     └──────────────────┘     │   Deploy)        │
                                                   └──────────────────┘
┌──────────────────┐     ┌──────────────────┐
│  Offensive       │────▶│  Blocklist       │
│  Content ML      │     │  Filter          │
└──────────────────┘     └──────────────────┘
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| CDN/Edge | Cache popular prefix responses, reduce latency to < 20ms |
| API Gateway | Route, authenticate, rate limit |
| Suggestion Service | Core lookup: merge global + personal + trending |
| Global Trie | In-memory trie with precomputed top-K per node |
| Personalization Service | Lookup user's recent queries, boost matching suggestions |
| Trending Service | Real-time trending query detection via stream processing |
| Kafka + Flink | Stream processing for sliding window frequency counting |
| Trie Builder | Offline: aggregate query logs, build optimized trie, deploy |
| Offensive Filter | ML + blocklist to prevent harmful suggestions |

---

## 7. Low-Level Design (LLD) - APIs

### Suggestion API
```
GET /v1/suggest?q={prefix}&lang={language}&n={count}&user_id={uid}&lat={lat}&lng={lng}

Headers:
  X-Session-Id: <session_uuid>
  X-Device-Type: mobile|desktop

Response 200:
{
    "prefix": "mach",
    "suggestions": [
        {
            "text": "machine learning",
            "type": "query",
            "score": 0.95,
            "source": "global",
            "entity": {"type": "topic", "id": "Q2539"}
        },
        {
            "text": "machine learning python",
            "type": "query",
            "score": 0.87,
            "source": "global"
        },
        {
            "text": "macbook pro",
            "type": "query",
            "score": 0.82,
            "source": "trending",
            "trending_badge": true
        },
        {
            "text": "machine learning course",
            "type": "query",
            "score": 0.78,
            "source": "personal"
        }
    ],
    "debug": {
        "latency_ms": 12,
        "cache_hit": false,
        "shard_id": 7
    }
}
```

### Delete Personal Suggestion
```
DELETE /v1/suggest/personal?user_id={uid}&text={suggestion_text}

Response 204: No Content
```

### Internal: Trie Refresh
```protobuf
service TrieService {
    rpc LookupPrefix(PrefixRequest) returns (SuggestionResponse);
    rpc RefreshTrie(TrieSnapshot) returns (RefreshStatus);
    rpc UpdateTrending(TrendingUpdate) returns (UpdateStatus);
}

message PrefixRequest {
    string prefix = 1;
    string language = 2;
    int32 max_results = 3;
    repeated string exclude_ids = 4;  // Already shown suggestions
}

message SuggestionResponse {
    repeated Suggestion suggestions = 1;
    int64 trie_version = 2;
}
```

---

## 8. Deep Dive: Trie Data Structure with Frequency Weights

```python
import heapq
import struct
import mmap
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Suggestion:
    text: str
    score: float
    category: str = ""
    entity_id: str = ""


@dataclass
class TrieNode:
    """
    Compressed trie node with precomputed top-K suggestions.
    
    Key optimization: Store top-K suggestions at every node so lookup is O(prefix_length)
    instead of O(subtree_size). Space trade-off but critical for latency.
    """
    children: dict = field(default_factory=dict)      # char → TrieNode
    is_terminal: bool = False
    terminal_suggestion: Optional[Suggestion] = None
    top_k: list = field(default_factory=list)         # Precomputed top-K for this prefix
    
    # For compressed (Patricia) trie
    compressed_edge: str = ""   # Multi-character edge label


class AutocompleteTrie:
    """
    Production-grade trie for autocomplete serving.
    
    Features:
    - Compressed edges (Patricia trie) to reduce memory ~60%
    - Precomputed top-K at each node for O(1) lookup after prefix traversal
    - Serializable to binary format for fast loading
    - Thread-safe read access (immutable after build)
    """
    
    TOP_K = 10  # Store top 10 suggestions per node
    
    def __init__(self):
        self.root = TrieNode()
        self.total_nodes = 0
        self.total_suggestions = 0
    
    def build_from_suggestions(self, suggestions: list[tuple[str, float, str]]):
        """
        Build trie from list of (text, score, category) tuples.
        Two-phase: 1) Insert all, 2) Propagate top-K up the tree.
        """
        # Phase 1: Insert all suggestions
        for text, score, category in suggestions:
            self._insert(text, Suggestion(text=text, score=score, category=category))
        
        # Phase 2: Bottom-up propagation of top-K
        self._propagate_top_k(self.root)
        
        print(f"Built trie: {self.total_nodes} nodes, {self.total_suggestions} suggestions")
    
    def _insert(self, text: str, suggestion: Suggestion):
        """Insert a suggestion into the trie"""
        node = self.root
        normalized = text.lower().strip()
        
        for char in normalized:
            if char not in node.children:
                node.children[char] = TrieNode()
                self.total_nodes += 1
            node = node.children[char]
        
        node.is_terminal = True
        node.terminal_suggestion = suggestion
        self.total_suggestions += 1
    
    def _propagate_top_k(self, node: TrieNode) -> list[Suggestion]:
        """
        DFS to propagate top-K suggestions from leaves to root.
        Each node stores the K highest-scoring suggestions in its subtree.
        """
        candidates = []
        
        # Add this node's suggestion if terminal
        if node.is_terminal and node.terminal_suggestion:
            candidates.append(node.terminal_suggestion)
        
        # Collect from children
        for child in node.children.values():
            child_top_k = self._propagate_top_k(child)
            candidates.extend(child_top_k)
        
        # Keep top-K by score
        node.top_k = heapq.nlargest(self.TOP_K, candidates, key=lambda s: s.score)
        
        return node.top_k
    
    def lookup(self, prefix: str, limit: int = 10) -> list[Suggestion]:
        """
        O(prefix_length) lookup - traverse to prefix node, return precomputed top-K.
        This is the hot path - must be as fast as possible.
        """
        node = self.root
        normalized = prefix.lower().strip()
        
        for char in normalized:
            if char not in node.children:
                return []  # No suggestions for this prefix
            node = node.children[char]
        
        return node.top_k[:limit]
    
    def compress(self):
        """
        Convert to Patricia trie: merge single-child chains into edge labels.
        Reduces node count by ~60% for natural language data.
        
        Before: m → a → c → h → i → n → e (7 nodes)
        After:  "machine" (1 node with edge label)
        """
        self._compress_node(self.root)
    
    def _compress_node(self, node: TrieNode):
        """Recursively compress single-child chains"""
        for char, child in list(node.children.items()):
            # Compress chain of single children
            edge = char
            current = child
            
            while (len(current.children) == 1 and 
                   not current.is_terminal):
                next_char = list(current.children.keys())[0]
                edge += next_char
                current = current.children[next_char]
            
            if len(edge) > 1:
                # Replace chain with single compressed node
                current.compressed_edge = edge
                node.children[char] = current
                self.total_nodes -= (len(edge) - 1)
            
            # Recurse into children
            self._compress_node(current)
    
    def serialize_to_binary(self, filepath: str):
        """
        Serialize trie to compact binary format for fast loading.
        
        Format:
        [Header: magic(4B) | version(2B) | num_nodes(4B) | num_suggestions(4B)]
        [String Table: offset_array + packed strings]
        [Node Array: serialized nodes with child pointers]
        [TopK Arrays: suggestion indices per node]
        
        This allows mmap-based loading for near-instant startup.
        """
        with open(filepath, 'wb') as f:
            # Header
            f.write(b'TRIE')                           # Magic
            f.write(struct.pack('<H', 1))              # Version
            f.write(struct.pack('<I', self.total_nodes))
            f.write(struct.pack('<I', self.total_suggestions))
            
            # Collect all strings and build string table
            strings = []
            string_to_idx = {}
            self._collect_strings(self.root, strings, string_to_idx)
            
            # Write string table
            str_offset = f.tell()
            for s in strings:
                encoded = s.encode('utf-8')
                f.write(struct.pack('<H', len(encoded)))
                f.write(encoded)
            
            # Serialize node tree (BFS)
            self._serialize_nodes(f, string_to_idx)
    
    def _collect_strings(self, node, strings, mapping):
        """Collect all unique strings for string table"""
        if node.is_terminal and node.terminal_suggestion:
            text = node.terminal_suggestion.text
            if text not in mapping:
                mapping[text] = len(strings)
                strings.append(text)
        
        for child in node.children.values():
            self._collect_strings(child, strings, mapping)
    
    def _serialize_nodes(self, f, string_mapping):
        """BFS serialization of trie nodes"""
        from collections import deque
        queue = deque([self.root])
        node_offsets = {}
        
        while queue:
            node = queue.popleft()
            node_offsets[id(node)] = f.tell()
            
            # Write node data
            f.write(struct.pack('<B', 1 if node.is_terminal else 0))
            f.write(struct.pack('<B', len(node.children)))
            
            # Write top-K indices
            f.write(struct.pack('<B', len(node.top_k)))
            for suggestion in node.top_k:
                idx = string_mapping.get(suggestion.text, 0)
                f.write(struct.pack('<I', idx))
                f.write(struct.pack('<f', suggestion.score))
            
            # Queue children
            for char, child in sorted(node.children.items()):
                f.write(char.encode('utf-8')[:1])
                queue.append(child)
    
    @classmethod
    def load_from_binary(cls, filepath: str) -> 'AutocompleteTrie':
        """
        Memory-mapped loading for near-instant startup.
        Avoids deserialization - reads directly from mapped file.
        """
        trie = cls()
        with open(filepath, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            
            # Read header
            magic = mm[:4]
            assert magic == b'TRIE', "Invalid trie file"
            version = struct.unpack_from('<H', mm, 4)[0]
            num_nodes = struct.unpack_from('<I', mm, 6)[0]
            num_suggestions = struct.unpack_from('<I', mm, 10)[0]
            
            trie.total_nodes = num_nodes
            trie.total_suggestions = num_suggestions
            # ... deserialize nodes from binary
            
            mm.close()
        
        return trie


class CompressedTrieWithScoring:
    """
    Production enhancement: score blending for suggestions.
    Final score = w1*frequency + w2*freshness + w3*personalization + w4*trending
    """
    
    WEIGHTS = {
        'frequency': 0.4,
        'freshness': 0.2,
        'personalization': 0.3,
        'trending': 0.1,
    }
    
    def compute_final_score(self, base_score: float, freshness: float,
                           personal_score: float, trending_score: float) -> float:
        """Weighted combination of scoring signals"""
        return (
            self.WEIGHTS['frequency'] * base_score +
            self.WEIGHTS['freshness'] * freshness +
            self.WEIGHTS['personalization'] * personal_score +
            self.WEIGHTS['trending'] * trending_score
        )
    
    def time_decay_score(self, raw_frequency: int, last_searched_hours_ago: float) -> float:
        """
        Exponential decay: older queries get lower scores.
        Half-life of 7 days for general queries.
        """
        import math
        half_life_hours = 7 * 24  # 7 days
        decay = math.exp(-0.693 * last_searched_hours_ago / half_life_hours)
        return raw_frequency * decay
```

---

## 9. Deep Dive: Distributed Serving (Shard by Prefix Range)

```python
class PrefixShardRouter:
    """
    Shard suggestions by prefix range for horizontal scaling.
    
    Strategy: Divide the alphabet space into N ranges.
    Each shard owns a contiguous prefix range.
    
    Example with 26 shards:
    Shard 0: a* - Shard 1: b* - ... - Shard 25: z*
    
    Better: Weight-based sharding (popular prefixes get more shards)
    """
    
    def __init__(self, shard_config: dict):
        """
        shard_config: {
            "shard_0": {"start": "a", "end": "d", "replicas": ["host1:9001", "host2:9001"]},
            "shard_1": {"start": "d", "end": "h", "replicas": ["host3:9001", "host4:9001"]},
            ...
        }
        """
        self.shards = shard_config
        self.sorted_boundaries = sorted(
            [(cfg['start'], shard_id) for shard_id, cfg in shard_config.items()]
        )
    
    def route_prefix(self, prefix: str) -> str:
        """Route a prefix to the appropriate shard"""
        if not prefix:
            return "shard_0"  # Default
        
        first_char = prefix[0].lower()
        
        # Binary search for the correct shard
        import bisect
        boundaries = [b[0] for b in self.sorted_boundaries]
        idx = bisect.bisect_right(boundaries, first_char) - 1
        
        if idx < 0:
            idx = 0
        
        return self.sorted_boundaries[idx][1]
    
    def get_replica(self, shard_id: str) -> str:
        """
        Select replica using power-of-two-choices:
        Pick 2 random replicas, route to least loaded.
        """
        import random
        replicas = self.shards[shard_id]['replicas']
        
        if len(replicas) == 1:
            return replicas[0]
        
        # Pick two random replicas
        candidates = random.sample(replicas, min(2, len(replicas)))
        
        # Return least loaded (based on pending request count)
        return min(candidates, key=lambda r: self.get_load(r))
    
    def rebalance_shards(self, load_metrics: dict):
        """
        Dynamic rebalancing when load is uneven.
        Split hot shards, merge cold shards.
        
        Example: If 'th*' prefix is hot (due to "the", "that", "this"),
        split shard covering 't*' into 'ta-tg' and 'th-tz'.
        """
        hot_threshold = 0.8  # 80% capacity
        cold_threshold = 0.1  # 10% capacity
        
        for shard_id, metrics in load_metrics.items():
            if metrics['cpu_utilization'] > hot_threshold:
                self._split_shard(shard_id)
            elif metrics['cpu_utilization'] < cold_threshold:
                self._try_merge_shard(shard_id)


class SuggestionServiceCluster:
    """
    Full serving cluster with read replicas and consistency management.
    """
    
    def __init__(self, router: PrefixShardRouter, num_shards: int):
        self.router = router
        self.num_shards = num_shards
        self.current_trie_version = 0
    
    def serve_request(self, prefix: str, user_id: str, context: dict) -> list:
        """
        Full request flow:
        1. Route to correct shard
        2. Lookup global suggestions
        3. Fetch personal suggestions (parallel)
        4. Fetch trending (parallel)
        5. Merge and rank
        6. Filter offensive
        7. Return top-K
        """
        import asyncio
        
        # Parallel fetches
        global_future = self._fetch_global(prefix)
        personal_future = self._fetch_personal(prefix, user_id)
        trending_future = self._fetch_trending(prefix, context.get('region'))
        
        global_sugg = global_future    # await in production
        personal_sugg = personal_future
        trending_sugg = trending_future
        
        # Merge with deduplication
        merged = self._merge_suggestions(global_sugg, personal_sugg, trending_sugg)
        
        # Apply offensive content filter
        filtered = [s for s in merged if not self._is_offensive(s)]
        
        # Final ranking with context
        ranked = self._contextual_rank(filtered, context)
        
        return ranked[:10]
    
    def _merge_suggestions(self, global_s, personal_s, trending_s) -> list:
        """
        Merge strategy with deduplication and source boosting:
        - Personal: 1.5x boost (user-specific relevance)
        - Trending: 1.3x boost (temporal relevance)
        - Global: 1.0x (baseline)
        """
        seen = set()
        merged = []
        
        for s in personal_s:
            if s.text not in seen:
                seen.add(s.text)
                merged.append(Suggestion(s.text, s.score * 1.5, source='personal'))
        
        for s in trending_s:
            if s.text not in seen:
                seen.add(s.text)
                merged.append(Suggestion(s.text, s.score * 1.3, source='trending'))
        
        for s in global_s:
            if s.text not in seen:
                seen.add(s.text)
                merged.append(Suggestion(s.text, s.score, source='global'))
        
        merged.sort(key=lambda x: x.score, reverse=True)
        return merged
    
    def rolling_deploy_new_trie(self, new_version: int, binary_path: str):
        """
        Zero-downtime trie deployment:
        1. Load new trie into memory alongside old
        2. Warm up caches with common prefixes
        3. Atomic pointer swap (old → new)
        4. Drain old trie after swap
        5. Release old memory
        
        This ensures no request is ever served from a partially loaded trie.
        """
        # Load new trie (takes ~30 seconds for 24GB)
        new_trie = AutocompleteTrie.load_from_binary(binary_path)
        
        # Warm up: pre-query top 10K prefixes
        for prefix in self.get_top_prefixes(10000):
            new_trie.lookup(prefix)
        
        # Atomic swap
        self.current_trie_version = new_version
        # old_trie reference dropped, GC reclaims
```

---

## 10. Deep Dive: Real-time Trending (Kafka + Flink)

```python
class TrendingQueryDetector:
    """
    Real-time trending detection using sliding window counters.
    
    Architecture:
    Query Logs → Kafka Topic → Flink Job → Trending Store → Serving Layer
    
    Detection: A query is "trending" if its current rate significantly exceeds
    its historical baseline (z-score > threshold).
    """
    
    def __init__(self, window_size_minutes: int = 5, 
                 baseline_window_hours: int = 24,
                 z_score_threshold: float = 3.0):
        self.window_size = window_size_minutes
        self.baseline_window = baseline_window_hours
        self.z_threshold = z_score_threshold
    
    def flink_job_pseudocode(self):
        """
        Apache Flink streaming job for trending detection.
        
        env = StreamExecutionEnvironment.get()
        
        # Source: Kafka topic with query events
        queries = env.add_source(
            FlinkKafkaConsumer("search-queries", QuerySchema(), kafka_props)
        )
        
        # Sliding window: count queries per 5-minute window, sliding every 1 minute
        windowed_counts = (
            queries
            .key_by(lambda q: q.normalized_text)
            .window(SlidingEventTimeWindows.of(
                Time.minutes(5),   # Window size
                Time.minutes(1)    # Slide interval
            ))
            .aggregate(CountAggregator())
        )
        
        # Compare against baseline (from Redis/state store)
        trending = (
            windowed_counts
            .process(TrendingDetectorFunction(z_threshold=3.0))
        )
        
        # Sink: Write to Redis for serving layer
        trending.add_sink(RedisSink("trending-queries"))
        
        env.execute("Trending Query Detection")
        """
        pass
    
    def detect_trending(self, query: str, current_count: int, 
                       baseline_mean: float, baseline_std: float) -> tuple[bool, float]:
        """
        Z-score based trending detection.
        
        A query is trending if: (current - mean) / std > threshold
        
        Also handles cold-start: if no baseline, use absolute threshold.
        """
        if baseline_std == 0:
            # Cold start: no historical data
            # Use absolute threshold
            is_trending = current_count > 100  # At least 100 queries in window
            trend_score = current_count / 100.0
            return is_trending, trend_score
        
        z_score = (current_count - baseline_mean) / baseline_std
        is_trending = z_score > self.z_threshold
        
        # Trend score normalized to [0, 1]
        trend_score = min(z_score / 10.0, 1.0) if z_score > 0 else 0.0
        
        return is_trending, trend_score
    
    def sliding_window_counter(self):
        """
        Redis-based sliding window counter for per-query frequency.
        
        Key structure:
        - query:{normalized}:current → Sorted Set with timestamp scores
        - query:{normalized}:baseline → {mean, std, updated_at}
        
        Implementation using Redis sorted sets:
        """
        pass


class SlidingWindowCounter:
    """
    Efficient sliding window counter using Redis sorted sets.
    Each event is stored with timestamp as score.
    Count = ZCOUNT with time range.
    """
    
    def __init__(self, redis_client, window_seconds: int = 300):
        self.redis = redis_client
        self.window_seconds = window_seconds
    
    def increment(self, query: str, timestamp: float):
        """Add an event to the sliding window"""
        key = f"qcount:{query}"
        # Add with timestamp as score, unique member to avoid dedup
        member = f"{timestamp}:{id(query)}"
        
        pipe = self.redis.pipeline()
        pipe.zadd(key, {member: timestamp})
        # Remove events outside window
        pipe.zremrangebyscore(key, 0, timestamp - self.window_seconds)
        # Set TTL to auto-cleanup
        pipe.expire(key, self.window_seconds * 2)
        pipe.execute()
    
    def get_count(self, query: str, timestamp: float) -> int:
        """Get count of events in current window"""
        key = f"qcount:{query}"
        window_start = timestamp - self.window_seconds
        return self.redis.zcount(key, window_start, timestamp)
    
    def get_top_trending(self, n: int = 100) -> list:
        """
        Get top-N trending queries.
        Maintained in a separate sorted set updated by Flink.
        """
        return self.redis.zrevrange("trending:global", 0, n - 1, withscores=True)


class KafkaQueryEventProducer:
    """
    Every search query produces an event to Kafka for trending detection.
    
    Topic: search-queries
    Partitioning: By hash(normalized_query) for per-query ordering
    Retention: 7 days
    """
    
    SCHEMA = {
        "type": "record",
        "name": "QueryEvent",
        "fields": [
            {"name": "query_text", "type": "string"},
            {"name": "normalized_text", "type": "string"},
            {"name": "timestamp", "type": "long"},
            {"name": "user_id", "type": ["null", "string"]},
            {"name": "region", "type": "string"},
            {"name": "language", "type": "string"},
            {"name": "device_type", "type": "string"}
        ]
    }
    
    def produce_event(self, query: str, user_id: str, region: str):
        """Emit query event to Kafka"""
        import time
        event = {
            "query_text": query,
            "normalized_text": query.lower().strip(),
            "timestamp": int(time.time() * 1000),
            "user_id": user_id,
            "region": region,
            "language": "en",
            "device_type": "mobile"
        }
        
        # Partition by query hash for ordering
        partition_key = event["normalized_text"].encode('utf-8')
        # producer.send("search-queries", key=partition_key, value=event)
```

---

## 11. Offensive Content Filtering

```python
class OffensiveContentFilter:
    """
    Multi-layer filtering to prevent offensive suggestions:
    
    Layer 1: Blocklist (exact match) - hardcoded banned terms
    Layer 2: Pattern matching (regex) - known offensive patterns
    Layer 3: ML classifier - trained on labeled data
    Layer 4: Human review queue - borderline cases
    """
    
    def __init__(self):
        self.blocklist = set()          # Exact banned suggestions
        self.pattern_blocklist = []     # Regex patterns
        self.ml_model = None            # Trained classifier
        self.threshold = 0.85           # ML confidence threshold
    
    def is_offensive(self, suggestion: str) -> tuple[bool, str]:
        """
        Returns (is_offensive, reason)
        Must be extremely fast (< 1ms) since called per suggestion.
        """
        normalized = suggestion.lower().strip()
        
        # Layer 1: Exact blocklist (O(1) hash lookup)
        if normalized in self.blocklist:
            return True, "blocklist_exact"
        
        # Layer 2: Token blocklist (any word is blocked)
        tokens = normalized.split()
        for token in tokens:
            if token in self.blocked_tokens:
                return True, "blocklist_token"
        
        # Layer 3: Pattern matching
        for pattern, reason in self.pattern_blocklist:
            if pattern.search(normalized):
                return True, f"pattern:{reason}"
        
        # Layer 4: ML classifier (only if above layers pass)
        if self.ml_model:
            score = self.ml_model.predict_proba(normalized)
            if score > self.threshold:
                return True, f"ml_classifier:{score:.2f}"
        
        return False, "clean"
    
    def build_at_index_time(self, suggestions: list) -> list:
        """
        Pre-filter during trie build (offline) - can use expensive models.
        Cheaper/faster check at serving time as backup.
        """
        clean = []
        for s in suggestions:
            is_bad, reason = self.is_offensive(s.text)
            if not is_bad:
                clean.append(s)
            else:
                self.log_filtered(s.text, reason)
        return clean
```

---

## 12. Caching Strategy

```
Multi-tier caching for autocomplete:

┌─────────────────────────────────────────────────────────┐
│ Layer 1: Browser/Client Cache                            │
│ - Cache responses for typed prefixes in session          │
│ - TTL: session duration                                  │
│ - Saves: ~40% of requests never reach server             │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│ Layer 2: CDN Edge Cache                                  │
│ - Cache popular prefixes (top 100K) at edge              │
│ - Key: prefix + language + region                        │
│ - TTL: 5 minutes (balance freshness vs hit rate)         │
│ - Hit rate: ~60% of requests served from edge            │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│ Layer 3: Application Cache (Redis)                       │
│ - Full suggestion lists for all prefixes ever queried    │
│ - Key: hash(prefix + language)                           │
│ - TTL: 1 hour                                           │
│ - Hit rate: ~80% of remaining requests                   │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│ Layer 4: In-Memory Trie (Origin)                         │
│ - Full trie in RAM - O(prefix_length) lookup             │
│ - Always available, no cache miss possible               │
│ - The "source of truth" for suggestions                  │
└─────────────────────────────────────────────────────────┘

Cache Invalidation:
- Trending queries: Push invalidation to CDN when trending list changes
- New trie version: Flush all caches, let them repopulate
- Personal: Never cache personal suggestions at shared layers
```

---

## 13. Observability

### Key Metrics
```yaml
latency:
  - suggest_latency_p50: target < 30ms
  - suggest_latency_p99: target < 100ms
  - trie_lookup_time: target < 5ms
  - personalization_fetch: target < 20ms

quality:
  - suggestion_acceptance_rate: user selects a suggestion (target > 40%)
  - position_of_accepted: avg position of clicked suggestion (target < 3)
  - zero_suggestion_rate: prefix returns no results (target < 1%)
  - offensive_leak_rate: offensive suggestions shown (target: 0)

infrastructure:
  - trie_memory_usage: per node (target < 30GB)
  - cache_hit_rate_cdn: target > 60%
  - cache_hit_rate_redis: target > 80%
  - shard_load_balance: max/min QPS ratio (target < 2x)
  - trie_build_time: offline build duration
  - trending_detection_lag: time from spike to serving

availability:
  - serving_error_rate: 5xx responses (target < 0.01%)
  - shard_availability: each shard has 2+ healthy replicas
  - failover_time: time to redirect from failed replica
```

### Alerting Rules
```yaml
alerts:
  - name: high_latency
    condition: suggest_latency_p99 > 200ms for 3 minutes
    severity: critical
    
  - name: offensive_content_leak
    condition: offensive_leak_count > 0
    severity: critical
    action: auto-rollback trie version
    
  - name: low_acceptance_rate
    condition: suggestion_acceptance_rate < 30% for 1 hour
    severity: warning
    
  - name: trending_lag
    condition: trending_detection_lag > 10 minutes
    severity: warning
```

---

## 14. Considerations & Trade-offs

### Space vs Latency
```
Trade-off: Storing top-K at every trie node uses ~10x memory
but gives O(1) lookup vs O(subtree traversal).

Decision: Store top-K. Memory is cheap (~$5/GB/month), latency is critical.
24GB trie in RAM costs ~$120/month per machine.
Without precomputed top-K, p99 would be 50-100ms instead of 5ms.
```

### Freshness vs Stability
```
Trade-off: Frequent trie updates for freshness vs stable suggestions.
Users expect consistent suggestions within a session.

Decision: 
- Full trie rebuild: every 4 hours (offline Spark job)
- Trending overlay: updates every 1 minute (in-memory hot list)
- Personal: real-time (user's own history always fresh)
```

### Personalization vs Cold Start
```
Trade-off: New users have no history for personalization.
Solution:
- Cold start: use demographics + location for initial signals
- Session-based: learn within current session (typed but not searched)
- Collaborative: "users like you also searched for..."
```

### Global Consistency
```
Trade-off: Each region has slightly different trie (latency vs consistency)
Decision: Accept regional differences.
- Each region builds trie from local query logs
- Global trending synced every minute
- Acceptable that US and UK see slightly different suggestions
```

---

## 15. Summary

| Dimension | Approach |
|-----------|----------|
| Data Structure | Compressed trie with precomputed top-K per node |
| Serving | Prefix-range sharded, 3x replicated, in-memory |
| Personalization | User history lookup + score boosting at merge time |
| Trending | Kafka → Flink sliding window → Redis → hot overlay |
| Caching | 4-tier: client → CDN → Redis → in-memory trie |
| Safety | Blocklist + patterns + ML classifier (offline + online) |
| Deployment | Binary-serialized trie, atomic swap, zero-downtime |
| Latency | p50 < 30ms, p99 < 100ms including personalization |
