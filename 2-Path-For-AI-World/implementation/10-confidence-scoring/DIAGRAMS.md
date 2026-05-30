# Confidence Scoring - Diagrams

## 1. Confidence Scoring Pipeline

```mermaid
flowchart TD
    Q[User Query] --> RE[Retrieval Engine]
    RE --> |Documents + Scores| SE[Signal Extractors]
    Q --> GEN[LLM Generation]
    GEN --> |Answer + Metadata| SE
    
    SE --> S1[Retrieval Score]
    SE --> S2[Reranker Score]
    SE --> S3[Source Freshness]
    SE --> S4[Source Authority]
    SE --> S5[Context Coverage]
    SE --> S6[Groundedness]
    SE --> S7[Citation Support]
    SE --> S8[Answer Consistency]
    SE --> S9[Tool Success]
    SE --> S10[Historical Performance]
    
    S1 & S2 & S3 & S4 & S5 & S6 & S7 & S8 & S9 & S10 --> NORM[Signal Normalization]
    NORM --> AGG[Weighted Aggregation]
    AGG --> |Raw Composite| CAL[Calibration Layer]
    CAL --> |Calibrated Score| DEC[Action Decision]
    
    RC[Risk Classifier] --> DEC
    
    DEC --> A1[Answer Directly]
    DEC --> A2[Answer with Caveats]
    DEC --> A3[Ask Clarification]
    DEC --> A4[Abstain]
    DEC --> A5[Human Review]
    
    DEC --> LOG[Confidence Logger]
    LOG --> MON[Monitoring Dashboard]
    LOG --> FB[Feedback Collection]
    FB --> |Outcomes| RECAL[Recalibration Trigger]
    RECAL --> CAL
```

## 2. Signal Aggregation Architecture

```mermaid
flowchart LR
    subgraph "Retrieval Signals"
        RS[Retrieval Score<br/>weight=1.0]
        RR[Reranker Score<br/>weight=1.2]
    end
    
    subgraph "Source Quality Signals"
        SF[Source Freshness<br/>weight=0.8]
        SA[Source Authority<br/>weight=0.7]
    end
    
    subgraph "Answer Quality Signals"
        CC[Context Coverage<br/>weight=1.0]
        GR[Groundedness<br/>weight=1.5]
        CS[Citation Support<br/>weight=0.9]
        AC[Answer Consistency<br/>weight=1.0]
    end
    
    subgraph "Operational Signals"
        TS[Tool Success<br/>weight=1.1]
        HP[Historical Perf<br/>weight=0.6]
    end
    
    RS & RR --> N1[Normalize 0-1]
    SF & SA --> N2[Normalize 0-1]
    CC & GR & CS & AC --> N3[Normalize 0-1]
    TS & HP --> N4[Normalize 0-1]
    
    N1 & N2 & N3 & N4 --> WA[Weighted Average<br/>Σ(score_i × weight_i) / Σ(weight_i)]
    WA --> |0.72| OUT[Composite Score]
    
    style GR fill:#ff9999,stroke:#cc0000
    style RR fill:#99ccff,stroke:#0066cc
```

## 3. Confidence-to-Action Decision Flow

```mermaid
flowchart TD
    CS[Calibrated Score] --> RC{Risk Level?}
    
    RC --> |Critical/High| HR{Score ≥ 0.85?}
    HR --> |No| REVIEW[🚨 Route to Human Review<br/>Draft answer provided]
    HR --> |Yes| HIGH_CHECK
    
    RC --> |Medium/Low| HIGH_CHECK{Score ≥ High Threshold?}
    
    HIGH_CHECK --> |Yes ≥0.85| ANSWER[✅ Answer Directly<br/>Include citations]
    HIGH_CHECK --> |No| MED_CHECK{Score ≥ Medium Threshold?}
    
    MED_CHECK --> |Yes ≥0.60| CAVEAT[⚠️ Answer with Caveats<br/>'Based on available info...']
    MED_CHECK --> |No| LOW_CHECK{Score ≥ Low Threshold?}
    
    LOW_CHECK --> |Yes ≥0.35| CLARIFY[❓ Request Clarification<br/>Present options]
    LOW_CHECK --> |No| ABSTAIN[🛑 Abstain<br/>'I cannot reliably answer this']
    
    ANSWER --> LOG[Log + Monitor]
    CAVEAT --> LOG
    CLARIFY --> LOG
    ABSTAIN --> LOG
    REVIEW --> LOG
    
    style REVIEW fill:#ffcccc,stroke:#cc0000
    style ANSWER fill:#ccffcc,stroke:#009900
    style ABSTAIN fill:#ffffcc,stroke:#cc9900
```

## 4. Calibration Workflow

