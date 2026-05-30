# AI UX and Human Trust - Diagrams

## 1. Trust Calibration Spectrum

```mermaid
graph LR
    subgraph "Trust Calibration Spectrum"
        A[Under-Trust] -->|"User ignores<br/>valid suggestions"| B[Calibrated Trust]
        B -->|"User verifies<br/>appropriately"| B
        B -->|"User blindly<br/>follows AI"| C[Over-Trust]
    end

    subgraph "Interventions"
        D[Show accuracy history] --> B
        E[Display confidence] --> B
        F[Validate predictions] --> B
        G[Require verification<br/>for high-stakes] --> B
    end

    style A fill:#f97316,color:#fff
    style B fill:#22c55e,color:#fff
    style C fill:#ef4444,color:#fff
```

## 2. Feedback Collection Flow

```mermaid
flowchart TD
    A[AI Response Delivered] --> B{User Interaction}
    
    B -->|Quick Signal| C[Thumbs Up/Down]
    B -->|Detailed| D[Rating 1-5]
    B -->|Issue Found| E[Report]
    B -->|Fix Needed| F[Correction]
    B -->|Behavioral| G[Implicit Signal]
    
    C --> H[Store Feedback]
    D --> H
    E --> I{Safety Issue?}
    F --> H
    G --> H
    
    I -->|Yes| J[Urgent Alert<br/>to Safety Team]
    I -->|No| H
    
    H --> K[Categorize]
    K --> L[Aggregate Patterns]
    L --> M{Threshold Met?}
    
    M -->|Yes| N[Generate<br/>Improvement Action]
    M -->|No| O[Continue<br/>Monitoring]
    
    N --> P[Update Eval Dataset]
    N --> Q[Update Prompts/Model]
    N --> R[Update Guardrails]
    
    P --> S[Measure Impact]
    Q --> S
    R --> S
    
    S -->|Improved| T[Close Loop]
    S -->|Not Improved| U[Escalate to Team]
    
    style J fill:#ef4444,color:#fff
    style N fill:#3b82f6,color:#fff
    style T fill:#22c55e,color:#fff
```

## 3. Human Approval UX Flow

```mermaid
flowchart TD
    A[AI Proposes Action] --> B{Assess Risk Level}
    
    B -->|Critical| C[Full Approval Flow]
    B -->|High| D[Approval + Preview]
    B -->|Medium| E[Edit-Before-Action]
    B -->|Low| F[Auto-Execute<br/>with Audit Log]
    
    C --> G[Show Action Details]
    G --> H[Show Impact Assessment]
    H --> I[Require Explicit Confirmation]
    I --> J{User Decision}
    
    D --> K[Show Preview]
    K --> L{User Decision}
    
    E --> M[Show Editable Draft]
    M --> N[User Edits]
    N --> O{User Decision}
    
    J -->|Approve| P[Execute Action]
    J -->|Edit| M
    J -->|Reject| Q[Cancel + Log Reason]
    J -->|Defer| R[Queue for Later]
    
    L -->|Approve| P
    L -->|Edit| M
    L -->|Reject| Q
    
    O -->|Confirm| P
    O -->|Discard| Q
    
    P --> S[Log in Audit Trail]
    Q --> S
    R --> T[Reminder After Timeout]
    T -->|No Response| U[Auto-Cancel]
    
    style C fill:#ef4444,color:#fff
    style D fill:#f97316,color:#fff
    style E fill:#eab308,color:#000
    style F fill:#22c55e,color:#fff
    style P fill:#3b82f6,color:#fff
```

## 4. Confidence Display Decision Tree

