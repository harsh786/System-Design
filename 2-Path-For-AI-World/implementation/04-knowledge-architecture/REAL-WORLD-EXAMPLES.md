# Knowledge Architecture: Real-World Examples & Case Studies

## Case Study 1: How Microsoft Built Their Internal Knowledge Graph for Support

### Context
Microsoft's support organization handles 1B+ customer interactions/year across 400+ products. Their internal knowledge system ("Knowledge Engine") serves 30K+ support agents with AI-powered answer suggestions, troubleshooting workflows, and escalation guidance.

### Scale
- 4.2 million knowledge articles
- 12 million relationships between entities
- 47 product taxonomies with 15K+ nodes
- Updated 50K+ times per day
- Serves 2M queries/day from agents and self-service bots

### Knowledge Graph Architecture

```
Microsoft Knowledge Engine — Simplified Architecture:
─────────────────────────────────────────────────────

Entity Types:
┌─────────────────────────────────────────────────────────┐
│ Products     │ Windows 11, Azure DevOps, Teams, ...     │
│ Features     │ BitLocker, Conditional Access, ...       │
│ Symptoms     │ "Blue screen", "sync failed", ...        │
│ Root Causes  │ Driver conflict, cert expired, ...       │
│ Solutions    │ Step-by-step fixes, workarounds          │
│ Articles     │ KB articles, docs pages, blog posts      │
│ Releases     │ Version numbers, patch IDs               │
│ Components   │ DLLs, services, APIs                     │
└─────────────────────────────────────────────────────────┘

Relationship Types:
┌─────────────────────────────────────────────────────────┐
│ Product ──[HAS_FEATURE]──▶ Feature                      │
│ Symptom ──[CAUSED_BY]──▶ Root Cause                     │
│ Root Cause ──[RESOLVED_BY]──▶ Solution                  │
│ Solution ──[DOCUMENTED_IN]──▶ Article                   │
│ Article ──[APPLIES_TO]──▶ Product + Version             │
│ Article ──[SUPERSEDED_BY]──▶ Article (newer)            │
│ Symptom ──[SIMILAR_TO]──▶ Symptom (weighted)            │
│ Product ──[DEPENDS_ON]──▶ Component                     │
│ Release ──[FIXES]──▶ Root Cause                         │
└─────────────────────────────────────────────────────────┘
```

### How Freshness Works at Scale

```
Freshness Pipeline:
───────────────────

Source Feeds (continuous):
├── docs.microsoft.com changes (webhook) ─────▶ ┐
├── Support ticket resolutions (streaming) ────▶ │
├── Product release notes (RSS + API) ─────────▶ ├── Ingestion
├── Internal engineering escalations ───────────▶ │   Queue
├── Community forums (top answers) ─────────────▶ │   (Kafka)
└── Known issues database (real-time) ──────────▶ ┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────┐
│  Change Detection & Classification                       │
│  • Is this a NEW article or UPDATE to existing?         │
│  • Diff analysis: what specifically changed?            │
│  • Impact scoring: how many customers affected?         │
│  • Urgency: security fix? → fast-path (< 5 min)        │
│             routine update? → batch (< 4 hours)         │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  Knowledge Graph Update                                  │
│  • Update entity properties (last_modified, version)    │
│  • Add/remove relationships                             │
│  • Propagate: if Article superseded → mark old as stale │
│  • Re-embed: if content changed substantially (>15%     │
│    semantic distance from previous embedding)           │
│  • Notify: agents who bookmarked this article           │
└─────────────────────────────────────────────────────────┘

Freshness SLAs:
  • Security advisories: < 15 minutes
  • Product updates/releases: < 2 hours
  • New KB articles: < 4 hours
  • Community-sourced solutions: < 24 hours (after validation)
```

### Query Resolution Using the Graph

```
Agent Query: "Customer on Windows 11 23H2 getting BitLocker 
             recovery prompt after KB5034441 update"

Graph Traversal:
1. Entity recognition:
   - Product: Windows 11
   - Version: 23H2
   - Feature: BitLocker
   - Symptom: "recovery prompt after update"
   - Trigger: KB5034441

2. Graph walk:
   KB5034441 ──[TRIGGERS]──▶ "BitLocker recovery prompt"
   "BitLocker recovery prompt" ──[CAUSED_BY]──▶ "TPM PCR mismatch after WinRE update"
   "TPM PCR mismatch..." ──[RESOLVED_BY]──▶ Solution_A (suspend BitLocker before update)
   "TPM PCR mismatch..." ──[RESOLVED_BY]──▶ Solution_B (manual PCR reset)
   Solution_A ──[DOCUMENTED_IN]──▶ KB5035849 (published 2024-03-12)
   KB5035849 ──[APPLIES_TO]──▶ Windows 11 23H2 ✓

3. Result: Surface KB5035849 with confidence "high" (exact symptom→cause→solution path exists)
```

### Impact Metrics

| Metric | Before Knowledge Graph | After |
|---|---|---|
| Mean time to resolution | 14.2 min | 8.7 min |
| First-contact resolution rate | 62% | 78% |
| Articles surfaced relevance (human eval) | 54% | 82% |
| Stale article served to agent | 11% of queries | 2% of queries |
| Agent satisfaction score | 3.4/5 | 4.3/5 |

---

## Case Study 2: Pharmaceutical Drug Interaction Knowledge System

### Company Profile
A top-10 pharma company built an AI system to assist researchers in identifying potential drug-drug interactions (DDIs) during early-stage drug development. The system combines structured databases, research papers, and clinical trial data.

### Knowledge Schema

