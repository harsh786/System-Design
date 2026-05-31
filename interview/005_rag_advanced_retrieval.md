# RAG Advanced Retrieval Strategies - Staff Architect Interview

## Question 21: Hypothetical Document Embedding (HyDE)
**Difficulty: Staff Level | Topic: Advanced Retrieval | Asked at: Google Research, Meta AI**

Explain HyDE (Hypothetical Document Embedding) and when it outperforms standard query embedding. Design a production system that dynamically chooses between HyDE and direct embedding based on query characteristics.

### Expected Answer:

**HyDE Architecture & Production Implementation:**

1. **Core Concept:**
   - Problem: User queries are often short/vague, creating a semantic gap with detailed documents
   - Solution: Use LLM to generate a hypothetical answer, then embed THAT instead of the query
   - The hypothetical document is closer in embedding space to actual relevant documents
   
   ```python
   class HyDERetriever:
       def retrieve_with_hyde(self, query: str) -> List[Document]:
           # Step 1: Generate hypothetical document
           hypothetical = self.llm.generate(
               f"Write a detailed paragraph that answers: {query}"
           )
           
           # Step 2: Embed the hypothetical document (not the query)
           hyde_embedding = self.embedder.encode(hypothetical)
           
           # Step 3: Search with hypothetical embedding
           results = self.vector_db.search(hyde_embedding, top_k=10)
           return results
   ```

2. **When HyDE Works Best vs Worst:**
   | Scenario | HyDE Effective? | Reason |
   |----------|-----------------|--------|
   | Vague queries ("best practices") | Yes | Expands into detailed content |
   | Technical jargon mismatch | Yes | Bridges vocabulary gap |
   | Exact fact lookup | No | Direct embedding is more precise |
   | Multi-lingual (query ≠ doc language) | Yes | Generates in target language |
   | Time-sensitive queries | No | LLM may generate outdated hypothetical |
   | Ambiguous queries | Risky | May generate wrong interpretation |

3. **Adaptive Selection System:**
   ```python
   class AdaptiveRetriever:
       def __init__(self):
           self.query_classifier = QueryTypeClassifier()
           self.confidence_estimator = RetrievalConfidenceModel()
       
       async def retrieve(self, query: str) -> List[Document]:
           query_type = self.query_classifier.classify(query)
           
           if query_type in ['factual', 'exact_match', 'entity_lookup']:
               # Direct embedding is better for precise queries
               return await self.direct_retrieval(query)
           
           elif query_type in ['conceptual', 'exploratory', 'how_to']:
               # Try direct first, fall back to HyDE if low confidence
               direct_results = await self.direct_retrieval(query)
               confidence = self.confidence_estimator.score(query, direct_results)
               
               if confidence < 0.6:
                   hyde_results = await self.hyde_retrieval(query)
                   # Merge with RRF (Reciprocal Rank Fusion)
                   return self.rrf_merge(direct_results, hyde_results)
               return direct_results
           
           else:
               # Multi-query approach: generate multiple hypotheticals
               return await self.multi_hyde_retrieval(query, n_hypotheticals=3)
   ```

4. **Multi-HyDE for Ambiguous Queries:**
   - Generate 3-5 different hypothetical documents capturing different interpretations
   - Embed each separately and search
   - Merge results with diversity-aware fusion (MMR)
   - This handles query ambiguity by exploring multiple directions

5. **Production Considerations:**
   - **Latency:** HyDE adds 200-500ms (LLM generation) → use only when beneficial
   - **Cost:** 10x more expensive than direct embedding → budget-aware routing
   - **Caching:** Cache hypothetical documents for similar queries
   - **Quality monitoring:** Track when HyDE improves vs degrades retrieval precision
   - **Fallback:** If LLM generates poor hypothetical, direct embedding is the safety net

---

## Question 22: Parent-Child Document Retrieval
**Difficulty: Staff Level | Topic: Document Hierarchy | Asked at: Elastic, MongoDB, Pinecone**

