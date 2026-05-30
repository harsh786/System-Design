# Privacy and Data Governance - Architecture Diagrams

## 1. Privacy Architecture Pattern

```mermaid
graph TB
    subgraph "User Layer"
        User[User Request]
        Consent[Consent Management UI]
        DeletionUI[Deletion Request UI]
    end

    subgraph "Privacy Gateway"
        PG[Privacy Gateway]
        PII_D[PII Detector]
        Classifier[Data Classifier]
        Redactor[PII Redactor]
        PurposeChk[Purpose Checker]
        ConsentChk[Consent Validator]
    end

    subgraph "Processing Layer"
        LLM[LLM Service]
        RAG[RAG Pipeline]
        Memory[Memory System]
        Agent[Agent Orchestrator]
    end

    subgraph "Storage Layer"
        ConvDB[(Conversations)]
        VectorDB[(Vector Index)]
        MemDB[(Memory Store)]
        Cache[(Cache)]
    end

    subgraph "Observability Layer"
        Logs[Log Store]
        Traces[Trace Store]
        Metrics[Metrics]
    end

    subgraph "Governance Layer"
        Catalog[Data Catalog]
        Lineage[Lineage Tracker]
        Retention[Retention Enforcer]
        Audit[Audit Log]
    end

    User --> PG
    PG --> PII_D --> Classifier --> Redactor
    PG --> PurposeChk --> ConsentChk
    ConsentChk -->|Allowed| LLM
    ConsentChk -->|Allowed| RAG
    ConsentChk -->|Allowed| Memory

    LLM --> Redactor -->|Redacted| Logs
    LLM --> Redactor -->|Redacted| Traces

    RAG --> VectorDB
    Memory --> MemDB
    Agent --> ConvDB

    Catalog --> Lineage --> Retention
    Retention --> Audit

    Consent --> ConsentChk
    DeletionUI --> Retention
```

## 2. Right-to-Delete Flow (Across All Components)

```mermaid
sequenceDiagram
    participant User
    participant API as Deletion API
    participant Auth as Auth Service
    participant Disc as Discovery Engine
    participant Conv as Conversation Store
    participant Vec as Vector Index
    participant Mem as Memory Store
    participant Cache as Cache Layer
    participant Logs as Log Store
    participant Eval as Eval Datasets
    participant Vendor as Vendor APIs
    participant Verify as Verification
    participant Audit as Audit Trail

    User->>API: DELETE /me/data
    API->>Auth: Verify identity
    Auth-->>API: Authenticated
    
    API->>Disc: Discover all user data
    
    par Data Discovery
        Disc->>Conv: Find user conversations
        Disc->>Vec: Find user embeddings
        Disc->>Mem: Find user memories
        Disc->>Cache: Find cached data
        Disc->>Logs: Find log references
        Disc->>Eval: Find eval data provenance
    end
    
    Disc-->>API: Discovery results (inventory)
    
    Note over API: Create deletion plan<br/>with dependency order
    
    API->>Cache: 1. Invalidate caches
    Cache-->>API: Done
    
    API->>Conv: 2. Delete conversations
    Conv-->>API: Done
    
    API->>Mem: 3. Delete memories
    Mem-->>API: Done
    
    API->>Vec: 4. Delete embeddings + re-index
    Vec-->>API: Done (re-index queued)
    
    API->>Eval: 5. Remove from eval datasets
    Eval-->>API: Done
    
    API->>Logs: 6. Redact from logs
    Logs-->>API: Done
    
    API->>Vendor: 7. Request vendor deletion
    Vendor-->>API: Acknowledged
    
    API->>Verify: Verify all deletions
    
    par Verification
        Verify->>Conv: Query for user data
        Verify->>Vec: Search for user vectors
        Verify->>Mem: Query for user memories
        Verify->>Cache: Check for cached data
    end
    
    Verify-->>API: Verification results
    
    API->>Audit: Record deletion certificate
    API-->>User: Deletion complete + certificate
```

## 3. Data Classification Pipeline