```
Drug Interaction Ontology:
──────────────────────────

Entities:
┌─────────────────────────────────────────────────────────────┐
│ Drug (compound)                                              │
│ ├── Properties: name, aliases, SMILES, molecular_weight,    │
│ │   mechanism_of_action, half_life, bioavailability         │
│ ├── Classifications: ATC code, therapeutic class            │
│ └── Approval: FDA status, EMA status, year_approved         │
│                                                              │
│ Target (biological)                                          │
│ ├── Properties: gene_name, protein_name, UniProt_ID         │
│ ├── Type: receptor, enzyme, transporter, ion_channel        │
│ └── Tissue_expression: liver, brain, kidney, ...            │
│                                                              │
│ Pathway (metabolic)                                          │
│ ├── CYP enzymes: CYP3A4, CYP2D6, CYP2C19, ...            │
│ ├── Transport: P-glycoprotein, OATP1B1, ...                │
│ └── Phase: I (oxidation), II (conjugation)                  │
│                                                              │
│ Interaction (the relationship itself is an entity)          │
│ ├── Type: pharmacokinetic, pharmacodynamic                  │
│ ├── Mechanism: inhibition, induction, competition           │
│ ├── Severity: major, moderate, minor                        │
│ ├── Evidence_level: clinical_trial, in_vitro, computational │
│ ├── Direction: Drug_A affects Drug_B (asymmetric)          │
│ └── Clinical_outcome: increased_toxicity, reduced_efficacy │
│                                                              │
│ Evidence (supporting data)                                   │
│ ├── Source: PubMed_ID, ClinicalTrials_ID, FDA_label        │
│ ├── Study_type: RCT, case_report, in_vitro, meta_analysis  │
│ ├── Sample_size, confidence_interval                        │
│ └── Date_published                                          │
└─────────────────────────────────────────────────────────────┘

Relationships:
  Drug ──[METABOLIZED_BY]──▶ CYP_Enzyme
  Drug ──[INHIBITS]──▶ CYP_Enzyme (with Ki value)
  Drug ──[INDUCES]──▶ CYP_Enzyme (with EC50)
  Drug ──[SUBSTRATE_OF]──▶ Transporter
  Drug ──[BINDS_TO]──▶ Target (with affinity Kd)
  Drug ──[INTERACTS_WITH]──▶ Drug (via Interaction entity)
  Interaction ──[SUPPORTED_BY]──▶ Evidence
  Evidence ──[PUBLISHED_IN]──▶ Journal
```

### Knowledge Pipeline

```
Data Sources → Knowledge Graph:
───────────────────────────────

┌──────────────────────┐
│ DrugBank (structured)│──▶ Direct entity/relationship extraction
│ 15K drugs, 5K targets│    Confidence: HIGH (curated)
└──────────────────────┘

┌──────────────────────┐
│ PubMed (unstructured)│──▶ BioNER + Relation Extraction model
│ 35M papers           │    Fine-tuned PubMedBERT for DDI extraction
│ (filtered to 200K    │    Confidence: MEDIUM (model-extracted)
│  DDI-relevant)       │    Human review for severity=major
└──────────────────────┘

┌──────────────────────┐
│ FDA Drug Labels      │──▶ Section 7 "Drug Interactions" parser
│ (DailyMed API)       │    Rule-based extraction + LLM verification
│ 40K labels           │    Confidence: HIGH (regulatory source)
└──────────────────────┘

┌──────────────────────┐
│ Clinical Trials      │──▶ Protocol & results mining
│ (ClinicalTrials.gov) │    Focus on DDI studies & AE reports
│ 450K trials          │    Confidence: HIGH (primary data)
└──────────────────────┘

┌──────────────────────┐
│ Internal Assay Data  │──▶ CYP inhibition assays, PAMPA results
│ (proprietary)        │    Direct structured ingestion
│ 8K compounds         │    Confidence: HIGHEST (own data)
└──────────────────────┘
```

### Query Example: New Drug Candidate Assessment

```
Researcher Query: "What are potential interactions between our compound 
                   XR-7291 (CYP3A4 inhibitor, Ki=0.3μM) and common 
                   cardiovascular medications?"

System Response:
──────────────────
1. CRITICAL INTERACTIONS (severity: major):

   XR-7291 + Simvastatin
   ├── Mechanism: XR-7291 inhibits CYP3A4 → ↑ simvastatin exposure
   ├── Predicted AUC increase: 4-8x (based on Ki=0.3μM, strong inhibitor)
   ├── Clinical risk: Rhabdomyolysis
   ├── Evidence: Analogous interaction with itraconazole (Ki=0.27μM)
   │   showed 10x AUC increase [PMID: 12811366]
   ├── FDA precedent: Simvastatin contraindicated with strong CYP3A4 inhibitors
   └── Recommendation: AVOID co-administration or limit simvastatin to 10mg

   XR-7291 + Amiodarone
   ├── Mechanism: Bidirectional — both CYP3A4 substrates AND inhibitors
   ├── Predicted effect: Mutual exposure increase
   ├── Clinical risk: QT prolongation (additive)
   ├── Evidence: [3 supporting papers listed]
   └── Recommendation: DDI study required before Phase II if cardiac population

2. MODERATE INTERACTIONS: [5 more listed...]
3. KNOWLEDGE GAPS: "No data on interaction with PCSK9 inhibitors — recommend in-vitro study"
```

### Impact
- Identified 3 critical DDIs in pre-clinical that would have been caught only in Phase I (saving ~$2M per avoided late-stage failure)
- Reduced DDI literature review time from 2 weeks to 2 hours per compound
- FDA submission packages now auto-generated with complete interaction profiles

---

## Knowledge Pipeline at Scale: 50K Documents/Day

