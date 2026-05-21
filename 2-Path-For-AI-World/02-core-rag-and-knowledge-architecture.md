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

---
