# RAG Advanced Patterns - Staff Architect Interview

## Question 6: Agentic RAG Architecture
**Difficulty: Staff Level | Topic: Agentic Systems | Asked at: OpenAI, Google DeepMind**

Design an agentic RAG system where the retrieval strategy is dynamically determined by an AI agent. The agent should decide what to retrieve, how many times to retrieve, and when to stop retrieving.

### Expected Answer:

**Agentic RAG Architecture:**

1. **Core Concept:** Instead of fixed retrieve-then-generate, an LLM agent orchestrates retrieval as a tool, making iterative decisions about what information it needs.

2. **Architecture:**
   ```
   User Query → Planning Agent → [Action Selection Loop]
                                        ↓
                    ┌─────────────────────────────────────────┐
                    │  Actions Available:                       │
                    │  - search_documents(query, filters)       │
                    │  - search_knowledge_graph(entity, rel)    │
                    │  - search_web(query)                      │
                    │  - calculate(expression)                  │
                    │  - ask_clarification(question)            │
                    │  - synthesize_answer(context)             │
                    └─────────────────────────────────────────┘
                                        ↓
                              Observation → Reasoning → Next Action
                                        ↓
                              [Loop until sufficient info or max_steps]
                                        ↓
                              Final Synthesis → Response
   ```

3. **Implementation with ReAct Pattern:**
   ```python
   class AgenticRAG:
       def __init__(self, llm, tools, max_steps=5):
           self.llm = llm
           self.tools = tools
           self.max_steps = max_steps
       
       async def execute(self, query: str) -> Response:
           context = AgentContext(query=query, history=[])
           
           for step in range(self.max_steps):
               # Agent decides next action
               action = await self.llm.plan(
                   query=query,
                   history=context.history,
                   available_tools=self.tools
               )
               
               if action.type == 'synthesize':
                   return await self.generate_final(query, context)
               
               # Execute tool
               observation = await self.tools[action.name].execute(action.params)
               context.history.append((action, observation))
               
               # Evaluate if we have enough
               sufficiency = await self.evaluate_sufficiency(query, context)
               if sufficiency.score > 0.9:
                   return await self.generate_final(query, context)
           
           return await self.generate_final(query, context)
   ```

4. **Key Design Decisions:**
   - **Budget management:** Token/cost budget per query, agent must optimize within constraints
   - **Retrieval diversity:** Agent tracks what's been retrieved to avoid redundancy
   - **Failure recovery:** If retrieval returns nothing useful, agent reformulates or tries different source
   - **Parallelism:** Agent can issue multiple retrievals simultaneously when independent
   - **Memory:** Short-term (within query) and long-term (across queries) memory for patterns

5. **Production Considerations:**
   - Timeout management: Max 5 steps or 10 seconds per query
   - Cost caps: Maximum $0.05 per query budget
   - Observability: Log full reasoning chain for debugging
   - A/B testing: Compare against fixed pipeline for quality/cost trade-off

---

## Question 7: RAG for Structured + Unstructured Data
**Difficulty: Staff Level | Topic: Hybrid Data | Asked at: Snowflake, Databricks**

Design a RAG system that seamlessly queries across structured databases (SQL), unstructured documents (PDFs), and semi-structured data (JSON/APIs). How do you create a unified query interface?

### Expected Answer:

**Unified Query Architecture:**

1. **Query Understanding Layer:**
   ```python
   class UnifiedQueryRouter:
       def route(self, query: str) -> QueryPlan:
           # Classify query intent and required data sources
           intent = self.classify_intent(query)
           # e.g., "What were Q3 sales for customers mentioned in the support escalations?"
           # Requires: SQL (sales data) + Unstructured (support tickets)
           
           plan = QueryPlan()
           if intent.needs_structured:
               plan.add(SQLQuery(self.generate_sql(query)))
           if intent.needs_unstructured:
               plan.add(VectorSearch(self.generate_search_query(query)))
           if intent.needs_api:
               plan.add(APICall(self.determine_endpoint(query)))
           
           plan.set_fusion_strategy(intent.fusion_type)
           return plan
   ```

2. **Data Source Adapters:**
   - **SQL Adapter:** Text-to-SQL with schema awareness (table descriptions, relationships)
   - **Vector Adapter:** Standard RAG retrieval with metadata filtering
   - **API Adapter:** OpenAPI spec-aware query construction
   - **Knowledge Graph Adapter:** SPARQL/Cypher generation for relationship queries

3. **Fusion Strategies:**
   - **Sequential:** SQL results feed into vector search filters
   - **Parallel:** Both execute independently, results merged
   - **Iterative:** Results from one inform queries to another
   
   ```python
   class FusionEngine:
       async def fuse(self, results: Dict[str, Any], strategy: str) -> Context:
           if strategy == 'sequential':
               sql_results = results['sql']
               # Use SQL results to filter vector search
               vector_results = await self.vector_search(
                   query, filters={'entity_id': sql_results.ids}
               )
               return self.merge(sql_results, vector_results)
           elif strategy == 'parallel':
               return self.reciprocal_rank_fusion(results.values())
   ```