### Company: Large management consulting firm with 200K+ employees

### Pipeline Architecture

```
Ingestion: 50,000 documents/day from 12 source systems
─────────────────────────────────────────────────────────

Sources & Volumes:
├── SharePoint/OneDrive: 20K docs/day (presentations, reports)
├── Confluence: 8K pages/day (technical documentation)
├── Email attachments (opted-in): 10K/day
├── Client deliverables (anonymized): 5K/day
├── Research databases: 4K articles/day
├── Internal wikis: 2K pages/day
└── Training materials: 1K/day

Pipeline Stages:
                                                    
Stage 1: INTAKE (Kafka topics per source)
─────────────────────────────────────────
├── Deduplication (MinHash LSH): ~8% duplicates removed
├── Format normalization: PPTX/DOCX/PDF → markdown + images
├── Language detection: route non-English to translation queue
├── PII detection: flag & redact (Presidio) before processing
└── Throughput: 50K docs in ~2 hours (parallel workers)

Stage 2: QUALITY GATE
─────────────────────
├── Content quality scoring:
│   ├── Length check: < 50 words → reject (likely stub/template)
│   ├── Boilerplate detection: > 80% matches template → low priority
│   ├── Freshness: is this a duplicate of existing content? (embedding similarity > 0.95)
│   ├── Completeness: missing title? no author? → flag for metadata enrichment
│   └── Readability: Flesch-Kincaid < 20 → likely auto-generated garbage → reject
├── Pass rate: ~72% (28% rejected or deferred)
└── Human review queue: 500 docs/day flagged for manual decision

Stage 3: ENRICHMENT
───────────────────
├── Entity extraction: people, projects, clients, technologies
├── Topic classification: 3-level taxonomy (47 practice areas)
├── Auto-summarization: 2-3 sentence abstract per document
├── Relationship extraction: "this doc references [other doc]"
├── Expertise inference: author → topics they write about
└── Processing: ~4 hours for full batch (GPU cluster, 8× A100)

Stage 4: CHUNKING & EMBEDDING
─────────────────────────────
├── Strategy: hierarchical (section-level + paragraph-level)
├── Average: 12 chunks per document
├── Total new vectors/day: ~430K (50K docs × 72% pass × 12 chunks)
├── Embedding model: text-embedding-3-large (API, batched)
├── Cost: ~$180/day for embeddings
└── Duration: ~3 hours (rate-limited by API)

Stage 5: INDEXING
─────────────────
├── Vector store: Qdrant (3-node cluster, 48GB RAM each)
├── Metadata store: PostgreSQL (for filtering, access control)
├── Knowledge graph: Neo4j (entity relationships)
├── Search index: Elasticsearch (keyword fallback)
└── Total indexed vectors: 85M (growing 430K/day)

Stage 6: VALIDATION
───────────────────
├── Retrieval smoke test: 100 golden queries, check recall > 0.80
├── Embedding quality: random sample cosine similarity sanity check
├── Access control: verify permissions propagated correctly
└── Rollback: if validation fails, revert batch (< 0.1% failure rate)
```

### Quality Metrics Dashboard

```
Daily Pipeline Health:
┌─────────────────────────────────────────────────────────┐
│ Documents ingested:        50,247    (target: 50K)      │
│ Quality gate pass rate:    71.8%     (target: >70%)     │
│ Duplicate detection:       8.2%      (normal: 6-10%)    │
│ PII incidents detected:    127       (all auto-redacted) │
│ Enrichment failures:       0.3%      (target: <1%)      │
│ Embedding latency (p99):   4.1 hrs   (target: <6 hrs)  │
│ Retrieval smoke test:      0.83      (target: >0.80)    │
│ Index size growth:         +432K vectors                 │
│ Total corpus:              85.2M vectors                 │
└─────────────────────────────────────────────────────────┘
```

---

## Graph RAG in Practice: Microsoft's GraphRAG

### Background
Microsoft Research published GraphRAG (2024), which constructs a knowledge graph from documents and uses graph communities for summarization. Here's how an enterprise applied it.

### Company: Insurance firm with 30K policy documents + 500K claims

### Problem with Standard RAG
Standard RAG failed on "global" questions:
- "What are the most common denial reasons across all commercial auto policies?"
- "Summarize the key differences between our 2023 and 2024 homeowner coverage terms"
- "What patterns exist in large-loss claims over the past 5 years?"

These questions require synthesizing information across hundreds of documents — no single chunk contains the answer.

### GraphRAG Implementation

```
Phase 1: Entity & Relationship Extraction (offline, batch)
──────────────────────────────────────────────────────────
For each document, LLM extracts:
  - Entities: coverage types, exclusions, limits, conditions, parties
  - Relationships: "exclusion X applies to coverage Y in state Z"

Document: "Commercial Auto Policy - Hired Auto Coverage"
  Extracted entities:
    [Hired Auto Coverage] (type: coverage)
    [Liability Limit: $1M CSL] (type: limit)
    [Driver Age Exclusion: <21] (type: exclusion)
    [State: California] (type: jurisdiction)
  Extracted relationships:
    [Hired Auto Coverage] ──has_limit──▶ [$1M CSL]
    [Hired Auto Coverage] ──has_exclusion──▶ [Driver Age <21]
    [Driver Age <21] ──applies_in──▶ [California]

After processing 30K documents:
  → 890K entities
  → 2.1M relationships
  → Stored in Neo4j

Phase 2: Community Detection (Leiden algorithm)
───────────────────────────────────────────────
Graph partitioned into hierarchical communities:
  Level 0: 12,000 communities (fine-grained, ~50 entities each)
  Level 1: 2,400 communities (mid-level, ~250 entities each)
  Level 2: 180 communities (high-level themes)

Example Level 2 community: "Commercial Auto Exclusions"
  Contains: 340 exclusion entities across all commercial auto policies
  Summary (LLM-generated):
    "Commercial auto policies contain 47 distinct exclusion categories.
     The most prevalent are: racing/speed contests (100% of policies),
     livery/delivery (94%), driver under influence (100%), intentional
     damage (100%). State-specific exclusions vary significantly..."

Phase 3: Query Routing
──────────────────────
Local query (specific): "What's excluded in Policy #CA-2024-7291?"
  → Standard RAG (retrieve chunks from that specific policy)

Global query (synthetic): "What are the most common exclusions?"
  → GraphRAG: retrieve community summaries at appropriate level
  → Level 2 summary already contains aggregated answer
  → No need to retrieve and synthesize 30K individual chunks

Map-reduce for complex global queries:
  "Compare exclusion patterns between commercial and personal auto"
  → Retrieve: commercial auto community summaries + personal auto summaries
  → Map: extract exclusion lists from each community
  → Reduce: compare and synthesize differences
```

