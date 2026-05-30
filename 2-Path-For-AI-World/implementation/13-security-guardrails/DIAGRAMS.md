# Security & Guardrails - Architecture Diagrams

## 1. Threat Landscape Overview

```mermaid
mindmap
  root((AI System Threats))
    Input Threats
      Direct Prompt Injection
      Jailbreaks
      Encoding Bypasses
    Data Threats
      Indirect Prompt Injection
      RAG Poisoning
      Vector DB Poisoning
      Unauthorized Retrieval
    Tool Threats
      Tool Injection
      SSRF / Tool Abuse
      Over-Permissioned Tools
    Output Threats
      PII Leakage
      Data Exfiltration
      System Prompt Leakage
    Systemic Threats
      Excessive Agency
      MCP Supply-Chain Risk
      A2A Remote-Agent Risk
```

## 2. Defense in Depth Layers

```mermaid
graph TB
    subgraph "Layer 9: Governance"
        GOV[Policy, Compliance, Audit, Red-Teaming]
    end
    
    subgraph "Layer 8: Platform"
        PLAT[Network Segmentation, Identity, Encryption, Secrets]
    end
    
    subgraph "Layer 7: Runtime"
        RT[Rate Limits, Cost Caps, Anomaly Detection, Circuit Breakers]
    end
    
    subgraph "Layer 6: Output"
        OUT[PII Redaction, Groundedness, Policy Compliance, Toxicity]
    end
    
    subgraph "Layer 5: Action"
        ACT[Human Approval, Side-Effect Detection, Blast Radius Limits]
    end
    
    subgraph "Layer 4: Tool"
        TOOL[Schema Validation, Allowlists, Argument Sanitization]
    end
    
    subgraph "Layer 3: Prompt"
        PROMPT[Context Separation, Source Labeling, Instruction Hierarchy]
    end
    
    subgraph "Layer 2: Retrieval"
        RET[ACL Enforcement, Trust Scoring, Injection Scanning]
    end
    
    subgraph "Layer 1: Input"
        INP[Moderation, Jailbreak Detection, PII Detection, Intent Classification]
    end
    
    USER[User Input] --> INP
    INP --> RET
    RET --> PROMPT
    PROMPT --> LLM[LLM Processing]
    LLM --> TOOL
    TOOL --> ACT
    ACT --> OUT
    OUT --> RESPONSE[Response to User]
    
    RT -.->|monitors| INP
    RT -.->|monitors| LLM
    RT -.->|monitors| TOOL
    PLAT -.->|secures| RET
    PLAT -.->|secures| TOOL
    GOV -.->|governs all| PLAT

    style INP fill:#ff6b6b,color:#fff
    style RET fill:#ffa94d,color:#fff
    style PROMPT fill:#ffd43b,color:#000
    style TOOL fill:#69db7c,color:#000
    style ACT fill:#4dabf7,color:#fff
    style OUT fill:#9775fa,color:#fff
    style RT fill:#f06595,color:#fff
    style PLAT fill:#868e96,color:#fff
    style GOV fill:#495057,color:#fff
```

## 3. Guardrail Pipeline Flow

