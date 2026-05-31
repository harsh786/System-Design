# RAG Systems Architecture - Staff Architect Interview

## Question 36: Production RAG Pipeline Design
**Difficulty: Staff Level | Topic: Information Retrieval + LLM | Asked at: OpenAI, Anthropic, Google, Databricks**

Design a production RAG system that handles 10M documents, supports multi-modal content (text, tables, images), maintains freshness within 5 minutes, and achieves >95% answer accuracy. Address chunking strategy, retrieval, re-ranking, and hallucination prevention.

### Expected Answer:

**Production RAG Architecture:**

1. **End-to-End Pipeline:**
   ```
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  Ingestion    │───▶│  Indexing     │───▶│  Serving     │
   │  Pipeline     │    │  Pipeline     │    │  Pipeline    │
   └──────────────┘    └──────────────┘    └──────────────┘
   
   Ingestion:
   Documents → Parse → Chunk → Embed → Store (Vector DB + Doc Store)
   
   Serving:
   Query → Embed → Retrieve → Re-rank → Generate → Validate → Respond
   ```

2. **Advanced Chunking Strategy:**
   ```python
   class HierarchicalChunker:
       """
       Multi-level chunking that preserves document structure.
       Key insight: Different retrieval needs require different granularities.
       """
       def chunk_document(self, document) -> List[Chunk]:
           chunks = []
           
           # Level 1: Document-level summary (for broad questions)
           doc_summary = self.summarize(document)
           chunks.append(Chunk(
               text=doc_summary,
               level='document',
               doc_id=document.id,
               metadata={'type': 'summary'}
           ))
           
           # Level 2: Section-level chunks (for topic questions)
           sections = self.split_by_sections(document)
           for section in sections:
               chunks.append(Chunk(
                   text=section.text,
                   level='section',
                   parent_id=document.id,
                   metadata={'heading': section.heading}
               ))
           
           # Level 3: Paragraph-level with overlap (for specific facts)
           paragraphs = self.split_by_semantics(
               document, 
               target_size=512,  # tokens
               overlap=64,       # token overlap
               respect_boundaries=True  # Don't split mid-sentence
           )
           for para in paragraphs:
               chunks.append(Chunk(
                   text=para.text,
                   level='paragraph',
                   parent_id=para.section_id,
                   metadata={
                       'position': para.position,
                       'context_before': para.prev_sentence,
                       'context_after': para.next_sentence,
                   }
               ))
           
           # Level 4: Table/figure extraction (specialized)
           for table in document.tables:
               chunks.append(Chunk(
                   text=self.table_to_text(table),
                   level='table',
                   parent_id=document.id,
                   metadata={'table_markdown': table.to_markdown()}
               ))
           
           return chunks
       
       def split_by_semantics(self, document, target_size, overlap, respect_boundaries):
           """Split using embedding similarity to find natural boundaries."""
           sentences = self.sentence_tokenize(document.text)
           embeddings = self.embed_sentences(sentences)
           
           # Find points where consecutive sentence similarity drops
           similarities = [
               cosine_similarity(embeddings[i], embeddings[i+1])
               for i in range(len(embeddings)-1)
           ]
           
           # Split at low-similarity points, respecting target_size
           split_points = self.find_optimal_splits(
               similarities, 
               sentence_lengths=[len(s) for s in sentences],
               target_chunk_tokens=target_size
           )
           
           return self.create_chunks_with_overlap(sentences, split_points, overlap)
   ```

3. **Multi-Stage Retrieval:**
   ```python
   class MultiStageRetriever:
       def retrieve(self, query: str, top_k: int = 5) -> List[Chunk]:
           # Stage 1: Query expansion (improve recall)
           expanded_queries = self.expand_query(query)
           # Original: "What's the revenue growth?"
           # Expanded: ["revenue growth rate", "year over year revenue", 
           #            "financial performance metrics"]
           
           # Stage 2: Hybrid retrieval (semantic + keyword)
           semantic_results = self.vector_search(expanded_queries, top_k=50)
           keyword_results = self.bm25_search(query, top_k=50)
           
           # Reciprocal Rank Fusion
           fused = self.rrf_merge(semantic_results, keyword_results, k=60)
           
           # Stage 3: Cross-encoder re-ranking (expensive but accurate)
           reranked = self.cross_encoder_rerank(query, fused[:30])
           
           # Stage 4: Diversity filtering (avoid redundant chunks)
           diverse = self.mmr_filter(reranked, diversity_weight=0.3)
           
           return diverse[:top_k]
       
       def expand_query(self, query):
           """Use LLM to generate alternative query formulations."""
           prompt = f"""Generate 3 alternative search queries for: "{query}"
           Focus on different aspects and terminology."""
           alternatives = self.llm.generate(prompt)
           return [query] + alternatives
       
       def rrf_merge(self, *result_lists, k=60):
           """Reciprocal Rank Fusion - robust fusion of multiple rankings."""
           scores = defaultdict(float)
           for results in result_lists:
               for rank, doc in enumerate(results):
                   scores[doc.id] += 1.0 / (k + rank + 1)
           return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```