### Results: GraphRAG vs Standard RAG

| Query Type | Standard RAG (answer quality 1-5) | GraphRAG | Improvement |
|---|---|---|---|
| Specific policy lookup | 4.3 | 4.1 | -5% (slight overhead) |
| Cross-document comparison | 2.1 | 4.2 | +100% |
| Trend/pattern questions | 1.8 | 3.9 | +117% |
| Summary/aggregation | 1.5 | 4.0 | +167% |
| "What are all the X?" | 2.3 | 4.4 | +91% |

### Cost Trade-off

```
GraphRAG Construction Cost (one-time, 30K documents):
  Entity extraction: 30K docs × ~2K tokens/doc × $10/1M = $600
  Relationship extraction: 30K docs × ~1K tokens/doc × $10/1M = $300
  Community summarization: 14,580 communities × ~500 tokens = $73
  Total construction: ~$973 (plus ~$50/day for incremental updates)

Query cost comparison:
  Standard RAG global query: often fails (no coherent answer) = wasted $0.04
  GraphRAG global query: $0.02 (retrieve community summary, shorter context)
  
  Standard RAG local query: $0.035
  GraphRAG local query: $0.035 (same, falls back to standard RAG)
```

---

## Knowledge Freshness: News Organization RAG System

### Company: Major international news wire (think Reuters/AP scale)

### Requirement
Journalists need an AI assistant that knows about events from the last hour. Standard RAG with nightly batch updates is useless for breaking news.

### Architecture for < 1 Hour Latency

```
Real-Time Knowledge Pipeline:
─────────────────────────────

┌─────────────────────────────────────────────────────────────┐
│  SOURCE TIER (continuous)                                     │
│  ├── Own wire feed: ~3,000 articles/day, streaming           │
│  ├── Partner feeds: Reuters, AP, AFP via API (< 30s delay)  │
│  ├── Press releases: PRNewswire, BusinessWire (webhook)      │
│  ├── Government sources: SEC EDGAR, FDA, WhiteHouse.gov      │
│  ├── Social signals: verified accounts, breaking hashtags    │
│  └── Scheduled events: earnings calls, press conferences     │
└─────────────────────────────┬───────────────────────────────┘
                              │ (Kafka, partitioned by topic)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PROCESSING TIER (< 5 minutes end-to-end)                    │
│                                                              │
│  Step 1: Dedup & Verify (30s)                               │
│  ├── Near-duplicate detection (SimHash)                      │
│  ├── Source credibility check (tier 1/2/3)                  │
│  └── If unverified source → hold in pending queue            │
│                                                              │
│  Step 2: Entity Extraction & Linking (60s)                   │
│  ├── NER: people, orgs, locations, events, figures          │
│  ├── Entity linking: "Apple" → Apple Inc (AAPL) not fruit   │
│  ├── Event detection: is this a NEW event or UPDATE?        │
│  └── Timeline linking: connect to ongoing story thread       │
│                                                              │
│  Step 3: Chunk & Embed (90s)                                │
│  ├── Chunk: paragraph-level (news articles are short)       │
│  ├── Embed: text-embedding-3-small (fastest API)            │
│  ├── Metadata: timestamp, source, entities, story_id        │
│  └── Tiered TTL: breaking=keep 7 days, archive=compress     │
│                                                              │
│  Step 4: Index (30s)                                        │
│  ├── Vector store: Qdrant with collection aliasing          │
│  ├── Keyword index: Elasticsearch (for exact quotes, names) │
│  ├── Timeline index: time-bucketed for temporal queries      │
│  └── Entity graph: update relationships in Neo4j            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  QUERY TIER (freshness-aware retrieval)                       │
│                                                              │
│  Query: "What happened with the Boeing whistleblower?"       │
│                                                              │
│  1. Detect temporal intent: "what happened" → recent bias    │
│  2. Entity resolution: "Boeing whistleblower" → story_id_X  │
│  3. Retrieve with recency boost:                            │
│     score = relevance × recency_weight(age)                 │
│     recency_weight = exp(-age_hours / 24)                   │
│  4. Story threading: pull full timeline for story_id_X      │
│  5. Generate with timeline context:                         │
│     "As of [timestamp], the latest development is..."       │
│                                                              │
│  Freshness guarantee:                                        │
│  ├── Article published at T                                 │
│  ├── Available in index by T + 5min (p95)                   │
│  ├── If user queries at T + 6min → article is retrievable   │
│  └── Stale indicator: if latest info > 2hrs old, flag it    │
└─────────────────────────────────────────────────────────────┘
```