4. **Schema-Aware Context Assembly:**
   - SQL results → Natural language summary + raw data table
   - Vector results → Relevant text chunks with citations
   - API results → Structured response formatting
   - Combined context respects token budget with priority scoring

5. **Challenges:**
   - **Consistency:** SQL gives exact numbers, vector search gives approximate context — reconcile conflicts
   - **Latency:** SQL is fast (50ms), vector is fast (30ms), but combined with LLM adds up
   - **Security:** Different data sources have different ACLs — enforce at query time
   - **Freshness:** SQL is real-time, vector index may be hours behind

---

## Question 8: Conversational RAG with Memory
**Difficulty: Staff Level | Topic: Stateful Systems | Asked at: Microsoft, Google**

Design a conversational RAG system that maintains context across multi-turn conversations while efficiently managing memory, context windows, and retrieval relevance across turns.

### Expected Answer:

**Conversational RAG Architecture:**

1. **Memory Hierarchy:**
   ```
   ┌─────────────────────────────────┐
   │  Working Memory (Current Turn)   │ ← Active context window
   ├─────────────────────────────────┤
   │  Short-term Memory (Session)     │ ← Conversation buffer (last N turns)
   ├─────────────────────────────────┤
   │  Long-term Memory (User Profile) │ ← Persistent preferences/facts
   └─────────────────────────────────┘
   ```

2. **Query Reformulation:**
   ```python
   class ConversationalQueryRewriter:
       def rewrite(self, current_query: str, history: List[Turn]) -> str:
           """
           Resolves coreferences and adds context from history.
           "What about their pricing?" → "What is Pinecone's pricing for enterprise tier?"
           """
           prompt = f"""Given conversation history:
           {self.format_history(history)}
           
           Rewrite this query to be standalone (resolve all pronouns/references):
           Query: {current_query}
           Standalone query:"""
           
           return self.llm.generate(prompt)
   ```

3. **Context Window Management:**
   - **Sliding window:** Keep last 5 turns verbatim
   - **Summarization:** Summarize turns 6-20 into a paragraph
   - **Key facts extraction:** Extract and store user preferences, constraints, decisions
   - **Token budget allocation:**
     - System prompt: 500 tokens
     - Conversation summary: 300 tokens
     - Recent turns: 1000 tokens
     - Retrieved context: 2000 tokens
     - Generation budget: 1000 tokens

4. **Retrieval-Aware Memory:**
   ```python
   class MemoryAwareRetriever:
       def retrieve(self, query, conversation_state):
           # Don't re-retrieve information already in context
           already_retrieved = conversation_state.retrieved_doc_ids
           
           # Combine current query with conversation context for better retrieval
           enriched_query = self.enrich_with_context(query, conversation_state)
           
           results = self.vector_search(
               enriched_query,
               exclude_ids=already_retrieved,  # Avoid redundancy
               boost_related=conversation_state.topic_entities  # Boost relevance
           )
           
           return results
   ```

5. **Production Considerations:**
   - Session storage: Redis with 24hr TTL for conversation state
   - Memory compaction: Background job summarizes old conversations
   - Privacy: User can request memory deletion (GDPR compliance)
   - Graceful degradation: If memory service is down, fall back to stateless RAG

---

## Question 9: RAG Evaluation Framework
**Difficulty: Staff Level | Topic: Quality & Evaluation | Asked at: Anthropic, Meta**

Design a comprehensive RAG evaluation framework that measures retrieval quality, generation accuracy, and end-to-end system performance. How do you build automated evaluation pipelines for continuous monitoring?

### Expected Answer:

**Multi-Level RAG Evaluation Framework:**

1. **Retrieval Metrics:**
   | Metric | Description | Target |
   |--------|-------------|--------|
   | Recall@K | Relevant docs in top K | >0.85 |
   | Precision@K | Precision of top K results | >0.70 |
   | MRR | Mean Reciprocal Rank | >0.75 |
   | NDCG | Normalized DCG | >0.80 |
   | Context Relevance | % of retrieved context actually used | >0.60 |

2. **Generation Metrics:**
   | Metric | Description | Target |
   |--------|-------------|--------|
   | Faithfulness | Answer supported by context (NLI) | >0.95 |
   | Answer Relevance | Answer addresses the question | >0.90 |
   | Completeness | All aspects of question addressed | >0.85 |
   | Hallucination Rate | Claims not in context | <0.05 |
   | Citation Accuracy | Correct source attribution | >0.90 |

