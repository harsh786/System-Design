# RAG Enterprise Patterns - Staff Architect Interview

## Question 16: Multi-Tenant RAG Architecture
**Difficulty: Staff Level | Topic: Multi-Tenancy | Asked at: Salesforce, Microsoft, ServiceNow**

Design a multi-tenant RAG platform serving 10,000 enterprise customers. Each tenant has different data, different access controls, different SLAs, and different compliance requirements. How do you architect isolation without per-tenant infrastructure?

### Expected Answer:

**Multi-Tenant RAG Platform Architecture:**

1. **Isolation Model:**
   ```
   Shared Infrastructure:
   ┌─────────────────────────────────────────────┐
   │  API Gateway (Tenant identification)         │
   ├─────────────────────────────────────────────┤
   │  Shared Compute (K8s pods with resource limits) │
   ├─────────────────────────────────────────────┤
   │  Vector DB (Namespace-per-tenant)            │
   ├─────────────────────────────────────────────┤
   │  LLM Pool (Shared with priority queuing)     │
   └─────────────────────────────────────────────┘
   
   Dedicated for Premium Tenants:
   ┌─────────────────────────────────────────────┐
   │  Dedicated Vector DB Cluster                 │
   │  Dedicated LLM Endpoint (fine-tuned)         │
   │  Dedicated Encryption Keys                   │
   └─────────────────────────────────────────────┘
   ```

2. **Data Isolation Strategies:**
   ```python
   class TenantAwareVectorDB:
       def search(self, tenant_id: str, query_embedding, top_k: int):
           # Option 1: Namespace isolation (recommended for <1000 tenants)
           return self.db.search(
               namespace=f"tenant_{tenant_id}",
               vector=query_embedding,
               top_k=top_k
           )
           
           # Option 2: Metadata filtering (for >1000 tenants)
           return self.db.search(
               vector=query_embedding,
               filter={"tenant_id": tenant_id},
               top_k=top_k
           )
           
           # Option 3: Collection-per-tenant (for premium tenants)
           return self.db.collection(f"premium_{tenant_id}").search(
               vector=query_embedding,
               top_k=top_k
           )
   ```

3. **SLA-Based Resource Allocation:**
   | Tier | Concurrency | Latency SLA | Vector DB | LLM Model |
   |------|-------------|-------------|-----------|-----------|
   | Free | 5 RPM | Best effort | Shared namespace | GPT-3.5 |
   | Pro | 100 RPM | p99 < 3s | Shared, priority | GPT-4 |
   | Enterprise | 1000 RPM | p99 < 1s | Dedicated cluster | GPT-4 + fine-tuned |
   | Regulated | 500 RPM | p99 < 2s | Isolated + encrypted | On-prem LLM |

4. **Noisy Neighbor Prevention:**
   - Per-tenant rate limiting at API gateway
   - Resource quotas in Kubernetes (CPU/memory per tenant pod)
   - Vector DB query queuing with priority scheduling
   - LLM token budgets per tenant per billing cycle
   - Circuit breakers: If one tenant's queries consistently fail, isolate them

5. **Compliance & Audit:**
   - Tenant data encryption with tenant-specific keys (envelope encryption)
   - Cross-tenant data access is architecturally impossible (not just policy)
   - Audit logs per tenant (who accessed what, when)
   - Data retention policies configurable per tenant
   - Right-to-erasure: Delete all tenant embeddings + documents + cache in <72 hours

---

## Question 17: RAG with Real-Time Data Streams
**Difficulty: Staff Level | Topic: Stream Processing | Asked at: Confluent, Databricks, Amazon**

Design a RAG system that incorporates real-time data (stock prices, news feeds, IoT sensors) alongside static knowledge bases. How do you maintain freshness while preserving retrieval quality?

### Expected Answer:

**Real-Time RAG Architecture:**

1. **Dual-Index Architecture:**
   ```
   ┌──────────────────┐     ┌──────────────────┐
   │  Static Index     │     │  Real-Time Index  │
   │  (Batch updated)  │     │  (Stream updated) │
   │                   │     │                   │
   │  - Documents      │     │  - News (< 5min)  │
   │  - Knowledge base │     │  - Prices (< 1s)  │
   │  - Historical     │     │  - Alerts (< 30s) │
   │                   │     │                   │
   │  Update: Daily    │     │  Update: Streaming │
   └────────┬──────────┘     └────────┬──────────┘
            │                          │
            └──────────┬───────────────┘
                       │
              Temporal-Aware Retrieval
                       │
              Freshness-Weighted Fusion
   ```