### Key Design: Collection Aliasing for Zero-Downtime Updates

```
Qdrant Collection Strategy:
───────────────────────────
Instead of updating vectors in-place (slow, causes inconsistency):

news_current (alias) ──▶ news_collection_v1 (active, serving queries)

Every hour:
1. Create news_collection_v2
2. Copy all valid (non-expired) vectors from v1 to v2
3. Add all new vectors from the last hour
4. Run validation (golden query set)
5. Atomic alias swap: news_current ──▶ news_collection_v2
6. Delete news_collection_v1

Result: Zero downtime, no stale vectors, consistent state
Latency impact: None (alias swap is O(1))
```

### Dealing with Corrections and Retractions

```
Correction Handling:
────────────────────
1. Original article published: "Company X revenue: $5.2B" (T=0)
2. Correction issued: "Company X revenue: $3.2B (corrected)" (T=45min)

System behavior:
├── Original chunk gets flag: superseded_by = correction_id
├── Original chunk score penalized: relevance × 0.1
├── Correction chunk gets flag: corrects = original_id
├── If both retrieved: LLM instructed to use ONLY the correction
├── After 24hrs: original chunk deleted entirely
└── Audit log: records that correction was issued + propagation time

Retraction handling:
├── Retracted articles: chunks hard-deleted within 5 minutes
├── Tombstone record left in metadata DB (for audit)
└── If cached in any CDN/cache layer → invalidation pushed
```

---

## Multi-Source Knowledge Fusion: Enterprise Knowledge Base

### Company: Series D SaaS startup (800 employees, remote-first)

### Problem
Knowledge scattered across 6 systems. Engineers spent 45 min/day searching for information. New hires took 3 months to become productive (vs. 6-week target).

### Source Mapping

```
Source Systems & Their Knowledge Types:
───────────────────────────────────────

┌──────────────┬─────────────────────────────────┬──────────────┐
│ Source       │ Knowledge Type                   │ Volume       │
├──────────────┼─────────────────────────────────┼──────────────┤
│ Confluence   │ Architecture docs, runbooks,     │ 12K pages    │
│              │ onboarding guides, RFCs          │ +50/day      │
├──────────────┼─────────────────────────────────┼──────────────┤
│ Slack        │ Decisions, troubleshooting,      │ 2M messages  │
│              │ tribal knowledge, Q&A            │ +15K/day     │
├──────────────┼─────────────────────────────────┼──────────────┤
│ GitHub       │ Code comments, PR discussions,   │ 500 repos    │
│              │ READMEs, ADRs, issue threads     │ +200 PRs/day │
├──────────────┼─────────────────────────────────┼──────────────┤
│ Jira         │ Requirements, acceptance         │ 45K tickets  │
│              │ criteria, bug reports            │ +80/day      │
├──────────────┼─────────────────────────────────┼──────────────┤
│ Google Docs  │ Design docs, meeting notes,      │ 8K docs      │
│              │ retrospectives, proposals        │ +30/day      │
├──────────────┼─────────────────────────────────┼──────────────┤
│ Notion       │ Team wikis, personal notes,      │ 5K pages     │
│              │ project trackers                 │ +20/day      │
└──────────────┴─────────────────────────────────┴──────────────┘
```

### Fusion Architecture

```
Multi-Source Fusion Pipeline:
─────────────────────────────

┌─────────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ ┌───────┐ ┌───────┐
│ Confluence  │ │  Slack  │ │ GitHub  │ │ Jira │ │ GDocs │ │Notion │
└──────┬──────┘ └────┬────┘ └────┬────┘ └──┬───┘ └───┬───┘ └───┬───┘
       │              │           │          │         │         │
       ▼              ▼           ▼          ▼         ▼         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Source Adapters (one per system)                                     │
│  • Confluence: REST API polling (5-min interval)                    │
│  • Slack: Events API (real-time, message.channels scope)            │
│  • GitHub: Webhooks (PR, issue, push events)                        │
│  • Jira: Webhooks (issue created/updated/resolved)                  │
│  • Google Docs: Drive API change feed                               │
│  • Notion: API polling (2-min interval)                             │
│                                                                      │
│  Each adapter outputs standardized: {                                │
│    source, source_id, content, title, author, timestamp,            │
│    url, permissions, parent_context, content_type                    │
│  }                                                                   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Source-Specific Processing                                          │
│                                                                      │
│  Slack messages:                                                     │
│  ├── Filter: only channels opted-in, skip bot messages              │
│  ├── Thread consolidation: merge thread into single document        │
│  ├── Signal extraction: messages with ✅ reactions = decisions       │
│  ├── Q&A detection: question + marked answer → Q&A pair            │
│  └── Noise filter: < 3 messages in thread → skip                   │
│                                                                      │
│  GitHub PRs:                                                         │
│  ├── Extract: PR description + review comments with decisions       │
│  ├── Link: PR → Jira ticket (from branch name/description)         │
│  ├── Code context: what files changed (for relevance)               │
│  └── ADR detection: docs/adr/ path → high priority                  │
│                                                                      │
│  Jira tickets:                                                       │
│  ├── Extract: description + acceptance criteria + resolution        │
│  ├── Link: to Confluence pages, GitHub PRs, Slack threads           │
│  └── Bug knowledge: root cause + fix (from resolved bugs)           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Cross-Source Linking & Deduplication                                 │
│                                                                      │
│  Entity Resolution:                                                  │
│  ├── "Payment Service" in Confluence = "payment-svc" in GitHub      │
│  │   = "PAYMENTS" Jira project = #team-payments in Slack            │
│  ├── Person resolution: Slack handle ↔ GitHub username ↔ Jira user │
│  └── Concept resolution: "retry logic" mentioned in 4 sources       │
│       → create unified knowledge node with 4 source links           │
│                                                                      │
│  Conflict Detection:                                                 │
│  ├── Confluence says "timeout is 30s" but code shows 60s → flag    │
│  ├── Resolution: most recent source wins + alert doc owner          │
│  └── ~3% of cross-source facts have conflicts (measured)            │
│                                                                      │
│  Deduplication:                                                      │
│  ├── Same info in Confluence AND Notion → keep authoritative source │
│  ├── Slack decision replicated in RFC → keep RFC, link Slack        │
│  └── Reduces index size by ~22%                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Results After 6 Months

| Metric | Before | After |
|---|---|---|
| Avg time to find information | 45 min/day/person | 12 min/day/person |
| New hire time-to-productivity | 12 weeks | 5 weeks |
| "I couldn't find it" survey responses | 67% | 18% |
| Duplicate documentation created | ~30% of new docs | ~8% |
| Cross-team knowledge discovery | "rarely" (78%) | "often" (61%) |

---

## Knowledge Quality Metrics in Production

### Framework Used by a Fortune 500 Technology Company

```
Knowledge Quality Scorecard (computed daily):
─────────────────────────────────────────────

