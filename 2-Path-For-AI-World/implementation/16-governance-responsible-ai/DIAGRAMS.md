# Governance and Responsible AI - Diagrams

## 1. NIST AI Risk Management Framework Overview

```mermaid
graph TB
    subgraph GOVERN["GOVERN (Crosscutting)"]
        G1[Policies & Procedures]
        G2[Accountability Structures]
        G3[Organizational Culture]
        G4[Stakeholder Engagement]
    end

    subgraph MAP["MAP"]
        M1[Context & Use Case]
        M2[Risk Identification]
        M3[Interdependencies]
        M4[Assumptions & Limitations]
    end

    subgraph MEASURE["MEASURE"]
        ME1[Metrics & Benchmarks]
        ME2[Testing & Evaluation]
        ME3[Continuous Monitoring]
        ME4[Feedback Integration]
    end

    subgraph MANAGE["MANAGE"]
        MA1[Risk Prioritization]
        MA2[Risk Response]
        MA3[Implementation]
        MA4[Effectiveness Monitoring]
    end

    GOVERN --> MAP
    GOVERN --> MEASURE
    GOVERN --> MANAGE
    MAP --> MEASURE
    MEASURE --> MANAGE
    MANAGE -->|Feedback| MAP

    style GOVERN fill:#4a90d9,color:#fff
    style MAP fill:#7b68ee,color:#fff
    style MEASURE fill:#f4a460,color:#fff
    style MANAGE fill:#2e8b57,color:#fff
```

## 2. Risk Assessment Matrix

```mermaid
graph TD
    subgraph Matrix["Risk Assessment Matrix (Likelihood x Impact)"]
        direction TB

        subgraph Critical["CRITICAL (16-25) - Stop/Escalate"]
            C1["5x4=20"]
            C2["5x5=25"]
            C3["4x5=20"]
            C4["4x4=16"]
        end

        subgraph High["HIGH (10-15) - Mitigate Immediately"]
            H1["5x3=15"]
            H2["5x2=10"]
            H3["3x5=15"]
            H4["4x3=12"]
            H5["3x4=12"]
            H6["2x5=10"]
        end

        subgraph Medium["MEDIUM (5-9) - Mitigate Within Quarter"]
            M1["3x3=9"]
            M2["5x1=5"]
            M3["1x5=5"]
            M4["4x2=8"]
            M5["2x4=8"]
            M6["2x3=6"]
            M7["3x2=6"]
        end

        subgraph Low["LOW (1-4) - Accept/Monitor"]
            L1["1x1=1"]
            L2["2x2=4"]
            L3["1x4=4"]
            L4["4x1=4"]
            L5["1x3=3"]
            L6["3x1=3"]
            L7["1x2=2"]
            L8["2x1=2"]
        end
    end

    style Critical fill:#dc3545,color:#fff
    style High fill:#fd7e14,color:#fff
    style Medium fill:#ffc107,color:#000
    style Low fill:#28a745,color:#fff
```

## 3. Governance Operating Model

```mermaid
graph TB
    subgraph Board["Board / Executive Level"]
        B1[AI Strategy & Risk Appetite]
        B2[Annual AI Governance Review]
    end

    subgraph SecondLine["Second Line: AI Governance Function"]
        S1[AI Ethics Board]
        S2[AI Risk Manager]
        S3[Policy & Standards]
        S4[Model Validation]
    end

    subgraph FirstLine["First Line: AI Development Teams"]
        F1[ML Engineers]
        F2[Data Scientists]
        F3[Product Managers]
        F4[Self-Assessment]
    end

    subgraph ThirdLine["Third Line: Internal Audit"]
        T1[Independent Assurance]
        T2[Governance Effectiveness]
    end

    Board -->|Sets direction| SecondLine
    SecondLine -->|Standards & Review| FirstLine
    FirstLine -->|Risk reports| SecondLine
    SecondLine -->|Assurance reports| Board
    ThirdLine -->|Audit findings| Board
    ThirdLine -.->|Audits| FirstLine
    ThirdLine -.->|Audits| SecondLine

    subgraph Cadence["Governance Cadence"]
        Weekly[Weekly: Monitoring Review]
        Monthly[Monthly: Risk Register Update]
        Quarterly[Quarterly: Ethics Board Meeting]
        Annual[Annual: Full Audit]
    end

    style Board fill:#1a237e,color:#fff
    style SecondLine fill:#4a148c,color:#fff
    style FirstLine fill:#006064,color:#fff
    style ThirdLine fill:#b71c1c,color:#fff
```