Design a parent-child document retrieval system where you search on fine-grained child chunks but return parent-level context to the LLM. How do you balance precision of search with richness of context?

### Expected Answer:

**Parent-Child Retrieval Architecture:**

1. **Hierarchical Document Storage:**
   ```
   Document (Full - not embedded)
       │
       ├── Section (Parent - stored, optionally embedded)
       │       │
       │       ├── Chunk A (Child - embedded for search)
       │       ├── Chunk B (Child - embedded for search)
       │       └── Chunk C (Child - embedded for search)
       │
       └── Section (Parent)
               │
               ├── Chunk D (Child - embedded)
               └── Chunk E (Child - embedded)
   ```

2. **Implementation:**
   ```python
   class ParentChildRetriever:
       def index_document(self, document):
           # Create hierarchy
           doc_id = self.store_document(document)
           
           for section in document.sections:
               parent_id = self.store_parent(section, doc_id=doc_id)
               
               for chunk in self.chunk_section(section):
                   # Only child chunks get embedded
                   embedding = self.embed(chunk.text)
                   self.vector_db.upsert(
                       id=chunk.id,
                       vector=embedding,
                       metadata={
                           'parent_id': parent_id,
                           'doc_id': doc_id,
                           'text': chunk.text,  # For display
                           'position': chunk.position
                       }
                   )
       
       def retrieve(self, query: str, return_level: str = 'parent') -> List[Context]:
           # Search at child (fine-grained) level
           child_results = self.vector_db.search(
               self.embed(query), top_k=20
           )
           
           if return_level == 'child':
               return child_results[:5]
           
           elif return_level == 'parent':
               # Group by parent, return parent context
               parent_ids = set(r.metadata['parent_id'] for r in child_results[:10])
               parents = [self.get_parent(pid) for pid in parent_ids]
               # Rank parents by best child score
               parents.sort(key=lambda p: max(
                   r.score for r in child_results if r.metadata['parent_id'] == p.id
               ), reverse=True)
               return parents[:5]
           
           elif return_level == 'adaptive':
               # Return parent when query is broad, child when specific
               return self.adaptive_context(query, child_results)
   ```

3. **Adaptive Context Window:**
   ```python
   def adaptive_context(self, query, child_results):
       """
       Dynamically decide how much context to include.
       - Specific query: Return matched child + surrounding siblings
       - Broad query: Return full parent sections
       - Multi-topic: Return multiple parents with key children highlighted
       """
       query_specificity = self.classify_specificity(query)
       
       if query_specificity == 'narrow':
           # Return child + 1 sibling on each side
           contexts = []
           for child in child_results[:3]:
               siblings = self.get_siblings(child, window=1)
               contexts.append(self.merge_with_highlighting(siblings, child))
           return contexts
       
       elif query_specificity == 'broad':
           # Return full parent sections
           parent_ids = list(set(r.metadata['parent_id'] for r in child_results[:5]))
           return [self.get_parent(pid) for pid in parent_ids[:3]]
       
       else:  # multi-topic
           # Return diverse parents with relevance-highlighted children
           return self.diverse_parent_selection(child_results, max_parents=4)
   ```

4. **Small-to-Big Retrieval Pattern:**
   - Index: Small chunks (128 tokens) for precision
   - Retrieve: Match small chunks
   - Return: Expand to surrounding context (512-1024 tokens)
   - Benefit: Best of both worlds - precise matching + rich context

5. **Challenges & Solutions:**
   - **Redundancy:** Multiple children from same parent match → deduplicate at parent level
   - **Context budget:** Parent may be too large → use extractive summarization to fit budget
   - **Stale hierarchy:** Document restructured → rebuild parent-child links
   - **Cross-reference:** Child references content in different parent → include both parents

---

## Question 23: Reciprocal Rank Fusion (RRF) and Hybrid Search
**Difficulty: Staff Level | Topic: Information Retrieval | Asked at: Elastic, Vespa, Google**

Implement and optimize a hybrid search system combining dense vector search, sparse BM25 search, and knowledge graph lookup using Reciprocal Rank Fusion. How do you tune the weights for different query types?