1. FRESHNESS SCORE (target: > 0.85)
   ─────────────────────────────────
   Formula: Σ(doc_weight × freshness(doc)) / Σ(doc_weight)
   
   freshness(doc) = {
     1.0  if updated within expected_refresh_interval
     0.7  if 1-2× past expected interval
     0.3  if 2-5× past expected interval
     0.0  if > 5× past expected interval (STALE)
   }
   
   expected_refresh_interval varies by type:
     API documentation: 30 days
     Product guides: 90 days
     Policy documents: 180 days
     Architecture decisions: 365 days (unless superseded)
   
   Current score: 0.82 (below target — 340 docs flagged as stale)
   Action: Auto-email sent to doc owners of stale content

2. COVERAGE SCORE (target: > 0.90)
   ────────────────────────────────
   Measures: "What % of user queries can be answered from our knowledge base?"
   
   Method:
   ├── Sample 1,000 queries/week
   ├── Human raters assess: "Was the answer in the KB?" (Y/N/Partial)
   ├── Coverage = (Y + 0.5×Partial) / Total
   └── Track gaps: queries with no coverage → knowledge gap backlog
   
   Current score: 0.87
   Top gaps identified:
     - New product feature launched 2 weeks ago (docs not written yet)
     - Edge case troubleshooting for Legacy System X
     - Cross-product integration scenarios
   
   Action: Gap reports sent to product teams weekly

3. CONFLICT SCORE (target: < 0.02)
   ────────────────────────────────
   Measures: "What % of knowledge items contradict each other?"
   
   Detection methods:
   ├── Automated: NLI model comparing overlapping chunks
   │   (premise from doc A, hypothesis from doc B)
   │   If "contradiction" confidence > 0.8 → flag
   ├── User-reported: "This answer contradicts what I read in [X]"
   └── Temporal: older doc states X, newer doc states NOT X
       (may be intentional update or may be inconsistency)
   
   Current score: 0.034 (above target — 89 conflicts detected)
   Resolution workflow:
     1. Auto-create Jira ticket assigned to doc owners of both docs
     2. 5-day SLA to resolve (update one, archive other, or clarify both)
     3. Escalate to knowledge manager if unresolved

4. RETRIEVAL QUALITY (target: MRR > 0.70)
   ───────────────────────────────────────
   Measured via golden test set (500 queries with known-good answers):
   ├── MRR@5: 0.73 ✓
   ├── Recall@10: 0.85 ✓
   ├── "Wrong answer served" rate: 2.1% (target < 3%) ✓
   └── "No answer available" rate: 8.4% (target < 10%) ✓

5. USAGE & FEEDBACK SIGNALS
   ─────────────────────────
   ├── Thumbs up/down on AI answers: 81% positive (target > 75%) ✓
   ├── "Answer copied" rate: 34% (indicates high utility)
   ├── Repeat queries (same user, same topic < 24hrs): 12%
   │   (indicates first answer was insufficient)
   └── Escalation to human after AI answer: 15% (target < 20%) ✓
```

### Alerting Rules

```python
# Automated quality alerts
ALERT_RULES = {
    "freshness_drop": {
        "condition": "freshness_score < 0.80 for 3 consecutive days",
        "action": "page knowledge-ops team",
        "severity": "P2"
    },
    "conflict_spike": {
        "condition": "new_conflicts_detected > 20 in 24 hours",
        "action": "alert knowledge manager + pause ingestion from flagged source",
        "severity": "P1"
    },
    "retrieval_degradation": {
        "condition": "MRR@5 drops > 5% week-over-week",
        "action": "alert ML team + auto-rollback to previous index version",
        "severity": "P1"
    },
    "coverage_gap_trending": {
        "condition": "same gap query appears > 50 times in a week",
        "action": "auto-create content request ticket with priority=high",
        "severity": "P3"
    }
}
```

---

## Taxonomy and Ontology Design for Enterprise AI

### Real Schema: Technology Company's Knowledge Taxonomy

```
Enterprise Knowledge Taxonomy (3 levels):
─────────────────────────────────────────

Level 1: Domain (12 domains)
├── Engineering
├── Product
├── Sales
├── Customer Success
├── Legal & Compliance
├── HR & People
├── Finance
├── Security
├── Data & Analytics
├── Infrastructure
├── Design
└── Executive/Strategy