4. **Hallucination Prevention:**
   ```python
   class HallucinationGuard:
       def validate_response(self, query, response, retrieved_chunks):
           """Multi-layer hallucination detection."""
           
           # Check 1: Attribution verification
           claims = self.extract_claims(response)
           for claim in claims:
               supported = self.verify_claim_against_sources(claim, retrieved_chunks)
               if not supported:
                   claim.mark_unsupported()
           
           # Check 2: Confidence calibration
           if self.count_unsupported(claims) / len(claims) > 0.3:
               # Too many unsupported claims - regenerate with stricter prompt
               return self.regenerate_with_citations(query, retrieved_chunks)
           
           # Check 3: Faithfulness score (NLI-based)
           faithfulness = self.nli_model.score(
               premise='\n'.join([c.text for c in retrieved_chunks]),
               hypothesis=response
           )
           
           if faithfulness < 0.7:
               return self.add_caveats(response, unsupported_claims)
           
           return response
       
       def generate_with_citations(self, query, chunks):
           """Force citation generation in output."""
           context = '\n'.join([f'[{i+1}] {c.text}' for i, c in enumerate(chunks)])
           prompt = f"""Answer based ONLY on the provided sources. 
           Cite sources using [1], [2], etc.
           If the sources don't contain the answer, say "I don't have enough information."
           
           Sources:
           {context}
           
           Question: {query}
           """
           return self.llm.generate(prompt)
   ```

5. **Freshness Architecture (5-minute SLA):**
   ```python
   class FreshnessManager:
       """Ensure index reflects document changes within 5 minutes."""
       
       def __init__(self):
           self.change_stream = ChangeDataCapture()  # CDC from source
           self.processing_queue = PriorityQueue()
       
       def process_changes(self):
           """Continuous processing of document changes."""
           for change in self.change_stream.listen():
               if change.type == 'CREATE':
                   chunks = self.chunker.chunk(change.document)
                   embeddings = self.embedder.batch_embed(chunks)
                   self.vector_db.upsert(chunks, embeddings)
               
               elif change.type == 'UPDATE':
                   # Identify affected chunks only
                   old_chunks = self.get_chunks(change.doc_id)
                   new_chunks = self.chunker.chunk(change.document)
                   diff = self.diff_chunks(old_chunks, new_chunks)
                   
                   self.vector_db.delete(diff.removed)
                   self.vector_db.upsert(diff.added)
                   self.vector_db.update(diff.modified)
               
               elif change.type == 'DELETE':
                   self.vector_db.delete_by_doc_id(change.doc_id)
               
               # Invalidate cache entries that used this document
               self.cache.invalidate_by_source(change.doc_id)
   ```

---

## Question 37: Evaluation and Testing for RAG Systems
**Difficulty: Staff Level | Topic: ML Evaluation | Asked at: Anthropic, Google, Microsoft**

How do you systematically evaluate a RAG system? Design an evaluation framework that measures retrieval quality, generation quality, and end-to-end performance. How do you handle regression testing when you change the embedding model or chunking strategy?

### Expected Answer:

**RAG Evaluation Framework:**

1. **Multi-Dimensional Metrics:**
   ```
   ┌─────────────────────────────────────────────────┐
   │           RAG Evaluation Dimensions              │
   ├─────────────────────────────────────────────────┤
   │ Retrieval Quality:                               │
   │   - Recall@K: Are relevant docs in top-K?       │
   │   - Precision@K: Are retrieved docs relevant?    │
   │   - MRR: How high is first relevant result?      │
   │   - NDCG: Quality of ranking                     │
   ├─────────────────────────────────────────────────┤
   │ Generation Quality:                              │
   │   - Faithfulness: Is answer supported by context?│
   │   - Relevance: Does answer address the query?    │
   │   - Completeness: Is the answer thorough?        │
   │   - Coherence: Is the answer well-structured?    │
   ├─────────────────────────────────────────────────┤
   │ End-to-End:                                      │
   │   - Answer correctness (vs ground truth)         │
   │   - Hallucination rate                           │
   │   - Latency (p50, p95, p99)                     │
   │   - Cost per query                              │
   └─────────────────────────────────────────────────┘
   ```