### Expected Answer:

**Hybrid Search with Adaptive RRF:**

1. **Reciprocal Rank Fusion Algorithm:**
   ```python
   def reciprocal_rank_fusion(result_lists: List[List[Result]], k: int = 60) -> List[Result]:
       """
       RRF formula: score(d) = Σ 1/(k + rank_i(d))
       k=60 is standard (from original paper), controls how much to penalize lower ranks
       """
       scores = defaultdict(float)
       doc_map = {}
       
       for result_list in result_lists:
           for rank, result in enumerate(result_list, start=1):
               scores[result.id] += 1.0 / (k + rank)
               doc_map[result.id] = result
       
       # Sort by fused score
       ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
       return [doc_map[doc_id] for doc_id, score in ranked]
   ```

2. **Weighted RRF for Multiple Sources:**
   ```python
   class WeightedHybridSearch:
       def __init__(self):
           self.weights = {
               'dense': 0.5,    # Semantic understanding
               'sparse': 0.3,   # Keyword matching
               'kg': 0.2        # Structural relationships
           }
       
       async def search(self, query: str, top_k: int = 10) -> List[Result]:
           # Parallel retrieval from all sources
           dense_results, sparse_results, kg_results = await asyncio.gather(
               self.dense_search(query, top_k=50),
               self.sparse_search(query, top_k=50),
               self.kg_search(query, top_k=20)
           )
           
           # Weighted RRF
           scores = defaultdict(float)
           for source, results, weight in [
               ('dense', dense_results, self.weights['dense']),
               ('sparse', sparse_results, self.weights['sparse']),
               ('kg', kg_results, self.weights['kg'])
           ]:
               for rank, result in enumerate(results, start=1):
                   scores[result.id] += weight / (60 + rank)
           
           ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
           return ranked[:top_k]
   ```

3. **Adaptive Weight Tuning:**
   ```python
   class AdaptiveWeightTuner:
       """
       Learn optimal weights per query type from feedback data.
       """
       def get_weights(self, query: str) -> Dict[str, float]:
           query_features = self.extract_features(query)
           # Features: query length, entity density, keyword specificity,
           #           vocabulary overlap with corpus
           
           if query_features['has_exact_terms']:
               # Keyword-heavy query → boost BM25
               return {'dense': 0.3, 'sparse': 0.6, 'kg': 0.1}
           elif query_features['is_conceptual']:
               # Conceptual query → boost dense
               return {'dense': 0.7, 'sparse': 0.1, 'kg': 0.2}
           elif query_features['has_entities']:
               # Entity-rich query → boost KG
               return {'dense': 0.3, 'sparse': 0.2, 'kg': 0.5}
           else:
               return self.default_weights
       
       def learn_weights(self, feedback_data: List[FeedbackRecord]):
           """Use historical feedback to learn optimal weights per query cluster."""
           # Group queries by type
           clusters = self.cluster_queries(feedback_data)
           
           for cluster in clusters:
               # Grid search or Bayesian optimization for weights
               best_weights = self.optimize_weights(
                   cluster.queries,
                   cluster.relevance_judgments,
                   metric='ndcg@10'
               )
               self.weight_lookup[cluster.id] = best_weights
   ```

4. **BM25 + Dense Complementarity:**
   - BM25 excels: Exact names, acronyms, rare terms, error codes
   - Dense excels: Paraphrases, conceptual similarity, cross-lingual
   - Together: Cover both precision (BM25) and recall (Dense)

5. **Production Optimization:**
   - Pre-compute BM25 scores for common terms (inverted index warm-up)
   - Approximate dense search with quantization (int8 vectors)
   - Cached RRF scores for popular queries
   - Early termination: If top result has very high score, skip remaining sources
   - A/B test different k values (k=60 vs k=20 vs k=100) for your domain

---

## Question 24: Query Decomposition and Multi-Hop RAG
**Difficulty: Staff Level | Topic: Complex Reasoning | Asked at: Google DeepMind, Meta AI**