```mermaid
flowchart TD
    INPUT[User Input] --> CM{Content<br/>Moderation}
    CM -->|toxic| BLOCK1[🚫 BLOCK]
    CM -->|safe| JD{Jailbreak<br/>Detection}
    
    JD -->|injection| BLOCK2[🚫 BLOCK]
    JD -->|safe| PII_IN{PII<br/>Detection}
    
    PII_IN -->|critical PII| FLAG1[⚠️ FLAG + Warn User]
    PII_IN -->|safe| INTENT{Intent<br/>Classification}
    
    INTENT -->|out of scope| BLOCK3[🚫 BLOCK]
    INTENT -->|in scope| RETRIEVE[Retrieve Documents]
    
    RETRIEVE --> ACL{ACL<br/>Check}
    ACL -->|unauthorized| FILTER[Remove Unauthorized Docs]
    ACL -->|authorized| TRUST{Trust<br/>Score}
    FILTER --> TRUST
    
    TRUST -->|low trust| FLAG2[⚠️ FLAG]
    TRUST -->|adequate| INJ_SCAN{Injection<br/>Scan}
    FLAG2 --> INJ_SCAN
    
    INJ_SCAN -->|infected| QUARANTINE[🚫 QUARANTINE Doc]
    INJ_SCAN -->|clean| BUILD[Build Prompt]
    
    BUILD --> CTX[Context Isolation]
    CTX --> HIER[Instruction Hierarchy]
    HIER --> LLM[Send to LLM]
    
    LLM --> TOOL_CHECK{Tool Call?}
    TOOL_CHECK -->|no| OUTPUT_CHECK
    TOOL_CHECK -->|yes| TOOL_ALLOW{Tool<br/>Allowlist}
    
    TOOL_ALLOW -->|blocked| BLOCK4[🚫 BLOCK Tool]
    TOOL_ALLOW -->|allowed| ARG_CHECK{Argument<br/>Sanitization}
    
    ARG_CHECK -->|dangerous| BLOCK5[🚫 BLOCK - SSRF/Injection]
    ARG_CHECK -->|safe| ACTION{Action<br/>Classification}
    
    ACTION -->|critical| HUMAN[👤 Human Approval Required]
    ACTION -->|safe| EXECUTE[Execute Tool]
    HUMAN -->|approved| EXECUTE
    HUMAN -->|rejected| BLOCK6[🚫 BLOCK]
    
    EXECUTE --> OUTPUT_CHECK{Output<br/>Guardrails}
    
    OUTPUT_CHECK --> PII_OUT{PII in<br/>Output?}
    PII_OUT -->|yes| REDACT[Redact PII]
    PII_OUT -->|no| GROUND{Groundedness<br/>Check}
    REDACT --> GROUND
    
    GROUND -->|hallucination| FLAG3[⚠️ FLAG + Disclaimer]
    GROUND -->|grounded| POLICY{Policy<br/>Check}
    FLAG3 --> POLICY
    
    POLICY -->|violation| BLOCK7[🚫 BLOCK]
    POLICY -->|compliant| DELIVER[✅ Deliver Response]

    style BLOCK1 fill:#ff0000,color:#fff
    style BLOCK2 fill:#ff0000,color:#fff
    style BLOCK3 fill:#ff0000,color:#fff
    style BLOCK4 fill:#ff0000,color:#fff
    style BLOCK5 fill:#ff0000,color:#fff
    style BLOCK6 fill:#ff0000,color:#fff
    style BLOCK7 fill:#ff0000,color:#fff
    style DELIVER fill:#00cc00,color:#fff
    style HUMAN fill:#0066ff,color:#fff
```

## 4. Prompt Injection Attack Vectors

```mermaid
flowchart LR
    subgraph "Attack Surfaces"
        A1[User Input<br/>Direct Injection]
        A2[Retrieved Docs<br/>Indirect Injection]
        A3[Tool Responses<br/>Tool Injection]
        A4[MCP Servers<br/>Supply Chain]
        A5[Remote Agents<br/>A2A Injection]
        A6[Email/Web<br/>Content Injection]
    end
    
    subgraph "Injection Techniques"
        T1[Instruction Override]
        T2[Role Hijacking]
        T3[Format Exploitation]
        T4[Encoding Bypass]
        T5[Multi-Turn Escalation]
        T6[Hidden Text/HTML]
        T7[Payload Splitting]
    end
    
    subgraph "Targets"
        X1[Override System Instructions]
        X2[Exfiltrate Data]
        X3[Execute Unauthorized Tools]
        X4[Leak System Prompt]
        X5[Bypass Safety Filters]
    end
    
    A1 --> T1 & T2 & T3 & T4 & T5
    A2 --> T1 & T6 & T7
    A3 --> T1 & T6
    A4 --> T1 & T7
    A5 --> T1 & T2
    A6 --> T6 & T7
    
    T1 --> X1 & X5
    T2 --> X1 & X5
    T3 --> X1 & X4
    T4 --> X5
    T5 --> X1 & X2
    T6 --> X2 & X3
    T7 --> X1 & X3
```

## 5. PII Protection Architecture

```mermaid
flowchart TD
    subgraph "Data Sources"
        US[User Input]
        RD[Retrieved Documents]
        TO[Tool Outputs]
        LM[LLM Response]
    end
    
    subgraph "Detection Engine"
        RE[Regex Patterns<br/>SSN, CC, Email, Phone]
        NER[NER Model<br/>Names, Addresses, Orgs]
        CTX[Context Analysis<br/>Reduce False Positives]
        CLS[PII Classifier<br/>Type + Severity]
    end
    
    subgraph "Decision Layer"
        POL{Retention<br/>Policy}
        SEV{Severity<br/>Assessment}
        ROL{User Role<br/>Check}
    end
    
    subgraph "Action Layer"
        MASK[Mask: J***n]
        HASH[Hash: #a3f2c1]
        GEN[Generalize: PERSON_NAME]
        REM[Remove Entirely]
        TOK[Tokenize: TOKEN:abc123]
    end
    
    subgraph "Enforcement Points"
        E1[Input Processing]
        E2[Prompt Construction]
        E3[Output Delivery]
        E4[Logging/Tracing]
        E5[Evaluation Datasets]
        E6[Analytics Pipeline]
    end
    
    US & RD & TO & LM --> RE & NER
    RE & NER --> CTX --> CLS
    CLS --> POL & SEV & ROL
    
    POL -->|never store| REM
    SEV -->|critical| MASK
    SEV -->|high| HASH
    SEV -->|medium| GEN
    ROL -->|authorized| ALLOW[Pass Through]
    ROL -->|unauthorized| MASK
    
    MASK & HASH & GEN & REM & TOK --> E1 & E2 & E3 & E4 & E5 & E6

    style REM fill:#ff0000,color:#fff
    style MASK fill:#ff6600,color:#fff
    style HASH fill:#ffaa00,color:#000
```