2. **Automated Evaluation Pipeline:**
   ```python
   class RAGEvaluator:
       def __init__(self):
           self.judge_model = load_model('gpt-4')  # LLM-as-judge
           self.test_set = self.load_golden_dataset()  # Human-labeled Q&A pairs
       
       def evaluate_full_pipeline(self, rag_system) -> EvalReport:
           results = []
           
           for test_case in self.test_set:
               # Run the RAG pipeline
               retrieved = rag_system.retrieve(test_case.query)
               response = rag_system.generate(test_case.query, retrieved)
               
               # Evaluate retrieval
               retrieval_metrics = self.eval_retrieval(
                   retrieved=retrieved,
                   relevant_docs=test_case.relevant_doc_ids
               )
               
               # Evaluate generation
               generation_metrics = self.eval_generation(
                   query=test_case.query,
                   response=response,
                   context=retrieved,
                   ground_truth=test_case.expected_answer
               )
               
               results.append({**retrieval_metrics, **generation_metrics})
           
           return self.aggregate_results(results)
       
       def eval_generation(self, query, response, context, ground_truth):
           """Use LLM-as-judge for generation quality."""
           # Faithfulness: Is the response grounded in context?
           faithfulness_prompt = f"""
           Context: {context}
           Response: {response}
           
           Rate faithfulness (1-5): Is every claim in the response 
           supported by the context? List unsupported claims.
           """
           faithfulness = self.judge_model.evaluate(faithfulness_prompt)
           
           # Correctness: Does it match ground truth?
           correctness_prompt = f"""
           Question: {query}
           Expected answer: {ground_truth}
           Actual answer: {response}
           
           Rate correctness (1-5): Does the actual answer convey 
           the same information as the expected answer?
           """
           correctness = self.judge_model.evaluate(correctness_prompt)
           
           return {
               'faithfulness': faithfulness.score,
               'correctness': correctness.score,
               'response_length': len(response.split()),
           }
   ```

3. **Regression Testing Framework:**
   ```python
   class RAGRegressionSuite:
       """Run when changing embedding model, chunking, or retrieval logic."""
       
       def __init__(self):
           # Golden dataset: 500+ hand-labeled examples across categories
           self.golden_set = {
               'factual_lookup': 100,      # Simple fact retrieval
               'multi_hop': 100,           # Requires combining multiple docs
               'temporal': 50,             # Time-sensitive questions
               'numerical': 50,            # Calculations from tables
               'negation': 50,             # "What is NOT true about..."
               'ambiguous': 50,            # Requires clarification
               'no_answer': 50,            # Answer not in corpus
               'adversarial': 50,          # Tricky/misleading queries
           }
       
       def run_regression(self, old_system, new_system):
           """Compare old vs new system across all test categories."""
           comparison = {}
           
           for category, test_cases in self.golden_set.items():
               old_scores = self.evaluate(old_system, test_cases)
               new_scores = self.evaluate(new_system, test_cases)
               
               comparison[category] = {
                   'old_accuracy': old_scores.mean(),
                   'new_accuracy': new_scores.mean(),
                   'delta': new_scores.mean() - old_scores.mean(),
                   'regressions': self.find_regressions(old_scores, new_scores),
                   'improvements': self.find_improvements(old_scores, new_scores),
               }
               
               # ALERT if any category regresses > 2%
               if comparison[category]['delta'] < -0.02:
                   self.alert(f"Regression in {category}: {comparison[category]['delta']:.1%}")
           
           return comparison
       
       def find_regressions(self, old_scores, new_scores):
           """Identify specific examples that got worse."""
           regressions = []
           for i, (old, new) in enumerate(zip(old_scores, new_scores)):
               if old.correct and not new.correct:
                   regressions.append({
                       'query': old.query,
                       'old_answer': old.response,
                       'new_answer': new.response,
                       'expected': old.ground_truth,
                   })
           return regressions
   ```

