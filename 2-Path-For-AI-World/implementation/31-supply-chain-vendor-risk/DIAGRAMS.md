# Supply Chain and Vendor Risk - Diagrams

## 1. AI Supply Chain Overview

```mermaid
graph TB
    subgraph "Your AI Application"
        APP[AI Application Layer]
        ORCH[Orchestration Layer]
        EVAL[Evaluation Layer]
    end

    subgraph "Model Providers"
        OPENAI[OpenAI]
        ANTHROPIC[Anthropic]
        GOOGLE[Google AI]
        LOCAL[Local Models]
    end

    subgraph "Embedding & Retrieval"
        EMB[Embedding APIs]
        VDB[(Vector Database)]
        RERANK[Rerankers]
    end

    subgraph "Tool Ecosystem"
        MCP1[MCP Server A]
        MCP2[MCP Server B]
        A2A[A2A Agents]
        PLUGINS[Plugins]
    end

    subgraph "Data Sources"
        DS1[(Training Data)]
        DS2[(Eval Datasets)]
        DS3[(RAG Corpus)]
    end

    subgraph "Infrastructure"
        CLOUD[Cloud Provider]
        GPU[GPU Providers]
        CDN[CDN / Edge]
    end

    subgraph "Open Source"
        OSS1[LangChain/LlamaIndex]
        OSS2[Transformers]
        OSS3[Vector Client SDKs]
    end

    APP --> ORCH
    ORCH --> OPENAI & ANTHROPIC & GOOGLE & LOCAL
    ORCH --> EMB --> VDB
    ORCH --> RERANK
    ORCH --> MCP1 & MCP2 & A2A & PLUGINS
    EVAL --> DS2
    APP --> DS3
    LOCAL --> DS1
    APP --> CLOUD & GPU
    APP --> OSS1 & OSS2 & OSS3

    style OPENAI fill:#ff6b6b,color:#fff
    style VDB fill:#ffa94d,color:#fff
    style MCP1 fill:#845ef7,color:#fff
    style MCP2 fill:#845ef7,color:#fff
    style DS1 fill:#20c997,color:#fff
```

## 2. AI Bill of Materials Structure

```mermaid
graph LR
    subgraph "AI-BOM"
        BOM[AI Bill of Materials]
    end

    subgraph "Component Registry"
        MODEL[Model Components<br/>- Provider<br/>- Model ID<br/>- Version Pin<br/>- Cost/1K tokens]
        EMBED[Embedding Components<br/>- Provider<br/>- Dimensions<br/>- Distance Metric<br/>- Max Tokens]
        VECTOR[Vector DB Components<br/>- Provider<br/>- Version<br/>- Index Config<br/>- Region]
        PROMPT[Prompt Components<br/>- Version Hash<br/>- Author<br/>- Template<br/>- Variables]
        TOOL[Tool Components<br/>- Schema Hash<br/>- Capabilities<br/>- MCP Version]
        DATA[Data Components<br/>- Source<br/>- License<br/>- Hash<br/>- Lineage]
    end

    subgraph "Metadata Per Component"
        META[Common Metadata<br/>─────────────<br/>• Risk Tier<br/>• Owner Team<br/>• License Info<br/>• Deployment Region<br/>• Artifact Hash<br/>• Signature<br/>• Exit Plan<br/>• Fallback ID<br/>• Last Review Date<br/>• Next Review Due]
    end

    subgraph "Relations"
        DEP[Dependency Graph<br/>- depends_on<br/>- embeds<br/>- calls<br/>- trains_on]
    end

    BOM --> MODEL & EMBED & VECTOR & PROMPT & TOOL & DATA
    MODEL & EMBED & VECTOR & PROMPT & TOOL & DATA --> META
    MODEL & EMBED & VECTOR & PROMPT & TOOL & DATA --> DEP
```

## 3. Vendor Risk Assessment Flow