## 4. Incident Response Flow

```mermaid
stateDiagram-v2
    [*] --> Detected: Trigger fires / Report received

    Detected --> Triaged: Assign responder, confirm severity
    Triaged --> Investigating: Begin root cause analysis

    Investigating --> Contained: Apply containment actions
    Contained --> Remediating: Deploy fix

    Remediating --> Resolved: Fix verified, service restored
    Resolved --> PostReview: Conduct blameless retrospective

    PostReview --> Closed: Action items assigned

    Triaged --> Escalated: SLA breach or severity upgrade
    Escalated --> Investigating

    note right of Detected
        Sources:
        - Automated monitoring
        - User reports
        - Red team findings
        - External reports
    end note

    note right of Contained
        Actions:
        - Disable system
        - Activate fallback
        - Block attack vector
        - Rate limit
    end note

    note right of PostReview
        Outputs:
        - Root cause
        - Lessons learned
        - Systemic improvements
        - Action items
    end note
```

## 5. Compliance Workflow

```mermaid
flowchart TD
    Start([New AI System Proposed]) --> Classify[EU AI Act Classification]

    Classify --> Unacceptable{Unacceptable Risk?}
    Unacceptable -->|Yes| Banned[PROHIBITED - Cannot Deploy]
    Unacceptable -->|No| HighRisk{High Risk?}

    HighRisk -->|Yes| FullCompliance[Full Compliance Regime]
    HighRisk -->|No| Limited{Limited Risk?}
    Limited -->|Yes| Transparency[Transparency Obligations]
    Limited -->|No| Minimal[Minimal Risk - Voluntary Codes]

    FullCompliance --> Requirements[Apply Art. 9-15 Requirements]
    Requirements --> Evidence[Collect Compliance Evidence]
    Evidence --> Assessment[Compliance Assessment]
    Assessment --> Gaps{Gaps Found?}
    Gaps -->|Yes| Remediate[Remediation Plan]
    Remediate --> Evidence
    Gaps -->|No| Certify[CE Marking / Registration]
    Certify --> Deploy[Deploy with Monitoring]
    Deploy --> Ongoing[Ongoing Compliance Monitoring]
    Ongoing -->|Change detected| Assessment

    Transparency --> Disclose[Implement Disclosure Requirements]
    Disclose --> Deploy2[Deploy with Monitoring]

    style Banned fill:#dc3545,color:#fff
    style FullCompliance fill:#fd7e14,color:#fff
    style Transparency fill:#ffc107,color:#000
    style Minimal fill:#28a745,color:#fff
```

## 6. Model Card Lifecycle

```mermaid
flowchart LR
    subgraph Creation["Creation Phase"]
        Train[Model Trained] --> Evaluate[Evaluation Pipeline]
        Evaluate --> Generate[Auto-Generate Card]
        Generate --> Enrich[Human Enrichment]
    end

    subgraph Review["Review Phase"]
        Enrich --> Submit[Submit for Review]
        Submit --> ModelOwner[Model Owner Review]
        Submit --> DataSteward[Data Steward Review]
        Submit --> Governance[Governance Review]
        ModelOwner --> Decision{All Approved?}
        DataSteward --> Decision
        Governance --> Decision
        Decision -->|No| Revise[Revise & Resubmit]
        Revise --> Submit
    end

    subgraph Publication["Publication Phase"]
        Decision -->|Yes| Publish[Publish Card]
        Publish --> Registry[Model Registry]
        Publish --> Internal[Internal Documentation]
    end

    subgraph Maintenance["Maintenance Phase"]
        Registry --> Monitor[Monitor for Changes]
        Monitor -->|Model updated| NewVersion[New Version]
        Monitor -->|Issue found| Update[Update Card]
        Monitor -->|Retired| Deprecate[Deprecate Card]
        NewVersion --> Generate
        Update --> Submit
    end
```