## 6. Red Team Workflow

```mermaid
flowchart TD
    subgraph "Phase 1: Preparation"
        P1[Define Scope & Objectives]
        P2[Map Attack Surface]
        P3[Select Attack Categories]
        P4[Generate Test Cases]
        P5[Set Success Criteria]
    end
    
    subgraph "Phase 2: Execution"
        E1[Run Automated Attacks]
        E2[Record All Responses]
        E3[Track Guardrail Triggers]
        E4[Generate Attack Variants]
        E5[Test Multi-Turn Scenarios]
    end
    
    subgraph "Phase 3: Analysis"
        A1[Classify Results<br/>Success/Partial/Blocked/Failed]
        A2[Identify Patterns]
        A3[Score by Category]
        A4[Calculate Defense Rate]
    end
    
    subgraph "Phase 4: Reporting"
        R1[Generate Vulnerability Reports]
        R2[Prioritize by Severity]
        R3[Recommend Mitigations]
        R4[Create Regression Tests]
    end
    
    subgraph "Phase 5: Remediation"
        M1[Implement Fixes]
        M2[Add to Regression Suite]
        M3[Re-run Failed Tests]
        M4[Verify No Regressions]
    end
    
    P1 --> P2 --> P3 --> P4 --> P5
    P5 --> E1 --> E2 --> E3
    E3 --> E4 --> E5
    E5 --> A1 --> A2 --> A3 --> A4
    A4 --> R1 --> R2 --> R3 --> R4
    R4 --> M1 --> M2 --> M3 --> M4
    M4 -->|schedule next| P1

    style P1 fill:#4dabf7,color:#fff
    style E1 fill:#ff6b6b,color:#fff
    style A1 fill:#ffd43b,color:#000
    style R1 fill:#9775fa,color:#fff
    style M1 fill:#69db7c,color:#000
```

## 7. Security Architecture for AI Systems

```mermaid
graph TB
    subgraph "External Boundary"
        WAF[WAF / API Gateway]
        AUTH[Authentication<br/>OAuth 2.0 / mTLS]
        RL[Rate Limiter]
    end
    
    subgraph "Application Layer"
        subgraph "Input Processing"
            IG[Input Guardrails]
            IC[Intent Classifier]
        end
        
        subgraph "RAG Pipeline"
            VDB[(Vector DB)]
            ACL[ACL Filter]
            TS[Trust Scorer]
            IS[Injection Scanner]
        end
        
        subgraph "LLM Execution"
            PC[Prompt Constructor<br/>Context Isolation]
            LLM[LLM API]
            TC[Tool Controller]
        end
        
        subgraph "Output Processing"
            OG[Output Guardrails]
            PR[PII Redactor]
            GC[Groundedness Check]
        end
    end
    
    subgraph "Tool Execution Layer"
        SANDBOX[Sandboxed Execution]
        ALLOW[Tool Allowlist]
        HUMAN[Human Approval]
    end
    
    subgraph "Platform Security"
        VAULT[Secret Vault]
        EGRESS[Egress Controls]
        NET[Network Isolation]
        ENC[Encryption at Rest]
    end
    
    subgraph "Observability"
        AUDIT[Audit Log<br/>Immutable]
        MON[Monitoring<br/>Anomaly Detection]
        ALERT[Alerting]
    end
    
    USER[User] --> WAF --> AUTH --> RL
    RL --> IG --> IC
    IC --> VDB
    VDB --> ACL --> TS --> IS
    IS --> PC
    PC --> LLM
    LLM --> TC
    TC --> ALLOW --> SANDBOX
    SANDBOX --> HUMAN
    LLM --> OG --> PR --> GC --> RESPONSE[Response]
    
    VAULT -.-> LLM
    VAULT -.-> TC
    EGRESS -.-> SANDBOX
    NET -.-> VDB
    
    IG & IC & LLM & TC & OG --> AUDIT
    AUDIT --> MON --> ALERT

    style WAF fill:#868e96,color:#fff
    style SANDBOX fill:#ff6b6b,color:#fff
    style VAULT fill:#ffd43b,color:#000
    style AUDIT fill:#9775fa,color:#fff
```

