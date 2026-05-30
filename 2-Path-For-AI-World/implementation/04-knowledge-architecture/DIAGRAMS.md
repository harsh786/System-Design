# Knowledge Architecture Diagrams

## 1. Complete Knowledge Architecture (End-to-End)

```mermaid
flowchart TB
    subgraph Sources["Source Systems"]
        CONF[Confluence]
        SP[SharePoint]
        S3[AWS S3]
        DB[(Databases)]
        GH[GitHub]
        SLACK[Slack]
        EMAIL[Email]
    end

    subgraph Connectors["Connector Layer"]
        CDC[Change Detection]
        AUTH[Auth & Token Mgmt]
        RATE[Rate Limiter]
        SCHED[Scheduler]
    end

    subgraph Ingestion["Ingestion Pipeline"]
        PARSE[Parser Orchestrator]
        CLEAN[Cleaner & Normalizer]
        CHUNK[Semantic Chunker]
        ENRICH[Metadata Enricher]
        PII[PII Classifier]
        EMBED[Embedding Service]
    end

    subgraph Storage["Storage Layer"]
        VDB[(Vector DB)]
        KW[(Keyword Index)]
        KG[(Knowledge Graph)]
        META[(Metadata Store)]
        AUDIT[(Audit Log)]
    end

    subgraph Retrieval["Retrieval Layer"]
        HYBRID[Hybrid Retriever]
        RERANK[Re-Ranker]
        ACL_F[ACL Filter]
        FRESH_F[Freshness Filter]
    end

    subgraph Governance["Governance & Observability"]
        FRESH[Freshness Monitor]
        QUALITY[Quality Evaluator]
        LINEAGE[Data Lineage]
        FEEDBACK[Feedback Loop]
        ALERTS[Alerting]
        DASH[Dashboards]
    end

    Sources --> Connectors
    Connectors --> Ingestion
    Ingestion --> Storage
    Storage --> Retrieval
    Governance -.->|monitors| Ingestion
    Governance -.->|monitors| Storage
    Governance -.->|monitors| Retrieval
    FEEDBACK -.->|improves| CHUNK
    FEEDBACK -.->|improves| RERANK

    USER[User Query] --> ACL_F --> HYBRID
    HYBRID --> VDB
    HYBRID --> KW
    HYBRID --> KG
    HYBRID --> RERANK --> RESPONSE[Response + Citations]
```

## 2. Ingestion Pipeline with All Stages

```mermaid
flowchart LR
    subgraph Fetch
        F1[Connector Fetch]
        F2[Change Detection]
        F3{Changed?}
    end

    subgraph Parse
        P1[Format Detection]
        P2[PDF Parser]
        P3[HTML Parser]
        P4[DOCX Parser]
        P5[Email Parser]
    end

    subgraph Process
        C1[Boilerplate Removal]
        C2[Unicode Normalization]
        C3[Deduplication]
        C4[Semantic Chunking]
        C5[Overlap Generation]
        C6[Table Preservation]
    end

    subgraph Enrich
        E1[Entity Extraction]
        E2[Topic Classification]
        E3[Content Type Detection]
        E4[Quality Scoring]
        E5[PII Detection]
        E6[Sensitivity Classification]
        E7[ACL Mapping]
    end

    subgraph Index
        I1[Embedding Generation]
        I2[Vector DB Upsert]
        I3[Keyword Indexing]
        I4[Graph Update]
        I5[Metadata Store]
    end

    F1 --> F2 --> F3
    F3 -->|Yes| P1
    F3 -->|No| SKIP[Skip]

    P1 --> P2 & P3 & P4 & P5
    P2 & P3 & P4 & P5 --> C1

    C1 --> C2 --> C3 --> C4 --> C5 --> C6

    C6 --> E1 --> E2 --> E3 --> E4 --> E5 --> E6 --> E7

    E7 --> I1 --> I2 & I3 & I4 & I5

    I2 & I3 & I4 & I5 --> DONE[✓ Indexed]
```

## 3. Knowledge Graph Entity Resolution Flow