```mermaid
flowchart TD
    START([New Vendor Identified]) --> INTAKE[Intake Form]
    INTAKE --> SEC[Security Assessment<br/>SOC2, encryption, audit logs]
    INTAKE --> REL[Reliability Assessment<br/>Uptime, DR, multi-region]
    INTAKE --> PRIV[Privacy Assessment<br/>DPA, GDPR, data residency]
    INTAKE --> BIZ[Business Assessment<br/>Viability, lock-in, funding]
    INTAKE --> OPS[Operational Assessment<br/>Docs, support, deprecation]

    SEC & REL & PRIV & BIZ & OPS --> SCORE[Calculate Risk Score]

    SCORE --> HIGH{Score < 55%?}
    HIGH -->|Yes| REJECT[Reject / Require Remediation]
    HIGH -->|No| MED{Score < 70%?}
    MED -->|Yes| COND[Conditional Approval<br/>+ Required Mitigations]
    MED -->|No| APPROVE[Approve]

    APPROVE --> REGISTER[Register in AI-BOM]
    COND --> REGISTER
    REGISTER --> MONITOR[Continuous Monitoring<br/>SLA, Cost, Drift, Outages]

    MONITOR --> DRIFT{Drift Detected?}
    DRIFT -->|Yes| REVIEW[Trigger Re-Assessment]
    REVIEW --> SCORE

    MONITOR --> OUTAGE{Outage?}
    OUTAGE -->|Yes| FAILOVER[Activate Fallback]
    FAILOVER --> POSTMORTEM[Post-Mortem Review]
    POSTMORTEM --> SCORE

    REJECT --> EXIT([Document & Archive])
```

## 4. Provider Fallback Architecture

```mermaid
flowchart TD
    REQ[Incoming Request] --> ROUTER{Request Router}

    ROUTER --> HC[Health Checker]
    HC --> |Check Status| P1_STATUS{Primary Healthy?}

    P1_STATUS -->|Yes| PRIMARY[Primary Provider<br/>OpenAI GPT-4<br/>Priority: 1]
    P1_STATUS -->|No| S1_STATUS{Secondary Healthy?}

    S1_STATUS -->|Yes| SECONDARY[Secondary Provider<br/>Anthropic Claude<br/>Priority: 2]
    S1_STATUS -->|No| T1_STATUS{Tertiary Healthy?}

    T1_STATUS -->|Yes| TERTIARY[Tertiary Provider<br/>Local Llama<br/>Priority: 3]
    T1_STATUS -->|No| EMERGENCY[Emergency Mode<br/>Cached Responses Only]

    PRIMARY --> RESULT[Response]
    SECONDARY --> DEGRADE1[Degraded Mode: Minor<br/>Some features reduced]
    TERTIARY --> DEGRADE2[Degraded Mode: Severe<br/>Basic completion only]
    EMERGENCY --> DEGRADE3[Emergency Mode<br/>Minimal service]

    DEGRADE1 & DEGRADE2 & DEGRADE3 --> RESULT

    subgraph "Health Check Loop"
        PERIODIC[Every 30s] --> CHECK_ALL[Check All Providers]
        CHECK_ALL --> UPDATE[Update Status]
        UPDATE --> RECOVER{Primary Recovered?}
        RECOVER -->|Yes| RESTORE[Restore to Primary]
    end

    subgraph "Capabilities Matrix"
        CAP[Provider Capabilities<br/>─────────────────<br/>OpenAI: Chat, FC, Vision, Stream, JSON<br/>Claude: Chat, FC, Vision, Stream<br/>Llama: Chat, Stream]
    end
```

## 5. Dependency Scanning Pipeline