Level 2: Category (example for Engineering)
├── Engineering
│   ├── Architecture & Design
│   ├── Development Practices
│   ├── Testing & Quality
│   ├── Deployment & Operations
│   ├── Incident Management
│   ├── Performance & Scalability
│   ├── API Design
│   ├── Data Engineering
│   └── Machine Learning

Level 3: Topic (example for Architecture & Design)
├── Architecture & Design
│   ├── System Architecture
│   │   ├── Microservices patterns
│   │   ├── Event-driven architecture
│   │   ├── Data flow diagrams
│   │   └── Service mesh configuration
│   ├── Architecture Decision Records
│   ├── Technology Selection
│   ├── Integration Patterns
│   ├── Security Architecture
│   └── Scalability Design
```

### Ontology Schema (OWL-lite, simplified)

```yaml
# Enterprise Knowledge Ontology
# Used to type entities and validate relationships in the knowledge graph

classes:
  KnowledgeArtifact:
    description: "Any piece of documented knowledge"
    subclasses:
      - Document        # Confluence page, Google Doc, wiki page
      - CodeArtifact    # README, ADR, code comment, PR description
      - Decision        # Slack thread conclusion, RFC decision
      - Procedure       # Runbook, how-to, troubleshooting guide
      - Policy          # Company policy, compliance requirement
      - Reference       # API doc, config reference, glossary entry
    properties:
      - title: string (required)
      - content: text (required)
      - author: Person (required)
      - created_at: datetime (required)
      - updated_at: datetime (required)
      - source_system: enum [confluence, github, slack, jira, gdocs, notion]
      - source_url: uri
      - confidence: float [0-1]  # how confident we are in accuracy
      - domains: list[Domain] (1+)
      - categories: list[Category] (1+)
      - status: enum [draft, published, deprecated, archived]
      - access_level: enum [public, internal, team, restricted]

  Person:
    properties:
      - name: string
      - email: string
      - teams: list[Team]
      - expertise_areas: list[Topic] (inferred from authorship)
      - role: string

  Team:
    properties:
      - name: string
      - domain: Domain
      - members: list[Person]
      - owned_services: list[Service]

  Service:
    properties:
      - name: string
      - repository: uri
      - owner_team: Team
      - dependencies: list[Service]
      - documentation: list[KnowledgeArtifact]

relationships:
  - authored_by: KnowledgeArtifact → Person
  - owned_by: KnowledgeArtifact → Team
  - supersedes: KnowledgeArtifact → KnowledgeArtifact
  - references: KnowledgeArtifact → KnowledgeArtifact
  - implements_decision: CodeArtifact → Decision
  - documents_service: KnowledgeArtifact → Service
  - expert_in: Person → Topic (weight: float, based on contribution count)
  - depends_on: Service → Service
  - related_to: KnowledgeArtifact → KnowledgeArtifact (symmetric, weighted)

constraints:
  - Every KnowledgeArtifact MUST have at least one domain
  - A deprecated artifact MUST have a supersedes link to its replacement
  - Procedures MUST be reviewed every 180 days (freshness enforcement)
  - Policies MUST have an owner from Legal or Compliance team
  - Decisions MUST link to the discussion thread where they were made
```

### How the Ontology Improves RAG

```
Without ontology (flat chunking):
  Query: "How do we handle authentication?"
  Retrieved: 15 random chunks mentioning "auth" from different contexts
  Problem: mix of user-facing auth, service-to-service auth, DB auth, old deprecated docs

With ontology-aware retrieval:
  Query: "How do we handle authentication?"
  1. Classify: Engineering > Security Architecture > Authentication
  2. Filter: status != deprecated, type = Procedure OR Reference
  3. Retrieve: within filtered subset, vector search
  4. Enrich: follow "documents_service" links to add service context
  Result: 5 relevant, current, authoritative chunks about production auth patterns
  
  Quality improvement: Relevance score from 0.62 → 0.84 (+35%)
```

---

## Document Lifecycle Management in Vector Stores

### The Problem
Vector stores are append-friendly but lifecycle-unfriendly. Documents get updated, deprecated, versioned — but their embeddings linger as "zombie vectors" causing retrieval pollution.

### Real Implementation: B2B Documentation Platform

```
Document States & Transitions:
──────────────────────────────

      ┌─────────┐     publish      ┌───────────┐
      │  DRAFT  │ ─────────────▶   │ PUBLISHED │
      └─────────┘                  └─────┬─────┘
                                         │
                            ┌────────────┼─────────────┐
                            │            │             │
                         update     deprecate      archive
                            │            │             │
                            ▼            ▼             ▼
                     ┌───────────┐ ┌───────────┐ ┌──────────┐
                     │ PUBLISHED │ │DEPRECATED │ │ ARCHIVED │
                     │ (new ver) │ │           │ │          │
                     └───────────┘ └───────────┘ └──────────┘

Vector Store Behavior per State:
─────────────────────────────────
DRAFT:       Not indexed. Only searchable by author.
PUBLISHED:   Fully indexed. All chunks active.
UPDATED:     Old version chunks deleted. New version chunks inserted.
             Atomic swap using versioned chunk IDs.
DEPRECATED:  Chunks remain but with score penalty (×0.3).
             If retrieved, response includes: "⚠️ This document is 
             deprecated. See [replacement] instead."
ARCHIVED:    Chunks moved to cold storage index (separate collection).
             Only searched if user explicitly opts in to "include archived".
             Cost savings: cold storage is 80% cheaper.