```mermaid
flowchart TD
    DOC[New Document Text] --> EXTRACT[Entity Extraction]
    
    EXTRACT --> CANDIDATES[Candidate Entities]
    
    CANDIDATES --> RESOLVE{Entity Resolution}
    
    subgraph Resolution["Resolution Strategies"]
        R1[Exact Name Match]
        R2[Alias Lookup]
        R3[String Similarity]
        R4[Embedding Similarity]
        R5[Rule-Based ID Match]
    end

    RESOLVE --> R1 & R2 & R3 & R4 & R5

    R1 & R2 & R3 & R4 & R5 --> DECISION{Match Found?}

    DECISION -->|Yes| MERGE[Merge into Existing Entity]
    DECISION -->|No| CREATE[Create New Entity]

    MERGE --> UPDATE_PROPS[Update Properties]
    MERGE --> ADD_ALIAS[Add Aliases]
    MERGE --> ADD_SOURCE[Add Source Document]
    MERGE --> UPDATE_CONF[Update Confidence]

    CREATE --> CANONICAL[Apply Canonical Name]
    CREATE --> ASSIGN_TYPE[Assign Entity Type]
    CREATE --> GEN_EMBED[Generate Embedding]

    UPDATE_PROPS & ADD_ALIAS & ADD_SOURCE & UPDATE_CONF --> GRAPH_UPDATE[Update Graph]
    CANONICAL & ASSIGN_TYPE & GEN_EMBED --> GRAPH_UPDATE

    GRAPH_UPDATE --> REL_EXTRACT[Relationship Extraction]
    REL_EXTRACT --> GRAPH_STORE[(Knowledge Graph)]
```

## 4. Freshness Monitoring and Alerting

```mermaid
flowchart TD
    subgraph Sources["Monitored Sources"]
        S1[Confluence - SLA: 1hr]
        S2[SharePoint - SLA: 4hr]
        S3[Database - SLA: 5min]
        S4[S3 - SLA: 4hr]
        S5[GitHub - SLA: 15min]
    end

    MONITOR[Freshness Monitor<br/>Runs every 1 min]

    Sources --> MONITOR

    MONITOR --> CHECK{Staleness vs SLA}

    CHECK -->|Within SLA| GREEN[✓ Fresh]
    CHECK -->|1x-2x SLA| YELLOW[⚠ Warning]
    CHECK -->|2x-5x SLA| RED[🔴 Alert]
    CHECK -->|>5x SLA| BLACK[⛔ Auto-Disable]

    YELLOW --> WARN_ALERT[Warning Notification]
    RED --> ESC_ALERT[Escalation Alert]
    BLACK --> DISABLE[Disable Source<br/>Stale > No Data]

    DISABLE --> INCIDENT[Create Incident]
    DISABLE --> REMOVE_RESULTS[Remove from Results]

    subgraph Dashboard["Freshness Dashboard"]
        D1[Compliance Rate: 99.2%]
        D2[Max Staleness: 45min]
        D3[Sync Failure Rate: 0.1%]
        D4[Time-to-Index P95: 12s]
    end

    MONITOR -.-> Dashboard
```

## 5. Deletion Propagation Flow

```mermaid
flowchart TD
    TRIGGER{Deletion Trigger}

    TRIGGER -->|Source Deleted| A1[Connector Detects Deletion]
    TRIGGER -->|Manual Delete| A2[Admin Request]
    TRIGGER -->|Policy Expiry| A3[Retention Policy]
    TRIGGER -->|Legal Hold Release| A4[Compliance Action]

    A1 & A2 & A3 & A4 --> PROPAGATOR[Deletion Propagator]

    PROPAGATOR --> STEP1[1. Tombstone in Vector DB]
    STEP1 --> STEP2[2. Remove from Keyword Index]
    STEP2 --> STEP3[3. Update Knowledge Graph]
    STEP3 --> STEP4[4. Remove from Change Detector State]
    STEP4 --> STEP5[5. Invalidate Caches]
    STEP5 --> STEP6[6. Hard Delete from Vector DB]
    STEP6 --> STEP7[7. Write Audit Log Entry]

    STEP7 --> VERIFY{Verification Check}

    VERIFY -->|Pass| COMPLETE[✓ Deletion Complete]
    VERIFY -->|Fail| RETRY[Retry with Backoff]
    RETRY --> PROPAGATOR

    COMPLETE --> AUDIT[(Audit Trail)]

    subgraph Guarantees["Deletion Guarantees"]
        G1[Never appears in search after SLA]
        G2[Full audit trail maintained]
        G3[Cascades to all derived data]
        G4[Consistency verified post-deletion]
    end
```