2. **Stream Processing Pipeline:**
   ```python
   class RealTimeIndexer:
       def __init__(self):
           self.kafka_consumer = KafkaConsumer('raw-events')
           self.embedding_service = EmbeddingService()
           self.realtime_index = MilvusCollection('realtime')
       
       async def process_stream(self):
           async for message in self.kafka_consumer:
               # Parse and validate
               event = self.parse(message)
               
               # Embed in real-time (lightweight model for speed)
               embedding = await self.embedding_service.embed_fast(event.text)
               
               # Upsert to real-time index with TTL
               await self.realtime_index.upsert(
                   id=event.id,
                   vector=embedding,
                   metadata={
                       'timestamp': event.timestamp,
                       'source': event.source,
                       'ttl': event.ttl,
                       'type': event.type
                   }
               )
               
               # Expire old entries
               await self.realtime_index.delete_expired()
   ```

3. **Temporal-Aware Retrieval:**
   ```python
   class TemporalRetriever:
       def retrieve(self, query: str, temporal_context: str = 'recent'):
           # Search both indices
           static_results = self.static_index.search(query, top_k=10)
           realtime_results = self.realtime_index.search(query, top_k=10)
           
           # Apply temporal scoring
           for result in static_results + realtime_results:
               age_hours = (now() - result.timestamp).total_hours()
               # Exponential decay: recent info scores higher
               result.temporal_score = math.exp(-age_hours / self.half_life)
               result.final_score = (
                   0.6 * result.similarity_score + 
                   0.4 * result.temporal_score
               )
           
           # Merge and re-rank
           all_results = sorted(
               static_results + realtime_results,
               key=lambda r: r.final_score, reverse=True
           )
           return all_results[:10]
   ```

4. **Conflict Resolution:**
   - When real-time data contradicts static knowledge → prefer real-time with disclaimer
   - Confidence scoring: Real-time data from verified sources gets higher weight
   - Version tracking: Show "as of [timestamp]" in responses
   - Contradiction detection: Alert when real-time contradicts established facts

5. **Production Challenges:**
   - **Embedding drift:** Real-time model may differ from batch model → use same model, different serving
   - **Index bloat:** Real-time index TTL management (auto-expire after 24hrs → promote to static)
   - **Consistency:** Eventual consistency between streams → tolerate small gaps
   - **Back-pressure:** If embedding service is slow, buffer with backpressure (Kafka lag monitoring)

---

## Question 18: RAG Quality Feedback Loops
**Difficulty: Staff Level | Topic: Continuous Improvement | Asked at: Google, Spotify, Netflix**

Design a feedback loop system that continuously improves RAG quality using implicit signals (clicks, dwell time, follow-up questions) and explicit signals (thumbs up/down, corrections). How do you close the loop from feedback to model improvement?

### Expected Answer:

**RAG Quality Feedback Loop Architecture:**

1. **Signal Collection:**
   ```python
   class FeedbackCollector:
       # Explicit signals
       EXPLICIT_SIGNALS = {
           'thumbs_up': {'weight': 1.0, 'confidence': 'high'},
           'thumbs_down': {'weight': -1.0, 'confidence': 'high'},
           'correction': {'weight': -0.8, 'confidence': 'high'},
           'citation_click': {'weight': 0.5, 'confidence': 'medium'},
           'copy_response': {'weight': 0.7, 'confidence': 'medium'},
       }
       
       # Implicit signals
       IMPLICIT_SIGNALS = {
           'reformulation': {'weight': -0.3, 'confidence': 'low'},
           # User asks same thing differently → first answer was bad
           'dwell_time_long': {'weight': 0.4, 'confidence': 'low'},
           'follow_up_question': {'weight': 0.2, 'confidence': 'low'},
           'session_end_after_answer': {'weight': 0.6, 'confidence': 'medium'},
           # User got what they needed
           'abandon_before_answer': {'weight': -0.5, 'confidence': 'medium'},
       }
   ```

