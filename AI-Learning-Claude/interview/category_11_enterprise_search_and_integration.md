# Search and Ranking Systems (Questions 201-205)

## Q201: Design a Learning-to-Rank System for RAG

**Question:** Design a learning-to-rank system for RAG that combines semantic similarity with behavioral signals (clicks, dwell time, conversions). Include feature engineering, model training, and online serving.

**Answer:**

### Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Query     │────▶│  Candidate   │────▶│  Feature        │
│   Input     │     │  Retrieval   │     │  Extraction     │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────┐     ┌─────────▼────────┐
                    │  Re-ranked   │◀────│  LTR Model       │
                    │  Results     │     │  Inference       │
                    └──────────────┘     └──────────────────┘
                           │
                    ┌──────▼──────┐     ┌──────────────────┐
                    │  User       │────▶│  Behavioral      │
                    │  Interaction│     │  Signal Store    │
                    └─────────────┘     └──────────────────┘
```

### Feature Engineering

```python
class LTRFeatureExtractor:
    def extract_features(self, query: str, document: dict, user: dict) -> dict:
        return {
            # Relevance features
            "semantic_similarity": self.embedding_similarity(query, document),
            "bm25_score": self.bm25(query, document),
            "title_match": self.title_overlap(query, document),
            
            # Behavioral features (aggregated)
            "historical_ctr": self.click_through_rate(document["id"]),
            "avg_dwell_time": self.avg_dwell(document["id"]),
            "conversion_rate": self.conversion_rate(document["id"]),
            "bounce_rate": self.bounce_rate(document["id"]),
            
            # Document quality features
            "freshness_score": self.freshness(document["updated_at"]),
            "authority_score": self.page_rank(document["id"]),
            "content_length": len(document["content"]),
            "readability_score": self.flesch_kincaid(document["content"]),
            
            # Query-document interaction features
            "query_doc_topic_match": self.topic_similarity(query, document),
            "exact_phrase_match": int(query.lower() in document["content"].lower()),
            
            # Personalization features
            "user_dept_relevance": self.dept_match(user, document),
            "user_history_affinity": self.user_doc_affinity(user, document),
        }
```

### Model Training Pipeline

```python
class LTRTrainingPipeline:
    def __init__(self):
        self.model = lightgbm.LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            n_estimators=300,
            num_leaves=31,
            learning_rate=0.05,
        )
    
    def prepare_training_data(self, click_logs: pd.DataFrame) -> tuple:
        """Generate pairwise labels from click data with position bias correction."""
        # Apply inverse propensity weighting for position bias
        click_logs["weight"] = 1.0 / self.position_propensity(click_logs["position"])
        
        # Label: 0=not shown, 1=shown not clicked, 2=clicked, 3=long dwell, 4=converted
        click_logs["relevance_label"] = self.compute_graded_relevance(click_logs)
        
        features = self.extract_all_features(click_logs)
        groups = click_logs.groupby("query_id").size().values
        
        return features, click_logs["relevance_label"], groups
    
    def train_with_online_evaluation(self):
        """Train with interleaving-based online evaluation."""
        X, y, groups = self.prepare_training_data(self.get_click_logs())
        
        # Time-based split (no leakage)
        train_X, val_X = X[X.index < cutoff], X[X.index >= cutoff]
        
        self.model.fit(train_X, y_train, group=groups_train,
                      eval_set=[(val_X, y_val)], eval_group=[groups_val],
                      callbacks=[lightgbm.early_stopping(50)])
        
        # Deploy via interleaving: serve both old and new model
        # Measure preference using Team Draft Interleaving
        self.deploy_interleaved(self.model)
```

### Online Serving Architecture

| Component | Technology | Latency Budget |
|-----------|-----------|---------------|
| Candidate retrieval | HNSW (Milvus) | 20ms |
| Feature extraction | Redis + precomputed | 10ms |
| Model inference | ONNX Runtime | 5ms |
| Total p99 | — | <50ms |

### Production Considerations

- **Position bias correction**: Users click top results regardless of relevance. Use inverse propensity scoring or intervention harvesting (randomize a small % of results).
- **Feature freshness**: Behavioral signals updated hourly via Flink streaming aggregations. Semantic features cached and invalidated on document update.
- **Cold-start documents**: New documents have no behavioral signals. Use content-based features only with a separate "exploration" slot that allocates 5-10% of impressions to new content.
- **Model staleness**: Retrain weekly with rolling 30-day window. Monitor NDCG@10 daily; trigger emergency retrain if drops >5%.

---

## Q202: Design a Query Understanding Pipeline

**Question:** Design a query understanding pipeline that handles typos, abbreviations, synonyms, intent classification, and entity extraction before retrieval. Include real-time query suggestion.

**Answer:**

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Query Understanding Pipeline                    │
├─────────────┬──────────────┬─────────────┬──────────────────────┤
│  Stage 1    │  Stage 2     │  Stage 3    │  Stage 4             │
│  Normalize  │  Correct     │  Expand     │  Classify            │
│             │              │             │                      │
│ • lowercase │ • spell fix  │ • synonyms  │ • intent detection   │
│ • tokenize  │ • abbrev     │ • related   │ • entity extraction  │
│ • remove    │   expansion  │   terms     │ • slot filling       │
│   noise     │ • split/join │ • acronyms  │                      │
└─────────────┴──────────────┴─────────────┴──────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Enriched Query    │
                    │  Representation    │
                    └───────────────────┘
```

### Implementation

```python
class QueryUnderstandingPipeline:
    def __init__(self):
        self.spell_checker = SymSpellCorrector(max_edit_distance=2)
        self.abbreviation_db = AbbreviationExpander()  # Redis-backed
        self.intent_classifier = IntentClassifier()  # Fine-tuned BERT
        self.ner_model = NERModel()  # spaCy + custom entities
        self.synonym_graph = SynonymGraph()  # WordNet + domain-specific
    
    async def process(self, raw_query: str, context: dict) -> EnrichedQuery:
        # Stage 1: Normalization
        normalized = self.normalize(raw_query)
        
        # Stage 2: Spelling correction with domain awareness
        corrected = self.spell_correct(normalized, context.get("domain"))
        
        # Stage 3: Parallel expansion (run concurrently)
        expansions, intent, entities = await asyncio.gather(
            self.expand_query(corrected),
            self.classify_intent(corrected, context),
            self.extract_entities(corrected),
        )
        
        return EnrichedQuery(
            original=raw_query,
            corrected=corrected,
            expansions=expansions,
            intent=intent,
            entities=entities,
            retrieval_query=self.build_retrieval_query(corrected, expansions, intent),
        )
    
    def spell_correct(self, query: str, domain: str) -> str:
        """Domain-aware spell correction using SymSpell + domain dictionary."""
        # Check domain dictionary first (e.g., "k8s" is valid in DevOps domain)
        if self.abbreviation_db.is_known(query, domain):
            return self.abbreviation_db.expand(query, domain)
        
        suggestions = self.spell_checker.lookup_compound(query, max_edit_distance=2)
        if suggestions and suggestions[0].distance <= 2:
            return suggestions[0].term
        return query
    
    def classify_intent(self, query: str, context: dict) -> Intent:
        """Multi-label intent classification."""
        # Intents: FACTUAL, NAVIGATIONAL, EXPLORATORY, TRANSACTIONAL, COMPARISON
        logits = self.intent_classifier.predict(query, context.get("history", []))
        return Intent(
            primary=INTENT_LABELS[logits.argmax()],
            confidence=float(logits.max()),
            secondary=[INTENT_LABELS[i] for i in (logits > 0.3).nonzero()],
        )
```

### Real-Time Query Suggestion

```python
class QuerySuggestionEngine:
    def __init__(self):
        self.trie = CompletionTrie()  # Prefix-based completions
        self.popular_queries = PopularQueryStore()  # Time-decayed popularity
        self.personalized_model = PersonalizedSuggestionModel()
    
    async def suggest(self, prefix: str, user: dict, limit: int = 8) -> list:
        """Generate suggestions within 50ms budget."""
        candidates = set()
        
        # Source 1: Trie completion (5ms)
        candidates.update(self.trie.complete(prefix, limit=20))
        
        # Source 2: Popular queries with prefix match (5ms, Redis ZRANGEBYLEX)
        candidates.update(self.popular_queries.match(prefix, limit=20))
        
        # Source 3: User's recent queries (2ms, local cache)
        candidates.update(self.user_recent(user["id"], prefix))
        
        # Rank by: popularity * recency * personalization_score
        scored = [(q, self.score(q, user)) for q in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [q for q, _ in scored[:limit]]
```

### Trade-offs

| Approach | Latency | Quality | Maintenance |
|----------|---------|---------|-------------|
| Rule-based pipeline | 5ms | Medium | High (manual rules) |
| LLM-based rewriting | 200ms | High | Low |
| Hybrid (rules + small model) | 20ms | High | Medium |

**Production choice**: Hybrid — use fast rules for normalization/spelling, small fine-tuned model (DistilBERT) for intent/NER, and cache LLM rewrites for common patterns.

---

## Q203: Design a Diversified Search Results System

**Question:** Design a diversified search results system that avoids returning redundant information. Include Maximum Marginal Relevance (MMR), subtopic coverage, and novelty scoring.

**Answer:**

### Architecture

```
┌──────────┐     ┌───────────────┐     ┌──────────────────┐
│  Initial │────▶│  Diversity    │────▶│  Final Ranked    │
│  Ranked  │     │  Re-ranker    │     │  Results         │
│  (top-K) │     │               │     │  (diversified)   │
└──────────┘     └───────────────┘     └──────────────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
    ┌─────────┐  ┌───────────┐  ┌─────────┐
    │  MMR    │  │  Subtopic │  │  Novelty│
    │  Score  │  │  Coverage │  │  Score  │
    └─────────┘  └───────────┘  └─────────┘
```

### MMR Implementation

```python
class DiversifiedRanker:
    def __init__(self, lambda_param: float = 0.7):
        self.lambda_param = lambda_param  # relevance vs diversity trade-off
    
    def mmr_rerank(self, query_embedding: np.ndarray, 
                   candidates: list[Document], k: int = 10) -> list[Document]:
        """
        MMR = λ * Sim(q, d) - (1-λ) * max(Sim(d, d_j)) for d_j in selected
        """
        selected = []
        remaining = list(candidates)
        
        # Precompute all pairwise similarities
        embeddings = np.array([d.embedding for d in candidates])
        query_sims = cosine_similarity([query_embedding], embeddings)[0]
        doc_sims = cosine_similarity(embeddings, embeddings)
        
        for _ in range(k):
            if not remaining:
                break
            
            best_score = -float("inf")
            best_idx = 0
            
            for i, doc in enumerate(remaining):
                orig_idx = candidates.index(doc)
                relevance = query_sims[orig_idx]
                
                # Max similarity to already selected documents
                if selected:
                    selected_indices = [candidates.index(s) for s in selected]
                    redundancy = max(doc_sims[orig_idx][j] for j in selected_indices)
                else:
                    redundancy = 0
                
                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * redundancy
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            
            selected.append(remaining.pop(best_idx))
        
        return selected
    
    def subtopic_diversify(self, query: str, candidates: list[Document], 
                           k: int = 10) -> list[Document]:
        """Ensure coverage of query subtopics using xQuAD framework."""
        subtopics = self.extract_subtopics(query)  # LLM or clustering
        
        selected = []
        subtopic_coverage = {s: 0.0 for s in subtopics}
        
        for _ in range(k):
            best_score = -float("inf")
            best_doc = None
            
            for doc in candidates:
                if doc in selected:
                    continue
                
                # Score = relevance + diversity bonus for uncovered subtopics
                relevance = doc.relevance_score
                diversity_bonus = sum(
                    (1 - subtopic_coverage[s]) * self.subtopic_relevance(doc, s)
                    for s in subtopics
                )
                score = (1 - self.lambda_param) * relevance + self.lambda_param * diversity_bonus
                
                if score > best_score:
                    best_score = score
                    best_doc = doc
            
            selected.append(best_doc)
            # Update coverage
            for s in subtopics:
                subtopic_coverage[s] = max(subtopic_coverage[s], 
                                           self.subtopic_relevance(best_doc, s))
        
        return selected
    
    def novelty_score(self, doc: Document, selected: list[Document]) -> float:
        """Information-theoretic novelty: how much new info does this doc add?"""
        doc_entities = set(doc.extracted_entities)
        doc_claims = set(doc.extracted_claims)
        
        covered_entities = set().union(*[set(s.extracted_entities) for s in selected]) if selected else set()
        covered_claims = set().union(*[set(s.extracted_claims) for s in selected]) if selected else set()
        
        new_entities = doc_entities - covered_entities
        new_claims = doc_claims - covered_claims
        
        entity_novelty = len(new_entities) / max(len(doc_entities), 1)
        claim_novelty = len(new_claims) / max(len(doc_claims), 1)
        
        return 0.4 * entity_novelty + 0.6 * claim_novelty
```

### Production Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| α-NDCG | Novelty-aware ranking quality | >0.45 |
| Subtopic Recall@10 | % subtopics covered in top-10 | >0.80 |
| Intent Satisfaction | User finds answer without scrolling | >70% |
| Result Redundancy | % near-duplicate content pairs | <5% |

### Trade-offs

- **λ too high (0.9)**: Results are relevant but repetitive — user sees same answer from 5 sources
- **λ too low (0.3)**: Results are diverse but some irrelevant — user confused by off-topic results
- **Production default**: λ=0.7, tuned per-query-type (factual queries need less diversity, exploratory need more)

---

## Q204: Design a Personalized Ranking System

**Question:** Design a personalized ranking system that re-ranks search results based on user profile, past interactions, and organizational context. Include cold-start handling for new users.

**Answer:**

### Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Base       │     │  Personalization │     │  Personalized│
│  Ranking    │────▶│  Layer           │────▶│  Results     │
│  (generic)  │     │                  │     │              │
└─────────────┘     └────────┬─────────┘     └──────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌───────────┐ ┌────────────┐
       │ User       │ │ Org       │ │ Session    │
       │ Profile    │ │ Context   │ │ Context    │
       └────────────┘ └───────────┘ └────────────┘