4. **Continuous Monitoring in Production:**
   ```python
   class RAGProductionMonitor:
       def track_live_metrics(self):
           """Real-time quality monitoring without ground truth."""
           
           # Proxy metrics (no labels needed):
           metrics = {
               # Retrieval signals
               'avg_retrieval_score': self.avg_top_k_similarity(),
               'empty_retrieval_rate': self.queries_with_no_results(),
               
               # Generation signals  
               'refusal_rate': self.count_responses_with('I don\'t know'),
               'avg_response_length': self.avg_token_count(),
               'citation_rate': self.responses_with_citations(),
               
               # User signals
               'thumbs_up_rate': self.positive_feedback_rate(),
               'follow_up_rate': self.users_who_ask_again(),  # Lower = better
               'copy_rate': self.users_who_copy_response(),   # Higher = better
           }
           
           # Statistical anomaly detection
           for metric, value in metrics.items():
               if self.is_anomalous(metric, value, window='1h'):
                   self.alert(f'{metric} anomaly: {value} vs baseline {self.baseline[metric]}')
   ```

5. **Synthetic Test Generation:**
   ```python
   class SyntheticTestGenerator:
       """Generate test cases automatically from the corpus."""
       
       def generate_test_set(self, corpus, n_questions=1000):
           test_cases = []
           
           for doc in random.sample(corpus, n_questions):
               # Generate question from document
               question = self.llm.generate(
                   f"Generate a specific question that can be answered "
                   f"using this document:\n{doc.text}\n\nQuestion:"
               )
               
               # Generate expected answer
               answer = self.llm.generate(
                   f"Based on this document:\n{doc.text}\n\n"
                   f"Answer this question: {question}"
               )
               
               test_cases.append(TestCase(
                   query=question,
                   expected_answer=answer,
                   relevant_doc_ids=[doc.id],
                   category=self.classify_question_type(question)
               ))
           
           # Human review a sample (10%) for quality
           return test_cases
   ```

---

## Question 38: Multi-Tenant RAG with Data Isolation
**Difficulty: Staff Level | Topic: Security & Architecture | Asked at: Microsoft, Salesforce, ServiceNow**

Design a multi-tenant RAG system where each tenant's data must be completely isolated, but the system shares infrastructure for cost efficiency. Address access control, embedding isolation, and preventing cross-tenant data leakage during retrieval.

### Expected Answer:

**Multi-Tenant RAG Architecture:**

