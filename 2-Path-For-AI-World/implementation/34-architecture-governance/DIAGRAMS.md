# Architecture Governance Diagrams

## 1. Architecture Review Board Workflow

```mermaid
flowchart TD
    A[Use-Case Owner Submits Intake] --> B{Chair Triages<br/>within 24h}
    B -->|Tier 0: Prohibited| C[REJECTED<br/>Documented & Closed]
    B -->|Tier 3: Low Risk| D[Automated Compliance Check]
    B -->|Tier 2: Medium| E[Assign 2-3 Reviewers]
    B -->|Tier 1: Critical| F[Assign Full Board]

    D -->|Pass| G[AUTO-APPROVED]
    D -->|Fail| H[Flag Issues → Fix → Recheck]
    H --> D

    E --> I[Async Review<br/>3-5 business days]
    F --> J[Async Review + Sync Discussion]

    I --> K{Decision}
    J --> K

    K -->|Approve| L[Record ADR<br/>Proceed to Implementation]
    K -->|Approve with Conditions| M[Record Conditions<br/>Track to Completion]
    K -->|Reject| N[Document Reasons<br/>Provide Guidance]

    M --> O{Conditions Met?}
    O -->|Yes| L
    O -->|No| P[Escalate / Rework]

    L --> Q[Implementation Phase]
    Q --> R[Production Readiness Gate]
```

## 2. Risk Tiering Decision Tree

```mermaid
flowchart TD
    START[New AI Use Case] --> PROHIB{Prohibited<br/>Use Case?}
    PROHIB -->|Yes: weapons, social scoring,<br/>mass surveillance| T0[TIER 0<br/>PROHIBITED]
    PROHIB -->|No| SAFETY{Can cause<br/>safety harm?}

    SAFETY -->|Yes| T1[TIER 1<br/>CRITICAL]
    SAFETY -->|No| A2A{Autonomous +<br/>Agent-to-Agent?}

    A2A -->|Yes| T1
    A2A -->|No| SCORE[Calculate Weighted<br/>Risk Score]

    SCORE --> DIM1[Autonomy × 0.25]
    SCORE --> DIM2[Data Sensitivity × 0.20]
    SCORE --> DIM3[Harm Potential × 0.25]
    SCORE --> DIM4[Audience × 0.15]
    SCORE --> DIM5[Reversibility × 0.15]

    DIM1 & DIM2 & DIM3 & DIM4 & DIM5 --> TOTAL[Total Weighted Score]

    TOTAL -->|Score 1.0 - 1.8| T3[TIER 3: LOW]
    TOTAL -->|Score 1.8 - 3.4| T2[TIER 2: MEDIUM]
    TOTAL -->|Score 3.4 - 5.0| T1

    T3 --> REG{Regulatory<br/>domains?}
    REG -->|Yes| T2
    REG -->|No| T3_FINAL[TIER 3 CONFIRMED]

    style T0 fill:#ff4444,color:#fff
    style T1 fill:#ff8800,color:#fff
    style T2 fill:#ffcc00,color:#000
    style T3_FINAL fill:#44bb44,color:#fff
```

## 3. Review Gates Pipeline

```mermaid
flowchart LR
    G1[Gate 1<br/>USE CASE] --> G2[Gate 2<br/>DATA]
    G2 --> G3[Gate 3<br/>ARCHITECTURE]
    G3 --> G4[Gate 4<br/>EVALUATION]
    G4 --> G5[Gate 5<br/>SECURITY]
    G5 --> G6[Gate 6<br/>PRIVACY]
    G6 --> G7[Gate 7<br/>PRODUCTION]
    G7 --> PROD[Production<br/>Deployment]

    G1 -.->|Business justification<br/>Risk tier assigned<br/>Sponsor identified| G1
    G2 -.->|Sources approved<br/>Privacy classified<br/>Quality assessed| G2
    G3 -.->|Design reviewed<br/>Model justified<br/>ADR recorded| G3
    G4 -.->|Suite comprehensive<br/>Baselines set<br/>Regression defined| G4
    G5 -.->|Threat model<br/>Pen test<br/>Incident plan| G5
    G6 -.->|DPIA complete<br/>Minimization verified<br/>Consent confirmed| G6
    G7 -.->|All gates passed<br/>SLOs defined<br/>Runbooks ready| G7

    style G1 fill:#4a90d9,color:#fff
    style G2 fill:#7b68ee,color:#fff
    style G3 fill:#4a90d9,color:#fff
    style G4 fill:#20b2aa,color:#fff
    style G5 fill:#ff6347,color:#fff
    style G6 fill:#daa520,color:#fff
    style G7 fill:#228b22,color:#fff
    style PROD fill:#333,color:#fff
```