3. **Automated Evaluation Pipeline:**
   ```python
   class RAGEvaluator:
       def __init__(self):
           self.retrieval_judge = RetrievalRelevanceModel()
           self.faithfulness_checker = NLIModel()  # Natural Language Inference
           self.answer_judge = LLMJudge(model='gpt-4')
       
       async def evaluate(self, query, retrieved_docs, response, ground_truth=None):
           scores = {}
           
           # Retrieval quality
           scores['context_relevance'] = self.retrieval_judge.score(query, retrieved_docs)
           scores['context_coverage'] = self.coverage_score(ground_truth, retrieved_docs)
           
           # Generation quality  
           scores['faithfulness'] = self.faithfulness_checker.check(response, retrieved_docs)
           scores['hallucination'] = self.detect_hallucination(response, retrieved_docs)
           
           # End-to-end
           if ground_truth:
               scores['correctness'] = self.answer_judge.compare(response, ground_truth)
           
           # LLM-as-judge for subjective quality
           scores['helpfulness'] = await self.llm_judge(query, response)
           
           return EvalResult(scores=scores, pass_threshold=self.thresholds)
   ```

4. **Continuous Monitoring Pipeline:**
   - **Online metrics:** Latency, token usage, error rates, user feedback (thumbs up/down)
   - **Offline eval:** Nightly runs against golden test set (500+ curated Q&A pairs)
   - **Regression detection:** Alert if any metric drops >5% from 7-day rolling average
   - **A/B testing framework:** Split traffic for retrieval/generation experiments
   - **Human-in-the-loop:** Weekly sample review by domain experts (50 random queries)

5. **Evaluation Dataset Management:**
   - Synthetic generation: Use LLMs to generate Q&A pairs from documents
   - Human annotation: Quarterly refresh with expert annotators
   - Adversarial examples: Include edge cases, ambiguous queries, multi-hop questions
   - Version control: Track eval set changes alongside model changes

---

## Question 10: RAG at Global Scale
**Difficulty: Staff Level | Topic: Distributed Systems | Asked at: Google, Microsoft, Amazon**

Design a RAG system that serves users globally across 5 continents with data sovereignty requirements. Documents are in 20+ languages. How do you handle multi-region deployment, cross-lingual retrieval, and compliance?

### Expected Answer:

**Global RAG Architecture:**

1. **Multi-Region Deployment:**
   ```
   ┌────────────────────────────────────────────────────────┐
   │                    Global Load Balancer                  │
   │              (Latency-based routing)                     │
   └─────────┬──────────┬──────────┬──────────┬─────────────┘
             │          │          │          │
        ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐
        │US-East │ │EU-West │ │AP-South│ │AP-East │
        │        │ │        │ │        │ │        │
        │Vector  │ │Vector  │ │Vector  │ │Vector  │
        │DB      │ │DB      │ │DB      │ │DB      │
        │(Local) │ │(Local) │ │(Local) │ │(Local) │
        └────────┘ └────────┘ └────────┘ └────────┘
   ```

2. **Data Sovereignty Compliance:**
   - **Data residency:** Documents tagged with jurisdiction, stored only in compliant regions
   - **Cross-border queries:** If user in EU queries US data → federated retrieval with result projection (only non-PII fields cross borders)
   - **Encryption:** Data encrypted at rest with region-specific keys (AWS KMS per region)
   - **Audit logging:** All cross-border data access logged for compliance

3. **Multi-Lingual Retrieval:**
   ```python
   class MultiLingualRetriever:
       def __init__(self):
           self.multilingual_encoder = load_model('multilingual-e5-large')
           # Single embedding space for all languages
       
       def retrieve(self, query: str, user_lang: str, target_langs: List[str] = None):
           # Encode query (works in any language)
           query_embedding = self.multilingual_encoder.encode(query)
           
           # Search across all languages in unified space
           results = self.vector_db.search(
               query_embedding,
               filter={'language': {'$in': target_langs or self.all_langs}}
           )
           
           # Translate results to user's language if needed
           translated = self.translate_results(results, target_lang=user_lang)
           return translated
   ```

4. **Consistency & Replication Strategy:**
   - **Global documents:** Replicated to all regions (eventual consistency, 5-min lag)
   - **Regional documents:** Stay in region, accessible only from that region
   - **Index synchronization:** Event-driven replication via Kafka/EventBridge
   - **Conflict resolution:** Last-write-wins for metadata, append-only for documents
   - **Cache invalidation:** TTL-based with pub/sub for urgent updates

5. **Performance Optimization:**
   - Edge caching for frequently asked queries (CloudFront/Akamai)
   - Regional embedding inference (GPU clusters per region)
   - Pre-computed embeddings for common queries
   - Tiered storage: Hot (in-memory HNSW) → Warm (SSD) → Cold (S3 + on-demand loading)
   - Query routing: Simple queries handled at edge, complex queries routed to primary region