## 6. Source Connector Architecture

```mermaid
flowchart TD
    subgraph ConnectorBase["Base Connector (Abstract)"]
        IFACE[/"list_documents()
        fetch_document()
        get_deleted_ids()
        health_check()"/]
    end

    subgraph Middleware["Connector Middleware"]
        AUTH[OAuth2 / API Key<br/>Token Refresh]
        RATE[Rate Limiter<br/>Backoff Strategy]
        RETRY[Retry Handler<br/>Exponential Backoff]
        CIRCUIT[Circuit Breaker<br/>Failure Threshold]
        CACHE[Response Cache<br/>ETag / If-Modified-Since]
        PAGE[Pagination Handler<br/>Cursor Management]
    end

    subgraph Implementations["Connector Implementations"]
        C_CONF[Confluence<br/>REST API + CQL]
        C_SP[SharePoint<br/>Graph API + Delta]
        C_S3[S3<br/>ListObjects + Events]
        C_DB[Database<br/>CDC + Polling]
        C_GH[GitHub<br/>REST + Webhooks]
        C_SLACK[Slack<br/>Events API]
    end

    subgraph Sync["Sync Strategies"]
        FULL[Full Re-index<br/>Weekly/On-demand]
        INCR[Incremental<br/>Timestamp-based]
        EVENT[Event-driven<br/>Webhooks/CDC]
        DELTA[Delta Queries<br/>Graph API Delta]
    end

    ConnectorBase --> Middleware
    Middleware --> Implementations
    Implementations --> Sync

    subgraph Health["Health & Observability"]
        HC[Health Checks<br/>Every 30s]
        MET[Metrics<br/>Latency, Errors, Throughput]
        LOG[Structured Logging]
    end

    Implementations -.-> Health
```

## 7. Knowledge Quality Feedback Loop

```mermaid
flowchart TD
    USER[User] -->|Query| SYSTEM[AI System]
    SYSTEM -->|Response + Citations| USER

    USER -->|Feedback| COLLECT[Feedback Collector]

    subgraph FeedbackTypes["Feedback Signals"]
        THUMB[👍/👎 Rating]
        CITE[Citation Correct/Wrong]
        MISS[Missing Information]
        STALE[Outdated Answer]
        WRONG[Factually Incorrect]
    end

    COLLECT --> FeedbackTypes

    FeedbackTypes --> ANALYZE[Feedback Analyzer]

    ANALYZE --> DIAG{Diagnose Failure Layer}

    DIAG -->|Retrieval Issue| RET_FIX[Retrieval Improvements]
    DIAG -->|Chunking Issue| CHUNK_FIX[Chunking Improvements]
    DIAG -->|Freshness Issue| FRESH_FIX[Freshness Improvements]
    DIAG -->|Coverage Gap| GAP_FIX[Coverage Improvements]
    DIAG -->|Ranking Issue| RANK_FIX[Ranking Improvements]

    subgraph Improvements["Improvement Actions"]
        RET_FIX --> R1[Tune embedding model]
        RET_FIX --> R2[Add query expansion]
        CHUNK_FIX --> C1[Adjust chunk sizes]
        CHUNK_FIX --> C2[Improve overlap]
        FRESH_FIX --> F1[Reduce sync interval]
        FRESH_FIX --> F2[Add webhook support]
        GAP_FIX --> G1[Add new source connector]
        GAP_FIX --> G2[Identify missing docs]
        RANK_FIX --> K1[Train re-ranker on feedback]
        RANK_FIX --> K2[Adjust score weights]
    end

    Improvements --> DEPLOY[Deploy Improvement]
    DEPLOY --> EVAL[A/B Evaluation]
    EVAL -->|Better| PROMOTE[Promote to Production]
    EVAL -->|Worse| ROLLBACK[Rollback]

    PROMOTE --> METRICS[Quality Metrics Dashboard]
    METRICS -.->|Monitors| SYSTEM
```