## 4. ADR Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Draft: Author creates
    Draft --> Proposed: Submit for review
    Proposed --> InReview: Reviewers assigned
    InReview --> Proposed: Request changes
    InReview --> Accepted: All approvals received
    InReview --> Rejected: Fundamental issues
    Accepted --> Deprecated: Context changed
    Accepted --> Superseded: New decision replaces
    Rejected --> [*]: Closed

    Accepted --> Accepted: Periodic review\n(confirm still valid)
    Deprecated --> [*]: Archived
    Superseded --> [*]: Links to successor

    note right of Accepted
        Active decision.
        Review every 6 months.
        Owner maintains.
    end note

    note right of Superseded
        Links to new ADR.
        Preserved for history.
    end note
```

## 5. Production Readiness Flow

```mermaid
flowchart TD
    START[System Ready<br/>for Assessment] --> CREATE[Create Readiness<br/>Assessment]
    CREATE --> AUTO[Run Automated<br/>Checks]
    AUTO --> MANUAL[Complete Manual<br/>Checks]
    MANUAL --> SCORE{Score<br/>Assessment}

    SCORE -->|< 60%| RED[NOT READY<br/>Major Gaps]
    SCORE -->|60-85%| YELLOW[PARTIALLY READY<br/>Gaps Exist]
    SCORE -->|85-95%| GREEN[READY<br/>Minor Items]
    SCORE -->|> 95%| BLUE[FULLY READY]

    RED --> GAPS[Identify Gaps]
    YELLOW --> GAPS
    GAPS --> REMED[Create Remediation<br/>Items]
    REMED --> ASSIGN[Assign Owners<br/>& Due Dates]
    ASSIGN --> TRACK[Track to<br/>Completion]
    TRACK --> AUTO

    GREEN --> APPROVE{Approval<br/>Workflow}
    BLUE --> APPROVE

    APPROVE -->|Tier 1-2| MULTI[Multiple Approvers<br/>Required]
    APPROVE -->|Tier 3| SINGLE[Single Approver]

    MULTI --> DECISION{All<br/>Approved?}
    SINGLE --> DECISION

    DECISION -->|Yes| LAUNCH[APPROVED<br/>FOR LAUNCH]
    DECISION -->|Conditional| COND[Track Conditions]
    DECISION -->|No| GAPS

    LAUNCH --> POST7[7-Day Review]
    POST7 --> POST30[30-Day Review]
    POST30 --> POST90[90-Day Review]
    POST90 --> STEADY[Steady State<br/>Operations]

    style RED fill:#ff4444,color:#fff
    style YELLOW fill:#ffcc00,color:#000
    style GREEN fill:#44bb44,color:#fff
    style BLUE fill:#4488ff,color:#fff
    style LAUNCH fill:#228b22,color:#fff
```

## 6. Platform Maturity Assessment

```mermaid
flowchart TD
    subgraph L0[L0: Ad Hoc]
        L0A[Individual experimentation]
        L0B[No shared infrastructure]
        L0C[No governance]
    end

    subgraph L1[L1: App-Specific]
        L1A[Purpose-built AI features]
        L1B[Some shared libraries]
        L1C[Basic monitoring]
    end

    subgraph L2[L2: Reusable Basics]
        L2A[Shared AI platform]
        L2B[Basic standards documented]
        L2C[Centralized model registry]
    end

    subgraph L3[L3: Governed Enterprise]
        L3A[Review board operational]
        L3B[All 7 gates enforced]
        L3C[ADR process active]
        L3D[Secure path = easy path]
    end

    subgraph L4[L4: Optimized]
        L4A[Metrics-driven improvement]
        L4B[Automated cost optimization]
        L4C[Golden paths for patterns]
    end

    subgraph L5[L5: Adaptive]
        L5A[Self-adjusting platform]
        L5B[Governance invisible]
        L5C[Competitive advantage]
    end

    L0 -->|Recognize need<br/>for sharing| L1
    L1 -->|Invest in<br/>platform| L2
    L2 -->|Implement<br/>governance| L3
    L3 -->|Optimize via<br/>metrics| L4
    L4 -->|ML-driven<br/>adaptation| L5

    style L0 fill:#ff6666,color:#000
    style L1 fill:#ff9944,color:#000
    style L2 fill:#ffcc44,color:#000
    style L3 fill:#88cc44,color:#000
    style L4 fill:#44aacc,color:#000
    style L5 fill:#8844cc,color:#fff