```mermaid
graph LR
    subgraph "Input Sources"
        Prompt[User Prompt]
        Doc[Document Upload]
        API_In[API Request]
        Memory_In[Memory Content]
    end

    subgraph "Classification Engine"
        Regex[Regex Scanner]
        NER[NER Model]
        Context[Context Analyzer]
        Custom[Custom Patterns]
        
        Regex --> Merge[Result Merger]
        NER --> Merge
        Context --> Merge
        Custom --> Merge
    end

    subgraph "Classification Output"
        Merge --> Level{Sensitivity Level}
        Level -->|Public| Public[Level 0: Public]
        Level -->|Internal| Internal[Level 1: Internal]
        Level -->|Confidential| Confidential[Level 2: Confidential]
        Level -->|Restricted| Restricted[Level 3: Restricted]
    end

    subgraph "Actions Based on Level"
        Public --> PassThrough[Pass Through]
        Internal --> LogMinimal[Log Minimal]
        Confidential --> Encrypt[Encrypt + Access Control]
        Restricted --> FullProtect[Full Protection Suite]
    end

    Prompt --> Regex
    Prompt --> NER
    Doc --> Regex
    Doc --> NER
    API_In --> Regex
    API_In --> Context
    Memory_In --> Regex
    Memory_In --> Custom
```

## 4. Consent Management Flow

```mermaid
stateDiagram-v2
    [*] --> NoConsent: User created

    NoConsent --> ConsentRequested: Feature requires consent
    ConsentRequested --> ConsentGranted: User grants
    ConsentRequested --> ConsentDenied: User denies
    
    ConsentGranted --> ConsentWithdrawn: User withdraws
    ConsentGranted --> ConsentExpired: Time-based expiry
    ConsentGranted --> ConsentGranted: User renews
    
    ConsentWithdrawn --> DeletionTriggered: Automatic
    ConsentExpired --> DeletionTriggered: Automatic
    
    DeletionTriggered --> DataDeleted: Deletion complete
    DataDeleted --> NoConsent: Clean state
    
    ConsentDenied --> NoConsent: Feature unavailable

    note right of ConsentGranted
        Data processing allowed
        for stated purpose only
    end note

    note right of DeletionTriggered
        All data collected under
        this consent must be deleted
    end note
```

## 5. Data Lineage Mapping

```mermaid
graph TD
    subgraph "Data Sources"
        UserInput[User Input]
        DocUpload[Document Upload]
        APIData[External API Data]
    end

    subgraph "Primary Processing"
        Conv[Conversation Service]
        Embed[Embedding Service]
        Memory[Memory Service]
    end

    subgraph "Storage Systems"
        ConvDB[(Conversation DB)]
        VecDB[(Vector DB)]
        MemDB[(Memory DB)]
        CacheR[(Redis Cache)]
    end

    subgraph "Secondary Processing"
        Analytics[Analytics Pipeline]
        Eval[Eval Dataset Builder]
        Training[Training Pipeline]
    end

    subgraph "External Systems"
        LLM_Vendor[LLM Vendor API]
        Observability[Observability Platform]
        Backup[Backup Storage]
    end

    UserInput -->|raw| Conv
    UserInput -->|raw| LLM_Vendor
    DocUpload -->|raw| Embed
    
    Conv -->|stored| ConvDB
    Conv -->|cached| CacheR
    Conv -->|logged| Observability
    
    Embed -->|vectors| VecDB
    
    Conv -->|summarized| Memory -->|stored| MemDB
    
    ConvDB -->|anonymized| Analytics
    ConvDB -->|sampled+anonymized| Eval
    ConvDB -->|with consent| Training
    
    ConvDB -->|encrypted| Backup
    VecDB -->|encrypted| Backup
    MemDB -->|encrypted| Backup

    style LLM_Vendor fill:#f96,stroke:#333
    style Observability fill:#ff9,stroke:#333
    style Backup fill:#9cf,stroke:#333
```

## 6. Privacy Impact Assessment Process