```mermaid
flowchart TD
    subgraph "Data Collection"
        PROD[Production Predictions] --> |score, query| STORE[(Prediction Store)]
        FB[User Feedback] --> |correct/incorrect| STORE
        STORE --> MATCH[Match Predictions<br/>to Outcomes]
    end
    
    MATCH --> |Labeled Data| SPLIT[Train/Val Split<br/>80/20]
    
    subgraph "Calibration Training"
        SPLIT --> PLATT[Platt Scaling<br/>Fit sigmoid: a,b]
        SPLIT --> ISO[Isotonic Regression<br/>PAV Algorithm]
        SPLIT --> TEMP[Temperature Scaling<br/>Fit T parameter]
        
        PLATT --> CV[Cross-Validation<br/>5-fold]
        ISO --> CV
        TEMP --> CV
        
        CV --> SELECT[Select Best Method<br/>Lowest CV ECE]
    end
    
    subgraph "Evaluation"
        SELECT --> EVAL[Evaluate on Held-Out]
        EVAL --> BRIER[Brier Score]
        EVAL --> ECE[ECE Computation]
        EVAL --> REL[Reliability Diagram]
        EVAL --> MCE[Max Cal. Error]
    end
    
    subgraph "Deployment"
        EVAL --> |Passes quality gate| DEPLOY[Deploy New Calibrator]
        DEPLOY --> BASELINE[Set New Baseline]
        BASELINE --> MONITOR[Monitor for Drift]
        MONITOR --> |Drift Detected| MATCH
    end
    
    style DEPLOY fill:#ccffcc,stroke:#009900
    style MONITOR fill:#ccccff,stroke:#0000cc
```

## 5. Threshold Tuning Loop

```mermaid
flowchart TD
    START[Collect Labeled Data<br/>n ≥ 500] --> ANALYZE[Analyze Score Distribution]
    
    ANALYZE --> OPT1[F-beta Optimization<br/>Grid search over thresholds]
    ANALYZE --> OPT2[Cost-Sensitive Optimization<br/>Minimize expected cost]
    ANALYZE --> OPT3[Precision-Constrained<br/>Max recall at min precision]
    
    OPT1 & OPT2 & OPT3 --> COMPARE[Compare Candidates]
    
    COMPARE --> STABILITY[Bootstrap Stability Analysis<br/>100 resamples]
    
    STABILITY --> |Stable?| DOMAIN[Domain-Specific Adjustment]
    STABILITY --> |Unstable| MORE[Collect More Data]
    MORE --> START
    
    DOMAIN --> MULTI[Multi-Class Threshold Tuning<br/>answer/caveat/clarify/abstain]
    
    MULTI --> VALIDATE[Validate on Held-Out Set]
    VALIDATE --> |Pass| DEPLOY[Deploy New Thresholds]
    VALIDATE --> |Fail| TUNE[Manual Review + Adjustment]
    TUNE --> VALIDATE
    
    DEPLOY --> MONITOR[Production Monitoring]
    MONITOR --> |Degradation Alert| START
    
    style MORE fill:#ffffcc
    style DEPLOY fill:#ccffcc
    style MONITOR fill:#ccccff
```

## 6. Confidence Monitoring Dashboard Layout

```mermaid
flowchart TD
    subgraph "Real-Time Panel (5-min refresh)"
        HIST[Score Distribution<br/>Histogram]
        RATE[Action Rate Gauges<br/>Answer/Caveat/Clarify/Abstain]
        LAT[Signal Latency<br/>P50/P95/P99]
    end
    
    subgraph "Calibration Panel (1-hour refresh)"
        RELDIAG[Reliability Diagram<br/>Predicted vs Actual]
        ECE_T[ECE Over Time<br/>Rolling 24h window]
        DRIFT[Drift Indicator<br/>🟢🟡🔴]
    end
    
    subgraph "Signal Health Panel (daily)"
        SIG_IMP[Signal Importance<br/>Ranked by discrimination]
        SIG_CORR[Signal Correlations<br/>Heatmap]
        SIG_FAIL[Signal Failures<br/>Error rates per extractor]
    end
    
    subgraph "Threshold Panel (weekly)"
        PR_CURVE[Precision-Recall Curve<br/>Current operating point]
        COST[Cost Analysis<br/>FP/FN breakdown]
        STAB[Threshold Stability<br/>Bootstrap CI]
    end
    
    subgraph "Alerts"
        A1[🔴 Calibration Drift > 0.05]
        A2[🟡 Abstention Spike > 2σ]
        A3[🔴 Precision Drop > 10%]
        A4[🟡 Score Distribution Collapse]
    end
```

## 7. Multi-Signal Fusion Diagram