1. **Isolation Levels:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │ Level 1: Logical Isolation (Shared Everything)       │
   │ - Shared vector DB with tenant_id filter             │
   │ - Cheapest, highest density                          │
   │ - Risk: Filter bypass, side-channel attacks          │
   ├─────────────────────────────────────────────────────┤
   │ Level 2: Collection Isolation (Shared Cluster)       │
   │ - Separate collection/namespace per tenant           │
   │ - Moderate cost, good isolation                      │
   │ - Risk: Noisy neighbor, resource exhaustion          │
   ├─────────────────────────────────────────────────────┤
   │ Level 3: Physical Isolation (Dedicated Instances)    │
   │ - Dedicated vector DB instance per tenant            │
   │ - Expensive, perfect isolation                       │
   │ - For: Enterprise, regulated industries              │
   └─────────────────────────────────────────────────────┘
   ```

2. **Recommended Hybrid Architecture:**
   ```python
   class MultiTenantRAG:
       def __init__(self):
           # Tier assignment based on tenant plan
           self.tier_map = {
               'free': 'shared_pool',      # Level 1: filter-based
               'pro': 'dedicated_namespace', # Level 2: namespace isolation
               'enterprise': 'dedicated_instance',  # Level 3: full isolation
           }
       
       def retrieve(self, tenant_id, query, top_k=5):
           tier = self.get_tenant_tier(tenant_id)
           
           if tier == 'shared_pool':
               # CRITICAL: Always enforce tenant filter
               return self.shared_db.search(
                   vector=self.embed(query),
                   filter={'tenant_id': tenant_id},  # Mandatory filter
                   top_k=top_k
               )
           elif tier == 'dedicated_namespace':
               namespace = f'tenant_{tenant_id}'
               return self.shared_cluster.search(
                   vector=self.embed(query),
                   namespace=namespace,
                   top_k=top_k
               )
           else:
               db = self.get_dedicated_instance(tenant_id)
               return db.search(vector=self.embed(query), top_k=top_k)
       
       def ingest(self, tenant_id, documents):
           """Ingest with strict tenant tagging."""
           chunks = self.chunker.chunk(documents)
           
           # Tag EVERY chunk with tenant_id (defense in depth)
           for chunk in chunks:
               chunk.metadata['tenant_id'] = tenant_id
               chunk.metadata['ingested_at'] = time.time()
               chunk.metadata['acl'] = self.get_tenant_acl(tenant_id)
           
           embeddings = self.embed_batch(chunks)
           self.store(tenant_id, chunks, embeddings)
   ```

3. **Preventing Cross-Tenant Leakage:**
   ```python
   class IsolationGuard:
       """Defense-in-depth against cross-tenant data leakage."""
       
       def validate_retrieval(self, tenant_id, results):
           """Post-retrieval validation - catch any filter failures."""
           for result in results:
               if result.metadata.get('tenant_id') != tenant_id:
                   # CRITICAL: Log security incident, drop result
                   self.security_alert(
                       f"Cross-tenant leak detected: "
                       f"tenant {tenant_id} received doc from "
                       f"tenant {result.metadata['tenant_id']}"
                   )
                   results.remove(result)
           return results
       
       def prevent_embedding_leakage(self):
           """
           Concern: Can you reverse-engineer content from embeddings?
           Mitigation: Tenant-specific embedding perturbation.
           """
           pass  # See approach below
       
       def audit_access(self, tenant_id, query, results):
           """Complete audit trail for compliance."""
           self.audit_log.write({
               'timestamp': time.time(),
               'tenant_id': tenant_id,
               'query_hash': hash(query),  # Don't log actual query (PII)
               'result_doc_ids': [r.id for r in results],
               'result_count': len(results),
           })
   ```

4. **Shared Model with Tenant Context:**
   ```python
   class TenantAwareLLM:
       """Single LLM serving all tenants with proper isolation."""
       
       def generate(self, tenant_id, query, context):
           # Tenant-specific system prompt (configurable per tenant)
           system_prompt = self.get_tenant_system_prompt(tenant_id)
           
           # Ensure context only contains tenant's own documents
           verified_context = self.isolation_guard.validate(tenant_id, context)
           
           # Generate with strict grounding instruction
           response = self.llm.generate(
               system=system_prompt,
               context=verified_context,
               query=query,
               stop_sequences=self.get_tenant_stop_sequences(tenant_id)
           )
           
           # Post-generation PII filter
           response = self.pii_filter.scrub(response, tenant_id)
           
           return response
       
       def prevent_prompt_injection(self, tenant_id, query):
           """Prevent tenant A from crafting prompts that leak tenant B's data."""
           # Input sanitization
           sanitized = self.sanitize_input(query)
           
           # Detect injection attempts
           if self.injection_detector.is_suspicious(sanitized):
               self.security_alert(tenant_id, 'prompt_injection_attempt')
               return "I cannot process this request."
           
           return sanitized
   ```

5. **Resource Isolation & Fair Scheduling:**
   ```python
   class TenantResourceManager:
       """Prevent noisy neighbor problems."""
       
       def __init__(self):
           self.rate_limiters = {}  # Per-tenant rate limits
           self.quotas = {}        # Per-tenant storage quotas
       
       def enforce_limits(self, tenant_id, operation):
           tenant_plan = self.get_plan(tenant_id)
           
           limits = {
               'free':       {'qps': 10,  'storage_gb': 1,   'docs': 10_000},
               'pro':        {'qps': 100, 'storage_gb': 50,  'docs': 1_000_000},
               'enterprise': {'qps': 1000,'storage_gb': 500, 'docs': 10_000_000},
           }
           
           if not self.rate_limiters[tenant_id].allow(operation):
               raise RateLimitExceeded(f"Tenant {tenant_id} exceeded {limits[tenant_plan]['qps']} QPS")
   ```

---

## Question 39: Agentic RAG with Tool Use
**Difficulty: Staff Level | Topic: AI Agents | Asked at: OpenAI, Anthropic, LangChain, Google**

Design an agentic RAG system where the LLM can decide to search multiple sources, refine queries, call APIs, and synthesize information across multiple retrieval steps. How do you handle loops, token budget management, and ensuring termination?

### Expected Answer:

**Agentic RAG Architecture:**

1. **Agent Loop Design:**
   ```python
   class AgenticRAG:
       def __init__(self):
           self.tools = {
               'vector_search': VectorSearchTool(),
               'web_search': WebSearchTool(),
               'sql_query': SQLQueryTool(),
               'calculator': CalculatorTool(),
               'code_executor': CodeExecutorTool(),
           }
           self.max_iterations = 10
           self.token_budget = 32000  # Total context budget
       
       def answer(self, query: str) -> AgentResponse:
           messages = [{'role': 'user', 'content': query}]
           iteration = 0
           tokens_used = 0
           
           while iteration < self.max_iterations:
               iteration += 1
               
               # LLM decides: answer directly or use a tool
               action = self.llm.plan(messages, self.tools, self.token_budget - tokens_used)
               
               if action.type == 'final_answer':
                   return AgentResponse(
                       answer=action.content,
                       sources=self.collect_sources(messages),
                       iterations=iteration,
                       tokens_used=tokens_used
                   )
               
               elif action.type == 'tool_call':
                   # Execute the tool
                   result = self.execute_tool(action.tool, action.params)
                   
                   # Add result to context
                   messages.append({
                       'role': 'tool',
                       'tool': action.tool,
                       'content': self.truncate_if_needed(result, budget_remaining)
                   })
                   
                   tokens_used += self.count_tokens(result)
               
               # Budget check
               if tokens_used > self.token_budget * 0.9:
                   # Force final answer with what we have
                   return self.force_answer(messages)
           
           # Max iterations reached
           return self.force_answer(messages)
   ```

2. **Query Decomposition & Planning:**
   ```python
   class QueryPlanner:
       """Break complex questions into retrieval sub-tasks."""
       
       def plan(self, query: str) -> List[SubTask]:
           planning_prompt = f"""
           Decompose this question into retrieval steps:
           "{query}"
           
           For each step, specify:
           1. What information to retrieve
           2. Which tool to use (vector_search, web_search, sql_query)
           3. Dependencies on previous steps
           
           Output as JSON.
           """
           
           plan = self.llm.generate(planning_prompt)
           return self.parse_plan(plan)
       
       # Example output for "Compare Q3 revenue to competitors":
       # [
       #   {"step": 1, "action": "sql_query", "query": "SELECT revenue FROM financials WHERE quarter='Q3'", "deps": []},
       #   {"step": 2, "action": "web_search", "query": "competitor Q3 2024 revenue", "deps": []},
       #   {"step": 3, "action": "synthesize", "query": "Compare our Q3 revenue to competitors", "deps": [1, 2]}
       # ]
   ```

3. **Adaptive Retrieval (Self-Reflective RAG):**
   ```python
   class SelfReflectiveRetriever:
       """Agent evaluates its own retrieval quality and retries if needed."""
       
       def retrieve_with_reflection(self, query, max_attempts=3):
           for attempt in range(max_attempts):
               # Retrieve
               results = self.retriever.search(query, top_k=5)
               
               # Self-evaluate: Are these results sufficient?
               evaluation = self.llm.evaluate(
                   f"Query: {query}\n"
                   f"Retrieved documents: {results}\n"
                   f"Are these documents sufficient to answer the query? "
                   f"If not, what's missing?"
               )
               
               if evaluation.sufficient:
                   return results
               
               # Refine query based on what's missing
               refined_query = self.llm.generate(
                   f"Original query: {query}\n"
                   f"Gap identified: {evaluation.missing_info}\n"
                   f"Generate a better search query to find the missing information."
               )
               
               # Search again with refined query
               additional = self.retriever.search(refined_query, top_k=3)
               results.extend(additional)
               
               query = refined_query  # Update for next iteration
           
           return results
   ```

4. **Token Budget Management:**
   ```python
   class TokenBudgetManager:
       """Prevent context overflow and manage costs."""
       
       def __init__(self, total_budget=32000):
           self.total_budget = total_budget
           self.allocations = {
               'system_prompt': 500,
               'query': 200,
               'tool_results': 20000,  # Largest allocation
               'reasoning': 5000,
               'final_answer': 2000,
               'buffer': 4300,
           }
       
       def allocate_for_tool_result(self, result_text, priority='normal'):
           available = self.get_remaining_budget('tool_results')
           result_tokens = self.count_tokens(result_text)
           
           if result_tokens <= available:
               return result_text  # Fits entirely
           
           # Must compress
           if priority == 'high':
               # Summarize to fit
               return self.summarize_to_fit(result_text, available)
           else:
               # Truncate with notice
               truncated = self.truncate_tokens(result_text, available - 50)
               return truncated + "\n[TRUNCATED - request more specific query]"
       
       def should_stop(self) -> bool:
           """Signal agent to wrap up."""
           remaining = self.total_budget - self.tokens_used
           return remaining < self.allocations['final_answer'] + self.allocations['buffer']
   ```

5. **Termination Guarantees:**
   ```python
   class TerminationGuard:
       """Ensure agent always terminates in bounded time/cost."""
       
       def __init__(self):
           self.limits = {
               'max_iterations': 10,
               'max_time_seconds': 30,
               'max_tokens': 50000,
               'max_tool_calls': 15,
               'max_cost_dollars': 0.50,
           }
           self.start_time = None
           self.metrics = defaultdict(int)
       
       def check(self) -> bool:
           """Returns True if agent should terminate."""
           elapsed = time.time() - self.start_time
           
           if elapsed > self.limits['max_time_seconds']:
               return True
           if self.metrics['iterations'] >= self.limits['max_iterations']:
               return True
           if self.metrics['total_tokens'] >= self.limits['max_tokens']:
               return True
           if self.metrics['tool_calls'] >= self.limits['max_tool_calls']:
               return True
           
           return False
       
       def detect_loops(self, actions_history):
           """Detect if agent is stuck in a loop."""
           if len(actions_history) < 4:
               return False
           
           # Check for repeated tool calls with same parameters
           recent = actions_history[-4:]
           if len(set(str(a) for a in recent)) <= 2:
               return True  # Same 1-2 actions repeating
           
           return False
   ```

---

## Question 40: RAG for Structured + Unstructured Data (Text-to-SQL + Vector Search)
**Difficulty: Staff Level | Topic: Hybrid Systems | Asked at: Databricks, Snowflake, Google**

Design a unified query system that can answer questions requiring both structured data (SQL databases) and unstructured data (documents). The system should automatically determine whether to query SQL, vector search, or both, and synthesize the results.

### Expected Answer:

**Hybrid Structured + Unstructured RAG:**

1. **Architecture Overview:**
   ```
   User Query: "Which customers in the Northeast had complaints 
                about delivery delays last quarter?"
   
   ┌─────────────────────────────────────────────────────┐
   │              Query Intent Classifier                  │
   │  → Structured (SQL): customer region, time filter    │
   │  → Unstructured (RAG): complaint content analysis    │
   │  → HYBRID: Need both!                                │
   └─────────────┬────────────────────────┬───────────────┘
                 │                        │
        ┌────────▼─────────┐    ┌────────▼─────────┐
        │  Text-to-SQL     │    │  Vector Search    │
        │  "SELECT from    │    │  "delivery delay  │
        │   customers      │    │   complaints"     │
        │   WHERE region   │    │   filtered by     │
        │   ='Northeast'"  │    │   customer_ids    │
        └────────┬─────────┘    └────────┬─────────┘
                 │                        │
                 └───────────┬────────────┘
                             │
                    ┌────────▼─────────┐
                    │   Synthesizer    │
                    │   (Join + LLM)   │
                    └──────────────────┘
   ```

2. **Intent Classification & Query Planning:**
   ```python
   class HybridQueryPlanner:
       def plan(self, query: str, schema_context: str) -> QueryPlan:
           planning_prompt = f"""
           Given this user question and available data sources, 
           create an execution plan.
           
           Available SQL tables:
           {schema_context}
           
           Available document collections:
           - support_tickets (customer complaints, feedback)
           - product_docs (manuals, specs)
           - internal_wiki (policies, procedures)
           
           Question: {query}
           
           Determine:
           1. What structured data is needed? (SQL query)
           2. What unstructured data is needed? (search query)
           3. How to combine results?
           4. Execution order (parallel or sequential)?
           """
           
           plan = self.llm.generate(planning_prompt)
           return self.parse_plan(plan)
       
       # Example plan:
       # {
       #   "sql_queries": [
       #     {"query": "SELECT customer_id, name FROM customers WHERE region='Northeast'",
       #      "purpose": "Get customer list for filtering"}
       #   ],
       #   "vector_queries": [
       #     {"query": "delivery delay complaint",
       #      "collection": "support_tickets",
       #      "filters": {"date_range": "Q3 2024", "customer_ids": "$sql_result_1"},
       #      "depends_on": "sql_query_1"}
       #   ],
       #   "execution_order": "sequential",
       #   "synthesis": "List customers with their specific complaints"
       # }
   ```

3. **Text-to-SQL with Safety:**
   ```python
   class SafeTextToSQL:
       def __init__(self, db_connection, schema):
           self.db = db_connection
           self.schema = schema
           self.query_validator = SQLValidator()
       
       def generate_and_execute(self, natural_query, context=None):
           # Generate SQL
           sql = self.llm.generate(
               f"Schema:\n{self.schema}\n\n"
               f"Convert to SQL: {natural_query}\n"
               f"Rules: SELECT only, no mutations, limit 1000 rows"
           )
           
           # Validate (CRITICAL for security)
           validation = self.query_validator.validate(sql)
           if not validation.safe:
               raise SecurityError(f"Unsafe SQL: {validation.reason}")
           
           # Execute with timeout and row limit
           try:
               results = self.db.execute(sql, timeout=10, max_rows=1000)
               return SQLResult(query=sql, data=results, row_count=len(results))
           except Exception as e:
               # Self-correction: try to fix the SQL
               fixed_sql = self.llm.generate(
                   f"This SQL failed: {sql}\nError: {e}\nFix it:"
               )
               return self.db.execute(fixed_sql, timeout=10, max_rows=1000)
       
       class SQLValidator:
           def validate(self, sql: str) -> ValidationResult:
               """Prevent dangerous SQL operations."""
               dangerous_patterns = [
                   r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', 
                   r'\bINSERT\b', r'\bALTER\b', r'\bTRUNCATE\b',
                   r'\bEXEC\b', r'--', r'/\*', r'\bUNION\b.*\bSELECT\b'
               ]
               for pattern in dangerous_patterns:
                   if re.search(pattern, sql, re.IGNORECASE):
                       return ValidationResult(safe=False, reason=f"Matched: {pattern}")
               return ValidationResult(safe=True)
   ```

4. **Result Synthesis:**
   ```python
   class HybridResultSynthesizer:
       def synthesize(self, query, sql_results, vector_results):
           """Combine structured and unstructured results into coherent answer."""
           
           # Format SQL results as table
           sql_context = self.format_sql_results(sql_results)
           
           # Format retrieved documents
           doc_context = self.format_documents(vector_results)
           
           synthesis_prompt = f"""
           User question: {query}
           
           Structured data (from database):
           {sql_context}
           
           Relevant documents:
           {doc_context}
           
           Synthesize a comprehensive answer combining both data sources.
           Cite specific numbers from the database and quote relevant 
           document excerpts. If there are contradictions between sources,
           note them.
           """
           
           return self.llm.generate(synthesis_prompt)
       
       def format_sql_results(self, results):
           """Convert SQL results to LLM-friendly format."""
           if results.row_count > 20:
               # Summarize large result sets
               return (
                   f"Query returned {results.row_count} rows. "
                   f"Summary statistics:\n{self.compute_stats(results)}\n"
                   f"Top 10 rows:\n{results.to_markdown(limit=10)}"
               )
           return results.to_markdown()
   ```

5. **Schema-Aware Embedding for Unified Search:**
   ```python
   class UnifiedSearchIndex:
       """Index both structured schema and unstructured docs in same space."""
       
       def build_schema_embeddings(self, database_schema):
           """Embed table/column descriptions for routing."""
           schema_chunks = []
           for table in database_schema.tables:
               # Embed table description
               schema_chunks.append({
                   'text': f"Table: {table.name}. {table.description}. "
                          f"Columns: {', '.join(c.name + ': ' + c.description for c in table.columns)}",
                   'type': 'schema',
                   'table': table.name,
               })
           
           self.schema_index.upsert(schema_chunks)
       
       def route_query(self, query):
           """Determine if query needs SQL, vector search, or both."""
           # Search both schema index and document index
           schema_matches = self.schema_index.search(query, top_k=3)
           doc_matches = self.doc_index.search(query, top_k=3)
           
           schema_relevance = max(m.score for m in schema_matches) if schema_matches else 0
           doc_relevance = max(m.score for m in doc_matches) if doc_matches else 0
           
           if schema_relevance > 0.8 and doc_relevance > 0.8:
               return 'hybrid'
           elif schema_relevance > doc_relevance:
               return 'sql'
           else:
               return 'vector'
   ```