```

### Versioning Implementation

```python
class DocumentVersionManager:
    """
    Manages document versions in vector store.
    Key principle: atomic version swaps — users never see partial updates.
    """
    
    def update_document(self, doc_id: str, new_content: str, version: int):
        new_chunks = self.chunker.chunk(new_content)
        new_vectors = self.embedder.embed_batch([c.text for c in new_chunks])
        
        # Step 1: Insert new version chunks with version suffix
        new_chunk_ids = []
        for i, (chunk, vector) in enumerate(zip(new_chunks, new_vectors)):
            chunk_id = f"{doc_id}_v{version}_chunk_{i}"
            self.vector_store.upsert(
                id=chunk_id,
                vector=vector,
                metadata={
                    "doc_id": doc_id,
                    "version": version,
                    "status": "pending",  # not yet searchable
                    "chunk_index": i,
                    "text": chunk.text,
                    **chunk.metadata
                }
            )
            new_chunk_ids.append(chunk_id)
        
        # Step 2: Atomic swap — activate new, deactivate old
        # Using metadata filter: queries only return status="active"
        old_chunk_ids = self.get_chunks_for_doc(doc_id, status="active")
        
        # Batch update: new chunks → active, old chunks → inactive
        self.vector_store.batch_update_metadata(
            ids=new_chunk_ids, 
            metadata={"status": "active"}
        )
        self.vector_store.batch_update_metadata(
            ids=old_chunk_ids,
            metadata={"status": "inactive"}
        )
        
        # Step 3: Schedule cleanup of old chunks (after 7-day safety window)
        self.scheduler.schedule(
            task="delete_chunks",
            chunk_ids=old_chunk_ids,
            execute_after=timedelta(days=7),
            reason=f"Superseded by v{version}"
        )
        
        # Step 4: Update version registry
        self.registry.set_current_version(doc_id, version)
        self.registry.log_version_history(doc_id, version, 
            previous=version-1, changed_chunks=len(new_chunks))
    
    def deprecate_document(self, doc_id: str, replacement_doc_id: str = None):
        """Soft-deprecate: keep searchable but penalized."""
        chunks = self.get_chunks_for_doc(doc_id, status="active")
        self.vector_store.batch_update_metadata(
            ids=chunks,
            metadata={
                "status": "deprecated",
                "deprecated_at": datetime.utcnow().isoformat(),
                "replacement_doc_id": replacement_doc_id,
                "score_penalty": 0.3  # applied at query time
            }
        )
```

### Garbage Collection & Cost Management

```
Vector Store Hygiene (weekly job):
──────────────────────────────────

1. Zombie detection:
   - Chunks with status="inactive" older than 7 days → DELETE
   - Chunks with no parent document in metadata DB → DELETE (orphans)
   - Result: ~5% of vectors are zombies at any given time

2. Archive migration:
   - Documents not accessed in 180 days → move to cold collection
   - Cold collection: same vectors, cheaper storage tier, not searched by default
   - Savings: 15% of total vector store cost

3. Embedding drift detection:
   - If embedding model is updated (e.g., ada-002 → text-embedding-3-small)
   - Must re-embed entire corpus (mixing models = terrible retrieval)
   - Strategy: create new collection, backfill in background, atomic alias swap
   - Timeline: 500K docs takes ~8 hours, scheduled over weekend

4. Size monitoring:
   Current: 12M active vectors (Qdrant, 3-node cluster)
   Growth: +150K vectors/week
   Alert: if > 80% storage capacity → scale cluster
   Budget: $2,400/month for vector infrastructure

Storage breakdown:
├── Active (published): 12M vectors = 85% of storage
├── Deprecated (penalized): 800K vectors = 6%
├── Pending (mid-update): <10K vectors = <0.1%
├── Cold (archived): 4M vectors = separate cluster, $400/month
└── Total managed: 16.8M vectors
```

### Version Conflict Resolution

```
Scenario: Two people edit the same Confluence page within 5 minutes

T=0:  Page version 7 is current in vector store
T=1:  User A saves edit → triggers re-chunking pipeline
T=3:  User B saves different edit → triggers re-chunking pipeline
T=4:  Pipeline for User A completes → version 8 activated
T=5:  Pipeline for User B completes → version 9 activated

Resolution: Last-write-wins (matches source system behavior)
Safety: 7-day retention of old versions allows rollback if needed
Audit: full version history maintained in metadata DB

Edge case: Concurrent updates to SAME version
├── Handled by optimistic locking on version number
├── Second pipeline detects version already incremented
├── Re-fetches latest content from source → re-processes
└── Adds ~30s latency for the losing write (acceptable)
```

---

## Summary: Knowledge Architecture Principles from Production

```
Lessons from These Case Studies:
────────────────────────────────

1. Knowledge graphs + vector search > vector search alone
   (GraphRAG showed 2x quality improvement on global queries)

2. Source-aware processing is critical
   (Slack messages need different treatment than Confluence pages)

3. Freshness is a feature, not an afterthought
   (News org: < 5 min; Enterprise: < 4 hours; both designed upfront)

4. Conflicts are inevitable in multi-source systems
   (Budget 3-5% conflict rate; have automated detection + resolution workflow)

5. Document lifecycle must be designed into the vector store layer
   (Atomic version swaps, deprecation with penalty, archival to cold storage)

6. Ontology/taxonomy enables precision that flat search cannot
   (+35% relevance when queries are routed through taxonomy)

7. Quality metrics must be continuous, not one-time
   (Freshness, coverage, conflict, retrieval quality — all measured daily)

8. Knowledge pipelines need quality gates
   (28% rejection rate is healthy — garbage in = garbage out)

9. Cross-source entity resolution is the hardest part
   ("payment-svc" = "Payment Service" = #team-payments requires maintenance)

10. Cost of knowledge infrastructure is small vs. value
    (45 min/day/person saved × 800 people = 600 person-hours/day recovered)
```