2. **Feedback Processing Pipeline:**
   ```
   Raw Signals → Aggregation → Quality Score → Training Data → Model Update
        ↓              ↓              ↓              ↓              ↓
   Event Stream   Per-query      Retrieval     Fine-tuning    A/B Test
                  scoring        ranking data   dataset        & Deploy
   ```

3. **Closing the Loop:**
   
   **Loop 1: Retrieval Improvement (Weekly)**
   - Aggregate feedback per query-document pair
   - Positive feedback → boost document relevance score
   - Negative feedback → demote or investigate document quality
   - Train retrieval model on click-through data (Learning to Rank)
   
   **Loop 2: Chunk Quality (Monthly)**
   - Documents with consistently low scores → re-chunk with different strategy
   - Identify "dead" chunks (never retrieved, or retrieved but never useful)
   - Surface chunks that are frequently retrieved but get negative feedback → content quality issue
   
   **Loop 3: Model Fine-tuning (Quarterly)**
   - Collect (query, context, good_response) triples from positive feedback
   - Fine-tune generation model on domain-specific successful interactions
   - Evaluate on held-out test set before deployment
   
   **Loop 4: Prompt Optimization (Continuous)**
   - Track which prompt templates get highest satisfaction scores
   - A/B test prompt variations automatically
   - Use DSPy/OPRO for automated prompt optimization based on feedback

4. **Safeguards:**
   - Feedback gaming detection (rate limiting, anomaly detection)
   - Minimum sample size before acting on feedback (statistical significance)
   - Human review for drastic changes (removing documents, major re-ranking)
   - Rollback capability if feedback-driven changes degrade quality

5. **Metrics Dashboard:**
   - Weekly quality trend (feedback score moving average)
   - Retrieval precision improvement over time
   - User satisfaction by query type/topic
   - Feedback coverage (% of queries with explicit feedback)
   - Model improvement attribution (which loop drove which improvement)

---

## Question 19: RAG for Code Generation
**Difficulty: Staff Level | Topic: Code-Specific RAG | Asked at: GitHub, Google, JetBrains**

Design a RAG system optimized for code generation that retrieves relevant code snippets, documentation, and examples to assist an LLM in generating accurate, contextual code. Consider repository-level understanding.

### Expected Answer:

**Code-Aware RAG Architecture:**

1. **Multi-Level Code Understanding:**
   ```
   Repository Level:    Architecture, patterns, dependencies
        ↓
   File Level:          Imports, exports, module purpose
        ↓
   Class/Function Level: Signatures, docstrings, types
        ↓
   Snippet Level:        Implementation details, algorithms
   ```

2. **Code-Specific Chunking:**
   ```python
   class CodeChunker:
       def chunk_repository(self, repo_path: str) -> List[CodeChunk]:
           chunks = []
           for file in self.walk_files(repo_path):
               ast = self.parse_ast(file)
               
               # Function-level chunks (primary unit)
               for func in ast.functions:
                   chunks.append(CodeChunk(
                       content=func.source,
                       metadata={
                           'type': 'function',
                           'name': func.name,
                           'file': file.path,
                           'signature': func.signature,
                           'docstring': func.docstring,
                           'imports': func.used_imports,
                           'calls': func.called_functions,
                           'called_by': self.find_callers(func),
                           'complexity': func.cyclomatic_complexity,
                       }
                   ))
               
               # Class-level chunks (with method summaries)
               for cls in ast.classes:
                   chunks.append(CodeChunk(
                       content=cls.summary,  # Class doc + method signatures
                       metadata={
                           'type': 'class',
                           'name': cls.name,
                           'methods': [m.name for m in cls.methods],
                           'inherits': cls.base_classes,
                       }
                   ))
           return chunks
   ```

3. **Retrieval Strategy for Code:**
   ```python
   class CodeRetriever:
       def retrieve(self, query: str, current_file: str, cursor_position: int):
           # Multiple retrieval strategies for code
           results = []
           
           # 1. Semantic search (natural language description → code)
           results += self.vector_search(query, filter={'type': 'function'})
           
           # 2. Structural search (find similar patterns by AST)
           if code_context := self.get_surrounding_code(current_file, cursor_position):
               results += self.ast_similarity_search(code_context)
           
           # 3. Dependency-aware retrieval (get related modules)
           imports = self.get_file_imports(current_file)
           for imp in imports:
               results += self.get_module_signatures(imp)
           
           # 4. Usage examples (how others use similar functions)
           results += self.find_usage_examples(query)
           
           # 5. Test files (show expected behavior)
           results += self.find_related_tests(current_file)
           
           return self.rerank_for_code(results, query, current_file)
   ```

