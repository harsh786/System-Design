# Knowledge Architecture for Enterprise AI

## Why a Production Knowledge Base is NOT Just PDFs in a Vector DB

The most common misconception in enterprise AI is that "RAG = throw documents into a vector database." This naive approach fails catastrophically in production because:

### The PDF-in-VectorDB Fallacy

| What You Think You Need | What Production Actually Requires |
|---|---|
| Upload documents | Continuous ingestion from 50+ source systems with change detection |
| Chunk text | Context-aware chunking that respects document structure, tables, and semantic boundaries |
| Embed chunks | Multi-modal embeddings with metadata enrichment, PII classification, and ACL tagging |
| Similarity search | Hybrid retrieval combining vector, keyword, graph, and structured queries with re-ranking |
| Return results | Permission-filtered, freshness-validated, confidence-scored responses with citations |

### Why Naive RAG Fails in Enterprise

1. **Stale knowledge**: Documents change daily; embeddings become outdated within hours
2. **Permission violations**: User retrieves content they shouldn't have access to
3. **No deletion propagation**: Deleted source document still returns results
4. **Context fragmentation**: Chunking splits a table across 3 chunks, destroying meaning
5. **Entity ambiguity**: "Mercury" could be a planet, element, car brand, or company name
6. **No provenance**: Cannot trace an answer back to its authoritative source
7. **Quality blind spots**: No way to know if retrieval quality is degrading
8. **Conflicting information**: Two documents say different things; no resolution mechanism
9. **Format loss**: PDF tables become gibberish; images lose context
10. **Scale collapse**: Approach that works for 100 docs fails at 10M docs

---

## Knowledge Architecture Components

### 1. Source Connectors

The knowledge architecture must connect to every system where enterprise knowledge lives:

- **Document stores**: Confluence, SharePoint, Google Drive, Notion, Box
- **Code repositories**: GitHub, GitLab, Bitbucket
- **Databases**: PostgreSQL, MySQL, Snowflake, BigQuery
- **Communication**: Slack, Teams, Email archives
- **Ticketing**: Jira, ServiceNow, Zendesk
- **CRM/ERP**: Salesforce, SAP, HubSpot
- **Object storage**: S3, Azure Blob, GCS
- **APIs**: REST endpoints, GraphQL, webhooks

Each connector must handle:
- Authentication and token refresh
- Rate limiting and backoff
- Pagination and cursor management
- Schema mapping to canonical format
- Health checks and failure alerting

### 2. Change Detection and Incremental Sync

```
Full Re-index: Expensive, slow, but guarantees consistency
Incremental Sync: Fast, efficient, but requires change tracking

Strategies:
- Webhook-based (real-time, requires source support)
- Polling with last-modified timestamps
- Change Data Capture (CDC) for databases
- Event streams (Kafka, EventBridge)
- Hash-based comparison for dumb sources
```

### 3. Parsing and Content Extraction

| Format | Parser | Challenges |
|--------|--------|------------|
| PDF | PyMuPDF, Unstructured, Adobe API | Tables, multi-column, scanned images |
| DOCX | python-docx, Unstructured | Embedded objects, track changes |
| HTML | BeautifulSoup, Trafilatura | Navigation noise, dynamic content |
| Email | email.parser, exchangelib | Attachments, threads, signatures |
| Slides | python-pptx | Speaker notes, animations |
| Spreadsheets | openpyxl, pandas | Formulas, multiple sheets, pivots |
| Images | Tesseract, Azure Doc Intelligence | Handwriting, diagrams, charts |
| Audio/Video | Whisper, AssemblyAI | Transcription accuracy, speaker diarization |

### 4. Cleaning and Normalization

- Remove boilerplate (headers, footers, navigation)
- Normalize Unicode and encoding
- Deduplicate near-identical content
- Resolve abbreviations and acronyms
- Standardize date/number formats
- Remove PII from training data (while preserving for authorized retrieval)
- Fix OCR errors
- Merge document fragments

### 5. Chunking Strategies

```
Strategy              | Best For              | Typical Size
─────────────────────────────────────────────────────────────
Fixed-size            | Uniform text          | 512-1024 tokens
Sentence-based       | Conversational text   | 3-5 sentences
Paragraph-based      | Structured documents  | 1-3 paragraphs
Semantic chunking    | Mixed content         | Variable
Document-section     | Technical docs        | Per heading
Table-aware          | Data-heavy docs       | Per table + context
Sliding window       | Dense information     | Overlap 10-20%
Hierarchical         | Long documents        | Parent + child chunks
Agentic chunking     | Complex documents     | LLM-determined boundaries
```

**Critical principle**: Every chunk must be self-contained enough to be useful without its neighbors, but include enough metadata to reconstruct context.