```mermaid
flowchart LR
    subgraph "Sources"
        CODE[Code Repository]
        CONFIG[Config Files]
        DEPLOY[Deployment Manifests]
        MCP[MCP Server Registry]
    end

    subgraph "Discovery"
        PARSE[Parse Dependencies]
        EXTRACT[Extract Versions]
        IDENTIFY[Identify Types]
    end

    subgraph "Scanning"
        VULN[Vulnerability Check<br/>NVD, OSV, GitHub Advisory]
        LICENSE[License Scan<br/>SPDX Compliance]
        TYPO[Typosquatting Detection<br/>Edit Distance Analysis]
        SIG[Signature Verification<br/>Artifact Integrity]
        FRESH[Freshness Check<br/>Staleness Detection]
        SUPPLY[Supply Chain Analysis<br/>Maintainer Changes]
    end

    subgraph "Policy Engine"
        REGISTRY[Approved Registry<br/>Check]
        RULES[Policy Rules<br/>Evaluation]
        APPROVE{Approved?}
    end

    subgraph "Actions"
        PASS_ACT[✓ Allow]
        WARN_ACT[⚠ Warning + Track]
        BLOCK_ACT[✗ Block Deployment]
        ALERT_ACT[🚨 Security Alert]
    end

    CODE & CONFIG & DEPLOY & MCP --> PARSE
    PARSE --> EXTRACT --> IDENTIFY
    IDENTIFY --> VULN & LICENSE & TYPO & SIG & FRESH & SUPPLY
    VULN & LICENSE & TYPO & SIG & FRESH & SUPPLY --> REGISTRY
    REGISTRY --> RULES --> APPROVE

    APPROVE -->|Clean| PASS_ACT
    APPROVE -->|Low Risk| WARN_ACT
    APPROVE -->|Violation| BLOCK_ACT
    APPROVE -->|Critical| ALERT_ACT
```

## 6. Exit Strategy Decision Tree

```mermaid
flowchart TD
    TRIGGER([Exit Trigger]) --> ASSESS{Why Exiting?}

    ASSESS -->|Outage| URGENT[Urgent Exit<br/>Activate Fallback NOW]
    ASSESS -->|Cost| PLANNED[Planned Migration<br/>Timeline: Weeks]
    ASSESS -->|Risk| PRIORITY[Priority Exit<br/>Timeline: Days]
    ASSESS -->|Strategic| LONG[Long-term Migration<br/>Timeline: Months]

    URGENT --> FALLBACK[Switch to Pre-configured Fallback]
    FALLBACK --> VERIFY_F[Verify Service Continuity]
    VERIFY_F --> PLAN_FULL[Plan Full Migration]

    PLANNED --> EVAL[Evaluate Alternatives]
    EVAL --> POC[Run PoC with Alternative]
    POC --> COMPARE[Compare: Cost, Quality, Latency]
    COMPARE --> DECIDE{Better?}
    DECIDE -->|Yes| MIGRATE
    DECIDE -->|No| RENEGOTIATE[Renegotiate Current Contract]

    PRIORITY --> DATA_EXP[Export All Data]
    DATA_EXP --> PARALLEL[Run Parallel with Alternative]
    PARALLEL --> CUTOVER[Cutover]

    LONG --> ABSTRACT[Build Abstraction Layer]
    ABSTRACT --> GRADUAL[Gradual Traffic Shift]
    GRADUAL --> COMPLETE[Complete Migration]

    MIGRATE[Execute Migration] --> VALIDATE[Validate]
    CUTOVER --> VALIDATE
    COMPLETE --> VALIDATE

    VALIDATE --> SUCCESS{All Tests Pass?}
    SUCCESS -->|Yes| DECOM[Decommission Old Vendor]
    SUCCESS -->|No| ROLLBACK[Rollback + Investigate]

    subgraph "Exit Readiness Checklist"
        CHECK[✓ Data export tested<br/>✓ Alternative identified<br/>✓ Runbook documented<br/>✓ Cost estimated<br/>✓ Capability gaps mapped<br/>✓ Team trained<br/>✓ Drill completed < 6 months]
    end
```

## 7. Vendor Health Monitoring