```mermaid
flowchart TD
    Start([New Feature/Change Proposed]) --> Triage{Processes<br/>Personal Data?}
    
    Triage -->|No| Exempt[No PIA Required]
    Triage -->|Yes| Assess[Conduct PIA]
    Triage -->|Unsure| Review[Privacy Team Review]
    Review --> Triage
    
    Assess --> Q1{New data<br/>collection?}
    Assess --> Q2{Sensitive data<br/>involved?}
    Assess --> Q3{Data leaves<br/>infrastructure?}
    Assess --> Q4{Persistent<br/>storage?}
    Assess --> Q5{Enters AI<br/>prompts/memory?}
    
    Q1 -->|Yes| R1[Medium Risk]
    Q2 -->|Yes| R2[Critical Risk]
    Q3 -->|Yes| R3[High Risk]
    Q4 -->|Yes| R4[Medium Risk]
    Q5 -->|Yes| R5[High Risk]
    
    R1 --> Score[Calculate Overall Risk]
    R2 --> Score
    R3 --> Score
    R4 --> Score
    R5 --> Score
    
    Score --> Decision{Overall Risk?}
    
    Decision -->|Low| Proceed[Proceed with Standard Controls]
    Decision -->|Medium| Modify[Proceed with Additional Mitigations]
    Decision -->|High| Escalate[Escalate to Privacy Board]
    Decision -->|Critical| Block[Block Until Redesigned]
    
    Escalate --> BoardDecision{Board Decision}
    BoardDecision -->|Approved| Modify
    BoardDecision -->|Rejected| Block
    
    Modify --> Implement[Implement with Mitigations]
    Implement --> Monitor[Ongoing Monitoring]
    
    Block --> Redesign[Redesign Feature]
    Redesign --> Start
```

## 7. PII Detection and Redaction Pipeline

```mermaid
graph LR
    subgraph "Input"
        Raw[Raw Text/Data]
    end

    subgraph "Detection Layer"
        direction TB
        RegexD[Regex Detection<br/>SSN, CC, Email, Phone]
        NERD[NER Detection<br/>Names, Orgs, Locations]
        ContextD[Context Detection<br/>Known user values]
        CustomD[Custom Patterns<br/>Org-specific IDs]
    end

    subgraph "Classification"
        Merge[Merge Results]
        Dedup[Deduplicate]
        Classify[Assign Sensitivity]
    end

    subgraph "Redaction Strategy Selection"
        direction TB
        Strategy{Destination?}
        S1[Logs → Type-preserving<br/>email → EMAIL]
        S2[Vendor API → Full redact<br/>email → REDACTED]
        S3[Internal → Tokenized<br/>email → tok_abc123]
        S4[Analytics → Hash<br/>email → HASH:a1b2c3]
    end

    subgraph "Output"
        Redacted[Redacted Text]
        Meta[Redaction Metadata]
        Audit[Audit Record]
    end

    Raw --> RegexD
    Raw --> NERD
    Raw --> ContextD
    Raw --> CustomD

    RegexD --> Merge
    NERD --> Merge
    ContextD --> Merge
    CustomD --> Merge

    Merge --> Dedup --> Classify --> Strategy
    
    Strategy --> S1
    Strategy --> S2
    Strategy --> S3
    Strategy --> S4

    S1 --> Redacted
    S2 --> Redacted
    S3 --> Redacted
    S4 --> Redacted

    Classify --> Meta
    Classify --> Audit
```

## 8. Retention Policy Enforcement

```mermaid
flowchart TD
    subgraph "Retention Policies"
        P1[Conversations: 365 days]
        P2[Logs: 90 days]
        P3[Traces: 30 days]
        P4[Cache: 24 hours]
        P5[Eval Data: Until refresh]
        P6[Memories: Until user deletes]
    end

    subgraph "Enforcement Engine (Daily Cron)"
        Scanner[Data Age Scanner]
        Checker[Policy Checker]
        Hold[Legal Hold Check]
        Action{Action Required?}
    end

    subgraph "Actions"
        Delete[Delete Data]
        Archive[Archive to Cold Storage]
        Anonymize[Anonymize in Place]
        Alert[Alert Data Owner]
    end

    subgraph "Verification"
        Verify[Verify Execution]
        Report[Generate Report]
        Escalate[Escalate Failures]
    end

    P1 --> Scanner
    P2 --> Scanner
    P3 --> Scanner
    P4 --> Scanner
    P5 --> Scanner
    P6 --> Scanner

    Scanner --> Checker
    Checker --> Hold
    Hold -->|No hold| Action
    Hold -->|Legal hold| Skip[Skip - Document Hold]

    Action -->|Expired| Delete
    Action -->|Archive policy| Archive
    Action -->|Anonymize policy| Anonymize
    Action -->|Near expiry| Alert

    Delete --> Verify
    Archive --> Verify
    Anonymize --> Verify

    Verify -->|Success| Report
    Verify -->|Failure| Escalate
    Escalate --> Alert
```