### 6. Metadata Enrichment

Every chunk must carry rich metadata:

```json
{
  "chunk_id": "uuid",
  "document_id": "source_doc_uuid",
  "source_system": "confluence",
  "source_url": "https://...",
  "title": "Deployment Runbook",
  "section_hierarchy": ["Operations", "Deployments", "Production"],
  "author": "jane.doe@company.com",
  "created_at": "2024-01-15T10:00:00Z",
  "modified_at": "2024-03-20T14:30:00Z",
  "version": 7,
  "content_type": "procedure",
  "entities": ["Kubernetes", "ArgoCD", "Production Cluster"],
  "topics": ["deployment", "operations", "kubernetes"],
  "sensitivity": "internal",
  "pii_detected": false,
  "acl_groups": ["engineering", "sre"],
  "language": "en",
  "quality_score": 0.92,
  "chunk_index": 3,
  "total_chunks": 12,
  "parent_chunk_id": "uuid_parent",
  "child_chunk_ids": ["uuid_c1", "uuid_c2"]
}
```

### 7. PII Classification and Sensitivity

Layers of sensitivity classification:

| Level | Label | Examples | Handling |
|-------|-------|----------|----------|
| 0 | Public | Marketing materials, public docs | No restrictions |
| 1 | Internal | Internal wikis, procedures | Employee-only access |
| 2 | Confidential | Financial data, HR policies | Role-based access |
| 3 | Restricted | PII, credentials, M&A data | Need-to-know, audit trail |
| 4 | Regulated | HIPAA, PCI, GDPR-covered | Compliance controls, encryption at rest |

PII detection must identify:
- Names, emails, phone numbers
- SSNs, passport numbers, driver's licenses
- Credit card numbers, bank accounts
- Medical records, health information
- Biometric data
- Location data (home addresses)

### 8. Access Control Lists (ACLs)

```
Source ACL → Mapped to → Knowledge Base ACL → Enforced at → Query Time

Key Challenges:
- ACL inheritance (folder permissions cascade to children)
- Group membership changes (user leaves team)
- Cross-system identity mapping (Confluence user = SharePoint user?)
- Temporal ACLs (access expires after date)
- ACL on chunk vs. ACL on document
```

### 9. Versioning

Every piece of knowledge must be versioned:

- **Document version**: Which version of the source was indexed
- **Chunk version**: When this specific chunk was last updated
- **Embedding version**: Which model version generated the embedding
- **Schema version**: Which metadata schema applies

Versioning enables:
- Rollback on quality regression
- A/B testing retrieval strategies
- Audit trail for compliance
- Temporal queries ("what did the policy say in Q1 2024?")

### 10. Freshness Management

```
Source Type         | Expected Freshness | Sync Strategy
───────────────────────────────────────────────────────────
Real-time feeds     | < 1 minute        | Streaming/webhooks
Chat/tickets        | < 5 minutes       | Event-driven
Wiki/docs           | < 1 hour          | Webhook + polling
Code repos          | < 15 minutes      | Git hooks
Databases           | < 5 minutes       | CDC
Email               | < 30 minutes      | IMAP polling
File shares         | < 4 hours         | Scheduled scan
Archived content    | < 24 hours        | Daily batch
```

### 11. Deletion Propagation

When a source document is deleted:
1. Mark all derived chunks as `tombstoned`
2. Remove from vector index (soft delete)
3. Remove from keyword index
4. Update knowledge graph (remove nodes/edges)
5. Log deletion event for audit
6. Propagate to all downstream caches
7. Verify deletion in next consistency check

**Hard requirement**: A deleted document must NEVER appear in retrieval results after propagation SLA.

### 12. Evaluation and Quality Monitoring

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| Retrieval Precision@K | Relevant chunks in top-K | > 0.85 |
| Retrieval Recall | Found all relevant chunks | > 0.75 |
| MRR (Mean Reciprocal Rank) | Rank of first relevant result | > 0.80 |
| Answer Faithfulness | Answer grounded in retrieved context | > 0.95 |
| Coverage | % of queries with adequate context | > 0.90 |
| Freshness compliance | % of chunks within freshness SLA | > 0.99 |
| ACL accuracy | % of queries with correct filtering | 1.00 |
| Latency P95 | End-to-end retrieval time | < 500ms |

### 13. Observability

Full observability stack for knowledge systems:

- **Metrics**: Ingestion rate, chunk count, embedding latency, retrieval latency, cache hit rate
- **Logs**: Every ingestion event, parsing failure, ACL decision, deletion event
- **Traces**: Full trace from query → retrieval → re-ranking → response
- **Alerts**: Freshness SLA breach, quality regression, connector failure, capacity threshold
- **Dashboards**: Real-time pipeline health, quality trends, source coverage