```mermaid
flowchart TD
    subgraph "Layer 1: Raw Extraction"
        direction LR
        E1[Cosine Sim<br/>0.89]
        E2[Cross-Encoder<br/>0.93]
        E3[Exp Decay<br/>0.75]
        E4[Authority Tier<br/>0.95]
        E5[Keyword Coverage<br/>0.82]
        E6[NLI Entailment<br/>0.71]
        E7[Citation F1<br/>0.65]
        E8[Pairwise Sim<br/>0.88]
        E9[HTTP Success<br/>1.00]
        E10[Cluster Acc<br/>0.73]
    end
    
    subgraph "Layer 2: Normalization"
        direction LR
        N_MINMAX[Min-Max Scaling]
        N_CLIP[Clip to 0,1]
        N_ZSCORE[Z-Score + Sigmoid]
    end
    
    E1 & E2 --> N_CLIP
    E3 & E4 & E5 --> N_MINMAX
    E6 & E7 & E8 --> N_CLIP
    E9 & E10 --> N_ZSCORE
    
    subgraph "Layer 3: Weighted Combination"
        WC[Σ(w_i × s_i) / Σ(w_i)<br/>= 0.817]
    end
    
    N_MINMAX & N_CLIP & N_ZSCORE --> WC
    
    subgraph "Layer 4: Calibration"
        PLATT[Platt: σ(2.1×0.817 - 0.85)<br/>= 0.763]
    end
    
    WC --> PLATT
    
    subgraph "Layer 5: Decision"
        DEC[0.763 → ANSWER_WITH_CAVEATS<br/>Medium band: 0.60-0.85]
    end
    
    PLATT --> DEC
```

## 8. Production Confidence Distribution Monitoring

```mermaid
flowchart TD
    subgraph "Healthy Distribution (Bimodal)"
        HD[Score Distribution]
        HD --> |"Many at 0.85-1.0"| HIGH_PEAK[High Confidence Peak<br/>System knows what it knows]
        HD --> |"Many at 0.0-0.30"| LOW_PEAK[Low Confidence Peak<br/>System knows what it doesn't]
        HD --> |"Few at 0.4-0.7"| MIDDLE[Thin Middle<br/>Good discrimination]
    end
    
    subgraph "Unhealthy Distribution (Clustered)"
        UD[Score Distribution]
        UD --> |"Everything at 0.5-0.7"| CLUSTER[Clustered in Middle<br/>❌ Poor discrimination]
        UD --> |"Everything at 0.9+"| OVERCONF[All High Confidence<br/>❌ Overconfident]
        UD --> |"Everything at 0.1-0.3"| UNDERCONF[All Low Confidence<br/>❌ Underconfident/Broken]
    end
    
    subgraph "Monitoring Actions"
        CLUSTER --> FIX1[Review signal quality<br/>Add more signals]
        OVERCONF --> FIX2[Check calibration<br/>Increase temperature]
        UNDERCONF --> FIX3[Check retrieval system<br/>Signal extractor errors?]
    end
    
    subgraph "Time Series Alerts"
        TS1[ECE over time<br/>Alert if trend > 0.05]
        TS2[Abstention rate<br/>Alert if spike > 2σ]
        TS3[Score mean shift<br/>Alert if Δ > 0.1 in 1h]
        TS4[Signal failure rate<br/>Alert if any > 5%]
    end
    
    style CLUSTER fill:#ffcccc
    style OVERCONF fill:#ffcccc
    style UNDERCONF fill:#ffcccc
    style HIGH_PEAK fill:#ccffcc
    style LOW_PEAK fill:#ccffcc
    style MIDDLE fill:#ccffcc
```

## 9. Confidence Aggregation for Multi-Step Agents

```mermaid
flowchart TD
    subgraph "Step 1: Query Understanding"
        S1[Confidence: 0.92]
    end
    
    subgraph "Step 2: Tool Selection"
        S2[Confidence: 0.85]
    end
    
    subgraph "Step 3: API Call"
        S3[Confidence: 0.78<br/>API returned partial results]
    end
    
    subgraph "Step 4: Result Synthesis"
        S4[Confidence: 0.81]
    end
    
    S1 --> S2 --> S3 --> S4
    
    subgraph "Aggregation Strategies"
        MIN[Bottleneck: min(0.92, 0.85, 0.78, 0.81)<br/>= 0.78]
        MULT[Multiplicative: 0.92 × 0.85 × 0.78 × 0.81<br/>= 0.494]
        DECAY[Bottleneck + Decay: 0.78 × 0.95³<br/>= 0.669]
        WMEAN[Weighted Mean: later steps weighted more<br/>= 0.82]
    end
    
    S4 --> MIN
    S4 --> MULT
    S4 --> DECAY
    S4 --> WMEAN
    
    DECAY --> |Recommended| FINAL[Final Chain Confidence: 0.669<br/>Action: ANSWER_WITH_CAVEATS]
    
    style DECAY fill:#ccffcc,stroke:#009900
    style MULT fill:#ffcccc,stroke:#cc0000
```