Design a system that handles complex multi-hop questions requiring information synthesis from multiple documents. For example: "Compare the revenue growth of companies that adopted RAG in 2023 vs those that didn't."

### Expected Answer:

**Multi-Hop RAG Architecture:**

1. **Query Decomposition:**
   ```python
   class QueryDecomposer:
       def decompose(self, complex_query: str) -> QueryPlan:
           """
           "Compare revenue growth of companies that adopted RAG in 2023 vs those that didn't"
           
           Decomposed into:
           1. "Which companies adopted RAG in 2023?" → List of companies
           2. "What is the revenue growth of [company_A]?" → For each RAG adopter
           3. "Which comparable companies did NOT adopt RAG?" → Control group
           4. "What is the revenue growth of [company_B]?" → For each non-adopter
           5. "Compare/synthesize the results" → Final analysis
           """
           prompt = """Decompose this complex question into simple sub-questions.
           Each sub-question should be answerable from a single document.
           Show dependencies between sub-questions.
           
           Complex question: {complex_query}
           
           Output format:
           - step_id: 1
             question: "..."
             depends_on: []
           - step_id: 2
             question: "... {step_1_result} ..."
             depends_on: [1]
           """
           
           plan = self.llm.generate(prompt)
           return self.parse_plan(plan)
   ```

2. **Execution DAG:**
   ```
   Step 1: "Companies that adopted RAG in 2023"
       ↓
   Step 2a: Revenue growth of [Company A]    Step 2b: Revenue of [Company B]
       ↓                                         ↓
   Step 3: "Companies that did NOT adopt RAG (similar size/industry)"
       ↓
   Step 4a: Revenue growth of [Company X]    Step 4b: Revenue of [Company Y]
       ↓                                         ↓
   Step 5: Synthesize comparison
   ```

3. **Parallel Execution with Dependencies:**
   ```python
   class MultiHopExecutor:
       async def execute(self, plan: QueryPlan) -> str:
           results = {}
           
           # Topological sort for execution order
           execution_order = self.topological_sort(plan.steps)
           
           for batch in execution_order:
               # Execute independent steps in parallel
               batch_tasks = []
               for step in batch:
                   # Substitute results from dependencies
                   resolved_query = self.resolve_references(step, results)
                   batch_tasks.append(self.execute_step(step.id, resolved_query))
               
               batch_results = await asyncio.gather(*batch_tasks)
               for step_id, result in batch_results:
                   results[step_id] = result
           
           # Final synthesis
           return await self.synthesize(plan.original_query, results)
       
       async def execute_step(self, step_id, query):
           # Standard RAG for each sub-question
           docs = await self.retrieve(query)
           answer = await self.generate(query, docs)
           return step_id, answer
   ```