### 14. Governance

- **Data lineage**: Trace any answer back to its source document
- **Audit trail**: Who accessed what, when, via which query
- **Retention policies**: Auto-expire content per regulatory requirements
- **Quality gates**: Content must pass quality threshold before indexing
- **Change approval**: Critical knowledge sources require review before re-indexing
- **Compliance reporting**: Generate reports for auditors

### 15. Feedback Loop

```
User Query → Retrieval → Response → User Feedback
                                          ↓
                                    Feedback Store
                                          ↓
                              ┌────────────┼────────────┐
                              ↓            ↓            ↓
                        Relevance     Quality      Missing
                        Signals       Signals      Knowledge
                              ↓            ↓            ↓
                        Re-rank       Re-chunk     Gap
                        Tuning        Strategy     Identification
                              ↓            ↓            ↓
                        Updated       Updated      New Source
                        Models        Pipeline     Connectors
```

---

## Semantic Architecture

### Taxonomy

A controlled hierarchical vocabulary that classifies knowledge:

```
Company Knowledge
├── Products
│   ├── Product A
│   │   ├── Features
│   │   ├── Pricing
│   │   └── Documentation
│   └── Product B
├── Engineering
│   ├── Architecture
│   ├── Operations
│   └── Security
├── Business
│   ├── Finance
│   ├── Legal
│   └── HR
└── Customer
    ├── Support
    ├── Success
    └── Feedback
```

### Ontology

Formal definitions of entities and their relationships:

```
Entity Types:
- Person (employee, customer, partner)
- Organization (department, team, vendor)
- Product (service, feature, component)
- Process (workflow, procedure, policy)
- Technology (tool, platform, language)
- Document (policy, runbook, spec)
- Event (incident, release, meeting)

Relationship Types:
- owns (Person → Product)
- belongs_to (Person → Organization)
- depends_on (Product → Technology)
- documents (Document → Process)
- caused_by (Event → Event)
- supersedes (Document → Document)
- implements (Technology → Process)
```

### Knowledge Graph

A graph representation connecting entities through typed relationships:

- **Nodes**: Entities with properties (name, type, attributes)
- **Edges**: Relationships with properties (type, confidence, valid_from, valid_to)
- **Enables**: Multi-hop reasoning, relationship discovery, context enrichment
- **Use cases**: "Who owns the service that caused last week's incident?"

### Entity Resolution

The process of determining that two references point to the same real-world entity:

```
"AWS Lambda" = "Lambda" = "serverless functions (AWS)" = "our FaaS layer"
"John Smith (Engineering)" ≠ "John Smith (Marketing)"
"Q4 revenue target" (2023) ≠ "Q4 revenue target" (2024)
```

Techniques:
- String similarity (Levenshtein, Jaro-Winkler)
- Embedding similarity
- Co-reference resolution
- Rule-based matching (email, ID)
- ML-based entity linking

### Canonical Data Model

A single, normalized schema that all source systems map to:

```python
@dataclass
class KnowledgeUnit:
    id: str                          # Globally unique
    canonical_type: EntityType       # From ontology
    title: str                       # Human-readable title
    content: str                     # Normalized text content
    structured_data: dict            # Type-specific fields
    source: SourceReference          # Where it came from
    relationships: List[Relationship] # Graph connections
    metadata: KnowledgeMetadata      # Enriched metadata
    access_control: ACLPolicy        # Who can see this
    lifecycle: LifecycleState        # Active, archived, tombstoned
```

### Business Glossary

Authoritative definitions for business terms:

| Term | Definition | Owner | Synonyms | Related |
|------|-----------|-------|----------|---------|
| ARR | Annual Recurring Revenue | Finance | Annual revenue | MRR, Churn |
| SLA | Service Level Agreement | SRE | Service guarantee | SLO, SLI |
| DAU | Daily Active Users | Product | Active users | MAU, WAU |

The glossary resolves ambiguity in queries and ensures consistent interpretation.

### Data Catalog

Registry of all knowledge sources and their metadata:

- What data exists and where
- Schema and format information
- Quality scores and freshness
- Ownership and stewardship
- Usage statistics
- Lineage connections

### Lineage

Track the full transformation path:

```
Source Document → Parsed Content → Cleaned Text → Chunks → Embeddings → Index Entry
     ↑                                                                        ↓
  Original URL                                                          Query Result
```

Every query result must be traceable back to its original source through the complete lineage chain.

### Temporal Validity

Knowledge has time boundaries:

```python
class TemporalKnowledge:
    valid_from: datetime      # When this knowledge became true
    valid_until: datetime     # When it stops being true (or None)
    superseded_by: str        # ID of newer version
    as_of_query: bool         # Support "what was true on date X?"
```