4. **Repository-Level Context:**
   - **Dependency graph:** Understand module relationships for better context
   - **Type information:** Include type definitions and interfaces in retrieval
   - **Project conventions:** Detect and include style guides, patterns used in repo
   - **Recent changes:** Git history to understand evolving patterns
   - **README/docs:** Project-level documentation for architectural context

5. **Evaluation Metrics for Code RAG:**
   - **Functional correctness:** Generated code passes tests
   - **Style consistency:** Matches repository conventions
   - **Import accuracy:** Uses correct dependencies
   - **Type correctness:** Type-checks against project type system
   - **Hallucination rate:** References to non-existent APIs/functions

---

## Question 20: RAG Cost Optimization at Scale
**Difficulty: Staff Level | Topic: Cost Engineering | Asked at: Amazon, Microsoft, Startups**

Your RAG system costs $500K/month serving 50M queries. The CEO wants to reduce cost by 60% without degrading quality by more than 5%. Design a cost optimization strategy.

### Expected Answer:

**RAG Cost Optimization Strategy:**

1. **Current Cost Breakdown (Hypothetical $500K/month):**
   | Component | Monthly Cost | % of Total |
   |-----------|-------------|------------|
   | LLM inference | $300K | 60% |
   | Embedding generation | $50K | 10% |
   | Vector DB infrastructure | $80K | 16% |
   | Compute/networking | $50K | 10% |
   | Monitoring/logging | $20K | 4% |

2. **Optimization Strategies (Target: $200K/month):**

   **Strategy 1: LLM Cost Reduction (Save $180K)**
   - Route simple queries to cheaper models (GPT-3.5/Claude Haiku): 60% of queries
   - Implement semantic caching (20% hit rate): Save 20% of remaining
   - Reduce average context length via compression: 30% token reduction
   - Batch similar queries for efficiency
   
   ```python
   class CostAwareRouter:
       def route(self, query: str, complexity: str) -> LLMConfig:
           if complexity == 'simple':
               return LLMConfig(model='gpt-3.5-turbo', max_tokens=256)  # $0.002/query
           elif complexity == 'moderate':
               return LLMConfig(model='gpt-4-mini', max_tokens=512)  # $0.008/query
           else:
               return LLMConfig(model='gpt-4-turbo', max_tokens=1024)  # $0.03/query
   ```

   **Strategy 2: Embedding Cost Reduction (Save $35K)**
   - Cache embeddings for repeated/similar queries
   - Use smaller embedding model for initial retrieval, full model only for re-ranking
   - Batch embedding requests (10x cheaper than individual)
   - Reduce embedding dimensions (1024 → 512 with Matryoshka)

   **Strategy 3: Vector DB Optimization (Save $40K)**
   - Tiered storage: Move cold data to cheaper storage with on-demand loading
   - Reduce replication factor for non-critical namespaces (3 → 2)
   - Optimize index parameters (lower M value for less-queried collections)
   - Archive old embeddings (>6 months) to cold storage

   **Strategy 4: Infrastructure Optimization (Save $30K)**
   - Spot instances for batch processing (embedding generation)
   - Auto-scaling based on time-of-day patterns
   - Edge caching for geographically clustered queries
   - Compress stored embeddings (quantization: float32 → int8)

3. **Quality Preservation:**
   - A/B test each optimization independently
   - Quality gate: Block deployment if eval scores drop >5%
   - Maintain premium path for enterprise customers (no cost optimization)
   - Monthly quality audit comparing optimized vs full pipeline

4. **Implementation Priority (ROI ordered):**
   1. Semantic caching (1 week, saves $60K/month) ← Highest ROI
   2. Query complexity routing (2 weeks, saves $120K/month)
   3. Context compression (2 weeks, saves $40K/month)
   4. Embedding optimization (1 week, saves $35K/month)
   5. Infrastructure tuning (ongoing, saves $30K/month)

5. **Projected Results:**
   - Total savings: ~$285K/month (57% reduction)
   - Quality impact: 2-3% degradation (within budget)
   - Implementation time: 6-8 weeks
   - New monthly cost: ~$215K/month