## 7. AI Risk Classification Decision Tree

```mermaid
flowchart TD
    Start([AI System Assessment]) --> Q1{Does system make or<br/>influence decisions about people?}

    Q1 -->|No| LowRisk[Low Risk<br/>Standard monitoring]
    Q1 -->|Yes| Q2{Are decisions<br/>safety-critical?}

    Q2 -->|Yes| Critical[Critical Risk<br/>Maximum controls + HITL]
    Q2 -->|No| Q3{Does it process<br/>sensitive/protected data?}

    Q3 -->|Yes| Q4{Can decisions be<br/>easily reversed?}
    Q3 -->|No| Q5{Is system<br/>customer-facing?}

    Q4 -->|No| HighRisk[High Risk<br/>Enhanced controls + oversight]
    Q4 -->|Yes| MediumRisk[Medium Risk<br/>Standard controls + monitoring]

    Q5 -->|Yes| Q6{High volume<br/>> 1000 decisions/day?}
    Q5 -->|No| MediumRisk

    Q6 -->|Yes| HighRisk
    Q6 -->|No| MediumRisk

    subgraph Controls["Required Controls by Level"]
        Critical --> C_Controls[Full HITL, real-time monitoring,<br/>daily review, incident playbook,<br/>regulatory notification]
        HighRisk --> H_Controls[HOTL, continuous monitoring,<br/>weekly review, bias testing,<br/>compliance documentation]
        MediumRisk --> M_Controls[Periodic monitoring, quarterly review,<br/>standard documentation]
        LowRisk --> L_Controls[Annual review, basic documentation]
    end

    style Critical fill:#dc3545,color:#fff
    style HighRisk fill:#fd7e14,color:#fff
    style MediumRisk fill:#ffc107,color:#000
    style LowRisk fill:#28a745,color:#fff
```

## 8. Human Oversight Decision Framework

```mermaid
flowchart TD
    Input([AI System Output]) --> Confidence{Confidence<br/>above threshold?}

    Confidence -->|No| HumanReview[Route to Human Review]
    Confidence -->|Yes| Sensitive{Involves protected<br/>characteristics?}

    Sensitive -->|Yes| FairnessCheck{Passes fairness<br/>guardrails?}
    Sensitive -->|No| Stakes{High-stakes<br/>decision?}

    FairnessCheck -->|No| HumanReview
    FairnessCheck -->|Yes| Stakes

    Stakes -->|Yes| FinancialThreshold{Above financial<br/>threshold?}
    Stakes -->|No| Anomaly{Anomaly<br/>detected?}

    FinancialThreshold -->|Yes| SeniorReview[Senior Human Review]
    FinancialThreshold -->|No| StandardReview[Standard Human Review]

    Anomaly -->|Yes| HumanReview
    Anomaly -->|No| AutoDecision{User requested<br/>human review?}

    AutoDecision -->|Yes| HumanReview
    AutoDecision -->|No| Proceed[Proceed with AI Decision]

    HumanReview --> HumanDecision{Human agrees<br/>with AI?}
    HumanDecision -->|Yes| Execute[Execute Decision]
    HumanDecision -->|No| Override[Override - Log Rationale]
    Override --> Execute

    StandardReview --> Execute
    SeniorReview --> Execute
    Proceed --> Execute

    Execute --> Log[Log Decision + Context]
    Log --> Monitor[Feed into Monitoring]

    style HumanReview fill:#2196F3,color:#fff
    style SeniorReview fill:#9C27B0,color:#fff
    style StandardReview fill:#4CAF50,color:#fff
    style Proceed fill:#8BC34A,color:#fff
    style Override fill:#FF9800,color:#fff
```