```

## 7. Standards Compliance Flow

```mermaid
flowchart TD
    SYS[AI System] --> ASSESS[Compliance Assessment<br/>Triggered]
    ASSESS --> TIER[Determine Risk Tier]
    TIER --> APPLICABLE[Get Applicable<br/>Standards]
    APPLICABLE --> CHECK[Run Automated<br/>Checks]

    CHECK --> PASS{All Pass?}
    PASS -->|Yes| COMPLIANT[COMPLIANT<br/>Badge Issued]
    PASS -->|No| FAILURES[Identify Failures]

    FAILURES --> REQUIRED{Required<br/>Standard?}
    REQUIRED -->|Yes| BLOCK[DEPLOYMENT<br/>BLOCKED]
    REQUIRED -->|No: Recommended| WARN[WARNING<br/>Flagged for Review]

    BLOCK --> FIX{Can Fix?}
    FIX -->|Yes| REMEDIATE[Remediate &<br/>Re-check]
    FIX -->|No: Valid Reason| EXCEPTION[Request<br/>Exception]

    REMEDIATE --> CHECK
    EXCEPTION --> EXC_REVIEW{Exception<br/>Review}
    EXC_REVIEW -->|Approved| EXC_GRANT[Exception Granted<br/>Time-Limited]
    EXC_REVIEW -->|Rejected| BLOCK2[Must Comply]
    BLOCK2 --> REMEDIATE

    EXC_GRANT --> COMPLIANT
    WARN --> COMPLIANT

    EXC_GRANT --> EXPIRY[Exception Expiry<br/>Check Monthly]
    EXPIRY -->|Expired| REASSESS[Re-assess<br/>Compliance]
    REASSESS --> CHECK

    style COMPLIANT fill:#228b22,color:#fff
    style BLOCK fill:#ff4444,color:#fff
    style WARN fill:#ffcc00,color:#000
```

## 8. Governance Operating Model

```mermaid
flowchart TD
    subgraph STRATEGIC[Strategic Layer - Quarterly]
        S1[Platform Maturity<br/>Assessment]
        S2[Standards Roadmap]
        S3[Risk Appetite<br/>Review]
        S4[Tooling Investment<br/>Decisions]
    end

    subgraph TACTICAL[Tactical Layer - Weekly/Monthly]
        T1[Review Board<br/>Sessions]
        T2[Standards<br/>Updates]
        T3[Exception<br/>Reviews]
        T4[Incident<br/>Reviews]
        T5[Adoption<br/>Metrics]
    end

    subgraph OPERATIONAL[Operational Layer - Continuous]
        O1[Automated<br/>Compliance Checks]
        O2[CI/CD Gate<br/>Enforcement]
        O3[Self-Service<br/>Tier 3 Approvals]
        O4[ADR Creation<br/>& Review]
        O5[Production<br/>Readiness]
    end

    subgraph ENABLEMENT[Enablement Layer - Always On]
        E1[Golden Paths<br/>& Templates]
        E2[Documentation<br/>& Training]
        E3[Platform SDKs<br/>& Tooling]
        E4[Office Hours<br/>& Support]
    end

    STRATEGIC --> TACTICAL
    TACTICAL --> OPERATIONAL
    ENABLEMENT --> OPERATIONAL

    T4 -->|Learnings| T2
    T5 -->|Gaps| S2
    O1 -->|Results| T5
    T1 -->|Decisions| O4

    style STRATEGIC fill:#4a90d9,color:#fff
    style TACTICAL fill:#7b68ee,color:#fff
    style OPERATIONAL fill:#20b2aa,color:#fff
    style ENABLEMENT fill:#228b22,color:#fff
```

---

## Diagram Summary

| Diagram | Purpose | Key Insight |
|---------|---------|-------------|
| Review Board Workflow | Shows the full intake-to-decision process | Different paths per tier reduce overhead for low-risk |
| Risk Tiering | Decision tree for classifying risk | Automatic escalation rules override scoring |
| Review Gates | The 7 sequential gates to production | Each gate has specific criteria per tier |
| ADR Lifecycle | States and transitions for decisions | Periodic review prevents stale decisions |
| Production Readiness | Assessment to launch flow | Gaps drive remediation before approval |
| Platform Maturity | L0-L5 progression | L3 is the key milestone (governance = enablement) |
| Standards Compliance | How standards are enforced | Exception process provides escape valve |
| Operating Model | Layered governance structure | Enablement makes operational governance work |
