# Core AI Track: RAG and Knowledge Architecture

**Learning level:** Core AI architect  
**Outcome:** You can design an enterprise knowledge system, not just a vector-search demo. This file combines the source roadmap's RAG mastery phase with the later knowledge architecture phase because they should be learned together.

---

## Phase 2: RAG Mastery

RAG means Retrieval-Augmented Generation. The system retrieves external knowledge and uses it to answer.

Basic RAG flow:

```text
User question
  -> query rewrite / classification
  -> retrieve relevant documents
  -> rerank and filter
  -> assemble context
  -> generate answer
  -> cite sources
  -> evaluate groundedness
```

## RAG Pattern Taxonomy

Different RAG patterns solve different failure modes. A senior architect should name the pattern, explain why it is needed, and define how it will be evaluated.

| RAG Pattern | Use When | Main Risk |
|---|---|---|
| naive RAG | baseline Q&A over simple documents | weak recall, weak citations |
| semantic RAG | semantic similarity is enough | misses exact terms, IDs, dates |
| keyword/BM25 RAG | exact terms matter | misses paraphrases |
| hybrid RAG | exact terms and semantic meaning both matter | score merging and tuning complexity |
| reranked RAG | high precision and citation quality matter | extra latency and cost |
| parent-child RAG | small chunks retrieve well but larger context is needed | parent context can add irrelevant text |
| hierarchical RAG | books, standards, manuals, policies | hierarchy metadata must be reliable |
| multi-query RAG | user query is ambiguous or underspecified | more retrieval calls and dedup complexity |
| query-decomposition RAG | question needs multiple subquestions | subquestion planning can drift |
| HyDE-style RAG | queries are short or abstract | generated hypothetical answer may bias retrieval |
| self-query RAG | metadata filters can be inferred from question | generated filters can be wrong |
| corrective RAG | retrieval result may be insufficient | needs reliable sufficiency detection |
| adaptive RAG | choose retrieval strategy per query | router must be evaluated |
| agentic RAG | multi-step planning, verification, or tool choice is needed | cost, latency, and control complexity |
| Graph RAG | relationships and multi-hop connected facts matter | graph quality and entity resolution cost |
| SQL + vector RAG | numeric facts and semantic docs both matter | consistency between SQL and text evidence |
| temporal RAG | answers depend on time/version/freshness | stale or conflicting source versions |
| multimodal RAG | documents include images, charts, screenshots, audio, or video | harder parsing, citation, and eval |
| federated RAG | knowledge lives across many systems | source auth, latency, and result merging |
| memory-augmented RAG | user/project history matters | privacy, staleness, and memory poisoning |

Architect rule:

> Start with the simplest measurable RAG design. Add hybrid search, reranking, decomposition, graph retrieval, agents, or multimodal retrieval only when evals show the simpler design cannot meet recall, groundedness, citation, latency, or cost targets.

Master ingestion:

- PDF parsing
- DOCX parsing
- HTML parsing
- email parsing
- Confluence ingestion
- SharePoint ingestion
- Google Drive ingestion
- S3 ingestion
- database ingestion
- scanned document OCR
- table extraction
- chart extraction
- page/section preservation
- duplicate removal
- boilerplate removal
- document versioning
- deletion propagation

Master chunking:

| Strategy | Use Case |
|---|---|
| fixed-size chunks | quick baseline |
| sentence chunks | clean text Q&A |
| section-aware chunks | policies, legal docs, manuals |
| parent-child chunks | retrieve small, show larger context |
| semantic chunks | irregular documents |
| hierarchical chunks | books, standards, long manuals |
| table-aware chunks | finance, legal, compliance |
| layout-aware chunks | scanned PDFs and forms |

Master retrieval:

- keyword search
- BM25
- dense vector search
- sparse vector search
- hybrid search
- metadata filtering
- reranking
- multi-query retrieval
- query decomposition
- HyDE-style retrieval
- self-query retrieval
- graph retrieval
- temporal retrieval
- multimodal retrieval
- access-controlled retrieval

Build:

- enterprise RAG app over real documents
- vector search
- keyword search
- hybrid retrieval
- reranker
- citations
- access control
- retrieval eval dashboard

Milestone:

> Your RAG system can prove it retrieved the right evidence, not just generate a nice answer.

---


## Phase 7: Knowledge Bases and Knowledge Architecture

A production knowledge base is not a folder of PDFs in a vector database.

It needs:

- source connectors
- ingestion pipeline
- parsing
- cleaning
- chunking
- metadata enrichment
- PII classification
- access control
- versioning
- freshness
- deletion propagation
- evaluation
- observability
- governance
- feedback loop

Knowledge architecture:

```text
Source systems
  -> connectors
  -> parser / OCR / table extraction
  -> cleaner / normalizer
  -> chunker
  -> metadata enricher
  -> PII / sensitivity classifier
  -> embedding service
  -> vector DB + keyword index + metadata DB
  -> retriever / reranker / ACL layer
  -> RAG or Agentic RAG application
  -> evaluation + observability + feedback
```

Learn semantic architecture:

- taxonomy
- ontology
- knowledge graph
- entity resolution
- canonical data model
- business glossary
- data catalog
- lineage
- temporal validity

Milestone:

> You understand that enterprise AI quality depends on governed knowledge, not just model power.

## Knowledge Quality and Retrieval Failure Modes

Senior architects diagnose RAG failures by layer:

| Failure | Likely Layer | Fix |
|---|---|---|
| correct document never retrieved | ingestion, chunking, embeddings, index, filters | improve parsing, chunking, metadata, embedding model, or hybrid retrieval |
| correct document retrieved but answer wrong | context assembly, prompt, model, verification | improve context budget, claim verification, citations, or model choice |
| stale answer | freshness, versioning, cache, sync pipeline | add freshness metadata, deletion propagation, cache invalidation, and reindex SLAs |
| user sees unauthorized content | auth, ACL sync, metadata filters, cache keying | enforce permission-filtered retrieval and negative access tests |
| citations point to weak evidence | chunking, reranking, citation builder | use claim-level citations, reranking, page/section offsets, citation evals |
| answer is incomplete | retrieval depth, query decomposition, source coverage | add multi-query, decomposition, source authority ranking, or Graph RAG |
| numeric answer is wrong | tool/data integration | use SQL/calculation tools and numeric accuracy evals |

Retrieval design principle:

> RAG quality is not one metric. Measure retrieval recall, context precision, groundedness, citation correctness, latency, freshness, permission safety, and cost together.

---