---

## Knowledge Quality and Retrieval Failure Modes

| # | Failure Mode | Likely Layer | Root Cause | Fix |
|---|---|---|---|---|
| 1 | Irrelevant chunks returned | Chunking | Chunks too large or context-poor | Semantic chunking with overlap; add section titles to chunks |
| 2 | Relevant doc not found | Embedding | Query-document vocabulary mismatch | Hybrid search (vector + BM25); query expansion |
| 3 | Stale information returned | Freshness | Sync lag or missing change detection | Reduce sync interval; add freshness filter to queries |
| 4 | Permission violation | ACL | ACL not propagated from source | Real-time ACL sync; query-time permission check |
| 5 | Deleted doc still appears | Deletion | Tombstone not propagated to all indexes | Synchronous deletion across all stores; consistency check |
| 6 | Table data garbled | Parsing | PDF table extraction failed | Specialized table parser; preserve as structured data |
| 7 | Conflicting answers | Governance | Multiple versions without supersession tracking | Version ordering; temporal validity; authoritative source ranking |
| 8 | Missing context | Chunking | Information split across chunks | Hierarchical chunking; parent-child retrieval |
| 9 | Entity confusion | Entity Resolution | Same name, different entities | Entity linking; disambiguation via context |
| 10 | Low recall for jargon | Embedding | Domain terms not in embedding vocabulary | Fine-tuned embeddings; synonym expansion; business glossary |
| 11 | Hallucinated source | Retrieval/Generation | Model invents citation | Strict grounding enforcement; citation verification |
| 12 | Slow retrieval | Infrastructure | Index too large or unoptimized | Sharding; approximate NN; caching; pre-filtering |
| 13 | Embedding drift | Model | New embedding model incompatible | Versioned indexes; gradual migration; dual-write |
| 14 | Duplicate chunks | Ingestion | Same content from multiple sources | Content hashing; deduplication at ingestion |
| 15 | Language mismatch | Embedding | Query in English, doc in French | Multilingual embeddings; language detection and routing |
| 16 | Image/diagram content missed | Parsing | No vision extraction | Multimodal parsing; image captioning; diagram description |
| 17 | Metadata wrong | Enrichment | Classifier error or stale metadata | Human-in-loop validation; periodic re-enrichment |
| 18 | Knowledge gap undetected | Evaluation | No coverage monitoring | Query coverage analysis; failed retrieval logging |
| 19 | Feedback not incorporated | Feedback Loop | No mechanism to improve from user signals | Thumbs up/down → re-ranking tuning; relevance labeling |
| 20 | Cross-document reasoning fails | Graph | No relationship modeling | Knowledge graph; multi-hop retrieval; graph-augmented RAG |

---

## Knowledge Freshness SLAs

### Tier Definitions

| Tier | Max Staleness | Use Case | Sync Method |
|------|--------------|----------|-------------|
| Real-time | < 60 seconds | Incident runbooks, live dashboards | Streaming/webhook |
| Near-real-time | < 5 minutes | Support tickets, chat threads | Event-driven |
| Frequent | < 1 hour | Wiki pages, documentation | Polling (5-min interval) |
| Standard | < 4 hours | Code repositories, design docs | Scheduled sync |
| Daily | < 24 hours | Archived content, reports | Daily batch |
| On-demand | Manual trigger | Historical records, legal docs | Manual re-index |

### SLA Enforcement

```
For each knowledge source:
1. Define freshness tier
2. Configure sync schedule matching tier
3. Monitor actual freshness (last_synced - source_modified)
4. Alert when freshness exceeds tier threshold
5. Escalate if freshness exceeds 2x tier threshold
6. Auto-disable source if freshness exceeds 5x (stale data is worse than no data)
```

### Freshness Dashboard Metrics

- `freshness_compliance_rate`: % of sources within SLA
- `max_staleness_seconds`: Worst-case staleness across all sources
- `sync_failure_rate`: % of sync attempts that failed
- `time_to_index`: Latency from source change to queryable

---

## Design Principle

> **"Enterprise AI quality depends on governed knowledge, not just model power."**

A mediocre model with excellent knowledge architecture will outperform a frontier model with poor knowledge management. The knowledge layer is the highest-leverage investment for enterprise AI quality.

### Corollaries

1. **Knowledge is a product, not a project** — It needs a team, roadmap, SLAs, and continuous investment
2. **Retrieval quality > Generation quality** — If you retrieve the wrong context, no model can save you
3. **Governance enables trust** — Without lineage, freshness, and access control, users won't trust AI answers
4. **Feedback is fuel** — Every user interaction is a signal to improve knowledge quality
5. **Measure everything** — You cannot improve what you cannot measure; instrument the full pipeline