```mermaid
flowchart TD
    A[Response Generated] --> B{Compute<br/>Confidence Score}
    
    B --> C{Score >= 0.95?}
    C -->|Yes| D["Very High Confidence<br/>🟢 No caveat needed<br/>Direct, authoritative language"]
    C -->|No| E{Score >= 0.80?}
    
    E -->|Yes| F["High Confidence<br/>🟢 Light caveat<br/>'You may want to verify key details'"]
    E -->|No| G{Score >= 0.60?}
    
    G -->|Yes| H["Medium Confidence<br/>🟡 Moderate caveat<br/>'I'd recommend verifying independently'<br/>Show alternatives"]
    G -->|No| I{Score >= 0.40?}
    
    I -->|Yes| J["Low Confidence<br/>🟠 Strong caveat<br/>'This is my best guess'<br/>Show alternatives + suggest expert"]
    I -->|No| K{Score >= 0.20?}
    
    K -->|Yes| L["Very Low Confidence<br/>🔴 Consider abstaining<br/>'I don't have enough information'<br/>Suggest authoritative sources"]
    K -->|No| M["Abstain<br/>⛔ Do not answer<br/>Escalate to human<br/>or suggest alternative resources"]
    
    D --> N{Risk Level?}
    F --> N
    H --> N
    J --> N
    
    N -->|High Risk| O[Lower effective threshold<br/>Show confidence even if high]
    N -->|Low Risk| P[Use standard display]
    
    style D fill:#22c55e,color:#fff
    style F fill:#84cc16,color:#000
    style H fill:#eab308,color:#000
    style J fill:#f97316,color:#fff
    style L fill:#ef4444,color:#fff
    style M fill:#7f1d1d,color:#fff
```

## 5. Citation UX Architecture

```mermaid
flowchart TD
    subgraph "Source Processing"
        A[AI Response Generated] --> B[Identify Claims]
        B --> C[Match Claims to Sources]
        C --> D[Score Source Relevance]
        D --> E[Assess Source Authority]
        E --> F[Check Source Agreement]
    end
    
    subgraph "Citation Formatting"
        F --> G{Display Context?}
        G -->|Chat| H[Inline Citations<br/>with footnotes]
        G -->|Dashboard| I[Sidebar Panel<br/>with grouped sources]
        G -->|Report| J[Full Bibliography<br/>with annotations]
        G -->|Mobile| K[Expandable Cards<br/>tap to reveal]
    end
    
    subgraph "Trust Indicators"
        H --> L[Source Authority Badges]
        I --> L
        J --> L
        K --> L
        
        L --> M[Agreement Indicator]
        M --> N{Sources Agree?}
        N -->|Yes| O["🟢 'Multiple sources confirm'"]
        N -->|Partial| P["🟡 'Some sources support this'"]
        N -->|No| Q["🔴 'Sources provide conflicting info'"]
    end
    
    subgraph "User Actions"
        O --> R[Verify Source Link]
        P --> R
        Q --> R
        R --> S[View Full Excerpt]
        S --> T[Report Bad Source]
    end
    
    style O fill:#22c55e,color:#fff
    style P fill:#eab308,color:#000
    style Q fill:#ef4444,color:#fff
```

## 6. Explainability Pipeline

```mermaid
flowchart LR
    subgraph "Input"
        A[User Query]
    end
    
    subgraph "Processing (Instrumented)"
        B[Retrieval<br/>Log: what searched,<br/>what found] 
        C[Reasoning<br/>Log: steps taken,<br/>confidence per step]
        D[Tool Use<br/>Log: which tools,<br/>why called]
        E[Generation<br/>Log: sources used,<br/>claims made]
    end
    
    subgraph "Explanation Engine"
        F[Attribution<br/>Engine]
        G[Decision<br/>Explainer]
        H[Confidence<br/>Explainer]
        I[Summarizer]
    end
    
    subgraph "Output Layers"
        J["Layer 1<br/>One-line summary<br/>(always shown)"]
        K["Layer 2<br/>Key factors<br/>(click to expand)"]
        L["Layer 3<br/>Full explanation<br/>(detailed view)"]
        M["Layer 4<br/>Technical trace<br/>(admin/debug)"]
    end
    
    A --> B --> C --> D --> E
    
    B --> F
    C --> G
    D --> G
    E --> F
    E --> H
    
    F --> I
    G --> I
    H --> I
    
    I --> J
    I --> K
    I --> L
    F --> M
    G --> M
    H --> M
```

## 7. Error Recovery Flow