```mermaid
flowchart TB
    subgraph "Data Collection"
        API_MON[API Monitoring<br/>Latency, Errors, Throughput]
        STATUS[Status Page Polling<br/>Uptime, Incidents]
        COST_MON[Cost Monitoring<br/>Spend, Unit Cost Trends]
        DRIFT_MON[Drift Detection<br/>Output Quality Metrics]
        CONTRACT[Contract Tracking<br/>Expiry, SLA Credits]
    end

    subgraph "Health Engine"
        AGG[Metric Aggregation]
        BASELINE[Baseline Comparison]
        TREND[Trend Analysis]
        ANOMALY[Anomaly Detection]
    end

    subgraph "Health Score"
        SCORE[Composite Health Score<br/>0-100]
        SLA_SCORE[SLA Score]
        RELIABILITY[Reliability Score]
        COST_SCORE[Cost Efficiency]
        DRIFT_SCORE[Stability Score]
    end

    subgraph "Actions"
        GREEN[🟢 Healthy<br/>Score > 80]
        YELLOW[🟡 Watch<br/>Score 60-80]
        ORANGE[🟠 Concern<br/>Score 40-60]
        RED[🔴 Critical<br/>Score < 40]
    end

    subgraph "Response"
        NONE_R[No action needed]
        WATCH_R[Increase monitoring frequency]
        PREPARE_R[Prepare fallback activation]
        ACTIVATE_R[Activate fallback + alert team]
    end

    API_MON & STATUS & COST_MON & DRIFT_MON & CONTRACT --> AGG
    AGG --> BASELINE & TREND & ANOMALY
    BASELINE & TREND & ANOMALY --> SLA_SCORE & RELIABILITY & COST_SCORE & DRIFT_SCORE
    SLA_SCORE & RELIABILITY & COST_SCORE & DRIFT_SCORE --> SCORE

    SCORE --> GREEN & YELLOW & ORANGE & RED
    GREEN --> NONE_R
    YELLOW --> WATCH_R
    ORANGE --> PREPARE_R
    RED --> ACTIVATE_R
```

## 8. Supply Chain Attack Vectors

```mermaid
flowchart TB
    subgraph "Attack Vectors"
        direction TB
        A1[Model Poisoning<br/>Compromised weights<br/>or fine-tuning data]
        A2[MCP Server Compromise<br/>Malicious tool responses<br/>injected into agent loop]
        A3[Typosquatting<br/>langchaln vs langchain<br/>Malicious lookalike packages]
        A4[Dependency Confusion<br/>Internal package name<br/>published to public registry]
        A5[Embedding Manipulation<br/>Poisoned embeddings<br/>alter retrieval results]
        A6[Dataset Poisoning<br/>Malicious data in<br/>training/eval sets]
        A7[API Key Theft<br/>Stolen credentials<br/>for provider APIs]
        A8[Provider Compromise<br/>Provider infrastructure<br/>breach affects all customers]
    end

    subgraph "Defenses"
        D1[Signed Model Artifacts<br/>Verify hash + signature]
        D2[MCP Sandboxing<br/>+ Response Validation]
        D3[Package Registry<br/>Approval + Scanning]
        D4[Scoped Registries<br/>+ Namespace Reservation]
        D5[Embedding Integrity<br/>Monitoring + Validation]
        D6[Data Provenance<br/>+ Integrity Checks]
        D7[Secret Management<br/>+ Rotation + Scoping]
        D8[Multi-Provider<br/>+ Egress Controls]
    end

    A1 --> D1
    A2 --> D2
    A3 --> D3
    A4 --> D4
    A5 --> D5
    A6 --> D6
    A7 --> D7
    A8 --> D8

    subgraph "Detection"
        DET1[Behavior Drift Monitoring]
        DET2[Anomaly Detection on Outputs]
        DET3[Network Egress Monitoring]
        DET4[Audit Log Analysis]
    end

    D1 & D2 & D3 & D4 & D5 & D6 & D7 & D8 --> DET1 & DET2 & DET3 & DET4
```