```

### Implementation

```python
class PersonalizedRanker:
    def __init__(self):
        self.user_embedding_model = UserTower()  # Two-tower architecture
        self.doc_embedding_model = DocTower()
        self.cross_encoder = PersonalizedCrossEncoder()
    
    def rerank(self, user: User, query: str, candidates: list[Document],
               session: Session) -> list[Document]:
        """Personalized re-ranking with cascading signals."""
        
        # Build user representation
        user_features = self.build_user_features(user, session)
        
        # Score each candidate
        scored = []
        for doc in candidates:
            base_score = doc.relevance_score
            personal_score = self.personalization_score(user_features, doc)
            
            # Blend: avoid over-personalization (filter bubble)
            alpha = self.compute_alpha(user)  # 0.2 for new users, 0.5 for established
            final_score = (1 - alpha) * base_score + alpha * personal_score
            scored.append((doc, final_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored]
    
    def build_user_features(self, user: User, session: Session) -> dict:
        return {
            # Long-term profile
            "role_embedding": self.role_to_embedding(user.role),
            "department": user.department,
            "expertise_topics": user.inferred_expertise,  # From past queries/clicks
            "preferred_content_types": user.content_preferences,
            "reading_level": user.avg_content_complexity,
            
            # Medium-term (last 30 days)
            "recent_topics": self.extract_topics(user.recent_queries),
            "recent_docs_read": user.recent_doc_embeddings_centroid,
            "active_projects": user.active_project_keywords,
            
            # Session context (last few minutes)
            "current_task": session.inferred_task,
            "session_queries": session.queries,
            "session_clicks": session.clicked_docs,
            
            # Organizational context
            "team_popular_docs": self.team_trending(user.team_id),
            "org_announcements": self.recent_org_updates(user.org_id),
        }
    
    def personalization_score(self, user_features: dict, doc: Document) -> float:
        """Multi-signal personalization scoring."""
        scores = {
            "topic_affinity": cosine_similarity(
                user_features["recent_topics"], doc.topic_embedding),
            "expertise_match": self.expertise_match(
                user_features["expertise_topics"], doc.complexity_level),
            "team_relevance": 1.0 if doc.id in user_features["team_popular_docs"] else 0.0,
            "recency_preference": self.recency_boost(doc, user_features),
            "format_preference": self.format_match(
                user_features["preferred_content_types"], doc.content_type),
        }
        
        # Learned weights per user cohort
        weights = self.get_cohort_weights(user_features)
        return sum(w * scores[k] for k, w in weights.items())
```

### Cold-Start Strategy

```python
class ColdStartHandler:
    """Progressive personalization as user data accumulates."""
    
    def compute_alpha(self, user: User) -> float:
        """Personalization weight: 0 (no personalization) to 0.5 (max)."""
        interactions = user.total_interactions
        
        if interactions < 5:
            return 0.0  # Pure generic ranking
        elif interactions < 20:
            return 0.1  # Light org-level personalization
        elif interactions < 100:
            return 0.3  # Medium personalization
        else:
            return 0.5  # Full personalization
    
    def cold_start_signals(self, user: User) -> dict:
        """Use available signals for new users."""
        return {
            # From onboarding / SSO
            "department_popular": self.dept_popular_docs(user.department),
            "role_typical_queries": self.role_based_recommendations(user.role),
            # Collaborative filtering from similar users
            "similar_users_preferences": self.find_similar_users(
                user.role, user.department, user.seniority),
        }
```

### Metrics and Guardrails

| Metric | Purpose | Threshold |
|--------|---------|-----------|
| Personalized NDCG lift | Quality improvement | >5% over generic |
| Filter bubble index | Diversity check | <0.3 (low is diverse) |
| Cold-start satisfaction | New user experience | >80% task completion |
| Fairness audit | No demographic bias | <2% outcome variance |

**Key guardrail**: Never let personalization alpha exceed 0.5 — always maintain ≥50% weight on objective relevance to prevent filter bubbles and ensure serendipitous discovery.

---

## Q205: Design a Federated Search System

**Question:** Design a federated search system that queries multiple independent indices (internal docs, external APIs, databases) and presents unified, ranked results. Include source reliability scoring.

**Answer:**

### Architecture

```
┌──────────┐     ┌───────────────────────────────────────────────┐
│  Query   │────▶│           Federated Search Orchestrator        │
└──────────┘     └───────────────────┬───────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
     │  Confluence    │    │  GitHub/Code   │    │  Slack         │
     │  Connector     │    │  Connector     │    │  Connector     │
     │  (500ms SLA)   │    │  (300ms SLA)   │    │  (400ms SLA)   │
     └────────┬───────┘    └────────┬───────┘    └────────┬───────┘
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     ▼
                          ┌──────────────────────┐
                          │  Result Fusion &     │
                          │  Unified Ranking     │
                          └──────────────────────┘
```

### Implementation

```python
class FederatedSearchEngine:
    def __init__(self):
        self.connectors: dict[str, SourceConnector] = {
            "confluence": ConfluenceConnector(timeout_ms=500),
            "github": GitHubConnector(timeout_ms=300),
            "slack": SlackConnector(timeout_ms=400),
            "jira": JiraConnector(timeout_ms=400),
            "gdrive": GDriveConnector(timeout_ms=600),
            "internal_kb": VectorDBConnector(timeout_ms=100),
        }
        self.source_reliability = SourceReliabilityScorer()
        self.fusion_model = ResultFusionModel()
    
    async def search(self, query: str, user: User, 
                     timeout_ms: int = 800) -> UnifiedResults:
        """Query all sources in parallel with timeout and partial results."""
        
        # Determine which sources to query based on intent
        relevant_sources = self.route_to_sources(query, user)
        
        # Fan-out: query all relevant sources in parallel
        tasks = {
            source: asyncio.create_task(
                self.query_source(source, query, user, timeout_ms)
            )
            for source in relevant_sources
        }
        
        # Gather with timeout — return partial results if some sources are slow
        results_by_source = {}
        done, pending = await asyncio.wait(
            tasks.values(), timeout=timeout_ms / 1000, 
            return_when=asyncio.ALL_COMPLETED
        )
        
        for source, task in tasks.items():
            if task in done and not task.exception():
                results_by_source[source] = task.result()
            else:
                # Log degraded source, proceed without it
                results_by_source[source] = DegradedResult(source=source)
                if task in pending:
                    task.cancel()
        
        # Fuse and rank
        unified = self.fuse_results(query, results_by_source, user)
        return unified
    
    def fuse_results(self, query: str, results_by_source: dict, 
                     user: User) -> UnifiedResults:
        """Reciprocal Rank Fusion with source reliability weighting."""
        
        all_results = []
        for source, results in results_by_source.items():
            if isinstance(results, DegradedResult):
                continue
            
            reliability = self.source_reliability.score(source, query)
            
            for rank, doc in enumerate(results.documents):
                # Reciprocal Rank Fusion score
                rrf_score = 1.0 / (60 + rank)  # k=60 standard
                
                # Weight by source reliability
                weighted_score = rrf_score * reliability
                
                all_results.append(FusedResult(
                    document=doc,
                    source=source,
                    score=weighted_score,
                    reliability=reliability,
                    source_rank=rank,
                ))
        
        # Deduplicate across sources (same content in Slack + Confluence)
        deduped = self.deduplicate(all_results)
        
        # Final ranking with cross-source features
        ranked = self.cross_source_rerank(query, deduped, user)
        return UnifiedResults(results=ranked, sources_queried=list(results_by_source.keys()))


class SourceReliabilityScorer:
    """Dynamic reliability scoring based on source quality signals."""
    
    def score(self, source: str, query: str) -> float:
        """Score 0-1 indicating how reliable this source is for this query type."""
        
        base_reliability = {
            "internal_kb": 0.95,      # Curated, reviewed
            "confluence": 0.80,       # May be stale
            "github": 0.85,           # Code is ground truth
            "slack": 0.50,            # Informal, may be outdated
            "gdrive": 0.70,           # Variable quality
            "jira": 0.75,             # Status may be stale
        }
        
        # Adjust based on historical accuracy for query type
        historical_accuracy = self.get_historical_accuracy(source, query)
        
        # Adjust based on freshness of source index
        freshness_penalty = self.index_staleness_penalty(source)
        
        # Adjust based on recent availability
        availability = self.recent_availability(source)  # 30-day p99
        
        return (
            0.4 * base_reliability.get(source, 0.5) +
            0.3 * historical_accuracy +
            0.2 * (1 - freshness_penalty) +
            0.1 * availability
        )
```

### Source Routing Strategy

| Query Intent | Primary Sources | Secondary Sources |
|-------------|----------------|-------------------|
| "How to deploy X" | Internal KB, Confluence | GitHub READMEs |
| "What did Y say about Z" | Slack, Email | Meeting notes |
| "Bug in feature X" | Jira, GitHub Issues | Slack threads |
| "Company policy on X" | Internal KB, GDrive | Confluence |

### Production Considerations

- **Timeout strategy**: Return results from fast sources immediately, stream slow sources as they complete (progressive rendering)
- **Access control**: Each connector respects source-level ACLs. Fused results filtered per-user permissions.
- **Deduplication**: MinHash + Jaccard similarity for near-duplicate detection across sources. Keep the version from the highest-reliability source.
- **Monitoring**: Track per-source latency p50/p99, availability, and result quality contribution. Auto-disable degraded sources.
# Knowledge Management and Organization (Questions 206-210)

## Q206: Design a Knowledge Graph Construction Pipeline

**Question:** Design a knowledge graph construction pipeline that automatically extracts entities and relationships from unstructured documents. Include entity resolution, relationship classification, and graph quality metrics.

**Answer:**

### Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Document    │────▶│  Entity      │────▶│  Relationship│────▶│  Graph       │
│  Ingestion   │     │  Extraction  │     │  Extraction  │     │  Construction│
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                       │
┌──────────────┐     ┌──────────────┐     ┌──────────────┐           │
│  Quality     │◀────│  Entity      │◀────│  Graph       │◀──────────┘
│  Metrics     │     │  Resolution  │     │  Store       │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Implementation

```python
class KnowledgeGraphBuilder:
    def __init__(self):
        self.entity_extractor = EntityExtractor()  # Fine-tuned NER + LLM
        self.relation_classifier = RelationClassifier()  # REBEL or LLM-based
        self.entity_resolver = EntityResolver()
        self.graph_store = Neo4jStore()
    
    async def process_document(self, doc: Document) -> GraphUpdate:
        """Extract entities and relationships from a single document."""
        
        # Chunk document for processing
        chunks = self.chunk_document(doc, max_tokens=512, overlap=50)
        
        all_entities = []
        all_relations = []
        
        for chunk in chunks:
            # Extract entities with types and spans
            entities = await self.entity_extractor.extract(chunk.text)
            # Extract relationships between entities in this chunk
            relations = await self.relation_classifier.classify(chunk.text, entities)
            
            all_entities.extend(entities)
            all_relations.extend(relations)
        
        # Cross-chunk entity resolution (same entity mentioned differently)
        resolved_entities = self.entity_resolver.resolve_within_doc(all_entities)
        
        # Global entity resolution (link to existing graph nodes)
        linked_entities = await self.entity_resolver.link_to_graph(resolved_entities)
        
        # Construct graph update
        return GraphUpdate(
            entities=linked_entities,
            relations=all_relations,
            source_doc=doc.id,
            confidence_scores=self.compute_confidences(linked_entities, all_relations),
        )
    
    def extract_entities_llm(self, text: str) -> list[Entity]:
        """LLM-based extraction for complex entity types."""
        prompt = f"""Extract all entities from the following text.
For each entity, provide: name, type, and any attributes.
Entity types: PERSON, ORGANIZATION, PRODUCT, TECHNOLOGY, CONCEPT, PROCESS, METRIC.

Text: {text}

Output as JSON array."""
        
        response = self.llm.generate(prompt)
        entities = json.loads(response)
        return [Entity(**e) for e in entities]


class EntityResolver:
    """Deduplicate entities across documents."""
    
    def __init__(self):
        self.blocking_index = MinHashLSH(threshold=0.5, num_perm=128)
        self.similarity_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    def resolve_within_doc(self, entities: list[Entity]) -> list[Entity]:
        """Merge entities that refer to the same real-world entity."""
        clusters = []
        
        for entity in entities:
            merged = False
            for cluster in clusters:
                if self.should_merge(entity, cluster[0]):
                    cluster.append(entity)
                    merged = True
                    break
            if not merged:
                clusters.append([entity])
        
        # Return canonical entity per cluster
        return [self.select_canonical(cluster) for cluster in clusters]
    
    def should_merge(self, e1: Entity, e2: Entity) -> bool:
        """Multi-signal merge decision."""
        if e1.type != e2.type:
            return False
        
        # String similarity
        name_sim = jellyfish.jaro_winkler_similarity(
            e1.name.lower(), e2.name.lower())
        
        # Embedding similarity
        emb_sim = cosine_similarity(
            self.similarity_model.encode(e1.name),
            self.similarity_model.encode(e2.name))
        
        # Acronym check
        is_acronym = self.is_acronym_of(e1.name, e2.name)
        
        return name_sim > 0.85 or emb_sim > 0.90 or is_acronym
```

### Graph Quality Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Entity precision | correct_entities / extracted_entities | >0.90 |
| Entity recall | correct_entities / total_entities_in_doc | >0.80 |
| Relation precision | correct_relations / extracted_relations | >0.85 |
| Resolution accuracy | correct_merges / total_merges | >0.95 |
| Graph connectivity | avg_degree / expected_degree | 0.7-1.3 |
| Freshness | % nodes updated in last 30 days | >60% |

### Production Considerations

- **Incremental updates**: Process only new/changed documents. Use document fingerprints to detect changes. Update affected subgraph only.
- **Confidence thresholds**: Only add edges with confidence >0.8 to the graph. Lower-confidence extractions go to a human review queue.
- **Conflict resolution**: When new extraction contradicts existing edge, keep both with provenance. Surface conflicts for resolution.
- **Scale**: Process 100K documents/day using Spark for batch extraction, Kafka for streaming updates to graph store.

---

## Q207: Design a Taxonomy and Ontology Management System

**Question:** Design a taxonomy and ontology management system for enterprise knowledge. How do you maintain consistent categorization across millions of documents as the business evolves?

**Answer:**

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Ontology Management Layer                 │
├─────────────┬──────────────┬──────────────┬─────────────┤
│  Taxonomy   │  Auto-       │  Version     │  Governance │
│  Editor     │  Classifier  │  Control     │  Workflow   │
└──────┬──────┴──────┬───────┴──────┬───────┴──────┬──────┘
       │             │              │              │
       ▼             ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│              Ontology Store (OWL/SKOS + Neo4j)           │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│         Document Classification Pipeline                 │
│  (Millions of documents auto-tagged against taxonomy)    │
└─────────────────────────────────────────────────────────┘
```

### Implementation

```python
class TaxonomyManager:
    def __init__(self):
        self.store = OntologyStore()  # Neo4j + versioned SKOS/OWL
        self.classifier = HierarchicalClassifier()
        self.drift_detector = TaxonomyDriftDetector()
    
    def evolve_taxonomy(self, proposed_change: TaxonomyChange) -> ChangeImpact:
        """Assess and apply taxonomy evolution with impact analysis."""
        
        # Impact analysis: how many documents affected?
        impact = self.analyze_impact(proposed_change)
        
        if proposed_change.type == "ADD_CONCEPT":
            # Check for overlap with existing concepts
            overlaps = self.find_overlaps(proposed_change.concept)
            if overlaps:
                return ChangeImpact(
                    status="NEEDS_REVIEW",
                    message=f"Overlaps with: {overlaps}",
                    affected_docs=0,
                )
            self.store.add_concept(proposed_change.concept, proposed_change.parent)
            
        elif proposed_change.type == "MERGE_CONCEPTS":
            # Reclassify affected documents
            affected_docs = self.store.get_docs_with_concept(proposed_change.source)
            self.queue_reclassification(affected_docs, proposed_change.target)
            self.store.merge(proposed_change.source, proposed_change.target)
            
        elif proposed_change.type == "SPLIT_CONCEPT":
            affected_docs = self.store.get_docs_with_concept(proposed_change.source)
            # Use classifier to redistribute documents among new sub-concepts
            self.redistribute_documents(affected_docs, proposed_change.new_concepts)
        
        # Version the change
        self.store.commit_version(proposed_change, impact)
        return impact
    
    def auto_classify(self, document: Document) -> list[Classification]:
        """Hierarchical multi-label classification against taxonomy."""
        
        # Top-down classification through taxonomy tree
        classifications = []
        candidates = self.store.get_root_concepts()
        
        while candidates:
            # Score document against candidate concepts
            scores = self.classifier.score(document, candidates)
            
            # Select concepts above threshold
            selected = [c for c, s in zip(candidates, scores) if s > 0.7]
            classifications.extend(selected)
            
            # Go deeper: get children of selected concepts
            candidates = []
            for concept in selected:
                children = self.store.get_children(concept)
                if children:
                    candidates.extend(children)
        
        return classifications


class TaxonomyDriftDetector:
    """Detect when taxonomy no longer fits the document corpus."""
    
    def detect_drift(self) -> list[DriftSignal]:
        signals = []
        
        # Signal 1: Emerging topics not in taxonomy
        uncategorized_clusters = self.cluster_uncategorized_docs()
        for cluster in uncategorized_clusters:
            if cluster.size > 100:
                signals.append(DriftSignal(
                    type="EMERGING_TOPIC",
                    description=cluster.label,
                    evidence_count=cluster.size,
                    suggested_parent=self.find_nearest_concept(cluster.centroid),
                ))
        
        # Signal 2: Categories with declining usage
        for concept in self.store.get_all_concepts():
            trend = self.compute_usage_trend(concept, window_days=90)
            if trend.slope < -0.5 and trend.current_count < 10:
                signals.append(DriftSignal(
                    type="DECLINING_CONCEPT",
                    description=f"{concept.name} rarely used",
                    evidence_count=trend.current_count,
                ))
        
        # Signal 3: Concepts with high misclassification rate
        for concept in self.store.get_all_concepts():
            precision = self.measure_classification_precision(concept)
            if precision < 0.7:
                signals.append(DriftSignal(
                    type="AMBIGUOUS_CONCEPT",
                    description=f"{concept.name} precision={precision:.2f}",
                ))
        
        return signals
```

### Governance Workflow

| Stage | Actor | Action |
|-------|-------|--------|
| Proposal | Any user | Submit taxonomy change request |
| Impact analysis | System | Auto-compute affected documents |
| Domain review | Subject matter expert | Validate semantic correctness |
| Technical review | Data team | Validate classifier can handle change |
| Approval | Taxonomy board | Monthly review of proposed changes |
| Rollout | System | Gradual reclassification with monitoring |
| Validation | QA | Sample review of reclassified documents |

### Production Scale

- **Batch reclassification**: When taxonomy changes, queue affected documents for reclassification via Spark job (process 1M docs in ~2 hours)
- **Consistency**: Use eventual consistency — new taxonomy version takes effect immediately for new docs, batch job catches up existing docs within 24h
- **Multi-language**: Store preferred labels in all supported languages. Classify using language-specific embeddings but map to universal concept IDs.

---

## Q208: Design a Knowledge Conflict Resolution System

**Question:** Design a knowledge conflict resolution system for RAG where multiple sources provide contradictory information. Include source authority ranking, temporal precedence, and explicit uncertainty communication.

**Answer:**

### Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Retrieved   │────▶│  Conflict        │────▶│  Resolution      │
│  Documents   │     │  Detection       │     │  Strategy        │
└──────────────┘     └──────────────────┘     └────────┬─────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  Response with     │
                                              │  Uncertainty       │
                                              │  Communication     │
                                              └───────────────────┘
```

### Implementation

```python
class ConflictResolver:
    def __init__(self):
        self.conflict_detector = ConflictDetector()
        self.authority_scorer = AuthorityScorer()
        self.temporal_analyzer = TemporalAnalyzer()
    
    async def resolve(self, query: str, documents: list[Document]) -> Resolution:
        """Detect and resolve conflicts in retrieved documents."""
        
        # Extract claims from each document
        claims_by_doc = {}
        for doc in documents:
            claims_by_doc[doc.id] = await self.extract_claims(doc, query)
        
        # Detect conflicting claims
        conflicts = self.conflict_detector.find_conflicts(claims_by_doc)
        
        if not conflicts:
            return Resolution(status="NO_CONFLICT", documents=documents)
        
        # Resolve each conflict
        resolutions = []
        for conflict in conflicts:
            resolution = self.resolve_conflict(conflict)
            resolutions.append(resolution)
        
        return Resolution(
            status="CONFLICTS_RESOLVED",
            resolutions=resolutions,
            uncertainty_level=self.compute_uncertainty(resolutions),
        )
    
    def resolve_conflict(self, conflict: Conflict) -> ConflictResolution:
        """Apply resolution strategy hierarchy."""
        
        claim_a, claim_b = conflict.claims
        doc_a, doc_b = conflict.source_docs
        
        # Strategy 1: Temporal precedence (newer wins for factual/policy)
        if self.is_time_sensitive(conflict.topic):
            newer = self.temporal_analyzer.get_newer(doc_a, doc_b)
            if newer and self.temporal_analyzer.staleness_gap(doc_a, doc_b) > timedelta(days=30):
                return ConflictResolution(
                    winner=newer,
                    strategy="TEMPORAL_PRECEDENCE",
                    confidence=0.85,
                    explanation=f"Using newer source ({newer.updated_at.date()})",
                )
        
        # Strategy 2: Source authority
        auth_a = self.authority_scorer.score(doc_a, conflict.topic)
        auth_b = self.authority_scorer.score(doc_b, conflict.topic)
        
        if abs(auth_a - auth_b) > 0.3:  # Clear authority difference
            winner = doc_a if auth_a > auth_b else doc_b
            return ConflictResolution(
                winner=winner,
                strategy="AUTHORITY",
                confidence=0.80,
                explanation=f"Source {winner.source} has higher authority for {conflict.topic}",
            )
        
        # Strategy 3: Consensus (if >2 sources agree)
        consensus = self.find_consensus(conflict.all_claims)
        if consensus:
            return ConflictResolution(
                winner=consensus.majority_doc,
                strategy="CONSENSUS",
                confidence=0.75,
                explanation=f"{consensus.count}/{len(conflict.all_claims)} sources agree",
            )
        
        # Strategy 4: Explicit uncertainty — present both views
        return ConflictResolution(
            winner=None,
            strategy="PRESENT_BOTH",
            confidence=0.50,
            explanation="Sources disagree; presenting both perspectives",
            both_claims=[claim_a, claim_b],
        )


class AuthorityScorer:
    """Score source authority for a given topic."""
    
    def score(self, doc: Document, topic: str) -> float:
        """0-1 authority score."""
        factors = {
            # Source type hierarchy
            "source_type": self.source_type_score(doc.source_type),
            # Author expertise (if known)
            "author_expertise": self.author_topic_expertise(doc.author, topic),
            # Document review status
            "review_status": {"approved": 1.0, "draft": 0.5, "unreviewed": 0.3}
                .get(doc.review_status, 0.3),
            # Citation count / reference frequency
            "citations": min(doc.citation_count / 50, 1.0),
            # Recency of last review
            "review_freshness": self.freshness_score(doc.last_reviewed_at),
        }
        
        weights = {"source_type": 0.3, "author_expertise": 0.25, 
                   "review_status": 0.2, "citations": 0.15, "review_freshness": 0.1}
        
        return sum(factors[k] * weights[k] for k in weights)
    
    def source_type_score(self, source_type: str) -> float:
        hierarchy = {
            "official_policy": 1.0,
            "documentation": 0.9,
            "peer_reviewed": 0.85,
            "internal_wiki": 0.7,
            "meeting_notes": 0.5,
            "slack_message": 0.3,
            "external_blog": 0.4,
        }
        return hierarchy.get(source_type, 0.5)
```

### Uncertainty Communication in Responses

```python
class UncertaintyFormatter:
    def format_response(self, answer: str, resolution: Resolution) -> str:
        if resolution.uncertainty_level < 0.2:
            return answer  # High confidence, no qualifier needed
        
        elif resolution.uncertainty_level < 0.5:
            return f"{answer}\n\n⚠️ Note: This information is based on " \
                   f"{resolution.primary_source} (last updated {resolution.date}). " \
                   f"Verify with the latest source."
        
        else:  # High uncertainty
            return f"There are conflicting sources on this topic:\n\n" \
                   f"**View 1** ({resolution.claims[0].source}): {resolution.claims[0].text}\n\n" \
                   f"**View 2** ({resolution.claims[1].source}): {resolution.claims[1].text}\n\n" \
                   f"The most recent source ({resolution.newest_source}) suggests View " \
                   f"{resolution.newest_view_idx}. Recommend verifying with the authoritative team."
```

### Production Metrics

| Metric | Target |
|--------|--------|
| Conflict detection recall | >90% (catch real conflicts) |
| Resolution accuracy | >85% (correct winner chosen) |
| User trust score | >4.2/5 (surveys on uncertain answers) |
| False conflict rate | <5% (don't flag non-conflicts) |

---

## Q209: Design an Automated Knowledge Gap Detection System

**Question:** Design an automated knowledge gap detection system that identifies topics where your RAG system has insufficient coverage. Include gap scoring, prioritized crawling, and content commissioning workflows.

**Answer:**

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Gap Detection Pipeline                    │
├───────────────┬───────────────┬───────────────────────────┤
│  Query        │  Coverage     │  Gap                      │
│  Analysis     │  Mapping      │  Prioritization           │
│               │               │                           │
│ • Failed      │ • Topic model │ • Business impact         │
│   queries     │ • Coverage    │ • Query frequency         │
│ • Low-conf    │   heatmap     │ • User frustration        │
│   answers     │ • Freshness   │ • Competitive gap         │
└───────────────┴───────────────┴───────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Remediation Engine  │
              ├──────────┬──────────┤
              │ Crawling │Commission│
              │ Pipeline │ Workflow │
              └──────────┴──────────┘
```

### Implementation

```python
class KnowledgeGapDetector:
    def __init__(self):
        self.query_store = QueryAnalyticsStore()
        self.coverage_mapper = CoverageMapper()
        self.gap_scorer = GapScorer()
    
    def detect_gaps(self, window_days: int = 30) -> list[KnowledgeGap]:
        """Identify topics with insufficient RAG coverage."""
        
        gaps = []
        
        # Signal 1: Queries with low retrieval confidence
        low_confidence_queries = self.query_store.get_queries(
            window_days=window_days,
            max_retrieval_score=0.5,  # Low similarity to any document
            min_frequency=5,  # Not one-off queries
        )
        
        # Cluster low-confidence queries into topics
        topic_clusters = self.cluster_queries(low_confidence_queries)
        
        for cluster in topic_clusters:
            gap = KnowledgeGap(
                topic=cluster.label,
                evidence_queries=cluster.queries,
                frequency=cluster.total_frequency,
                avg_retrieval_score=cluster.avg_score,
                gap_type="NO_COVERAGE",
            )
            gap.priority_score = self.gap_scorer.score(gap)
            gaps.append(gap)
        
        # Signal 2: Queries with high retrieval but negative feedback
        negative_feedback_queries = self.query_store.get_queries(
            window_days=window_days,
            min_retrieval_score=0.7,  # Good retrieval
            feedback="negative",  # But user unhappy
        )
        
        for cluster in self.cluster_queries(negative_feedback_queries):
            gaps.append(KnowledgeGap(
                topic=cluster.label,
                gap_type="STALE_OR_WRONG_COVERAGE",
                priority_score=self.gap_scorer.score_staleness(cluster),
            ))
        
        # Signal 3: Topic model coverage analysis
        corpus_topics = self.coverage_mapper.get_corpus_topics()
        expected_topics = self.coverage_mapper.get_expected_topics()  # From sitemap, org chart
        
        missing_topics = expected_topics - corpus_topics
        for topic in missing_topics:
            gaps.append(KnowledgeGap(
                topic=topic,
                gap_type="EXPECTED_BUT_MISSING",
                priority_score=self.gap_scorer.score_expected_topic(topic),
            ))
        
        # Sort by priority
        gaps.sort(key=lambda g: g.priority_score, reverse=True)
        return gaps


class GapScorer:
    """Prioritize gaps based on business impact."""
    
    def score(self, gap: KnowledgeGap) -> float:
        return (
            0.35 * self.normalize(gap.frequency) +          # How often asked
            0.25 * self.user_frustration_score(gap) +       # Repeated attempts
            0.20 * self.business_impact(gap.topic) +        # Revenue/support impact
            0.10 * self.ease_of_fill(gap) +                 # How easy to fix
            0.10 * self.competitive_importance(gap.topic)   # Competitors cover it
        )


class RemediationEngine:
    """Automatically fill knowledge gaps."""
    
    async def remediate(self, gap: KnowledgeGap) -> RemediationAction:
        # Strategy 1: Auto-crawl if content exists somewhere
        crawl_candidates = await self.find_crawlable_sources(gap.topic)
        if crawl_candidates:
            return RemediationAction(
                type="AUTO_CRAWL",
                sources=crawl_candidates,
                estimated_time="4 hours",
            )
        
        # Strategy 2: Commission content from SME
        sme = self.find_subject_matter_expert(gap.topic)
        if sme:
            return RemediationAction(
                type="COMMISSION_CONTENT",
                assignee=sme,
                template=self.generate_content_brief(gap),
                deadline=self.compute_deadline(gap.priority_score),
            )
        
        # Strategy 3: Flag for manual review
        return RemediationAction(
            type="MANUAL_REVIEW",
            description=f"No auto-remediation available for: {gap.topic}",
        )
```

### Gap Dashboard Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Coverage score | % of expected topics covered | >90% |
| Gap resolution time | Days from detection to fix | <14 days (P1), <30 days (P2) |
| Query success rate | % queries with confident answers | >85% |
| Gap recurrence | % gaps that reopen after fix | <10% |

---

## Q210: Design a Knowledge Lifecycle Management System

**Question:** Design a knowledge lifecycle management system (creation → review → publication → deprecation → archival) for AI-consumed documents. Include quality gates and freshness guarantees.

**Answer:**

### Lifecycle State Machine

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐
│  DRAFT   │───▶│  REVIEW  │───▶│ PUBLISHED │───▶│DEPRECATED │───▶│ ARCHIVED │
└──────────┘    └──────────┘    └───────────┘    └───────────┘    └──────────┘
     │               │               │                │
     │               │               ▼                │
     │               │         ┌───────────┐          │
     │               └────────▶│  REJECTED │          │
     │                         └───────────┘          │
     │                               │                │
     └───────────────────────────────┘                │
              (revision requested)                     │
                                                      ▼
                                              ┌──────────────┐
                                              │   DELETED    │
                                              └──────────────┘
```

### Implementation

```python
class KnowledgeLifecycleManager:
    def __init__(self):
        self.store = DocumentStore()
        self.quality_gate = QualityGateEngine()
        self.freshness_monitor = FreshnessMonitor()
        self.rag_index = RAGIndexManager()
    
    def transition(self, doc_id: str, target_state: str, actor: str) -> TransitionResult:
        """Manage state transitions with quality gates."""
        doc = self.store.get(doc_id)
        current_state = doc.lifecycle_state
        
        # Validate transition is allowed
        if target_state not in ALLOWED_TRANSITIONS[current_state]:
            raise InvalidTransitionError(f"{current_state} → {target_state} not allowed")
        
        # Run quality gates for this transition
        gate_result = self.quality_gate.evaluate(doc, current_state, target_state)
        if not gate_result.passed:
            return TransitionResult(
                success=False,
                blocked_by=gate_result.failures,
                suggestions=gate_result.remediation_suggestions,
            )
        
        # Execute transition
        doc.lifecycle_state = target_state
        doc.state_history.append(StateChange(
            from_state=current_state, to_state=target_state,
            actor=actor, timestamp=datetime.utcnow(),
        ))
        
        # Side effects
        self.execute_side_effects(doc, current_state, target_state)
        self.store.save(doc)
        
        return TransitionResult(success=True, new_state=target_state)
    
    def execute_side_effects(self, doc: Document, from_state: str, to_state: str):
        """Actions triggered by state transitions."""
        
        if to_state == "PUBLISHED":
            # Add to RAG index
            self.rag_index.add_document(doc)
            # Set review reminder
            self.schedule_review(doc, days=doc.review_frequency_days or 90)
            # Notify subscribers
            self.notify_topic_subscribers(doc)
        
        elif to_state == "DEPRECATED":
            # Remove from primary RAG results (but keep for historical queries)
            self.rag_index.mark_deprecated(doc)
            # Add deprecation notice to content
            doc.deprecation_notice = self.generate_deprecation_notice(doc)
            # Find and update documents that reference this one
            self.flag_referencing_docs(doc)
        
        elif to_state == "ARCHIVED":
            # Remove from RAG index entirely
            self.rag_index.remove_document(doc)
            # Move to cold storage
            self.store.move_to_archive(doc)


class QualityGateEngine:
    """Quality gates for each transition."""
    
    def evaluate(self, doc: Document, from_state: str, to_state: str) -> GateResult:
        gates = GATE_REGISTRY[(from_state, to_state)]
        failures = []
        
        for gate in gates:
            result = gate.check(doc)
            if not result.passed:
                failures.append(result)
        
        return GateResult(passed=len(failures) == 0, failures=failures)

# Gate definitions
GATE_REGISTRY = {
    ("DRAFT", "REVIEW"): [
        MinimumContentLength(min_words=100),
        MetadataComplete(required=["title", "author", "topic", "audience"]),
        NoPlaceholders(),  # No TODO or TBD markers
        SpellCheckPassed(),
    ],
    ("REVIEW", "PUBLISHED"): [
        PeerReviewApproved(min_approvals=1),
        TechnicalAccuracyVerified(),
        NoContradictionWithExisting(),  # Check against knowledge graph
        AIReadabilityCheck(max_complexity=12),  # Flesch-Kincaid grade
        AccessControlDefined(),
    ],
    ("PUBLISHED", "DEPRECATED"): [
        ReplacementDocumentExists(),  # Must point to successor
        NoActiveHighTrafficReferences(),  # Warn if heavily referenced
        DeprecationNoticeAdded(),
    ],
}


class FreshnessMonitor:
    """Ensure documents don't go stale in the RAG index."""
    
    def run_freshness_check(self) -> list[FreshnessAlert]:
        alerts = []
        
        for doc in self.store.get_published_documents():
            days_since_review = (datetime.utcnow() - doc.last_reviewed_at).days
            review_sla = doc.review_frequency_days or 90
            
            if days_since_review > review_sla:
                staleness_ratio = days_since_review / review_sla
                
                if staleness_ratio > 2.0:
                    # Severely stale — auto-deprecate with warning
                    alerts.append(FreshnessAlert(
                        doc=doc, severity="CRITICAL",
                        action="AUTO_DEPRECATE",
                        message=f"Not reviewed in {days_since_review} days (SLA: {review_sla})",
                    ))
                elif staleness_ratio > 1.5:
                    # Moderately stale — reduce ranking weight
                    alerts.append(FreshnessAlert(
                        doc=doc, severity="WARNING",
                        action="REDUCE_RANKING_WEIGHT",
                    ))
                else:
                    # Slightly overdue — notify owner
                    alerts.append(FreshnessAlert(
                        doc=doc, severity="INFO",
                        action="NOTIFY_OWNER",
                    ))
        
        return alerts
```

### Freshness SLAs by Content Type

| Content Type | Review Frequency | Auto-deprecate After | Staleness Penalty |
|-------------|-----------------|---------------------|-------------------|
| API docs | 30 days | 90 days | -50% ranking weight |
| Policy docs | 90 days | 180 days | -30% ranking weight |
| Tutorials | 60 days | 120 days | -40% ranking weight |
| Architecture decisions | 180 days | 365 days | -20% ranking weight |
| Meeting notes | Never reviewed | 90 days auto-archive | N/A |

### Production Considerations

- **Bulk operations**: When a product is EOL'd, cascade-deprecate all related docs in a single transaction
- **Ownership transfer**: When an author leaves, auto-assign docs to team lead with review reminder
- **RAG index sync**: Use event-driven architecture (doc state change → Kafka → RAG index update) with exactly-once semantics
- **Audit trail**: Every state change logged with actor, reason, and timestamp for compliance
# Conversational AI Architecture (Questions 211-215)

## Q211: Design a Production Conversational AI System

**Question:** Design a production conversational AI system that handles multi-turn dialogues with context management, topic switching, and graceful conversation repair. Include state machine and memory architecture.

**Answer:**

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Conversation Engine                        │
├──────────┬──────────────┬───────────────┬───────────────────┤
│  Input   │  Dialogue    │  Response     │  Output           │
│  Process │  Manager     │  Generator    │  Process          │
│          │              │               │                   │
│ • ASR/NLU│ • State      │ • RAG/LLM    │ • Safety filter   │
│ • Intent │   tracking   │ • Template   │ • TTS (if voice)  │
│ • Entity │ • Topic      │ • Action     │ • Channel adapt   │
│   extract│   switching  │   execution  │                   │
└──────────┴──────────────┴───────────────┴───────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────┐       ┌──────────────┐
│  Short-term  │       │  Long-term   │
│  Memory      │       │  Memory      │
│  (session)   │       │  (user)      │
└──────────────┘       └──────────────┘
```

### State Machine

```python
from enum import Enum
from transitions import Machine

class ConversationState(Enum):
    GREETING = "greeting"
    TOPIC_EXPLORATION = "topic_exploration"
    INFORMATION_GATHERING = "information_gathering"
    TASK_EXECUTION = "task_execution"
    CLARIFICATION = "clarification"
    REPAIR = "repair"
    HANDOFF = "handoff"
    CLOSING = "closing"

class ConversationStateMachine:
    states = [s.value for s in ConversationState]
    
    transitions = [
        {"trigger": "user_greeting", "source": "*", "dest": "greeting"},
        {"trigger": "new_topic", "source": "*", "dest": "topic_exploration"},
        {"trigger": "need_info", "source": "topic_exploration", "dest": "information_gathering"},
        {"trigger": "execute", "source": "information_gathering", "dest": "task_execution"},
        {"trigger": "unclear_input", "source": "*", "dest": "clarification"},
        {"trigger": "error_detected", "source": "*", "dest": "repair"},
        {"trigger": "escalate", "source": "*", "dest": "handoff"},
        {"trigger": "farewell", "source": "*", "dest": "closing"},
    ]
    
    def __init__(self):
        self.machine = Machine(
            model=self, states=self.states, 
            transitions=self.transitions, initial="greeting"
        )


class DialogueManager:
    def __init__(self):
        self.state_machine = ConversationStateMachine()
        self.memory = ConversationMemory()
        self.topic_tracker = TopicTracker()
    
    async def process_turn(self, user_input: str, session: Session) -> Response:
        """Process a single conversation turn."""
        
        # 1. Understand the input
        understanding = await self.understand(user_input, session)
        
        # 2. Detect topic switch
        topic_switch = self.topic_tracker.detect_switch(
            understanding, session.current_topic)
        
        if topic_switch:
            # Save current topic context before switching
            self.memory.park_topic(session.current_topic, session.topic_context)
            session.current_topic = topic_switch.new_topic
            
            # Check if returning to a parked topic
            if parked := self.memory.get_parked_topic(topic_switch.new_topic):
                session.topic_context = parked
        
        # 3. Update state machine
        trigger = self.determine_trigger(understanding, session)
        getattr(self.state_machine, trigger)()
        
        # 4. Generate response based on current state
        response = await self.generate_response(
            state=self.state_machine.state,
            understanding=understanding,
            session=session,
        )
        
        # 5. Update memory
        self.memory.add_turn(session.id, user_input, response, understanding)
        
        return response
    
    async def repair_conversation(self, session: Session, error_type: str) -> Response:
        """Graceful conversation repair strategies."""
        
        if error_type == "MISUNDERSTANDING":
            return Response(
                text="I think I may have misunderstood. Let me try again — "
                     f"are you asking about {session.last_intent}?",
                action="CLARIFY",
            )
        
        elif error_type == "LOST_CONTEXT":
            # Summarize what we know and ask to continue
            summary = self.memory.summarize_session(session.id)
            return Response(
                text=f"Let me recap what we've discussed: {summary}. "
                     "What would you like to focus on next?",
                action="RECAP",
            )
        
        elif error_type == "CAPABILITY_LIMIT":
            return Response(
                text="I'm not able to help with that specific request. "
                     "Would you like me to connect you with a specialist, "
                     "or is there something else I can assist with?",
                action="OFFER_ALTERNATIVES",
            )
```

### Memory Architecture

```python
class ConversationMemory:
    """Hierarchical memory: buffer → summary → long-term."""
    
    def __init__(self):
        self.buffer_store = Redis()       # Last N turns (raw)
        self.summary_store = Redis()      # Compressed session summaries
        self.long_term_store = PostgreSQL() # Cross-session user memory
    
    def get_context_for_llm(self, session_id: str, max_tokens: int = 4000) -> str:
        """Build context window with recency bias."""
        
        context_parts = []
        tokens_used = 0
        
        # Priority 1: System prompt + current topic context
        # Priority 2: Last 3-5 turns (raw)
        recent_turns = self.buffer_store.get_recent(session_id, limit=5)
        for turn in reversed(recent_turns):
            turn_text = f"User: {turn.user}\nAssistant: {turn.assistant}\n"
            if tokens_used + count_tokens(turn_text) > max_tokens * 0.6:
                break
            context_parts.append(turn_text)
            tokens_used += count_tokens(turn_text)
        
        # Priority 3: Session summary (for older context)
        summary = self.summary_store.get(session_id)
        if summary and tokens_used < max_tokens * 0.8:
            context_parts.append(f"[Earlier in conversation: {summary}]")
        
        # Priority 4: User long-term preferences
        user_context = self.long_term_store.get_user_context(session_id)
        if user_context:
            context_parts.append(f"[User preferences: {user_context}]")
        
        return "\n".join(context_parts)
    
    def summarize_and_compress(self, session_id: str):
        """Compress old turns into summary when buffer exceeds threshold."""
        turns = self.buffer_store.get_all(session_id)
        if len(turns) > 10:
            old_turns = turns[:-5]  # Keep last 5 raw
            summary = self.llm_summarize(old_turns)
            self.summary_store.set(session_id, summary)
            self.buffer_store.trim(session_id, keep_last=5)
```

### Production Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Task completion rate | >80% | User achieves goal without escalation |
| Avg turns to resolution | <5 | Fewer turns = better understanding |
| Topic switch accuracy | >90% | Correctly identifies context changes |
| Repair success rate | >70% | Conversation recovers after confusion |
| User satisfaction (CSAT) | >4.2/5 | Post-conversation survey |

---

## Q212: Design a Dialogue Management System for Complex Workflows

**Question:** Design a dialogue management system that tracks user intent across a complex multi-step workflow (e.g., booking a flight with multiple stops, date changes, and passenger additions).

**Answer:**

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                 Workflow Dialogue Manager                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────┐    ┌──────────┐    ┌─────────────────┐    │
│  │ Intent  │───▶│  Slot    │───▶│  Workflow        │    │
│  │ Router  │    │  Filler  │    │  Orchestrator    │    │
│  └─────────┘    └──────────┘    └────────┬────────┘    │
│                                           │              │
│                                  ┌────────▼────────┐    │
│                                  │  Domain Actions │    │
│                                  │  (API calls)    │    │
│                                  └─────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Slot:
    name: str
    type: str  # "date", "city", "int", "enum"
    required: bool = True
    value: Optional[any] = None
    confirmed: bool = False
    prompt: str = ""
    validation: callable = None

@dataclass
class WorkflowStep:
    name: str
    slots: list[Slot]
    action: str  # API action to execute when all slots filled
    next_steps: list[str] = field(default_factory=list)
    condition: callable = None  # Dynamic next step based on results

class FlightBookingWorkflow:
    """Multi-step flight booking with modifications."""
    
    def __init__(self):
        self.steps = {
            "search_flights": WorkflowStep(
                name="search_flights",
                slots=[
                    Slot("origin", "city", required=True, prompt="Where are you flying from?"),
                    Slot("destination", "city", required=True, prompt="Where to?"),
                    Slot("departure_date", "date", required=True, prompt="When do you want to depart?"),
                    Slot("return_date", "date", required=False, prompt="Is this a round trip? If so, when do you return?"),
                    Slot("passengers", "int", required=True, prompt="How many passengers?"),
                    Slot("cabin_class", "enum", required=False, prompt="Any cabin preference?"),
                ],
                action="search_flights_api",
                next_steps=["select_flight"],
            ),
            "select_flight": WorkflowStep(
                name="select_flight",
                slots=[
                    Slot("selected_flight_id", "string", required=True, prompt="Which flight would you like?"),
                ],
                action="hold_flight",
                next_steps=["add_passengers", "add_stop"],
            ),
            "add_stop": WorkflowStep(
                name="add_stop",
                slots=[
                    Slot("stop_city", "city", required=True, prompt="Which city for the stopover?"),
                    Slot("stop_duration", "duration", required=True, prompt="How long in that city?"),
                ],
                action="search_multi_city",
                next_steps=["select_flight"],
            ),
            "add_passengers": WorkflowStep(
                name="add_passengers",
                slots=[
                    Slot("passenger_name", "string", required=True, prompt="Passenger full name?"),
                    Slot("passenger_dob", "date", required=True, prompt="Date of birth?"),
                    Slot("passenger_doc", "string", required=True, prompt="Passport/ID number?"),
                ],
                action="add_passenger_api",
                next_steps=["add_passengers", "payment"],  # Loop or proceed
            ),
            "payment": WorkflowStep(
                name="payment",
                slots=[
                    Slot("payment_method", "enum", required=True, prompt="How would you like to pay?"),
                ],
                action="process_payment",
                next_steps=["confirmation"],
            ),
        }
        self.current_step = "search_flights"
        self.completed_steps = []
        self.context = {}  # Accumulated slot values
    
    async def process_input(self, user_input: str, nlu_result: dict) -> Response:
        """Process user input within the workflow."""
        
        step = self.steps[self.current_step]
        
        # Check for workflow-level intents (modifications)
        if nlu_result["intent"] == "MODIFY_PREVIOUS":
            return await self.handle_modification(nlu_result)
        
        if nlu_result["intent"] == "ADD_STOP":
            self.current_step = "add_stop"
            step = self.steps["add_stop"]
        
        # Fill slots from the input
        filled = self.fill_slots(step, nlu_result["entities"])
        
        # Check for unfilled required slots
        missing = [s for s in step.slots if s.required and s.value is None]
        
        if missing:
            # Ask for next missing slot (with context-aware prompting)
            return Response(
                text=self.contextualize_prompt(missing[0], self.context),
                state="SLOT_FILLING",
                missing_slots=[s.name for s in missing],
            )
        
        # All slots filled — confirm before executing
        if not self.all_confirmed(step):
            return self.generate_confirmation(step)
        
        # Execute action
        result = await self.execute_action(step)
        self.completed_steps.append(self.current_step)
        self.context.update(result)
        
        # Determine next step
        self.current_step = self.determine_next_step(step, result)
        
        return Response(
            text=self.format_action_result(result),
            state="STEP_COMPLETE",
            next_step=self.current_step,
        )
    
    async def handle_modification(self, nlu_result: dict) -> Response:
        """Handle mid-workflow modifications (e.g., 'change the date')."""
        
        target_slot = nlu_result.get("target_slot")
        target_step = self.find_step_with_slot(target_slot)
        
        if target_step in self.completed_steps:
            # Need to undo downstream steps
            steps_to_undo = self.get_downstream_steps(target_step)
            for step_name in steps_to_undo:
                await self.undo_step(step_name)
                self.completed_steps.remove(step_name)
            
            # Reset the target slot
            self.steps[target_step].slots[target_slot].value = None
            self.steps[target_step].slots[target_slot].confirmed = False
            self.current_step = target_step
            
            return Response(
                text=f"No problem! Let me update the {target_slot}. "
                     f"{self.steps[target_step].slots[target_slot].prompt}",
                state="MODIFICATION",
            )
        
        # Slot in current or future step — just clear it
        self.steps[target_step].slots[target_slot].value = None
        return Response(text=f"Sure, what would you like the new {target_slot} to be?")
```

### State Persistence

```python
class WorkflowStateStore:
    """Persist workflow state for recovery and async operations."""
    
    def save_state(self, session_id: str, workflow: FlightBookingWorkflow):
        state = {
            "current_step": workflow.current_step,
            "completed_steps": workflow.completed_steps,
            "context": workflow.context,
            "slot_values": {
                step_name: {s.name: s.value for s in step.slots}
                for step_name, step in workflow.steps.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.redis.set(f"workflow:{session_id}", json.dumps(state), ex=86400)
```

### Metrics

| Metric | Target |
|--------|--------|
| Workflow completion rate | >75% |
| Avg turns per workflow | <12 |
| Modification success rate | >90% |
| Slot filling accuracy | >95% |
| Abandonment rate | <20% |

---

## Q213: Design a Proactive AI Assistant

**Question:** Design a proactive AI assistant that anticipates user needs based on context (time of day, calendar, recent activities) and offers suggestions without being asked. Include relevance scoring and annoyance avoidance.

**Answer:**

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                Proactive Suggestion Engine                 │
├────────────────┬─────────────────┬───────────────────────┤
│  Context       │  Suggestion     │  Delivery             │
│  Collector     │  Generator      │  Manager              │
│                │                 │                       │
│ • Calendar     │ • Rule engine   │ • Relevance filter    │
│ • Activity     │ • ML predictor  │ • Annoyance limiter   │
│ • Location     │ • Pattern match │ • Channel selector    │
│ • Time/date    │                 │ • Timing optimizer    │
└────────────────┴─────────────────┴───────────────────────┘
```

### Implementation

```python
class ProactiveAssistant:
    def __init__(self):
        self.context_collector = ContextCollector()
        self.suggestion_generator = SuggestionGenerator()
        self.delivery_manager = DeliveryManager()
        self.annoyance_tracker = AnnoyanceTracker()
    
    async def generate_suggestions(self, user: User) -> list[Suggestion]:
        """Generate proactive suggestions based on current context."""
        
        # Collect all available context signals
        context = await self.context_collector.collect(user)
        
        # Generate candidate suggestions from multiple sources
        candidates = []
        candidates.extend(self.calendar_suggestions(context))
        candidates.extend(self.activity_suggestions(context))
        candidates.extend(self.pattern_suggestions(context))
        candidates.extend(self.deadline_suggestions(context))
        
        # Score each suggestion for relevance and timeliness
        scored = []
        for suggestion in candidates:
            relevance = self.score_relevance(suggestion, context, user)
            timeliness = self.score_timeliness(suggestion, context)
            annoyance_risk = self.annoyance_tracker.risk_score(user, suggestion)
            
            # Final score: high relevance + good timing - annoyance risk
            final_score = (0.5 * relevance + 0.3 * timeliness - 0.2 * annoyance_risk)
            
            if final_score > 0.6:  # Threshold for showing
                suggestion.score = final_score
                scored.append(suggestion)
        
        # Apply delivery limits
        return self.delivery_manager.filter_and_schedule(scored, user)
    
    def calendar_suggestions(self, context: Context) -> list[Suggestion]:
        """Suggestions based on upcoming calendar events."""
        suggestions = []
        
        for event in context.upcoming_events(hours=2):
            # Meeting prep
            if event.type == "meeting" and event.starts_in_minutes < 30:
                suggestions.append(Suggestion(
                    type="MEETING_PREP",
                    title=f"Prepare for: {event.title}",
                    content=f"Meeting with {event.attendees} in {event.starts_in_minutes} min. "
                            f"Would you like me to summarize recent docs about {event.topic}?",
                    action="summarize_meeting_context",
                    urgency=0.8,
                ))
            
            # Travel reminder
            if event.location and event.requires_travel:
                travel_time = self.estimate_travel(context.location, event.location)
                leave_by = event.start - travel_time - timedelta(minutes=10)
                if datetime.now() > leave_by - timedelta(minutes=15):
                    suggestions.append(Suggestion(
                        type="TRAVEL_REMINDER",
                        title=f"Leave soon for {event.title}",
                        content=f"~{travel_time.minutes}min travel time to {event.location}",
                        urgency=0.9,
                    ))
        
        return suggestions


class AnnoyanceTracker:
    """Prevent suggestion fatigue."""
    
    def __init__(self):
        self.interaction_log = InteractionLog()
        self.user_preferences = UserPreferenceStore()
    
    def risk_score(self, user: User, suggestion: Suggestion) -> float:
        """Score 0-1 indicating how annoying this suggestion would be."""
        
        factors = {
            # How many suggestions shown today already?
            "daily_count": min(self.today_count(user) / self.daily_limit(user), 1.0),
            
            # Was a similar suggestion dismissed recently?
            "recently_dismissed": 1.0 if self.was_dismissed_recently(
                user, suggestion.type, hours=24) else 0.0,
            
            # Is the user in focus mode / DND?
            "focus_mode": 1.0 if self.is_focused(user) else 0.0,
            
            # User's historical acceptance rate for this type
            "type_rejection_rate": self.rejection_rate(user, suggestion.type),
            
            # Time since last suggestion
            "recency": max(0, 1 - (self.minutes_since_last(user) / 30)),
        }
        
        return (
            0.25 * factors["daily_count"] +
            0.25 * factors["recently_dismissed"] +
            0.20 * factors["focus_mode"] +
            0.15 * factors["type_rejection_rate"] +
            0.15 * factors["recency"]
        )
    
    def daily_limit(self, user: User) -> int:
        """Adaptive daily limit based on user engagement."""
        base_limit = self.user_preferences.get(user, "suggestion_limit", default=8)
        
        # Reduce if user has been dismissing a lot
        recent_acceptance = self.acceptance_rate(user, days=7)
        if recent_acceptance < 0.2:
            return max(2, base_limit // 2)  # Cut in half
        elif recent_acceptance > 0.6:
            return min(15, base_limit + 2)  # Increase slightly
        
        return base_limit
```

### Delivery Timing Strategy

| Signal | Action | Example |
|--------|--------|---------|
| User idle >5 min | Safe to suggest | Show meeting prep |
| User typing | Do NOT interrupt | Queue for later |
| Between tasks | Good timing | Suggest next priority |
| End of day | Summary appropriate | Daily recap |
| DND / Focus | Suppress all | Only emergencies |

### Key Design Principles

1. **Value > interruption cost**: Only show if expected value to user exceeds interruption cost
2. **Graceful degradation**: If user ignores suggestions, reduce frequency automatically
3. **Explainability**: Always show WHY suggesting ("Because you have a meeting in 20 min...")
4. **Easy dismissal**: One-tap dismiss, with option "don't show this type again"
5. **Learning loop**: Track accept/dismiss/ignore to improve scoring model

---

## Q214: Design a Multi-Channel Conversational AI

**Question:** Design a multi-channel conversational AI that maintains consistent state across web chat, voice, email, and mobile. Include handoff between channels and conversation continuity.

**Answer:**

### Architecture

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│  Web    │  │  Voice  │  │  Email  │  │  Mobile │
│  Chat   │  │  (IVR)  │  │         │  │  App    │
└────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
     │            │            │            │
     ▼            ▼            ▼            ▼
┌──────────────────────────────────────────────────┐
│           Channel Adapter Layer                    │
│  (Normalize input/output per channel)             │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────▼────────┐
              │  Unified        │
              │  Conversation   │
              │  Engine         │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Conversation   │
              │  State Store    │
              │  (cross-channel)│
              └─────────────────┘
```

### Implementation

```python
class ChannelAdapter:
    """Normalize channel-specific I/O to unified format."""
    
    adapters = {
        "web_chat": WebChatAdapter(),
        "voice": VoiceAdapter(),
        "email": EmailAdapter(),
        "mobile": MobileAdapter(),
    }
    
    def normalize_input(self, channel: str, raw_input: dict) -> UnifiedMessage:
        """Convert channel-specific input to unified format."""
        adapter = self.adapters[channel]
        return adapter.to_unified(raw_input)
    
    def format_output(self, channel: str, response: UnifiedResponse) -> dict:
        """Convert unified response to channel-specific format."""
        adapter = self.adapters[channel]
        return adapter.from_unified(response)


class VoiceAdapter:
    def to_unified(self, raw: dict) -> UnifiedMessage:
        return UnifiedMessage(
            text=raw["transcript"],  # ASR output
            confidence=raw["asr_confidence"],
            channel="voice",
            metadata={"caller_id": raw["phone"], "duration": raw["duration"]},
        )
    
    def from_unified(self, response: UnifiedResponse) -> dict:
        # Voice: shorter responses, no markdown, SSML for pronunciation
        text = self.simplify_for_voice(response.text)
        return {
            "ssml": self.text_to_ssml(text),
            "max_duration_sec": 30,  # Keep voice responses short
            "actions": self.convert_actions_to_dtmf(response.actions),
        }


class EmailAdapter:
    def to_unified(self, raw: dict) -> UnifiedMessage:
        # Extract the actual question from email thread (ignore signatures, quotes)
        clean_text = self.extract_new_content(raw["body"])
        return UnifiedMessage(
            text=clean_text,
            channel="email",
            metadata={"subject": raw["subject"], "thread_id": raw["thread_id"]},
        )
    
    def from_unified(self, response: UnifiedResponse) -> dict:
        # Email: can be longer, include links, formatted
        return {
            "subject": f"Re: {response.context.get('subject', 'Your inquiry')}",
            "body_html": self.format_as_email(response.text, response.sources),
            "attachments": response.attachments,
        }


class CrossChannelStateManager:
    """Maintain conversation state across channels."""
    
    def __init__(self):
        self.store = DynamoDB()  # Conversation state
        self.identity_resolver = IdentityResolver()  # Link user across channels
    
    async def get_or_create_conversation(self, user_identity: dict, 
                                          channel: str) -> Conversation:
        """Find existing conversation or create new one."""
        
        # Resolve user identity across channels
        user_id = await self.identity_resolver.resolve(user_identity, channel)
        
        # Find active conversation for this user (any channel)
        active_conv = await self.store.get_active_conversation(user_id)
        
        if active_conv:
            # Continue existing conversation on new channel
            active_conv.add_channel_event(ChannelEvent(
                type="CHANNEL_SWITCH",
                from_channel=active_conv.current_channel,
                to_channel=channel,
                timestamp=datetime.utcnow(),
            ))
            active_conv.current_channel = channel
            return active_conv
        
        # Create new conversation
        return Conversation(
            id=uuid4(),
            user_id=user_id,
            current_channel=channel,
            created_at=datetime.utcnow(),
        )
    
    async def handoff_to_channel(self, conversation: Conversation, 
                                  target_channel: str, reason: str) -> HandoffResult:
        """Initiate handoff from one channel to another."""
        
        # Generate handoff context summary
        summary = self.summarize_conversation(conversation)
        
        # Create handoff token (user can resume on target channel)
        token = HandoffToken(
            conversation_id=conversation.id,
            target_channel=target_channel,
            summary=summary,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        
        # Notify user on target channel
        if target_channel == "email":
            await self.send_handoff_email(conversation.user, token, summary)
        elif target_channel == "mobile":
            await self.send_push_notification(conversation.user, token)
        
        return HandoffResult(token=token, summary=summary)
```

### Channel Capability Matrix

| Feature | Web Chat | Voice | Email | Mobile |
|---------|----------|-------|-------|--------|
| Response length | Medium | Short | Long | Medium |
| Rich media | Yes | No | Limited | Yes |
| Real-time | Yes | Yes | No | Yes |
| Interruption | Allowed | Allowed | N/A | Allowed |
| Actions/buttons | Yes | DTMF only | Links | Yes |
| File upload | Yes | No | Yes | Yes |
| Latency budget | 2s | 500ms | 30min | 2s |

### Production Considerations

- **Identity resolution**: Match users across channels using email, phone, SSO ID, or device fingerprint. Handle ambiguity gracefully.
- **Context compression**: When switching from verbose channel (email) to constrained channel (voice), auto-summarize context.
- **Channel-specific guardrails**: Voice responses must be <30s. Email can include detailed tables. Mobile adapts to screen size.
- **Async continuity**: If user starts on chat, leaves, returns via email 2 hours later, seamlessly continue with context summary.

---

## Q215: Design a Conversation Analytics System

**Question:** Design a conversation analytics system that extracts insights from millions of AI-user conversations. Include topic clustering, sentiment analysis, failure pattern detection, and product feedback extraction.

**Answer:**

### Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Conversation│────▶│  Analytics       │────▶│  Insights        │
│  Stream      │     │  Pipeline        │     │  Dashboard       │
│  (Kafka)     │     │  (Spark/Flink)   │     │  (Superset)      │
└──────────────┘     └────────┬─────────┘     └──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌────────────┐  ┌──────────────┐  ┌────────────┐
     │  Topic     │  │  Sentiment   │  │  Failure   │
     │  Clustering│  │  Analysis    │  │  Detection │
     └────────────┘  └──────────────┘  └────────────┘
```

### Implementation

```python
class ConversationAnalyticsPipeline:
    def __init__(self):
        self.topic_clusterer = TopicClusterer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.failure_detector = FailureDetector()
        self.feedback_extractor = FeedbackExtractor()
    
    async def analyze_conversation(self, conversation: Conversation) -> ConversationInsights:
        """Extract all insights from a single conversation."""
        
        # Run all analyzers in parallel
        topics, sentiment, failures, feedback = await asyncio.gather(
            self.topic_clusterer.classify(conversation),
            self.sentiment_analyzer.analyze_trajectory(conversation),
            self.failure_detector.detect(conversation),
            self.feedback_extractor.extract(conversation),
        )
        
        return ConversationInsights(
            conversation_id=conversation.id,
            topics=topics,
            sentiment=sentiment,
            failures=failures,
            feedback=feedback,
            metadata={
                "duration": conversation.duration,
                "turns": len(conversation.turns),
                "resolution": conversation.resolution_status,
            },
        )


class TopicClusterer:
    """Hierarchical topic clustering across conversations."""
    
    def __init__(self):
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.cluster_model = BERTopic(
            embedding_model=self.embedding_model,
            nr_topics="auto",
            min_topic_size=50,
        )
    
    def batch_cluster(self, conversations: list[Conversation]) -> TopicReport:
        """Cluster thousands of conversations into topics."""
        
        # Embed conversation summaries
        summaries = [self.summarize(c) for c in conversations]
        
        topics, probs = self.cluster_model.fit_transform(summaries)
        
        # Extract topic labels using representative docs
        topic_info = self.cluster_model.get_topic_info()
        
        return TopicReport(
            topics=topic_info,
            distribution=Counter(topics),
            emerging_topics=self.detect_emerging(topics, conversations),
            declining_topics=self.detect_declining(topics, conversations),
        )


class FailureDetector:
    """Detect conversation failures and their patterns."""
    
    FAILURE_SIGNALS = {
        "REPEATED_QUERY": lambda c: c.has_repeated_questions(threshold=2),
        "ESCALATION": lambda c: c.ended_with_human_handoff,
        "NEGATIVE_FEEDBACK": lambda c: c.explicit_feedback == "negative",
        "ABANDONMENT": lambda c: c.abandoned_mid_task,
        "HALLUCINATION_FLAGGED": lambda c: c.has_correction_pattern,
        "LONG_CONVERSATION": lambda c: len(c.turns) > 15 and not c.resolved,
        "SENTIMENT_DROP": lambda c: c.sentiment_trajectory[-1] < -0.5,
    }
    
    def detect(self, conversation: Conversation) -> list[Failure]:
        """Identify all failure signals in a conversation."""
        failures = []
        
        for signal_name, detector in self.FAILURE_SIGNALS.items():
            if detector(conversation):
                failures.append(Failure(
                    type=signal_name,
                    turn_index=self.find_failure_turn(conversation, signal_name),
                    severity=self.compute_severity(signal_name, conversation),
                    root_cause=self.infer_root_cause(conversation, signal_name),
                ))
        
        return failures
    
    def aggregate_failure_patterns(self, failures: list[Failure], 
                                    window_days: int = 7) -> FailureReport:
        """Find systemic failure patterns across conversations."""
        
        # Group by root cause
        by_cause = defaultdict(list)
        for f in failures:
            by_cause[f.root_cause].append(f)
        
        # Rank by frequency × severity
        patterns = []
        for cause, instances in by_cause.items():
            avg_severity = np.mean([f.severity for f in instances])
            patterns.append(FailurePattern(
                root_cause=cause,
                frequency=len(instances),
                avg_severity=avg_severity,
                impact_score=len(instances) * avg_severity,
                example_conversations=[f.conversation_id for f in instances[:5]],
                suggested_fix=self.suggest_fix(cause, instances),
            ))
        
        patterns.sort(key=lambda p: p.impact_score, reverse=True)
        return FailureReport(patterns=patterns)


class FeedbackExtractor:
    """Extract product feedback from conversations."""
    
    async def extract(self, conversation: Conversation) -> list[ProductFeedback]:
        """Use LLM to extract actionable product feedback."""
        
        prompt = f"""Analyze this conversation and extract any product feedback, 
feature requests, or pain points expressed by the user.

Conversation:
{conversation.to_text()}

For each piece of feedback, provide:
- category: bug_report | feature_request | usability_issue | praise
- description: one sentence summary
- urgency: low | medium | high
- affected_feature: which product area

Return as JSON array. Return empty array if no feedback found."""
        
        response = await self.llm.generate(prompt)
        feedback_items = json.loads(response)
        
        return [ProductFeedback(**item) for item in feedback_items]
```

### Dashboard Metrics

| Category | Metrics |
|----------|---------|
| Volume | Conversations/day, turns/conversation, messages/hour |
| Quality | Resolution rate, CSAT, first-contact resolution |
| Failures | Failure rate by type, MTTR, escalation rate |
| Topics | Top topics, emerging topics, topic shift velocity |
| Feedback | Feature requests/week, bug reports, NPS trend |

### Scale Considerations

- **Processing**: Spark Structured Streaming for real-time aggregation, daily batch for deep clustering
- **Storage**: Raw conversations in S3 (parquet), aggregated metrics in ClickHouse, topic model in MLflow
- **Privacy**: PII redaction before analytics. Conversation content only accessible with audit log. Aggregate metrics available to all.
- **Alerting**: Real-time alerts when failure rate spikes >2σ above baseline. Auto-page on-call when CSAT drops below threshold.
# Enterprise AI Integration (Questions 216-220)

## Q216: Design an AI Gateway

**Question:** Design an AI gateway that sits between enterprise applications and multiple LLM providers. Include request routing, response caching, content filtering, cost tracking, and provider failover.

**Answer:**

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI Gateway                               │
├─────────┬──────────┬──────────┬───────────┬────────────────────┤
│  Auth   │  Rate    │  Content │  Router   │  Response          │
│  & ACL  │  Limiter │  Filter  │           │  Cache             │
└────┬────┴────┬─────┴────┬─────┴─────┬─────┴──────┬─────────────┘
     │         │          │           │            │
     ▼         ▼          ▼           ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Provider Abstraction Layer                     │
├────────────┬────────────┬────────────┬────────────┬─────────────┤
│  OpenAI    │  Anthropic │  Azure     │  Self-     │  Fallback   │
│            │            │  OpenAI    │  Hosted    │  Provider   │
└────────────┴────────────┴────────────┴────────────┴─────────────┘
```

### Implementation

```python
class AIGateway:
    def __init__(self):
        self.router = ModelRouter()
        self.cache = ResponseCache()
        self.content_filter = ContentFilter()
        self.cost_tracker = CostTracker()
        self.rate_limiter = RateLimiter()
        self.circuit_breakers = {p: CircuitBreaker() for p in PROVIDERS}
    
    async def process_request(self, request: AIRequest) -> AIResponse:
        """Main gateway request processing pipeline."""
        
        # 1. Authentication & authorization
        self.authenticate(request)
        self.authorize(request.app_id, request.model_tier)
        
        # 2. Rate limiting (per app, per user, global)
        await self.rate_limiter.check(request.app_id, request.user_id)
        
        # 3. Content filtering (input)
        filtered_input = await self.content_filter.filter_input(request)
        if filtered_input.blocked:
            return AIResponse(status="BLOCKED", reason=filtered_input.reason)
        
        # 4. Cache check (semantic cache)
        cached = await self.cache.get(request)
        if cached:
            self.cost_tracker.record(request, cost=0, cache_hit=True)
            return cached
        
        # 5. Route to provider
        provider, model = self.router.route(request)
        
        # 6. Execute with failover
        response = await self.execute_with_failover(request, provider, model)
        
        # 7. Content filtering (output)
        filtered_output = await self.content_filter.filter_output(response)
        
        # 8. Track costs
        self.cost_tracker.record(request, response.usage, provider)
        
        # 9. Cache response
        await self.cache.set(request, filtered_output)
        
        return filtered_output
    
    async def execute_with_failover(self, request: AIRequest, 
                                     primary_provider: str, 
                                     model: str) -> AIResponse:
        """Execute request with automatic failover on provider failure."""
        
        fallback_chain = self.router.get_fallback_chain(primary_provider, model)
        
        for provider in [primary_provider] + fallback_chain:
            cb = self.circuit_breakers[provider]
            
            if not cb.is_available():
                continue
            
            try:
                response = await asyncio.wait_for(
                    self.providers[provider].generate(request, model),
                    timeout=request.timeout_ms / 1000,
                )
                cb.record_success()
                return response
                
            except (TimeoutError, ProviderError) as e:
                cb.record_failure()
                self.alerter.warn(f"Provider {provider} failed: {e}")
                continue
        
        raise AllProvidersFailedError("All providers in fallback chain failed")


class ModelRouter:
    """Route requests to optimal provider based on requirements."""
    
    def route(self, request: AIRequest) -> tuple[str, str]:
        """Select provider and model based on request requirements."""
        
        routing_rules = [
            # Cost-sensitive: use cheapest provider
            (lambda r: r.priority == "cost", self.cheapest_available),
            # Latency-sensitive: use fastest provider
            (lambda r: r.priority == "latency", self.fastest_available),
            # Quality-sensitive: use best model
            (lambda r: r.priority == "quality", self.best_quality),
            # Data residency: specific region required
            (lambda r: r.data_residency, self.region_compliant),
            # Default: balanced
            (lambda r: True, self.balanced_route),
        ]
        
        for condition, router_fn in routing_rules:
            if condition(request):
                return router_fn(request)
    
    def balanced_route(self, request: AIRequest) -> tuple[str, str]:
        """Balance cost, latency, and quality."""
        candidates = self.get_capable_providers(request.capabilities_needed)
        
        scored = []
        for provider, model in candidates:
            score = (
                0.4 * self.quality_score(provider, model) +
                0.3 * (1 - self.latency_score(provider)) +
                0.3 * (1 - self.cost_score(provider, model, request.est_tokens))
            )
            scored.append((provider, model, score))
        
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[0][0], scored[0][1]


class CostTracker:
    """Real-time cost tracking and budget enforcement."""
    
    def record(self, request: AIRequest, usage: TokenUsage, provider: str):
        cost = self.calculate_cost(provider, usage)
        
        # Record per-app, per-team, per-user
        self.redis.incrbyfloat(f"cost:app:{request.app_id}:daily", cost)
        self.redis.incrbyfloat(f"cost:team:{request.team_id}:monthly", cost)
        
        # Check budget alerts
        daily_spend = float(self.redis.get(f"cost:app:{request.app_id}:daily") or 0)
        budget = self.get_budget(request.app_id)
        
        if daily_spend > budget.daily_limit * 0.8:
            self.alert(f"App {request.app_id} at 80% daily budget")
        if daily_spend > budget.daily_limit:
            self.enforce_throttle(request.app_id)
```

### Cost and Performance Metrics

| Provider | Cost (per 1M tokens) | p50 Latency | Availability |
|----------|---------------------|-------------|--------------|
| OpenAI GPT-4 | $30 input / $60 output | 800ms | 99.5% |
| Anthropic Claude | $15 / $75 | 600ms | 99.7% |
| Azure OpenAI | $30 / $60 | 500ms | 99.9% |
| Self-hosted Llama | $2 / $2 | 300ms | 99.0% |

### Production Considerations

- **Semantic caching**: Hash normalized prompts + embedding similarity for cache hits on semantically similar (not identical) queries. 30-40% cache hit rate typical.
- **Budget enforcement**: Hard limits prevent runaway costs. Soft limits alert teams approaching budget.
- **Audit logging**: Every request/response logged (with PII redaction) for compliance. 90-day retention.
- **A/B testing**: Route % of traffic to new models, measure quality before full rollout.

---

## Q217: Design an Enterprise Search Platform

**Question:** Design an enterprise search platform powered by AI that indexes Slack, Confluence, Google Drive, GitHub, Jira, and email. Include cross-platform entity resolution and access control.

**Answer:**

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Source Connectors                     │
├──────┬──────────┬────────┬────────┬──────┬─────────────────┤
│Slack │Confluence│ GDrive │ GitHub │ Jira │ Email (Graph)   │
└──┬───┴────┬─────┴───┬────┴───┬────┴──┬───┴────┬────────────┘
   │        │         │        │       │        │
   ▼        ▼         ▼        ▼       ▼        ▼
┌─────────────────────────────────────────────────────────────┐
│              Unified Ingestion Pipeline                       │
│  (Extract → Transform → Embed → Index)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌──────────────┐ ┌────────┐ ┌──────────────┐
     │ Vector Index │ │ Full-  │ │ Knowledge    │
     │ (Milvus)     │ │ Text   │ │ Graph        │
     │              │ │ (ES)   │ │ (Neo4j)      │
     └──────────────┘ └────────┘ └──────────────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
              ┌────────────────────────┐
              │   Query Engine +       │
              │   ACL Enforcement      │
              └────────────────────────┘
```

### Implementation

```python
class EnterpriseSearchPlatform:
    def __init__(self):
        self.connectors = ConnectorRegistry()
        self.ingestion = IngestionPipeline()
        self.entity_resolver = CrossPlatformEntityResolver()
        self.acl_engine = ACLEngine()
    
    async def search(self, query: str, user: User) -> SearchResults:
        """Search with access control enforcement."""
        
        # Get user's access permissions across all platforms
        user_acls = await self.acl_engine.get_user_permissions(user)
        
        # Search across indices with ACL filter
        results = await asyncio.gather(
            self.vector_search(query, user_acls),
            self.fulltext_search(query, user_acls),
            self.graph_search(query, user_acls),
        )
        
        # Fuse results
        fused = self.fuse_and_rank(results, query)
        
        # Enrich with cross-platform context
        enriched = self.enrich_results(fused)
        
        return enriched


class CrossPlatformEntityResolver:
    """Resolve same entities across different platforms."""
    
    def __init__(self):
        self.entity_store = EntityStore()  # Canonical entity registry
    
    def resolve_person(self, mentions: list[PersonMention]) -> CanonicalPerson:
        """Link @john-doe (GitHub) = John Doe (Confluence) = john.doe@company.com."""
        
        # Resolution signals
        signals = {
            "email_match": self.match_by_email(mentions),
            "display_name_sim": self.match_by_name(mentions),
            "sso_id": self.match_by_sso(mentions),  # Most reliable
            "activity_correlation": self.match_by_activity(mentions),
        }
        
        # SSO ID is authoritative if available
        if signals["sso_id"]:
            return signals["sso_id"]
        
        # Fall back to email → name similarity
        return signals["email_match"] or self.fuzzy_match(mentions)
    
    def resolve_project(self, references: list[ProjectRef]) -> CanonicalProject:
        """Link GitHub repo = Jira project = Confluence space = Slack channel."""
        
        # Build linkage graph
        links = []
        for ref in references:
            # Check explicit links (Jira-GitHub integrations, etc.)
            explicit = self.get_explicit_links(ref)
            links.extend(explicit)
            
            # Check naming conventions (project-x repo, PROJECT-X Jira, #project-x Slack)
            name_matches = self.match_by_naming_convention(ref, references)
            links.extend(name_matches)
        
        # Cluster linked references into canonical projects
        return self.cluster_into_canonical(links)


class ACLEngine:
    """Enforce access control across all indexed sources."""
    
    async def get_user_permissions(self, user: User) -> UserACL:
        """Aggregate permissions from all sources."""
        
        # Fetch permissions from each source (cached, refreshed every 15 min)
        perms = await asyncio.gather(
            self.get_confluence_perms(user),
            self.get_gdrive_perms(user),
            self.get_github_perms(user),
            self.get_slack_perms(user),
            self.get_jira_perms(user),
        )
        
        return UserACL(
            confluence_spaces=perms[0],
            gdrive_files=perms[1],  # Folder-level inheritance
            github_repos=perms[2],
            slack_channels=perms[3],
            jira_projects=perms[4],
        )
    
    def build_search_filter(self, user_acl: UserACL) -> dict:
        """Convert ACLs to search filter for vector/fulltext queries."""
        return {
            "bool": {
                "should": [
                    {"terms": {"source_space": user_acl.confluence_spaces}},
                    {"terms": {"source_repo": user_acl.github_repos}},
                    {"terms": {"source_channel": user_acl.slack_channels}},
                    {"term": {"is_public": True}},
                ],
                "minimum_should_match": 1,
            }
        }
```

### Connector Sync Strategy

| Source | Sync Method | Frequency | Avg Latency |
|--------|-------------|-----------|-------------|
| Slack | Real-time (Events API) | Instant | <5s |
| Confluence | Webhook + polling | ~1 min | <60s |
| Google Drive | Push notifications | ~2 min | <120s |
| GitHub | Webhooks | Instant | <10s |
| Jira | Webhooks | Instant | <10s |
| Email | Graph delta sync | 5 min | <300s |

### Production Considerations

- **ACL correctness over speed**: Better to deny access than leak. Cache ACLs with short TTL (15 min). On cache miss, deny and refresh async.
- **Incremental indexing**: Only re-embed changed documents. Track change tokens per source for delta sync.
- **PII handling**: Redact PII in search results unless user has explicit access to the source document.
- **Scale**: 50M documents across sources, 10K queries/day. Shard vector index by source type for independent scaling.

---

## Q218: Design a Workflow Automation System Powered by AI

**Question:** Design a workflow automation system powered by AI that can understand natural language instructions and execute multi-step business processes. Include approval gates and audit trails.

**Answer:**

### Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Natural     │────▶│  Workflow        │────▶│  Execution       │
│  Language    │     │  Planner         │     │  Engine          │
│  Input       │     │  (LLM + Rules)   │     │  (Step Runner)   │
└──────────────┘     └──────────────────┘     └────────┬─────────┘
                                                        │
                     ┌──────────────────┐              │
                     │  Approval Gates  │◀─────────────┤
                     │  & Human-in-Loop │              │
                     └──────────────────┘              │
                                                        │
                     ┌──────────────────┐              │
                     │  Audit Trail     │◀─────────────┘
                     │  (Immutable Log) │
                     └──────────────────┘
```

### Implementation

```python
class AIWorkflowEngine:
    def __init__(self):
        self.planner = WorkflowPlanner()
        self.executor = StepExecutor()
        self.approval_gate = ApprovalGateManager()
        self.audit_log = AuditLogger()
    
    async def execute_instruction(self, instruction: str, user: User) -> WorkflowResult:
        """Parse natural language instruction into executable workflow."""
        
        # 1. Plan the workflow
        plan = await self.planner.plan(instruction, user)
        
        # 2. Validate plan is safe and within user permissions
        validation = self.validate_plan(plan, user)
        if not validation.safe:
            return WorkflowResult(status="REJECTED", reason=validation.reason)
        
        # 3. Show plan to user for confirmation
        confirmation = await self.request_confirmation(plan, user)
        if not confirmation.approved:
            return WorkflowResult(status="CANCELLED")
        
        # 4. Execute step by step
        self.audit_log.start_workflow(plan, user, instruction)
        
        for step in plan.steps:
            # Check if step requires approval
            if step.requires_approval:
                approval = await self.approval_gate.request(step, plan, user)
                if not approval.granted:
                    self.audit_log.log_rejection(step, approval)
                    return WorkflowResult(status="BLOCKED", blocked_at=step)
            
            # Execute step
            try:
                result = await self.executor.execute_step(step)
                self.audit_log.log_step_success(step, result)
                
                # Update context for next steps
                plan.context.update(result.outputs)
                
            except StepError as e:
                self.audit_log.log_step_failure(step, e)
                
                # Attempt recovery or rollback
                recovery = await self.handle_failure(plan, step, e)
                if not recovery.success:
                    await self.rollback(plan, up_to=step)
                    return WorkflowResult(status="FAILED", error=str(e))
        
        self.audit_log.complete_workflow(plan)
        return WorkflowResult(status="COMPLETED", outputs=plan.context)


class WorkflowPlanner:
    """Convert natural language to executable workflow plan."""
    
    async def plan(self, instruction: str, user: User) -> WorkflowPlan:
        """Use LLM to decompose instruction into steps."""
        
        available_actions = self.get_available_actions(user)
        
        prompt = f"""Decompose this business instruction into executable steps.

Available actions: {json.dumps(available_actions)}

Instruction: "{instruction}"

For each step provide:
- action: one of the available actions
- parameters: required parameters for the action
- requires_approval: true if step modifies data or costs money
- rollback_action: how to undo this step if needed
- depends_on: list of step indices this depends on

Return as JSON array of steps."""
        
        steps_json = await self.llm.generate(prompt)
        steps = [WorkflowStep(**s) for s in json.loads(steps_json)]
        
        # Validate all referenced actions exist and params are valid
        for step in steps:
            self.validate_step(step, available_actions)
        
        return WorkflowPlan(
            instruction=instruction,
            steps=steps,
            estimated_duration=self.estimate_duration(steps),
            risk_level=self.assess_risk(steps),
        )


class ApprovalGateManager:
    """Configurable approval gates based on risk and policy."""
    
    APPROVAL_POLICIES = {
        "financial": {"threshold": 1000, "approvers": ["finance_team"]},
        "data_modification": {"threshold": 100, "approvers": ["data_owner"]},  # >100 records
        "external_communication": {"approvers": ["manager"]},
        "access_change": {"approvers": ["security_team"]},
    }
    
    async def request(self, step: WorkflowStep, plan: WorkflowPlan, 
                      user: User) -> ApprovalResult:
        """Request and wait for approval."""
        
        policy = self.get_policy(step)
        approvers = self.resolve_approvers(policy, user)
        
        # Create approval request
        request = ApprovalRequest(
            step=step,
            workflow=plan,
            requester=user,
            approvers=approvers,
            context=self.build_context(step, plan),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        
        # Send notifications to approvers
        await self.notify_approvers(request)
        
        # Wait for approval (with timeout)
        result = await self.wait_for_decision(request, timeout_hours=24)
        return result
```

### Audit Trail Schema

```python
@dataclass
class AuditEntry:
    workflow_id: str
    step_index: int
    action: str
    actor: str  # User or system
    timestamp: datetime
    input_params: dict  # What was requested
    output: dict  # What happened
    decision: str  # "executed", "approved", "rejected", "rolled_back"
    approver: Optional[str]
    ip_address: str
    duration_ms: int
```

### Risk Classification

| Risk Level | Criteria | Approval Required | Example |
|-----------|----------|-------------------|---------|
| Low | Read-only, no cost | No | Search, report generation |
| Medium | Modifies < 10 records | User confirmation | Update ticket status |
| High | Modifies > 10 records or costs > $100 | Manager approval | Bulk email, data export |
| Critical | Irreversible or financial > $10K | Multi-party approval | Delete data, payment |

---

## Q219: Design an AI-Powered Natural Language to SQL Layer

**Question:** Design an AI-powered data integration layer that uses natural language to query across enterprise databases without requiring SQL knowledge. Include schema understanding and query validation.

**Answer:**

### Architecture

```
┌────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Natural   │────▶│  Schema      │────▶│  SQL         │────▶│  Query   │
│  Language  │     │  Understander│     │  Generator   │     │  Validator│
│  Query     │     │              │     │  (LLM)       │     │          │
└────────────┘     └──────────────┘     └──────────────┘     └────┬─────┘
                                                                   │
                   ┌──────────────┐     ┌──────────────┐          │
                   │  Result      │◀────│  Safe        │◀─────────┘
                   │  Formatter   │     │  Executor    │
                   └──────────────┘     └──────────────┘
```

### Implementation

```python
class NaturalLanguageQueryEngine:
    def __init__(self):
        self.schema_store = SchemaStore()
        self.sql_generator = SQLGenerator()
        self.validator = QueryValidator()
        self.executor = SafeQueryExecutor()
    
    async def query(self, nl_query: str, user: User) -> QueryResult:
        """Convert natural language to SQL, validate, and execute."""
        
        # 1. Identify relevant tables/schemas
        relevant_schema = await self.schema_store.find_relevant(nl_query, user)
        
        # 2. Generate SQL
        sql = await self.sql_generator.generate(nl_query, relevant_schema)
        
        # 3. Validate SQL (safety, correctness, permissions)
        validation = self.validator.validate(sql, user, relevant_schema)
        if not validation.safe:
            return QueryResult(status="REJECTED", reason=validation.reason)
        
        # 4. Execute with guardrails
        result = await self.executor.execute(sql, timeout_sec=30, max_rows=10000)
        
        # 5. Format result in natural language
        formatted = self.format_result(nl_query, result)
        
        return QueryResult(
            status="SUCCESS",
            sql=sql,
            data=result.rows,
            natural_language_summary=formatted,
            confidence=validation.confidence,
        )


class SchemaStore:
    """Schema understanding with business context."""
    
    def __init__(self):
        self.schema_embeddings = {}  # Table/column descriptions embedded
        self.business_glossary = BusinessGlossary()
    
    async def find_relevant(self, query: str, user: User) -> SchemaContext:
        """Find relevant tables and columns for a query."""
        
        # Embed the query
        query_embedding = self.embed(query)
        
        # Find relevant tables by semantic similarity
        table_scores = {}
        for table, embedding in self.schema_embeddings.items():
            score = cosine_similarity(query_embedding, embedding)
            table_scores[table] = score
        
        # Top-K relevant tables
        relevant_tables = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Build schema context with descriptions
        schema_context = SchemaContext()
        for table_name, _ in relevant_tables:
            table_info = self.get_table_info(table_name)
            # Filter columns user has access to
            accessible_columns = self.filter_by_access(table_info.columns, user)
            schema_context.add_table(table_name, accessible_columns, table_info.description)
        
        # Add business glossary terms
        schema_context.glossary = self.business_glossary.get_relevant_terms(query)
        
        return schema_context


class SQLGenerator:
    """LLM-based SQL generation with few-shot examples."""
    
    async def generate(self, nl_query: str, schema: SchemaContext) -> str:
        prompt = f"""Convert this natural language query to SQL.

Database schema:
{schema.to_prompt()}

Business glossary:
{schema.glossary_to_prompt()}

Examples of correct queries:
{self.get_few_shot_examples(nl_query)}

Natural language query: "{nl_query}"

Rules:
- Use only tables and columns from the schema above
- Always use explicit JOINs (no implicit joins)
- Add LIMIT 1000 unless the user asks for all results
- Use date functions appropriate for the database type
- Never use DELETE, UPDATE, INSERT, DROP, or ALTER

SQL:"""
        
        sql = await self.llm.generate(prompt)
        return self.clean_sql(sql)


class QueryValidator:
    """Multi-layer SQL validation."""
    
    def validate(self, sql: str, user: User, schema: SchemaContext) -> ValidationResult:
        checks = [
            self.check_no_mutations(sql),           # No DDL/DML
            self.check_tables_exist(sql, schema),   # All tables valid
            self.check_columns_exist(sql, schema),  # All columns valid
            self.check_user_access(sql, user),      # User can access these tables
            self.check_query_cost(sql),             # Estimated cost within budget
            self.check_no_injection(sql),           # No SQL injection patterns
            self.check_has_limit(sql),              # Has reasonable LIMIT
        ]
        
        failures = [c for c in checks if not c.passed]
        
        return ValidationResult(
            safe=len(failures) == 0,
            failures=failures,
            confidence=self.estimate_confidence(sql, schema),
        )
    
    def check_query_cost(self, sql: str) -> CheckResult:
        """Estimate query cost using EXPLAIN."""
        explain = self.db.explain(sql)
        estimated_rows = explain.total_rows_scanned
        
        if estimated_rows > 10_000_000:
            return CheckResult(passed=False, reason="Query scans >10M rows. Please add filters.")
        return CheckResult(passed=True)
```

### Safety Guardrails

| Layer | Protection |
|-------|-----------|
| Parsing | Reject any DDL/DML statements |
| Schema | Only expose tables/columns user has access to |
| Cost | EXPLAIN-based cost estimation, reject expensive queries |
| Execution | Read-only connection, query timeout (30s), row limit (10K) |
| Results | PII masking for sensitive columns |

### Production Considerations

- **Ambiguity handling**: When query is ambiguous, ask clarifying questions before generating SQL. "By 'revenue' do you mean gross revenue or net revenue?"
- **Query correction loop**: If SQL fails, use error message + original query to regenerate (max 2 retries)
- **Caching**: Cache NL→SQL mappings for common queries. Invalidate on schema change.
- **Feedback loop**: Users can thumbs-up/down results. Use accepted queries as few-shot examples for future generation.

---

## Q220: Design a Knowledge Transfer System for Departing Employees

**Question:** Design a knowledge transfer system where departing employees' expertise is captured into the RAG system. Include interview extraction, document organization, and knowledge verification.

**Answer:**

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│              Knowledge Transfer Pipeline                   │
├──────────────┬──────────────┬──────────────┬─────────────┤
│  Knowledge   │  Interview   │  Document    │  Verification│
│  Mapping     │  & Capture   │  Organization│  & Handoff   │
│              │              │              │              │
│ • Expertise  │ • AI-guided  │ • Categorize │ • SME review │
│   inventory  │   interviews │ • Structure  │ • Gap check  │
│ • Gap        │ • Screen     │ • Link to    │ • Successor  │
│   analysis   │   recording  │   existing   │   training   │
└──────────────┴──────────────┴──────────────┴─────────────┘
```

### Implementation

```python
class KnowledgeTransferSystem:
    def __init__(self):
        self.expertise_mapper = ExpertiseMapper()
        self.interview_engine = AIInterviewEngine()
        self.document_organizer = DocumentOrganizer()
        self.verifier = KnowledgeVerifier()
    
    async def initiate_transfer(self, departing_user: User, 
                                 notice_period_days: int) -> TransferPlan:
        """Create a knowledge transfer plan for a departing employee."""
        
        # 1. Map the employee's expertise footprint
        expertise = await self.expertise_mapper.map(departing_user)
        
        # 2. Identify knowledge gaps (what they know that nobody else does)
        critical_gaps = self.identify_critical_knowledge(expertise, departing_user)
        
        # 3. Generate transfer plan
        plan = TransferPlan(
            user=departing_user,
            critical_topics=critical_gaps,
            schedule=self.schedule_sessions(critical_gaps, notice_period_days),
            successors=self.identify_successors(critical_gaps),
        )
        
        return plan
    
    def identify_critical_knowledge(self, expertise: ExpertiseMap, 
                                     user: User) -> list[CriticalTopic]:
        """Find knowledge that only this person has."""
        
        critical = []
        for topic in expertise.topics:
            # How many other people know this?
            other_experts = self.expertise_mapper.find_experts(
                topic, exclude=[user.id])
            
            if len(other_experts) == 0:
                # Single point of failure - critical
                critical.append(CriticalTopic(
                    topic=topic,
                    criticality="HIGH",
                    reason="No other known experts",
                    estimated_capture_hours=self.estimate_capture_time(topic),
                ))
            elif len(other_experts) == 1:
                # Bus factor = 1 after departure
                critical.append(CriticalTopic(
                    topic=topic,
                    criticality="MEDIUM",
                    reason=f"Only {other_experts[0].name} remains",
                ))
        
        critical.sort(key=lambda t: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[t.criticality], 
                     reverse=True)
        return critical


class AIInterviewEngine:
    """AI-guided knowledge extraction interviews."""
    
    async def conduct_session(self, topic: CriticalTopic, 
                               user: User) -> InterviewOutput:
        """Conduct an AI-guided interview to extract tacit knowledge."""
        
        # Generate topic-specific questions
        questions = await self.generate_questions(topic)
        
        transcript_chunks = []
        
        for question in questions:
            # Present question to user (via chat or voice)
            response = await self.ask(user, question)
            transcript_chunks.append({"q": question, "a": response})
            
            # Generate follow-up questions based on answer
            follow_ups = await self.generate_follow_ups(topic, question, response)
            for fq in follow_ups[:2]:  # Max 2 follow-ups per question
                follow_response = await self.ask(user, fq)
                transcript_chunks.append({"q": fq, "a": follow_response})
        
        # Process transcript into structured knowledge
        structured = await self.structure_knowledge(transcript_chunks, topic)
        
        return InterviewOutput(
            topic=topic,
            transcript=transcript_chunks,
            structured_knowledge=structured,
            documents_generated=self.generate_documents(structured),
        )
    
    async def generate_questions(self, topic: CriticalTopic) -> list[str]:
        """Generate probing questions for knowledge extraction."""
        
        prompt = f"""Generate 8-10 interview questions to extract tacit knowledge about:
Topic: {topic.topic}
Context: {topic.context}

Questions should cover:
1. How things work (processes, systems)
2. Why decisions were made (rationale, trade-offs)
3. Common problems and solutions (troubleshooting)
4. Undocumented dependencies and gotchas
5. Key contacts and relationships
6. Future plans and recommendations

Make questions specific and actionable, not generic."""
        
        return await self.llm.generate_list(prompt)
    
    async def structure_knowledge(self, transcript: list[dict], 
                                   topic: CriticalTopic) -> StructuredKnowledge:
        """Convert interview transcript to structured, searchable knowledge."""
        
        prompt = f"""Convert this interview transcript into structured knowledge articles.

Topic: {topic.topic}
Transcript: {json.dumps(transcript)}

Create separate articles for:
1. System/process overview (how it works)
2. Decision log (why things are the way they are)  
3. Troubleshooting guide (common issues + solutions)
4. Dependencies and contacts
5. Recommendations for successors

Each article should be self-contained and understandable by someone new to the topic."""
        
        return await self.llm.generate_structured(prompt, StructuredKnowledge)


class KnowledgeVerifier:
    """Verify captured knowledge is accurate and complete."""
    
    async def verify(self, knowledge: StructuredKnowledge, 
                     topic: CriticalTopic) -> VerificationResult:
        """Multi-step verification of captured knowledge."""
        
        checks = []
        
        # 1. Completeness: are all key areas covered?
        completeness = self.check_completeness(knowledge, topic)
        checks.append(completeness)
        
        # 2. Accuracy: does the knowledge match existing docs?
        accuracy = await self.cross_reference(knowledge)
        checks.append(accuracy)
        
        # 3. Actionability: can someone follow these instructions?
        actionability = self.check_actionability(knowledge)
        checks.append(actionability)
        
        # 4. Successor validation: assign to successor for trial
        # Successor tries to use the knowledge, reports gaps
        
        return VerificationResult(
            checks=checks,
            overall_score=np.mean([c.score for c in checks]),
            gaps_identified=[c.gaps for c in checks if c.gaps],
        )
```

### Transfer Timeline

| Week | Activities | Output |
|------|-----------|--------|
| 1 | Expertise mapping, gap analysis | Transfer plan |
| 2-3 | AI-guided interview sessions (2-3 per week) | Raw transcripts |
| 3-4 | Document structuring, cross-referencing | Draft knowledge articles |
| 4-5 | Successor review, gap filling sessions | Verified articles |
| 5-6 | Final handoff, successor shadow period | Complete knowledge base |

### Metrics

| Metric | Target |
|--------|--------|
| Critical topics captured | 100% |
| Successor confidence score | >4/5 (self-reported) |
| Post-departure incidents | <2 in first 3 months |
| Knowledge article usage | >80% accessed within 30 days |
| Gap discovery rate after departure | <10% new gaps found |
# Architecture Decision Records for AI (Questions 226-230)

## Q226: Monolithic vs Microservices for AI Applications

**Question:** You need to choose between a monolithic AI application and a microservices-based AI platform. Present the trade-offs for a team of 20 engineers building a customer-facing AI product. Include migration paths.

**Answer:**

### Decision Matrix

```
┌────────────────────┬─────────────────────┬─────────────────────────┐
│  Dimension         │  Monolith           │  Microservices           │
├────────────────────┼─────────────────────┼─────────────────────────┤
│  Time to MVP       │  2-3 months ✓       │  4-6 months              │
│  Team coordination │  Simple ✓           │  Complex (contracts)     │
│  Deployment speed  │  All-or-nothing     │  Independent ✓           │
│  Scaling           │  Uniform only       │  Per-component ✓         │
│  GPU utilization   │  Wasted during I/O  │  Dedicated pools ✓       │
│  Debugging         │  Stack trace ✓      │  Distributed tracing     │
│  Model updates     │  Full redeploy      │  Hot-swap per service ✓  │
│  Latency           │  No network hops ✓  │  +10-50ms per hop        │
│  Cost (initial)    │  Lower ✓            │  Higher (infra overhead) │
│  Cost (at scale)   │  Higher (waste)     │  Lower (right-sizing) ✓  │
└────────────────────┴─────────────────────┴─────────────────────────┘
```

### Recommended Approach: Modular Monolith → Extract

```python
# Phase 1: Modular Monolith (Months 1-6)
# Clear module boundaries, shared deployment

class AIApplication:
    """Monolith with clean module boundaries."""
    
    def __init__(self):
        # Modules with clear interfaces (future service boundaries)
        self.embedding_module = EmbeddingModule()
        self.retrieval_module = RetrievalModule()
        self.generation_module = GenerationModule()
        self.safety_module = SafetyModule()
    
    async def query(self, request: QueryRequest) -> QueryResponse:
        # All in-process, zero network overhead
        embedding = self.embedding_module.embed(request.query)
        documents = self.retrieval_module.search(embedding, request.filters)
        response = self.generation_module.generate(request.query, documents)
        safe_response = self.safety_module.filter(response)
        return safe_response


# Phase 2: Extract Hot Paths (Months 6-12)
# Extract embedding and generation as services (GPU-bound, scale differently)

# Phase 3: Full Microservices (Months 12-18, only if needed)
# Extract retrieval, safety, caching as independent services
```

### When to Extract Services

| Signal | Action |
|--------|--------|
| GPU models need different scaling than CPU code | Extract model-serving services |
| Teams stepping on each other in CI/CD | Extract team-owned services |
| Single model update requires full redeployment | Extract model serving |
| Retrieval latency dominates and needs separate tuning | Extract retrieval service |
| >50% of incidents caused by coupling | Time to decouple |

### Recommendation for 20-Engineer Team

**Start monolith, plan for extraction.** With 20 engineers:
- 3 teams of 6-7 is optimal
- Monolith for first 6 months to find domain boundaries
- Extract embedding/model serving first (GPU scaling is the forcing function)
- Don't extract everything — only extract what has different scaling/deployment needs

---

## Q227: Build vs Buy Decision Framework

**Question:** Design the decision framework for build-vs-buy for AI components. When do you build your own embedding model, vector database, or LLM vs using managed services? Include TCO analysis.

**Answer:**

### Decision Framework

```
┌─────────────────────────────────────────────────────────┐
│              Build vs Buy Decision Tree                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Is this a core differentiator?                          │
│     YES → Strong build signal                            │
│     NO  → Default to buy                                 │
│                                                          │
│  Do you have domain-specific requirements                │
│  that no vendor satisfies?                               │
│     YES → Build (or customize open-source)               │
│     NO  → Buy                                            │
│                                                          │
│  Can you staff and maintain it for 3+ years?             │
│     YES → Build is viable                                │
│     NO  → Buy (hidden maintenance cost kills)            │
│                                                          │
│  Is vendor lock-in risk acceptable?                      │
│     YES → Buy managed service                            │
│     NO  → Build on open-source                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### TCO Analysis Template

```python
class TCOCalculator:
    """Total Cost of Ownership comparison."""
    
    def calculate_build_tco(self, component: str, years: int = 3) -> TCOBreakdown:
        costs = {
            "embedding_model": {
                "initial_development": 200_000,  # 2 ML engineers × 3 months
                "training_compute": 50_000,       # GPU hours for training
                "infrastructure": 36_000 * years, # Serving infrastructure/year
                "maintenance": 100_000 * years,   # 1 ML engineer ongoing
                "opportunity_cost": 150_000,      # What else could they build?
            },
            "vector_database": {
                "initial_development": 400_000,   # 3 engineers × 4 months
                "infrastructure": 60_000 * years,
                "maintenance": 200_000 * years,   # 2 engineers ongoing
                "opportunity_cost": 300_000,
            },
            "llm": {
                "initial_development": 2_000_000, # Team of 5 × 6 months
                "training_compute": 500_000,      # Pre-training compute
                "infrastructure": 200_000 * years,
                "maintenance": 500_000 * years,
                "opportunity_cost": 1_000_000,
            },
        }
        
        build = costs[component]
        total = sum(build.values())
        return TCOBreakdown(component=component, costs=build, total=total)
    
    def calculate_buy_tco(self, component: str, years: int = 3, 
                          monthly_volume: int = 1_000_000) -> TCOBreakdown:
        costs = {
            "embedding_model": {
                "api_costs": 0.0001 * monthly_volume * 12 * years,  # $0.0001/call
                "integration": 20_000,    # 1 engineer × 1 month
                "vendor_management": 5_000 * years,
                "migration_risk": 30_000,  # If vendor changes/dies
            },
            "vector_database": {
                "managed_service": 3_000 * 12 * years,  # Pinecone/Weaviate
                "integration": 30_000,
                "data_egress": 1_000 * 12 * years,
            },
            "llm": {
                "api_costs": 0.03 * monthly_volume * 12 * years / 1000,  # Per 1K tokens
                "integration": 40_000,
                "vendor_management": 10_000 * years,
            },
        }
        
        buy = costs[component]
        total = sum(buy.values())
        return TCOBreakdown(component=component, costs=buy, total=total)
```

### Component-Level Recommendations

| Component | Build When | Buy When |
|-----------|-----------|----------|
| Embedding model | Domain-specific vocab, regulated data | General-purpose search |
| Vector DB | >1B vectors, extreme perf needs | <100M vectors, standard patterns |
| LLM | Highly regulated, unique domain | 95% of use cases |
| Orchestration | Core product differentiator | Standard RAG patterns |
| Safety filters | Industry-specific requirements | General content safety |

### Key Insight

**Build the orchestration layer (your secret sauce), buy the infrastructure (commoditized).** Most companies should buy embeddings, buy LLM APIs, buy vector DB hosting, but build the RAG orchestration, domain logic, and evaluation pipeline that ties it all together.

---

## Q228: Synchronous vs Asynchronous RAG

**Question:** You need to choose between synchronous RAG (user waits for retrieval + generation) and asynchronous RAG (pre-compute and cache). Design the hybrid approach for a documentation assistant.

**Answer:**

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hybrid RAG Strategy                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Query ──▶ [Cache Check] ──▶ Hit? ──▶ Return cached     │
│                      │                                       │
│                      │ Miss                                   │
│                      ▼                                       │
│              [Query Classification]                           │
│                 /          \                                  │
│           Common/          Unique/                            │
│           Predictable      Complex                           │
│              │                │                               │
│              ▼                ▼                               │
│         [Warm Cache]    [Sync RAG]                           │
│         (pre-computed)  (real-time)                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class HybridRAGSystem:
    def __init__(self):
        self.cache = SemanticCache()
        self.precomputer = AsyncPrecomputer()
        self.sync_rag = SyncRAGPipeline()
        self.query_classifier = QueryClassifier()
    
    async def query(self, query: str, user: User) -> RAGResponse:
        """Hybrid: serve from cache or compute on-demand."""
        
        # 1. Check semantic cache (similar queries answered before)
        cached = await self.cache.get_similar(query, threshold=0.92)
        if cached:
            return RAGResponse(
                text=cached.text, 
                source="cache",
                latency_ms=50,
                freshness=cached.computed_at,
            )
        
        # 2. Classify query
        classification = self.query_classifier.classify(query)
        
        if classification.type == "COMMON_FAQ":
            # Pre-computed answer exists (generated nightly)
            precomputed = await self.precomputer.get(query, classification.topic)
            if precomputed:
                return RAGResponse(text=precomputed.text, source="precomputed")
        
        # 3. Sync RAG for unique/complex queries
        response = await self.sync_rag.execute(query, user)
        
        # 4. Cache the response for future similar queries
        await self.cache.store(query, response)
        
        return response


class AsyncPrecomputer:
    """Pre-compute answers for predictable queries."""
    
    async def precompute_daily(self):
        """Nightly job: pre-generate answers for common patterns."""
        
        # Source 1: Top 1000 queries from yesterday
        popular_queries = self.analytics.top_queries(days=1, limit=1000)
        
        # Source 2: All documentation pages → generate FAQ per page
        doc_pages = self.doc_store.get_all_pages()
        anticipated_queries = self.generate_anticipated_queries(doc_pages)
        
        # Source 3: Recently updated docs → anticipate questions
        updated_docs = self.doc_store.get_updated_since(days=1)
        update_queries = self.generate_update_queries(updated_docs)
        
        all_queries = set(popular_queries + anticipated_queries + update_queries)
        
        # Batch generate (cheaper, no latency constraint)
        for batch in chunk(all_queries, size=50):
            responses = await self.sync_rag.batch_execute(batch)
            await self.cache.store_batch(batch, responses)


class SemanticCache:
    """Cache with semantic similarity matching."""
    
    async def get_similar(self, query: str, threshold: float = 0.92) -> Optional[CachedResponse]:
        query_embedding = self.embed(query)
        
        # Search cache index for similar queries
        results = await self.vector_store.search(
            embedding=query_embedding,
            threshold=threshold,
            limit=1,
        )
        
        if results and results[0].score >= threshold:
            cached = results[0]
            
            # Check freshness — don't serve stale cached responses
            if self.is_fresh(cached, max_age_hours=24):
                return cached
        
        return None
```

### Strategy by Query Type

| Query Type | Strategy | Latency | Example |
|-----------|----------|---------|---------|
| FAQ (top 100) | Pre-computed daily | 50ms | "How to reset password" |
| Common pattern | Semantic cache | 100ms | "What are the pricing tiers" |
| Doc-specific | Sync RAG | 2-3s | "Explain the auth flow in v3.2" |
| Complex/multi-hop | Sync RAG + streaming | 5-10s | "Compare features A vs B vs C" |
| Unique/novel | Always sync | 3-5s | First-time asked question |

### Freshness Guarantees

- Pre-computed answers invalidated when source docs change (webhook trigger)
- Semantic cache entries expire after 24h or on source update
- Version tag on cached responses to detect staleness
- "Last updated" timestamp shown to users for transparency

---

## Q229: Multi-Language Content Architecture

**Question:** Design the architecture decision for handling multi-language content. Compare translate-then-embed, multilingual-embeddings, and language-specific-indices approaches with cost/quality trade-offs.

**Answer:**

### Approach Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│ Approach 1: Translate-Then-Embed                                     │
│ [French Doc] → [Translate to EN] → [EN Embedding] → [EN Index]     │
│                                                                      │
│ Approach 2: Multilingual Embeddings                                  │
│ [French Doc] → [Multilingual Embedding] → [Shared Index]           │
│                                                                      │
│ Approach 3: Language-Specific Indices                                 │
│ [French Doc] → [FR Embedding] → [FR Index]                          │
│ [English Doc] → [EN Embedding] → [EN Index]                         │
│ Query routes to relevant language index(es)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Decision Matrix

| Dimension | Translate-Then-Embed | Multilingual Embed | Language-Specific |
|-----------|---------------------|-------------------|-------------------|
| **Quality (same-lang)** | 95% (best EN models) | 85-90% | 95% |
| **Quality (cross-lang)** | 90% (translation loss) | 85% | 70% (separate) |
| **Ingestion cost** | High (translation) | Low | Medium |
| **Query cost** | Low (single index) | Low | Medium (fan-out) |
| **Maintenance** | Medium | Low | High (N indices) |
| **New language** | Add translator | Zero-shot | Train new model |
| **Scale** | 1 index | 1 index | N indices |
| **Latency** | +200ms (translate) | Same as mono | +fan-out |

### Recommended Hybrid Approach

```python
class MultiLanguageRAG:
    """Hybrid: multilingual for retrieval, translate for generation."""
    
    def __init__(self):
        # Multilingual embeddings for retrieval (cross-lingual search)
        self.embedder = SentenceTransformer("multilingual-e5-large")
        # Single shared index (all languages together)
        self.index = VectorIndex(dimensions=1024)
        # Translation for generation (better quality in user's language)
        self.translator = TranslationService()
    
    async def query(self, query: str, user_language: str) -> Response:
        """Search multilingually, generate in user's language."""
        
        # Embed query in its original language (multilingual model handles it)
        query_embedding = self.embedder.encode(query)
        
        # Search across ALL languages in single index
        results = await self.index.search(query_embedding, top_k=10)
        
        # Translate retrieved documents to user's language for generation
        translated_context = []
        for doc in results:
            if doc.language != user_language:
                translated = await self.translator.translate(
                    doc.content, source=doc.language, target=user_language)
                translated_context.append(translated)
            else:
                translated_context.append(doc.content)
        
        # Generate response in user's language
        response = await self.generate(query, translated_context, user_language)
        return response
```

### Cost Analysis (10M docs, 5 languages)

| Approach | Ingestion (one-time) | Monthly Query Cost | Monthly Infra |
|----------|---------------------|-------------------|---------------|
| Translate-then-embed | $50K (translation) | $500 | $2K (1 index) |
| Multilingual embed | $2K (embedding) | $500 | $2K (1 index) |
| Language-specific | $10K (5 embeddings) | $2.5K (5 queries) | $10K (5 indices) |

### Recommendation

**Multilingual embeddings for retrieval + translate for generation context.** This gives:
- Single index (simpler operations, lower cost)
- Cross-lingual search (English query finds French docs)
- High-quality generation (translating 5 context docs is cheap vs translating 10M)
- Zero-shot new languages (no reindexing needed)

---

## Q230: Context Window Size Decision Framework

**Question:** Design the decision framework for choosing context window sizes and models. When do you use 4K vs 32K vs 128K context windows? Include cost, quality, and latency analysis.

**Answer:**

### Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│              Context Window Decision Tree                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  How much context does the task ACTUALLY need?                   │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐     │
│  │  <4K tokens │  │  4K-32K      │  │  32K-128K          │     │
│  │             │  │              │  │                    │     │
│  │ • Simple QA │  │ • Multi-doc  │  │ • Full document   │     │
│  │ • Single    │  │   RAG        │  │   analysis        │     │
│  │   doc chunk │  │ • Summarize  │  │ • Code review     │     │
│  │ • Chat (few │  │   5-10 pages │  │   (full repo)     │     │
│  │   turns)    │  │ • Complex    │  │ • Book-length     │     │
│  │             │  │   reasoning  │  │   content         │     │
│  └─────────────┘  └──────────────┘  └────────────────────┘     │
│       │                  │                    │                   │
│       ▼                  ▼                    ▼                   │
│   GPT-4-mini       GPT-4 (32K)        Claude 3.5 (200K)        │
│   Claude Haiku     Claude Sonnet       Gemini 1.5 Pro           │
│   $0.15/1M        $10/1M              $3.75/1M                  │
│   ~200ms          ~2s                  ~5-15s                    │
└─────────────────────────────────────────────────────────────────┘
```

### Cost-Latency-Quality Analysis

```python
class ContextWindowOptimizer:
    """Choose optimal context window based on task requirements."""
    
    MODELS = {
        "small_4k": {"max_ctx": 4096, "cost_per_1m_input": 0.15, 
                     "latency_per_1k": 50, "quality_score": 0.75},
        "medium_32k": {"max_ctx": 32768, "cost_per_1m_input": 3.0,
                       "latency_per_1k": 80, "quality_score": 0.90},
        "large_128k": {"max_ctx": 131072, "cost_per_1m_input": 3.75,
                       "latency_per_1k": 100, "quality_score": 0.95},
    }
    
    def select_model(self, task: Task) -> ModelChoice:
        """Select model based on actual context needs."""
        
        # Estimate required context
        required_tokens = self.estimate_context_need(task)
        
        # Filter models that can handle the context
        viable = [m for m, cfg in self.MODELS.items() 
                  if cfg["max_ctx"] >= required_tokens]
        
        if not viable:
            # Need chunking strategy
            return self.chunk_and_aggregate_strategy(task)
        
        # Score viable models
        scores = {}
        for model in viable:
            cfg = self.MODELS[model]
            
            # Cost for this specific request
            cost = (required_tokens / 1_000_000) * cfg["cost_per_1m_input"]
            
            # Estimated latency
            latency_ms = (required_tokens / 1000) * cfg["latency_per_1k"]
            
            # Quality (accounts for "lost in the middle" degradation)
            quality = cfg["quality_score"] * self.attention_degradation(
                required_tokens, cfg["max_ctx"])
            
            # Weighted score (customize weights per use case)
            score = (
                0.4 * quality -
                0.3 * (cost / self.budget_per_request) -
                0.3 * (latency_ms / self.latency_budget_ms)
            )
            scores[model] = ModelChoice(model=model, cost=cost, 
                                        latency=latency_ms, quality=quality, score=score)
        
        return max(scores.values(), key=lambda x: x.score)
    
    def attention_degradation(self, used_tokens: int, max_tokens: int) -> float:
        """Model quality degrades when context is mostly full (lost in middle)."""
        fill_ratio = used_tokens / max_tokens
        if fill_ratio < 0.25:
            return 1.0      # Best quality — plenty of headroom
        elif fill_ratio < 0.5:
            return 0.95     # Slight degradation
        elif fill_ratio < 0.75:
            return 0.85     # Noticeable "lost in the middle"
        else:
            return 0.70     # Significant quality loss
    
    def chunk_and_aggregate_strategy(self, task: Task) -> ModelChoice:
        """For content exceeding all context windows."""
        return ModelChoice(
            model="medium_32k",
            strategy="map_reduce",  # Process chunks, aggregate
            chunks=self.plan_chunks(task),
            estimated_cost=self.estimate_map_reduce_cost(task),
        )
```

### Strategy by Use Case

| Use Case | Recommended | Reasoning |
|----------|-------------|-----------|
| Chat (3-5 turns) | 4K model | Cheap, fast, sufficient |
| RAG (5-10 docs) | 8-16K model | Fits context, good quality |
| Doc summarization | 32K model | Whole doc without chunking |
| Code review | 128K model | Need full file context |
| Multi-doc analysis | Map-reduce with 32K | Cost-effective at scale |
| Real-time autocomplete | 4K model | Latency critical |

### Key Insight: "Just Because You Can Doesn't Mean You Should"

Using a 128K context window for a question that only needs 2K tokens of context:
- **Costs 30x more** than using a 4K model
- **Takes 5x longer** due to attention computation
- **Quality may be WORSE** due to irrelevant context diluting attention

**Rule of thumb**: Use the smallest context window that fits your actual context. More context ≠ better answers. Focused, relevant context in a small window beats unfocused large context.
# API Design for AI Services (Questions 231-235)

## Q231: Design the API Specification for a Production RAG Service

**Question:** Design the API specification for a production RAG service. Include endpoints, request/response schemas, streaming interfaces, pagination, error handling, and rate limit headers.

**Answer:**

### API Specification

```
┌─────────────────────────────────────────────────────────┐
│                RAG Service API v1                         │
├─────────────────────────────────────────────────────────┤
│  POST /v1/query           - Single query                 │
│  POST /v1/query/stream    - Streaming query              │
│  POST /v1/documents       - Upload document              │
│  GET  /v1/documents/:id   - Get document status          │
│  POST /v1/conversations   - Start conversation           │
│  POST /v1/conversations/:id/messages - Add message       │
│  GET  /v1/usage           - Usage and costs              │
└─────────────────────────────────────────────────────────┘
```

### Implementation

```python
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import asyncio

app = FastAPI(title="RAG Service", version="1.0.0")

# === REQUEST/RESPONSE SCHEMAS ===

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None
    filters: Optional[dict] = Field(default=None, description="Document filters")
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = True
    response_format: str = Field(default="text", pattern="^(text|json|markdown)$")
    max_tokens: int = Field(default=500, ge=50, le=4000)
    temperature: float = Field(default=0.7, ge=0, le=1.0)
    language: Optional[str] = Field(default=None, pattern="^[a-z]{2}$")

class Citation(BaseModel):
    document_id: str
    title: str
    content_snippet: str
    relevance_score: float
    page_number: Optional[int] = None
    url: Optional[str] = None

class QueryResponse(BaseModel):
    id: str
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0, le=1)
    model_used: str
    usage: dict  # {"input_tokens": int, "output_tokens": int, "cost_usd": float}
    latency_ms: int
    metadata: dict = {}

class ErrorResponse(BaseModel):
    error: dict  # {"code": str, "message": str, "details": Optional[dict]}
    request_id: str


# === ENDPOINTS ===

@app.post("/v1/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    authorization: str = Header(...),
    x_request_id: Optional[str] = Header(None),
    x_idempotency_key: Optional[str] = Header(None),
):
    """Synchronous query endpoint."""
    # Rate limit check (returns 429 with headers)
    await check_rate_limit(authorization)
    
    # Execute RAG pipeline
    result = await rag_pipeline.execute(request)
    
    return QueryResponse(
        id=result.id,
        answer=result.answer,
        citations=result.citations,
        confidence=result.confidence,
        model_used=result.model,
        usage=result.usage,
        latency_ms=result.latency_ms,
    )


@app.post("/v1/query/stream")
async def query_stream(request: QueryRequest, authorization: str = Header(...)):
    """Server-Sent Events streaming endpoint."""
    
    async def event_generator():
        async for chunk in rag_pipeline.stream(request):
            if chunk.type == "retrieval_complete":
                yield f"event: retrieval\ndata: {json.dumps(chunk.data)}\n\n"
            elif chunk.type == "token":
                yield f"event: token\ndata: {json.dumps({'text': chunk.text})}\n\n"
            elif chunk.type == "citation":
                yield f"event: citation\ndata: {json.dumps(chunk.citation)}\n\n"
            elif chunk.type == "done":
                yield f"event: done\ndata: {json.dumps(chunk.final_metadata)}\n\n"
            elif chunk.type == "error":
                yield f"event: error\ndata: {json.dumps({'error': chunk.error})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# === RATE LIMITING ===

@app.middleware("http")
async def rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add rate limit headers to every response
    app_id = extract_app_id(request)
    limits = get_rate_limits(app_id)
    
    response.headers["X-RateLimit-Limit"] = str(limits.requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(limits.remaining)
    response.headers["X-RateLimit-Reset"] = str(limits.reset_timestamp)
    response.headers["X-RateLimit-Limit-Tokens"] = str(limits.tokens_per_minute)
    response.headers["X-RateLimit-Remaining-Tokens"] = str(limits.tokens_remaining)
    
    return response


# === ERROR HANDLING ===

ERROR_CODES = {
    "rate_limited": (429, "Rate limit exceeded. Retry after {retry_after}s"),
    "context_too_long": (400, "Query + context exceeds maximum token limit"),
    "no_results": (200, "No relevant documents found"),  # Not an error, but flagged
    "model_overloaded": (503, "Model serving capacity exceeded. Retry with backoff"),
    "content_filtered": (400, "Query or response blocked by content filter"),
    "invalid_filter": (400, "Document filter references non-existent field"),
}

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": str(exc)}},
        headers={"Retry-After": str(exc.retry_after)},
    )
```

### Streaming Protocol (SSE)

```
event: retrieval
data: {"documents_found": 5, "search_time_ms": 45}

event: token
data: {"text": "Based"}

event: token
data: {"text": " on"}

event: token
data: {"text": " the"}

event: citation
data: {"document_id": "doc_123", "title": "Deploy Guide", "relevance": 0.92}

event: done
data: {"total_tokens": 234, "latency_ms": 1850, "confidence": 0.87}
```

### Pagination (for document listing)

```
GET /v1/documents?cursor=eyJpZCI6MTAwfQ&limit=20

Response:
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTIwfQ",
    "has_more": true,
    "total_count": 5432
  }
}
```

---

## Q232: Design Webhook and Callback Architecture for Long-Running AI Operations

**Question:** Design a webhook and callback architecture for long-running AI operations (document processing, batch embedding, model fine-tuning). Include retry logic, delivery guarantees, and status polling.

**Answer:**

### Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Client  │────▶│  Job Queue   │────▶│  Worker      │────▶│  Webhook │
│  Submit  │     │  (accept)    │     │  (process)   │     │  Delivery│
└──────────┘     └──────────────┘     └──────────────┘     └──────────┘
     │                                        │                    │
     │           ┌──────────────┐             │                    │
     └──────────▶│  Status      │◀────────────┘                    │
      (poll)     │  API         │                                   │
                 └──────────────┘                                   │
                                                                    ▼
                                                           ┌──────────────┐
                                                           │  Client      │
                                                           │  Endpoint    │
                                                           └──────────────┘
```

### Implementation

```python
class AsyncJobManager:
    def __init__(self):
        self.queue = JobQueue()  # SQS/Redis
        self.store = JobStore()  # DynamoDB
        self.webhook_sender = WebhookSender()
    
    async def submit_job(self, job_type: str, payload: dict, 
                         webhook_url: Optional[str] = None) -> JobSubmission:
        """Submit a long-running job and return immediately."""
        
        job = Job(
            id=str(uuid4()),
            type=job_type,
            status="QUEUED",
            payload=payload,
            webhook_url=webhook_url,
            created_at=datetime.utcnow(),
            estimated_duration=self.estimate_duration(job_type, payload),
        )
        
        await self.store.save(job)
        await self.queue.enqueue(job)
        
        return JobSubmission(
            job_id=job.id,
            status="QUEUED",
            estimated_completion=job.estimated_duration,
            status_url=f"/v1/jobs/{job.id}",
            cancel_url=f"/v1/jobs/{job.id}/cancel",
        )
    
    async def update_status(self, job_id: str, status: str, 
                            progress: float = None, result: dict = None):
        """Update job status and fire webhooks."""
        
        job = await self.store.get(job_id)
        job.status = status
        job.progress = progress
        job.result = result
        job.updated_at = datetime.utcnow()
        
        await self.store.save(job)
        
        # Fire webhook for significant status changes
        if job.webhook_url and status in ["PROCESSING", "COMPLETED", "FAILED"]:
            await self.webhook_sender.send(job)


class WebhookSender:
    """Reliable webhook delivery with retries."""
    
    RETRY_DELAYS = [10, 30, 60, 300, 900, 3600]  # seconds
    
    async def send(self, job: Job):
        """Send webhook with exponential backoff retry."""
        
        payload = WebhookPayload(
            event_id=str(uuid4()),
            event_type=f"job.{job.status.lower()}",
            timestamp=datetime.utcnow().isoformat(),
            data={
                "job_id": job.id,
                "type": job.type,
                "status": job.status,
                "progress": job.progress,
                "result": job.result,
                "error": job.error,
            },
        )
        
        # Sign payload for verification
        signature = self.sign_payload(payload, job.webhook_secret)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-ID": payload.event_id,
            "X-Webhook-Timestamp": payload.timestamp,
        }
        
        # Attempt delivery with retries
        for attempt, delay in enumerate(self.RETRY_DELAYS):
            try:
                response = await httpx.post(
                    job.webhook_url,
                    json=payload.dict(),
                    headers=headers,
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    await self.log_delivery(payload.event_id, "DELIVERED", attempt)
                    return
                elif response.status_code >= 500:
                    # Server error — retry
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Client error (4xx) — don't retry
                    await self.log_delivery(payload.event_id, "REJECTED", attempt)
                    return
                    
            except (httpx.TimeoutException, httpx.ConnectError):
                await asyncio.sleep(delay)
                continue
        
        # All retries exhausted
        await self.log_delivery(payload.event_id, "FAILED", len(self.RETRY_DELAYS))
        await self.dead_letter_queue.enqueue(payload)


# === STATUS POLLING API ===

@app.get("/v1/jobs/{job_id}")
async def get_job_status(job_id: str) -> JobStatus:
    job = await job_store.get(job_id)
    return JobStatus(
        id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        estimated_completion=job.estimated_duration,
        result=job.result if job.status == "COMPLETED" else None,
        error=job.error if job.status == "FAILED" else None,
    )
```

### Webhook Event Types

| Event | Trigger | Payload Includes |
|-------|---------|-----------------|
| `job.queued` | Job accepted | job_id, estimated_time |
| `job.processing` | Worker picks up | job_id, progress: 0% |
| `job.progress` | Periodic update | job_id, progress: N% |
| `job.completed` | Success | job_id, result |
| `job.failed` | Error | job_id, error details |

### Delivery Guarantees

- **At-least-once delivery**: Retry until 200 OK or retries exhausted
- **Idempotency**: Include `X-Webhook-ID` — clients should deduplicate
- **Ordering**: Events for same job delivered in order (use queue per job)
- **Verification**: HMAC-SHA256 signature for authenticity

---

## Q233: Design a GraphQL API for an AI Knowledge Base

**Question:** Design a GraphQL API for an AI knowledge base that supports complex queries (search + filter + aggregate) across documents, conversations, and analytics data.

**Answer:**

### Schema

```python
# schema.graphql

import strawberry
from strawberry.types import Info

@strawberry.type
class Document:
    id: str
    title: str
    content: str
    source: str
    created_at: datetime
    updated_at: datetime
    metadata: JSON
    tags: list[str]
    embedding_status: str
    
    @strawberry.field
    async def related_documents(self, limit: int = 5) -> list["Document"]:
        """Semantic similarity-based related docs."""
        return await doc_service.find_related(self.id, limit)
    
    @strawberry.field
    async def conversations_referencing(self, limit: int = 10) -> list["Conversation"]:
        """Conversations that cited this document."""
        return await analytics_service.get_citing_conversations(self.id, limit)

@strawberry.type
class SearchResult:
    document: Document
    relevance_score: float
    snippet: str
    highlights: list[str]

@strawberry.type  
class Conversation:
    id: str
    user_id: str
    started_at: datetime
    messages: list["Message"]
    topic: str
    satisfaction_score: Optional[float]
    
    @strawberry.field
    async def analytics(self) -> "ConversationAnalytics":
        return await analytics_service.get_conversation_analytics(self.id)

@strawberry.type
class Message:
    id: str
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime
    citations: list[Document]
    feedback: Optional[str]

@strawberry.type
class AnalyticsAggregate:
    total_queries: int
    avg_confidence: float
    top_topics: list[TopicCount]
    satisfaction_trend: list[TimeSeriesPoint]
    failure_rate: float

@strawberry.input
class SearchInput:
    query: str
    filters: Optional[DocumentFilter] = None
    date_range: Optional[DateRange] = None
    sources: Optional[list[str]] = None
    top_k: int = 10

@strawberry.input
class DocumentFilter:
    tags: Optional[list[str]] = None
    source: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    metadata_match: Optional[JSON] = None

@strawberry.type
class Query:
    @strawberry.field
    async def search(self, input: SearchInput) -> list[SearchResult]:
        """Semantic search with filters."""
        return await search_service.search(input)
    
    @strawberry.field
    async def document(self, id: str) -> Optional[Document]:
        return await doc_service.get(id)
    
    @strawberry.field
    async def conversations(
        self, 
        user_id: Optional[str] = None,
        topic: Optional[str] = None,
        date_range: Optional[DateRange] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> Connection[Conversation]:
        """Paginated conversations with cursor-based pagination."""
        return await conversation_service.list(user_id, topic, date_range, first, after)
    
    @strawberry.field
    async def analytics(
        self,
        period: str = "7d",
        group_by: Optional[str] = None,
    ) -> AnalyticsAggregate:
        return await analytics_service.aggregate(period, group_by)

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def ask(self, query: str, conversation_id: Optional[str] = None) -> Message:
        """Submit a question to the RAG system."""
        return await rag_service.query(query, conversation_id)
    
    @strawberry.mutation
    async def upload_document(self, file: Upload, metadata: JSON) -> Document:
        return await doc_service.upload(file, metadata)
    
    @strawberry.mutation
    async def provide_feedback(self, message_id: str, rating: int, comment: Optional[str]) -> bool:
        return await feedback_service.record(message_id, rating, comment)

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def query_stream(self, query: str) -> AsyncGenerator[StreamChunk, None]:
        """Stream RAG response tokens."""
        async for chunk in rag_service.stream(query):
            yield chunk
```

### Example Queries

```graphql
# Complex search with aggregation
query {
  search(input: {
    query: "deployment best practices"
    filters: { tags: ["devops"], created_after: "2024-01-01" }
    top_k: 5
  }) {
    document { id title source tags }
    relevance_score
    snippet
  }
  
  analytics(period: "30d") {
    total_queries
    avg_confidence
    top_topics { topic count }
  }
}
```

### Performance Considerations

- **DataLoader pattern**: Batch N+1 queries (related documents, citations)
- **Complexity limiting**: Max query depth=5, max fields=100, cost analysis
- **Caching**: `@cacheControl(maxAge: 60)` on stable fields, no cache on search
- **Persisted queries**: Pre-approve query shapes in production for security

---

## Q234: Design an SDK/Client Library for an AI Platform

**Question:** Design an SDK/client library for an AI platform that handles streaming responses, automatic retries, token counting, cost estimation, and offline fallback. Include multi-language support.

**Answer:**

### SDK Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Platform SDK                            │
├────────────┬────────────┬────────────┬──────────────────────┤
│  Client    │  Streaming │  Retry     │  Cost                │
│  Core      │  Handler   │  Engine    │  Tracker             │
├────────────┼────────────┼────────────┼──────────────────────┤
│  Token     │  Offline   │  Cache     │  Telemetry           │
│  Counter   │  Fallback  │  Layer     │                      │
└────────────┴────────────┴────────────┴──────────────────────┘
```

### Python SDK Implementation

```python
class AIClient:
    """Production AI Platform SDK."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.aiplatform.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        enable_cache: bool = True,
        offline_fallback: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.retry_engine = RetryEngine(max_retries=max_retries)
        self.token_counter = TokenCounter()
        self.cost_tracker = CostTracker()
        self.cache = ResponseCache() if enable_cache else None
        self.offline = OfflineFallback() if offline_fallback else None
        self._session = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    
    async def query(
        self,
        query: str,
        *,
        conversation_id: Optional[str] = None,
        filters: Optional[dict] = None,
        max_tokens: int = 500,
        stream: bool = False,
    ) -> Union[QueryResponse, AsyncIterator[StreamChunk]]:
        """Send a query to the RAG service."""
        
        # Pre-flight: estimate tokens and cost
        estimated_tokens = self.token_counter.count(query)
        estimated_cost = self.cost_tracker.estimate(estimated_tokens, max_tokens)
        
        if stream:
            return self._stream_query(query, conversation_id, filters, max_tokens)
        
        # Check cache
        if self.cache:
            cached = await self.cache.get(query, filters)
            if cached:
                return cached
        
        # Execute with retry
        try:
            response = await self.retry_engine.execute(
                self._do_query, query, conversation_id, filters, max_tokens
            )
        except AllRetriesExhausted:
            if self.offline:
                return await self.offline.fallback(query)
            raise
        
        # Track actual cost
        self.cost_tracker.record(response.usage)
        
        # Cache response
        if self.cache:
            await self.cache.store(query, filters, response)
        
        return response
    
    async def _stream_query(self, query, conversation_id, filters, max_tokens):
        """Stream response tokens via SSE."""
        
        async with self._session.stream(
            "POST", "/v1/query/stream",
            json={"query": query, "conversation_id": conversation_id,
                  "filters": filters, "max_tokens": max_tokens},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    yield StreamChunk(**data)


class RetryEngine:
    """Intelligent retry with backoff and jitter."""
    
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
    
    async def execute(self, fn, *args, **kwargs):
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in self.RETRYABLE_STATUS_CODES:
                    raise  # Non-retryable error
                
                last_error = e
                
                # Use Retry-After header if present
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    delay = float(retry_after)
                else:
                    delay = min(2 ** attempt + random.uniform(0, 1), 60)
                
                await asyncio.sleep(delay)
            
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                delay = min(2 ** attempt + random.uniform(0, 1), 60)
                await asyncio.sleep(delay)
        
        raise AllRetriesExhausted(last_error)


class CostTracker:
    """Track token usage and costs."""
    
    PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},  # per 1M tokens
        "gpt-4-mini": {"input": 0.15, "output": 0.60},
    }
    
    def __init__(self):
        self.session_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    
    def estimate(self, input_tokens: int, max_output: int, model: str = "gpt-4") -> float:
        pricing = self.PRICING[model]
        return (input_tokens * pricing["input"] + max_output * pricing["output"]) / 1_000_000
    
    def record(self, usage: dict):
        self.session_usage["input_tokens"] += usage["input_tokens"]
        self.session_usage["output_tokens"] += usage["output_tokens"]
        self.session_usage["cost_usd"] += usage.get("cost_usd", 0)
    
    @property
    def total_cost(self) -> float:
        return self.session_usage["cost_usd"]
```

### Multi-Language SDK Interface (TypeScript)

```typescript
const client = new AIClient({ apiKey: "...", baseUrl: "..." });

// Streaming with async iterator
for await (const chunk of client.query("How to deploy?", { stream: true })) {
  process.stdout.write(chunk.text);
}

// Cost tracking
console.log(`Session cost: $${client.costTracker.totalCost.toFixed(4)}`);
```

### SDK Design Principles

| Principle | Implementation |
|-----------|---------------|
| Sensible defaults | Works with zero config beyond API key |
| Progressive disclosure | Simple for basics, powerful for advanced |
| Observable | Built-in logging, metrics, cost tracking |
| Resilient | Retries, circuit breaker, offline fallback |
| Efficient | Connection pooling, streaming, caching |

---

## Q235: Design API Versioning and Deprecation Strategy

**Question:** Design API versioning and deprecation strategy for an AI platform where models, capabilities, and response formats change frequently. Include backward compatibility and migration tooling.

**Answer:**

### Versioning Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                  API Versioning Layers                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  URL-based major versions:  /v1/query, /v2/query            │
│  Header-based minor:        X-API-Version: 2024-01-15       │
│  Feature flags:             X-Enable-Feature: citations-v2   │
│                                                              │
│  Stability Tiers:                                            │
│  • Stable:    12-month deprecation notice                    │
│  • Beta:      3-month notice, may break                      │
│  • Preview:   No guarantees, can change weekly               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class APIVersionManager:
    """Manage API versions with backward compatibility."""
    
    VERSIONS = {
        "2024-01-15": {"citations_format": "v1", "streaming": "sse"},
        "2024-06-01": {"citations_format": "v2", "streaming": "sse", "confidence_score": True},
        "2024-09-01": {"citations_format": "v2", "streaming": "websocket", "confidence_score": True},
    }
    
    DEPRECATION_SCHEDULE = {
        "2024-01-15": {"deprecated_at": "2024-07-01", "sunset_at": "2025-01-01"},
    }
    
    def resolve_version(self, request: Request) -> str:
        """Determine which API version to use."""
        
        # Explicit header takes precedence
        explicit = request.headers.get("X-API-Version")
        if explicit and explicit in self.VERSIONS:
            return explicit
        
        # URL-based major version
        if "/v2/" in request.url.path:
            return self.latest_v2_version()
        
        # Default to latest stable
        return self.latest_stable_version()
    
    def add_deprecation_headers(self, response, version: str):
        """Add deprecation warnings to response headers."""
        
        if version in self.DEPRECATION_SCHEDULE:
            schedule = self.DEPRECATION_SCHEDULE[version]
            response.headers["Deprecation"] = schedule["deprecated_at"]
            response.headers["Sunset"] = schedule["sunset_at"]
            response.headers["Link"] = f'</v1/docs/migration>; rel="deprecation"'
            
            # Also include in response body for visibility
            response.headers["X-Deprecation-Warning"] = (
                f"API version {version} is deprecated. "
                f"Sunset date: {schedule['sunset_at']}. "
                f"See /docs/migration for upgrade guide."
            )


class ResponseTransformer:
    """Transform responses to match requested API version."""
    
    def transform(self, response: dict, target_version: str) -> dict:
        """Convert internal response format to version-specific format."""
        
        version_config = APIVersionManager.VERSIONS[target_version]
        
        # Citations format changed between v1 and v2
        if version_config["citations_format"] == "v1":
            # v1: flat list of source strings
            response["sources"] = [c["title"] for c in response.pop("citations", [])]
        # v2: rich citation objects (current internal format) — no transform needed
        
        # Confidence score added in 2024-06-01
        if not version_config.get("confidence_score"):
            response.pop("confidence", None)
        
        return response


class MigrationToolkit:
    """Tools to help clients migrate between API versions."""
    
    def generate_migration_guide(self, from_version: str, to_version: str) -> str:
        """Auto-generate migration guide between versions."""
        
        from_schema = self.get_schema(from_version)
        to_schema = self.get_schema(to_version)
        
        changes = self.diff_schemas(from_schema, to_schema)
        
        guide = MigrationGuide(
            breaking_changes=[c for c in changes if c.breaking],
            new_features=[c for c in changes if c.type == "addition"],
            deprecations=[c for c in changes if c.type == "deprecation"],
            code_examples=self.generate_code_examples(changes),
        )
        
        return guide
    
    def compatibility_proxy(self, old_version: str):
        """Run a proxy that translates old API calls to new format."""
        # Useful during migration period
        pass


# === DEPRECATION LIFECYCLE ===

DEPRECATION_PROCESS = """
1. ANNOUNCE (Day 0):
   - Add Deprecation header to all responses
   - Email all API key holders
   - Update docs with migration guide
   - Log deprecation warnings in client SDKs

2. WARN (Month 3):
   - Return X-Deprecation-Warning in response body
   - Dashboard alert for affected clients
   - Increase logging for old version usage

3. THROTTLE (Month 9):
   - Reduce rate limits for deprecated version (50% of normal)
   - Return 299 Warning header

4. SUNSET (Month 12):
   - Return 410 Gone for all requests to deprecated version
   - Keep docs available for reference
   - Redirect to migration guide
"""
```

### Version Compatibility Matrix

| Client SDK v | API 2024-01 | API 2024-06 | API 2024-09 |
|-------------|-------------|-------------|-------------|
| SDK 1.x | Full | Partial (no new fields) | Unsupported |
| SDK 2.x | Full (compat) | Full | Full |
| SDK 3.x | Deprecated | Full | Full |

### Key Principles

1. **Never break existing clients silently** — always deprecation headers first
2. **Date-based versions** (not semver) — easier to reason about timeline
3. **Additive changes are free** — new fields don't require version bump
4. **Removal/rename = breaking** — requires new version + migration period
5. **SDKs abstract versions** — client never sees raw version negotiation
# Migration and Modernization (Questions 236-240)

## Q236: Migrate from Keyword Search to Semantic Search

**Question:** Design a migration plan from keyword search (Elasticsearch) to semantic search (vector DB) for an enterprise with 5 years of user behavior data. How do you migrate without disrupting relevance?

**Answer:**

### Migration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Dual-Stack Migration Architecture                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1: Shadow Mode                                        │
│  ┌────────┐     ┌────────────────┐     ┌────────────────┐  │
│  │ Query  │────▶│ Elasticsearch  │────▶│ Results (shown)│  │
│  │        │────▶│ Vector DB      │────▶│ Results (logged)│  │
│  └────────┘     └────────────────┘     └────────────────┘  │
│                                                              │
│  Phase 2: Interleaving                                       │
│  Results from both systems interleaved, measure preference   │
│                                                              │
│  Phase 3: Primary Switch                                     │
│  Vector DB primary, ES fallback                              │
│                                                              │
│  Phase 4: Decommission                                       │
│  ES removed, Vector DB only                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class SearchMigrationManager:
    def __init__(self):
        self.es_client = ElasticsearchClient()
        self.vector_db = VectorDBClient()
        self.traffic_splitter = TrafficSplitter()
        self.quality_monitor = QualityMonitor()
    
    async def query_shadow_mode(self, query: str, user: User) -> SearchResults:
        """Phase 1: Query both, serve ES, log vector results."""
        
        # Both queries in parallel
        es_results, vector_results = await asyncio.gather(
            self.es_client.search(query),
            self.vector_db.search(query),
        )
        
        # Log both for comparison
        self.quality_monitor.log_comparison(
            query=query,
            es_results=es_results,
            vector_results=vector_results,
            user=user,
        )
        
        # Serve ES results (no user impact)
        return es_results
    
    async def query_interleaved(self, query: str, user: User) -> SearchResults:
        """Phase 2: Team Draft Interleaving for unbiased comparison."""
        
        es_results, vector_results = await asyncio.gather(
            self.es_client.search(query, top_k=10),
            self.vector_db.search(query, top_k=10),
        )
        
        # Interleave results using Team Draft algorithm
        interleaved, team_assignments = self.team_draft_interleave(
            es_results, vector_results)
        
        # Track which team the user clicks on
        self.quality_monitor.track_interleaving(
            query=query, user=user,
            interleaved=interleaved,
            team_assignments=team_assignments,
        )
        
        return interleaved
    
    def team_draft_interleave(self, list_a, list_b):
        """Unbiased interleaving: randomly assign positions to each system."""
        interleaved = []
        team_a_items = set()
        team_b_items = set()
        
        ptr_a, ptr_b = 0, 0
        for position in range(min(10, len(list_a) + len(list_b))):
            # Coin flip for who picks next
            if random.random() < 0.5 and ptr_a < len(list_a):
                item = list_a[ptr_a]
                ptr_a += 1
                team_a_items.add(item.id)
            elif ptr_b < len(list_b):
                item = list_b[ptr_b]
                ptr_b += 1
                team_b_items.add(item.id)
            else:
                item = list_a[ptr_a]
                ptr_a += 1
                team_a_items.add(item.id)
            
            if item.id not in [i.id for i in interleaved]:
                interleaved.append(item)
        
        return interleaved, {"es": team_a_items, "vector": team_b_items}


class BehaviorDataMigration:
    """Migrate 5 years of click/behavior data to train vector ranking."""
    
    def create_training_data_from_clicks(self):
        """Convert click logs to relevance labels for vector ranking."""
        
        click_logs = self.es_client.get_click_logs(years=5)
        
        training_data = []
        for log in click_logs:
            # Positive: clicked documents
            for clicked_doc in log.clicked_docs:
                training_data.append({
                    "query": log.query,
                    "document_id": clicked_doc.id,
                    "label": self.compute_label(log, clicked_doc),
                    # Label: 0=not clicked, 1=clicked, 2=long dwell, 3=converted
                })
            
            # Negative: shown but not clicked (with position bias correction)
            for shown_doc in log.shown_not_clicked:
                training_data.append({
                    "query": log.query,
                    "document_id": shown_doc.id,
                    "label": 0,
                    "position_bias_weight": 1.0 / self.propensity(shown_doc.position),
                })
        
        return training_data
```

### Migration Timeline

| Phase | Duration | Risk | Rollback |
|-------|----------|------|----------|
| Shadow mode | 4 weeks | Zero (no user impact) | N/A |
| Interleaving (5% traffic) | 2 weeks | Very low | Instant |
| Interleaving (50% traffic) | 4 weeks | Low | Instant |
| Vector primary (90/10) | 4 weeks | Medium | Switch config |
| Full vector | Ongoing | Low (proven) | ES still indexed |
| ES decommission | After 4 weeks stable | N/A | Re-index (hours) |

### Success Criteria to Advance Phases

- **Shadow → Interleave**: Vector NDCG@10 within 90% of ES
- **Interleave → Primary**: Vector wins interleaving test (>50% preference)
- **Primary → Full**: No CSAT regression, latency within SLA, error rate <0.1%

---

## Q237: Migrate from OpenAI to Self-Hosted Open-Source Models

**Question:** Design a migration from OpenAI APIs to self-hosted open-source models (Llama/Mistral). Include capability mapping, quality gap analysis, infrastructure requirements, and rollback strategy.

**Answer:**

### Migration Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Model Migration Plan                        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────┐  │
│  │  Capability │───▶│  Quality Gap     │───▶│  Infra     │  │
│  │  Mapping    │    │  Analysis        │    │  Sizing    │  │
│  └─────────────┘    └──────────────────┘    └────────────┘  │
│         │                    │                      │         │
│         ▼                    ▼                      ▼         │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────┐  │
│  │  Task-based │    │  Fine-tune to    │    │  Deploy    │  │
│  │  Routing    │    │  close gaps      │    │  + Monitor │  │
│  └─────────────┘    └──────────────────┘    └────────────┘  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class ModelMigrationPlan:
    """Structured migration from OpenAI to self-hosted."""
    
    def capability_mapping(self) -> dict:
        """Map current OpenAI usage to open-source equivalents."""
        return {
            "gpt-4": {
                "tasks": ["complex_reasoning", "code_generation", "analysis"],
                "replacement": "Llama-3.1-70B-Instruct",
                "expected_quality": 0.85,  # vs GPT-4 baseline
                "fine_tune_potential": 0.92,
            },
            "gpt-4-mini": {
                "tasks": ["classification", "extraction", "simple_qa"],
                "replacement": "Mistral-7B-Instruct-v0.3",
                "expected_quality": 0.90,
                "fine_tune_potential": 0.95,
            },
            "text-embedding-3-small": {
                "tasks": ["document_embedding", "query_embedding"],
                "replacement": "bge-large-en-v1.5",
                "expected_quality": 0.95,
            },
        }
    
    def quality_gap_analysis(self) -> QualityReport:
        """Benchmark open-source vs OpenAI on your actual workload."""
        
        # Collect production query sample
        sample = self.get_production_sample(n=1000)
        
        results = {}
        for task_type, queries in sample.group_by_task():
            openai_outputs = self.run_batch(queries, model="gpt-4")
            oss_outputs = self.run_batch(queries, model="llama-3.1-70b")
            
            # Human eval or LLM-as-judge
            scores = self.evaluate_pairwise(openai_outputs, oss_outputs)
            
            results[task_type] = {
                "win_rate_oss": scores.oss_wins / len(queries),
                "tie_rate": scores.ties / len(queries),
                "critical_failures": scores.oss_critical_failures,
                "acceptable": scores.oss_wins + scores.ties > 0.85 * len(queries),
            }
        
        return QualityReport(results=results)
    
    def infrastructure_requirements(self) -> InfraSpec:
        """Calculate GPU requirements for self-hosting."""
        
        # Based on current OpenAI usage
        current_usage = self.get_usage_stats()
        
        specs = {
            "llama-3.1-70b": {
                "gpu_type": "A100-80GB",
                "gpus_per_instance": 4,  # Tensor parallelism
                "instances_for_throughput": math.ceil(
                    current_usage.peak_qps / 10),  # ~10 QPS per 4×A100
                "monthly_cost": 4 * 2.5 * 730,  # $2.5/hr per A100 × 730 hrs
                "vram_required_gb": 140,  # 70B × 2 bytes (FP16)
            },
            "mistral-7b": {
                "gpu_type": "A10G",
                "gpus_per_instance": 1,
                "instances_for_throughput": math.ceil(
                    current_usage.peak_qps / 30),  # ~30 QPS per A10G
                "monthly_cost": 1 * 1.0 * 730,
            },
        }
        
        total_monthly = sum(s["monthly_cost"] * s["instances_for_throughput"] 
                          for s in specs.values())
        
        # Compare with OpenAI costs
        openai_monthly = current_usage.monthly_spend
        
        return InfraSpec(
            specs=specs,
            total_monthly_cost=total_monthly,
            openai_comparison=openai_monthly,
            break_even_months=self.calculate_break_even(total_monthly, openai_monthly),
        )
```

### Cost Comparison

| Component | OpenAI (current) | Self-hosted | Savings |
|-----------|-----------------|-------------|---------|
| LLM inference | $50K/month | $15K/month (GPUs) | 70% |
| Embeddings | $5K/month | $1K/month | 80% |
| Infrastructure | $0 | $5K/month (ops) | N/A |
| Engineering | $0 | $20K/month (team) | N/A |
| **Total** | **$55K/month** | **$41K/month** | **25%** |
| Break-even | — | 6 months (setup costs) | — |

### Rollback Strategy

```python
class MigrationRollback:
    """Instant rollback to OpenAI if quality degrades."""
    
    def __init__(self):
        self.router = ModelRouter()
        self.quality_monitor = QualityMonitor()
    
    async def check_and_rollback(self):
        """Continuous quality monitoring with auto-rollback."""
        
        current_quality = self.quality_monitor.get_rolling_quality(window_min=15)
        baseline = self.quality_monitor.get_baseline()
        
        if current_quality < baseline * 0.9:  # >10% quality drop
            # Auto-rollback: route back to OpenAI
            self.router.set_routing({"openai": 1.0, "self_hosted": 0.0})
            self.alert("Auto-rollback triggered: quality dropped below threshold")
```

### Migration Phases

| Phase | Traffic to Self-Hosted | Duration | Gate |
|-------|----------------------|----------|------|
| Eval only | 0% (shadow) | 2 weeks | Quality within 90% |
| Canary | 5% | 2 weeks | No critical failures |
| Gradual | 25% → 50% → 75% | 6 weeks | Metrics stable |
| Full | 100% | Ongoing | Keep OpenAI as backup 30 days |

---

## Q238: Migrate to Multi-Model Router Architecture

**Question:** Design a migration from a single-model architecture to a multi-model router architecture. How do you introduce model routing without quality regression during transition?

**Answer:**

### Architecture Evolution

```
BEFORE:                          AFTER:
┌──────────┐                     ┌──────────────────────────┐
│  All     │                     │      Model Router        │
│  Queries │──▶ GPT-4            │                          │
│          │                     │  Simple ──▶ GPT-4-mini   │
└──────────┘                     │  Medium ──▶ Claude 3.5   │
                                 │  Complex──▶ GPT-4        │
                                 │  Code   ──▶ Codestral   │
                                 └──────────────────────────┘
```

### Implementation

```python
class MultiModelMigration:
    """Safely introduce model routing."""
    
    def __init__(self):
        self.classifier = QueryComplexityClassifier()
        self.router = ModelRouter()
        self.quality_gate = QualityGate()
    
    async def route_with_safety(self, query: str, context: dict) -> Response:
        """Route to appropriate model with quality verification."""
        
        # Classify query complexity
        classification = self.classifier.classify(query, context)
        
        # Route to model
        model = self.router.select(classification)
        
        # Phase 1: Shadow comparison (no user impact)
        if self.in_shadow_phase():
            primary = await self.call_model("gpt-4", query, context)  # Always GPT-4
            shadow = await self.call_model(model, query, context)
            self.log_comparison(query, classification, primary, shadow)
            return primary
        
        # Phase 2: Route with verification
        response = await self.call_model(model, query, context)
        
        # Quality check on routed response
        quality = self.quality_gate.check(query, response, model)
        
        if quality.score < quality.threshold:
            # Fallback to GPT-4 for this request
            response = await self.call_model("gpt-4", query, context)
            self.log_fallback(query, model, quality.score)
        
        return response


class QueryComplexityClassifier:
    """Classify queries to route to appropriate model."""
    
    def classify(self, query: str, context: dict) -> Classification:
        features = {
            "query_length": len(query.split()),
            "requires_reasoning": self.detect_reasoning(query),
            "requires_code": self.detect_code_request(query),
            "context_size": context.get("token_count", 0),
            "multi_step": self.detect_multi_step(query),
            "domain_specific": self.detect_domain(query),
        }
        
        # Simple heuristic (replace with trained classifier)
        if features["query_length"] < 20 and not features["requires_reasoning"]:
            return Classification(complexity="SIMPLE", confidence=0.9)
        elif features["requires_code"]:
            return Classification(complexity="CODE", confidence=0.85)
        elif features["multi_step"] or features["requires_reasoning"]:
            return Classification(complexity="COMPLEX", confidence=0.8)
        else:
            return Classification(complexity="MEDIUM", confidence=0.75)


class ModelRouter:
    """Route queries to models based on classification."""
    
    ROUTING_TABLE = {
        "SIMPLE": {"model": "gpt-4-mini", "cost_per_1k": 0.00015, "latency_p50_ms": 300},
        "MEDIUM": {"model": "claude-3.5-sonnet", "cost_per_1k": 0.003, "latency_p50_ms": 600},
        "COMPLEX": {"model": "gpt-4", "cost_per_1k": 0.03, "latency_p50_ms": 1200},
        "CODE": {"model": "codestral", "cost_per_1k": 0.001, "latency_p50_ms": 400},
    }
    
    def select(self, classification: Classification) -> str:
        if classification.confidence < 0.7:
            # Low confidence in classification — use premium model
            return "gpt-4"
        return self.ROUTING_TABLE[classification.complexity]["model"]
```

### Migration Safety Metrics

| Metric | Threshold for Advancing | Rollback Trigger |
|--------|------------------------|-----------------|
| Quality parity | >95% win/tie rate vs single-model | <90% |
| Cost reduction | >30% cost savings | N/A (not blocking) |
| Latency p99 | Within 2x of single-model | >3x regression |
| Misrouting rate | <10% fallback to expensive model | >25% |
| User satisfaction | No change in CSAT | >5% drop |

### Expected Outcomes

- **Cost reduction**: 40-60% (most queries are simple)
- **Latency improvement**: 30% p50 reduction (simple queries answered faster)
- **Quality**: Maintained or improved (right model for right task)

---

## Q239: Migrate from Prompt-Based to Fine-Tuned Models

**Question:** Design a migration strategy for moving from prompt-based AI to fine-tuned models. Include data collection from production, training pipeline setup, and quality comparison methodology.

**Answer:**

### Migration Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Collect     │────▶│  Curate      │────▶│  Fine-tune   │
│  Production  │     │  Training    │     │  Model       │
│  Data        │     │  Dataset     │     │              │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │
┌──────────────┐     ┌──────────────┐             │
│  Deploy      │◀────│  Evaluate    │◀────────────┘
│  Gradually   │     │  Quality     │
└──────────────┘     └──────────────┘
```

### Implementation

```python
class PromptToFineTuneMigration:
    def __init__(self):
        self.data_collector = ProductionDataCollector()
        self.curator = DatasetCurator()
        self.trainer = FineTuneTrainer()
        self.evaluator = QualityEvaluator()
    
    def collect_training_data(self, min_samples: int = 5000) -> Dataset:
        """Collect high-quality examples from production."""
        
        # Source 1: Queries with positive user feedback
        positive_feedback = self.data_collector.get_examples(
            filter={"feedback": "positive", "confidence": ">0.8"},
            limit=min_samples // 2,
        )
        
        # Source 2: Queries where prompt-based model performed well
        # (high confidence + no follow-up questions)
        high_quality = self.data_collector.get_examples(
            filter={"confidence": ">0.9", "follow_up_count": 0},
            limit=min_samples // 3,
        )
        
        # Source 3: Manually curated edge cases
        curated = self.data_collector.get_curated_examples(
            limit=min_samples // 6,
        )
        
        all_examples = positive_feedback + high_quality + curated
        
        # Format for fine-tuning
        training_data = []
        for example in all_examples:
            training_data.append({
                "messages": [
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": example.query},
                    {"role": "assistant", "content": example.response},
                ],
            })
        
        return Dataset(examples=training_data)
    
    def curate_dataset(self, raw_data: Dataset) -> Dataset:
        """Quality filtering and deduplication."""
        
        filtered = []
        for example in raw_data.examples:
            # Remove low-quality examples
            if self.quality_score(example) < 0.7:
                continue
            # Remove near-duplicates
            if self.is_duplicate(example, filtered):
                continue
            # Remove PII
            example = self.redact_pii(example)
            filtered.append(example)
        
        # Balance across topics/categories
        balanced = self.balance_dataset(filtered)
        
        # Train/validation split (time-based, not random)
        train, val = self.temporal_split(balanced, val_ratio=0.1)
        
        return Dataset(train=train, validation=val)
    
    def evaluate_fine_tuned(self, base_model: str, fine_tuned: str) -> EvalReport:
        """Compare fine-tuned vs prompt-based on held-out test set."""
        
        test_set = self.get_test_set(n=500)
        
        results = {"base": [], "fine_tuned": []}
        
        for example in test_set:
            base_response = self.generate(base_model, example.query, 
                                          system_prompt=self.full_prompt)
            ft_response = self.generate(fine_tuned, example.query,
                                        system_prompt="")  # No prompt needed
            
            results["base"].append(base_response)
            results["fine_tuned"].append(ft_response)
        
        # Automated metrics
        metrics = {
            "base_quality": self.auto_eval(results["base"], test_set),
            "ft_quality": self.auto_eval(results["fine_tuned"], test_set),
            "cost_reduction": self.calculate_cost_savings(fine_tuned),
            "latency_reduction": self.measure_latency_diff(base_model, fine_tuned),
        }
        
        # LLM-as-judge for nuanced comparison
        judge_results = self.llm_judge_pairwise(results["base"], results["fine_tuned"])
        
        return EvalReport(metrics=metrics, judge=judge_results)
```

### Decision Criteria: When to Fine-Tune

| Signal | Threshold | Action |
|--------|-----------|--------|
| Prompt token count | >2000 tokens system prompt | Fine-tune to bake in knowledge |
| Cost | >$10K/month on single task | Fine-tune smaller model |
| Latency | >3s due to long prompt | Fine-tune to eliminate prompt |
| Consistency | >20% response format violations | Fine-tune for format compliance |
| Volume | >100K queries/month same pattern | Fine-tune for efficiency |

### Expected Improvements

- **Cost**: 70-90% reduction (smaller model, no long system prompt)
- **Latency**: 50-70% reduction (fewer input tokens)
- **Quality**: 0-10% improvement (model specialized for your task)
- **Consistency**: 30-50% improvement (format/style adherence)

---

## Q240: Cloud Migration for On-Premises AI with Data Sovereignty

**Question:** Design a cloud migration for an on-premises AI system. The data can't leave certain geographic regions (data sovereignty). Include hybrid connectivity and gradual cutover.

**Answer:**

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Region A (EU) - Data Sovereign                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  On-Premises Data Center                                │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐  │     │
│  │  │  Source  │  │  Vector DB   │  │  Embeddings     │  │     │
│  │  │  Data    │  │  (on-prem)   │  │  (on-prem GPU)  │  │     │
│  │  └──────────┘  └──────────────┘  └─────────────────┘  │     │
│  └─────────────────────────┬──────────────────────────────┘     │
│                             │ VPN / ExpressRoute                  │
│  ┌─────────────────────────▼──────────────────────────────┐     │
│  │  Cloud (EU Region) - Same geographic region             │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐  │     │
│  │  │  API     │  │  Orchestration│  │  Model Serving  │  │     │
│  │  │  Gateway │  │  Layer       │  │  (cloud GPU)    │  │     │
│  │  └──────────┘  └──────────────┘  └─────────────────┘  │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Global (non-sovereign components)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  CDN / Edge  │  │  Monitoring  │  │  CI/CD               │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class SovereignCloudMigration:
    """Migrate AI workloads respecting data sovereignty."""
    
    def __init__(self, sovereign_region: str = "eu-west-1"):
        self.sovereign_region = sovereign_region
        self.data_classifier = DataClassifier()
    
    def classify_components(self) -> dict:
        """Classify what can move to cloud vs must stay on-prem."""
        
        return {
            "must_stay_on_prem": [
                "source_documents",         # PII, regulated data
                "user_data",                # GDPR-covered
                "vector_embeddings_of_pii", # Derived from PII = also sovereign
            ],
            "can_move_to_sovereign_cloud": [
                "api_gateway",              # Stateless, no data storage
                "model_serving",            # Models don't contain user data
                "orchestration_logic",      # Business logic
                "monitoring_metrics",       # Aggregated, no PII
            ],
            "can_be_global": [
                "cdn_for_static_assets",
                "ci_cd_pipelines",
                "model_artifacts",          # If not trained on sovereign data
                "documentation",
            ],
        }
    
    def migration_phases(self) -> list[MigrationPhase]:
        return [
            MigrationPhase(
                name="Phase 1: Lift non-sovereign compute",
                duration_weeks=4,
                components=["api_gateway", "orchestration"],
                data_movement="NONE",
                connectivity="VPN (on-prem DB → cloud compute)",
                rollback="DNS switch back to on-prem endpoints",
            ),
            MigrationPhase(
                name="Phase 2: Move model serving to cloud GPU",
                duration_weeks=6,
                components=["model_inference"],
                data_movement="Model weights only (not user data)",
                connectivity="Low-latency link for embeddings",
                rollback="Route inference back to on-prem GPU",
            ),
            MigrationPhase(
                name="Phase 3: Migrate vector DB to sovereign cloud",
                duration_weeks=8,
                components=["vector_database"],
                data_movement="Embeddings replicated to cloud region",
                connectivity="Direct connect for bulk sync",
                rollback="Failover to on-prem vector DB",
                prerequisites=["Legal approval for cloud-in-region storage"],
            ),
            MigrationPhase(
                name="Phase 4: Decommission on-prem (optional)",
                duration_weeks=4,
                components=["remaining on-prem infra"],
                data_movement="Full data migration within region",
                prerequisites=["All compliance audits passed"],
            ),
        ]


class HybridConnectivity:
    """Manage connectivity between on-prem and cloud."""
    
    def setup_connectivity(self) -> ConnectivityConfig:
        return ConnectivityConfig(
            primary=DirectConnect(
                bandwidth_gbps=10,
                latency_target_ms=5,  # On-prem to cloud within region
                encryption="IPSec + TLS 1.3",
            ),
            failover=VPNConnection(
                bandwidth_gbps=1,
                latency_target_ms=20,
            ),
            data_flow_rules=[
                # PII never leaves the sovereign boundary
                DataFlowRule(
                    data_type="PII",
                    allowed_destinations=[self.sovereign_region, "on_prem"],
                    blocked_destinations=["*"],
                ),
                # Embeddings can go to sovereign cloud only
                DataFlowRule(
                    data_type="embeddings",
                    allowed_destinations=[self.sovereign_region],
                ),
                # Aggregated metrics can go global
                DataFlowRule(
                    data_type="metrics",
                    allowed_destinations=["*"],
                    condition="must_be_aggregated_and_anonymized",
                ),
            ],
        )
```

### Compliance Checklist

| Requirement | Solution |
|-------------|----------|
| Data residency | All data stays in EU region (cloud + on-prem) |
| Encryption at rest | AES-256, customer-managed keys (on-prem HSM) |
| Encryption in transit | TLS 1.3, IPSec tunnels |
| Access control | Zero-trust, on-prem IAM federated to cloud |
| Audit logging | All access logged, retained 7 years, stored in-region |
| Right to deletion | Propagated to all copies (cloud + on-prem) |
| Data processing agreement | Cloud provider DPA for sovereign region |

### Gradual Cutover Strategy

| Week | On-Prem Traffic | Cloud Traffic | Validation |
|------|----------------|---------------|------------|
| 1-2 | 100% | 0% (shadow) | Compare responses |
| 3-4 | 95% | 5% (canary) | Monitor errors |
| 5-8 | 50% | 50% | Performance parity |
| 9-12 | 10% | 90% | Stability confirmed |
| 13+ | 0% (standby) | 100% | On-prem as DR |