```mermaid
flowchart TD
    A[Error Occurs] --> B{Error Type?}
    
    B -->|Transient| C[Auto-Retry]
    B -->|Input| D[Guide User]
    B -->|Capacity| E[Queue + Wait]
    B -->|Logic| F[Graceful Degrade]
    B -->|System| G[Failover]
    
    C --> H{Retry Successful?}
    H -->|Yes| I[Continue Normally<br/>User may not notice]
    H -->|No, Retry 1| C
    H -->|No, Max Retries| J[Show Error Message]
    
    D --> K[Highlight Problem]
    K --> L[Suggest Fix]
    L --> M[User Corrects Input]
    M --> N[Re-process]
    
    E --> O[Show ETA]
    O --> P[Process When Ready]
    P --> Q[Notify User]
    
    F --> R{Partial Result?}
    R -->|Yes| S[Show Partial + Caveat]
    R -->|No| J
    
    G --> T[Switch to Backup]
    T --> U{Backup Available?}
    U -->|Yes| V[Process with Degraded Service]
    U -->|No| J
    
    J --> W[Compose Error Message]
    W --> X["Formula:<br/>[What happened]<br/>[Impact on user]<br/>[What user can do]<br/>[What system is doing]"]
    X --> Y[Present with Actions]
    Y --> Z[Log for Monitoring]
    
    style I fill:#22c55e,color:#fff
    style J fill:#ef4444,color:#fff
    style S fill:#eab308,color:#000
```

## 8. User Trust Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Initial_Skepticism: First interaction
    
    Initial_Skepticism --> Exploration: User tries AI
    Exploration --> Building_Trust: Positive experiences
    Exploration --> Distrust: Bad first experience
    
    Building_Trust --> Calibrated_Trust: Consistent accuracy + honest uncertainty
    Building_Trust --> Over_Trust: AI too confident, user stops verifying
    
    Calibrated_Trust --> Calibrated_Trust: Regular positive interactions
    Calibrated_Trust --> Trust_Repair: AI makes noticeable error
    Calibrated_Trust --> Deep_Trust: Sustained reliability over months
    
    Over_Trust --> Trust_Violation: Major incorrect action
    Trust_Violation --> Distrust: No acknowledgment or recovery
    Trust_Violation --> Trust_Repair: Transparent error handling
    
    Trust_Repair --> Building_Trust: Successful recovery
    Trust_Repair --> Abandonment: Repeated failures
    
    Distrust --> Exploration: Forced to try again (no alternative)
    Distrust --> Abandonment: User finds alternative
    
    Deep_Trust --> Calibrated_Trust: AI honestly communicates new limitations
    Deep_Trust --> Over_Trust: User stops paying attention
    
    Abandonment --> [*]
    
    note right of Calibrated_Trust
        GOAL STATE
        User trusts appropriately
        Verifies when needed
        Accepts when reasonable
    end note
    
    note right of Trust_Repair
        KEY MOMENT
        How errors are handled
        determines trust trajectory
    end note
```

## 9. Feedback-to-Improvement Closed Loop

```mermaid
flowchart TD
    subgraph "Collection"
        A[User Interaction] --> B[Explicit Feedback<br/>👍👎 ratings, reports]
        A --> C[Implicit Feedback<br/>copy, retry, ignore, edit]
        A --> D[Corrections<br/>user edits AI output]
    end
    
    subgraph "Processing"
        B --> E[Categorize]
        C --> E
        D --> E
        E --> F[Aggregate Patterns]
        F --> G[Prioritize by Impact]
    end
    
    subgraph "Action"
        G --> H{Action Type}
        H -->|Safety| I[Update Guardrails<br/>IMMEDIATE]
        H -->|Quality| J[Update Prompts<br/>or Retrain]
        H -->|Retrieval| K[Improve Search<br/>Index/Ranking]
        H -->|UX| L[Update UI<br/>Components]
    end
    
    subgraph "Validation"
        I --> M[Add to Eval Dataset]
        J --> M
        K --> M
        L --> M
        M --> N[Run Evals]
        N --> O{Improved?}
        O -->|Yes| P[Deploy + Monitor]
        O -->|No| Q[Iterate on Fix]
        Q --> H
    end
    
    subgraph "Monitoring"
        P --> R[Track Metrics<br/>CSAT, NPS, Resolution Rate]
        R --> S{Regression?}
        S -->|Yes| T[Alert Team]
        S -->|No| U[Continue Monitoring]
        T --> H
    end
    
    style I fill:#ef4444,color:#fff
    style P fill:#22c55e,color:#fff
    style T fill:#f97316,color:#fff
```