## 8. Incident Response Flow for AI Security Events

```mermaid
stateDiagram-v2
    [*] --> Detection
    
    Detection --> Triage: Alert triggered
    
    state Detection {
        [*] --> GuardrailAlert
        [*] --> AnomalyDetected
        [*] --> CanaryTriggered
        [*] --> UserReport
        [*] --> RedTeamFinding
    }
    
    state Triage {
        [*] --> ClassifySeverity
        ClassifySeverity --> Critical: Data breach / Active exploit
        ClassifySeverity --> High: Successful injection
        ClassifySeverity --> Medium: Partial bypass
        ClassifySeverity --> Low: Failed attempt
    }
    
    Triage --> Containment: Critical/High
    Triage --> Investigation: Medium/Low
    
    state Containment {
        [*] --> BlockUser
        BlockUser --> DisableTool
        DisableTool --> IsolateSystem
        IsolateSystem --> PreserveEvidence
    }
    
    state Investigation {
        [*] --> ReviewLogs
        ReviewLogs --> AnalyzeAttackVector
        AnalyzeAttackVector --> AssessImpact
        AssessImpact --> IdentifyRootCause
    }
    
    Containment --> Investigation
    Investigation --> Remediation
    
    state Remediation {
        [*] --> PatchVulnerability
        PatchVulnerability --> UpdateGuardrails
        UpdateGuardrails --> AddRegressionTest
        AddRegressionTest --> ValidateFix
    }
    
    Remediation --> Recovery
    
    state Recovery {
        [*] --> RestoreService
        RestoreService --> MonitorClosely
        MonitorClosely --> ConfirmResolution
    }
    
    Recovery --> PostIncident
    
    state PostIncident {
        [*] --> WritePostmortem
        WritePostmortem --> UpdatePlaybooks
        UpdatePlaybooks --> ShareLearnings
        ShareLearnings --> ScheduleRedTeam
    }
    
    PostIncident --> [*]
```

## 9. Trust Boundary Model

```mermaid
flowchart TD
    subgraph "TRUSTED (Developer-Controlled)"
        SYS[System Prompt]
        CODE[Application Code]
        SCHEMA[Tool Schemas]
        POLICY[Security Policies]
    end
    
    subgraph "SEMI-TRUSTED (Verified Sources)"
        INTERNAL_DOCS[Internal Documents<br/>ACL-Controlled]
        VERIFIED_TOOLS[Verified MCP Servers<br/>Pinned Versions]
        AUTHED_USERS[Authenticated Users<br/>Role-Based]
    end
    
    subgraph "UNTRUSTED (External)"
        USER_INPUT[User Input]
        WEB[Web Content]
        EMAIL[Email Content]
        UPLOADED[User-Uploaded Docs]
        THIRD_PARTY[3rd Party Tools]
        REMOTE_AGENTS[Remote A2A Agents]
    end
    
    SYS -->|immutable context| LLM[LLM]
    CODE -->|controls flow| LLM
    SCHEMA -->|constrains tools| LLM
    
    INTERNAL_DOCS -->|ACL filtered| LLM
    VERIFIED_TOOLS -->|sandboxed| LLM
    AUTHED_USERS -->|rate limited| LLM
    
    USER_INPUT -->|validated + classified| LLM
    WEB -->|injection scanned| LLM
    EMAIL -->|injection scanned| LLM
    UPLOADED -->|quarantined + scanned| LLM
    THIRD_PARTY -->|sandboxed + monitored| LLM
    REMOTE_AGENTS -->|validated + isolated| LLM

    style SYS fill:#00cc00,color:#fff
    style CODE fill:#00cc00,color:#fff
    style SCHEMA fill:#00cc00,color:#fff
    style POLICY fill:#00cc00,color:#fff
    style INTERNAL_DOCS fill:#ffaa00,color:#000
    style VERIFIED_TOOLS fill:#ffaa00,color:#000
    style AUTHED_USERS fill:#ffaa00,color:#000
    style USER_INPUT fill:#ff0000,color:#fff
    style WEB fill:#ff0000,color:#fff
    style EMAIL fill:#ff0000,color:#fff
    style UPLOADED fill:#ff0000,color:#fff
    style THIRD_PARTY fill:#ff0000,color:#fff
    style REMOTE_AGENTS fill:#ff0000,color:#fff
```