4. **Verification & Consistency:**
   - Cross-check facts across steps (Company A's revenue should be consistent)
   - Confidence propagation: If step 1 is uncertain, mark downstream steps as lower confidence
   - Contradiction detection: If different documents give conflicting answers, flag for resolution
   - Source tracking: Maintain provenance chain (which document answered which sub-question)

5. **Optimization:**
   - **Speculative execution:** Start likely needed retrievals before decomposition completes
   - **Result caching:** Cache sub-question answers for reuse in similar queries
   - **Early termination:** If key sub-question can't be answered, abort and report
   - **Depth limiting:** Maximum 4 hops (diminishing returns + error accumulation)
   - **Fallback:** If decomposition fails, try direct RAG on original query

---

## Question 25: Self-Reflective RAG (CRAG/Self-RAG)
**Difficulty: Staff Level | Topic: Self-Correction | Asked at: Meta AI, Google Research**

Implement a Self-Reflective RAG system where the model evaluates its own retrieval quality and generation accuracy, deciding when to re-retrieve, when to generate from parametric knowledge, and when to refuse to answer.

### Expected Answer:

**Self-Reflective RAG (Corrective RAG) Architecture:**

1. **Core Loop:**
   ```
   Query → Retrieve → [EVALUATE RETRIEVAL] → Decision:
                              │
                    ┌─────────┼─────────────┐
                    │         │             │
               CORRECT    AMBIGUOUS     INCORRECT
                    │         │             │
               Generate   Refine &      Web Search /
               Answer     Re-retrieve   Refuse
                    │         │             │
                    └─────────┼─────────────┘
                              │
                    [EVALUATE GENERATION]
                              │
                    ┌─────────┼─────────────┐
                    │         │             │
               SUPPORTED  PARTIAL      HALLUCINATED
                    │         │             │
               Return     Add caveat    Regenerate /
                          & sources     Refuse
   ```

2. **Implementation:**
   ```python
   class SelfReflectiveRAG:
       def __init__(self):
           self.retriever = HybridRetriever()
           self.generator = LLM()
           self.retrieval_evaluator = RetrievalGrader()  # Trained classifier
           self.generation_evaluator = FactualityChecker()  # NLI model
       
       async def answer(self, query: str, max_attempts: int = 3) -> Response:
           for attempt in range(max_attempts):
               # Retrieve
               docs = await self.retriever.search(query)
               
               # Evaluate retrieval quality
               retrieval_grade = self.retrieval_evaluator.grade(query, docs)
               
               if retrieval_grade == 'incorrect':
                   if attempt < max_attempts - 1:
                       # Try different retrieval strategy
                       query = await self.reformulate_query(query)
                       continue
                   else:
                       # All attempts failed - use web or refuse
                       return await self.fallback_strategy(query)
               
               elif retrieval_grade == 'ambiguous':
                   # Supplement with additional retrieval
                   extra_docs = await self.supplemental_retrieval(query, docs)
                   docs.extend(extra_docs)
               
               # Generate answer
               response = await self.generator.generate(query, docs)
               
               # Evaluate generation
               gen_grade = self.generation_evaluator.check(response, docs)
               
               if gen_grade.is_supported:
                   return Response(
                       answer=response,
                       confidence=gen_grade.confidence,
                       sources=self.extract_citations(response, docs)
                   )
               elif gen_grade.has_hallucinations:
                   # Remove hallucinated claims and regenerate
                   response = await self.regenerate_without_hallucinations(
                       query, docs, gen_grade.hallucinated_claims
                   )
               
               return Response(answer=response, confidence=gen_grade.confidence)
           
           return Response(answer="I cannot find a reliable answer.", confidence=0.0)
   ```

3. **Retrieval Grading Model:**
   ```python
   class RetrievalGrader:
       """Fine-tuned classifier that grades query-document relevance."""
       
       def grade(self, query: str, documents: List[str]) -> str:
           scores = []
           for doc in documents:
               # Binary relevance: is this document relevant to the query?
               score = self.model.predict(
                   f"Query: {query}\nDocument: {doc}\nRelevant?"
               )
               scores.append(score)
           
           relevant_ratio = sum(1 for s in scores if s > 0.5) / len(scores)
           
           if relevant_ratio > 0.6:
               return 'correct'
           elif relevant_ratio > 0.3:
               return 'ambiguous'
           else:
               return 'incorrect'
   ```

4. **Knowledge Source Selection:**
   | Condition | Action | Rationale |
   |-----------|--------|-----------|
   | High retrieval confidence | Use retrieved docs only | Grounded, traceable |
   | Medium retrieval + parametric agreement | Blend both | Cross-validation |
   | Low retrieval, high parametric confidence | Use parametric + disclaimer | Best available |
   | Low retrieval, low parametric confidence | Refuse to answer | Honesty over helpfulness |
   | Contradictory sources | Present both with analysis | Transparent disagreement |

5. **Production Metrics:**
   - Self-correction rate: How often does the system re-retrieve (target: 15-20%)
   - Refusal rate: How often it refuses (target: 5-10%, too high = too conservative)
   - Correction accuracy: When it self-corrects, does quality improve? (target: >80%)
   - Latency impact: Self-reflection adds 200-400ms average
   - Cost impact: 1.3-1.5x base cost (worth it for quality-critical applications)
