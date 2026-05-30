# AI SRE - Diagrams

## 1. SLO Monitoring Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        API[API Gateway Metrics]
        MODEL[Model Provider Metrics]
        VDB[Vector DB Metrics]
        EVAL[Quality Evaluator]
        SAFETY[Safety Classifier]
        COST[Cost Tracker]
        TOOLS[Tool Metrics]
    end

    subgraph "SLI Computation Layer"
        AVAIL[Availability SLI]
        LAT[Latency SLI]
        QUAL[Quality SLI]
        CSLI[Cost SLI]
        SAFE[Safety SLI]
        TOOL_SLI[Tool Success SLI]
        ESC[Escalation SLI]
    end

    subgraph "Error Budget Engine"
        BUDGET[Budget Calculator]
        BURN[Burn Rate Computer]
        MULTI[Multi-Window Alerter]
    end

    subgraph "Response Layer"
        ALERT[Alert Router]
        ONCALL[On-Call Page]
        TICKET[Ticket Creation]
        AUTO[Auto-Responder]
        DASH[Dashboard]
        REPORT[Weekly Report]
    end

    API --> AVAIL
    API --> LAT
    MODEL --> AVAIL
    MODEL --> LAT
    VDB --> LAT
    EVAL --> QUAL
    SAFETY --> SAFE
    COST --> CSLI
    TOOLS --> TOOL_SLI

    AVAIL --> BUDGET
    LAT --> BUDGET
    QUAL --> BUDGET
    CSLI --> BUDGET
    SAFE --> BUDGET
    TOOL_SLI --> BUDGET
    ESC --> BUDGET

    BUDGET --> BURN
    BURN --> MULTI

    MULTI -->|Critical 14.4x| ONCALL
    MULTI -->|High 6x| ONCALL
    MULTI -->|Medium 3x| TICKET
    MULTI -->|Low 1x| ALERT

    BUDGET --> DASH
    BUDGET --> REPORT
    MULTI --> AUTO
    AUTO -->|"Execute Runbook"| RUNBOOK[Runbook Engine]
```

## 2. Incident Response Flow

```mermaid
flowchart TD
    START((Signal Received)) --> DETECT{Signal Type?}
    
    DETECT -->|Metrics Alert| CORR[Correlate Signals]
    DETECT -->|User Report| VERIFY[Verify Report]
    DETECT -->|Health Check| CORR
    DETECT -->|Security Scanner| SEC_TRIAGE[Security Triage]
    
    CORR --> CREATE{Incident\nThreshold Met?}
    VERIFY --> CREATE
    SEC_TRIAGE --> CREATE
    
    CREATE -->|No| MONITOR[Continue Monitoring]
    CREATE -->|Yes| INCIDENT[Create Incident]
    
    INCIDENT --> CLASSIFY[Classify Severity]
    CLASSIFY --> AUTO_RESP[Automated Response]
    
    AUTO_RESP --> NOTIFY[Notify Stakeholders]
    AUTO_RESP --> PAGE[Page On-Call]
    AUTO_RESP --> MITIGATE[Auto-Mitigate]
    
    PAGE --> ACK{Acknowledged\nin 5 min?}
    ACK -->|No| ESCALATE[Escalate to Secondary]
    ACK -->|Yes| INVESTIGATE[Investigate]
    
    INVESTIGATE --> RC{Root Cause\nIdentified?}
    RC -->|No| MORE_DATA[Gather More Data]
    MORE_DATA --> INVESTIGATE
    RC -->|Yes| FIX[Apply Fix/Runbook]
    
    FIX --> VERIFY_FIX{Fix\nVerified?}
    VERIFY_FIX -->|No| ROLLBACK[Rollback Fix]
    ROLLBACK --> INVESTIGATE
    VERIFY_FIX -->|Yes| MONITOR_REC[Monitor Recovery]
    
    MONITOR_REC --> STABLE{Metrics\nStable?}
    STABLE -->|No| INVESTIGATE
    STABLE -->|Yes| RESOLVE[Resolve Incident]
    
    RESOLVE --> POSTMORTEM[Schedule Postmortem]
    POSTMORTEM --> ACTIONS[Track Action Items]
    ACTIONS --> CLOSE[Close Incident]
```

## 3. Runbook Execution Flow

```mermaid
flowchart TD
    TRIGGER((Trigger)) --> LOOKUP[Lookup Runbook]
    LOOKUP --> COOLDOWN{In\nCooldown?}
    COOLDOWN -->|Yes| REJECT[Reject - Wait]
    COOLDOWN -->|No| CONCURRENT{Max Concurrent\nReached?}
    CONCURRENT -->|Yes| QUEUE[Queue for Later]
    CONCURRENT -->|No| PREFLIGHT[Run Preflight Checks]
    
    PREFLIGHT --> PF_RESULT{All Blocking\nChecks Pass?}
    PF_RESULT -->|No| FAIL_PRE[Fail - Log Reason]
    PF_RESULT -->|Yes| APPROVAL{Requires\nApproval?}
    
    APPROVAL -->|Yes| WAIT_APPROVE[Wait for Approval]
    WAIT_APPROVE --> APPROVED{Approved?}
    APPROVED -->|No| CANCEL[Cancel Execution]
    APPROVED -->|Yes| EXECUTE
    APPROVAL -->|No| EXECUTE[Execute Steps]
    
    EXECUTE --> STEP[Execute Next Step]
    
    STEP --> PRE_CHECK{Pre-Check\nPass?}
    PRE_CHECK -->|No & Required| STEP_FAIL[Step Failed]
    PRE_CHECK -->|No & Skippable| SKIP[Skip Step]
    PRE_CHECK -->|Yes| RUN_STEP[Run Step Action]
    
    RUN_STEP --> STEP_OK{Step\nSucceeded?}
    STEP_OK -->|No & Retries Left| RETRY[Retry After Delay]
    RETRY --> RUN_STEP
    STEP_OK -->|No & No Retries| STEP_FAIL
    STEP_OK -->|Yes| POST_CHECK{Post-Check\nPass?}
    
    POST_CHECK -->|No| STEP_FAIL
    POST_CHECK -->|Yes| MORE{More\nSteps?}
    SKIP --> MORE
    
    MORE -->|Yes| STEP
    MORE -->|No| COMPLETE[Complete - Success]
    
    STEP_FAIL --> ROLLBACK[Rollback Completed Steps]
    ROLLBACK --> FAIL_EXEC[Fail - Rolled Back]
    
    COMPLETE --> VERIFY[Post-Runbook Verification]
    VERIFY --> AUDIT[Write Audit Log]
    FAIL_EXEC --> AUDIT
    FAIL_PRE --> AUDIT
```

## 4. Error Budget Burn Rate Visualization

```mermaid
graph LR
    subgraph "28-Day Window"
        direction TB
        D1[Day 1] --- D7[Day 7]
        D7 --- D14[Day 14]
        D14 --- D21[Day 21]
        D21 --- D28[Day 28]
    end

    subgraph "Budget Status"
        HEALTHY[🟢 Healthy<br/>Budget > 50%<br/>Normal velocity]
        WARNING[🟡 Warning<br/>Budget 20-50%<br/>Slow deployments]
        CRITICAL[🔴 Critical<br/>Budget < 20%<br/>Freeze deploys]
        EXHAUSTED[⚫ Exhausted<br/>Budget = 0%<br/>All stop]
    end

    subgraph "Multi-Window Burn Rate Alerts"
        FAST[14.4x burn<br/>5min + 1h windows<br/>→ PAGE NOW]
        MED_BURN[6x burn<br/>30min + 6h windows<br/>→ PAGE]
        SLOW[3x burn<br/>2h + 24h windows<br/>→ TICKET]
        VERY_SLOW[1x burn<br/>6h + 72h windows<br/>→ ALERT]
    end

    HEALTHY -.->|"Burn rate increases"| WARNING
    WARNING -.->|"Burn rate increases"| CRITICAL
    CRITICAL -.->|"Budget consumed"| EXHAUSTED
```

## 5. Chaos Engineering Process

```mermaid
flowchart TD
    subgraph "Planning"
        HYPOTHESIS[Define Hypothesis]
        SCOPE[Set Blast Radius]
        SAFETY[Define Safety Controls]
        SCHEDULE[Schedule on Calendar]
        APPROVE[Get Approval]
    end

    subgraph "Execution"
        PRE_STATE[Verify Steady State<br/>Pre-Experiment]
        INJECT[Inject Chaos]
        MONITOR[Monitor + Check Abort]
        CLEANUP[Remove Chaos]
        POST_STATE[Verify Steady State<br/>Post-Experiment]
    end

    subgraph "Safety Controls"
        KILL[Kill Switch]
        BLAST[Blast Radius Limits]
        DURATION[Duration Limits]
        THRESHOLD[Impact Thresholds]
        AUTO_ABORT[Auto-Abort on SLO Breach]
    end

    subgraph "Analysis"
        RESULTS[Collect Results]
        COMPARE[Compare Pre/Post State]
        VALIDATE[Validate Hypothesis]
        REPORT[Generate Report]
        ACTIONS[Create Action Items]
    end

    HYPOTHESIS --> SCOPE --> SAFETY --> SCHEDULE --> APPROVE
    APPROVE --> PRE_STATE
    
    PRE_STATE -->|Pass| INJECT
    PRE_STATE -->|Fail| ABORT_UNHEALTHY[Abort: System Already Unhealthy]
    
    INJECT --> MONITOR
    
    MONITOR -->|Duration Complete| CLEANUP
    MONITOR -->|Abort Triggered| CLEANUP
    
    KILL -.->|Emergency| CLEANUP
    BLAST -.-> MONITOR
    DURATION -.-> MONITOR
    THRESHOLD -.-> MONITOR
    AUTO_ABORT -.-> MONITOR
    
    CLEANUP --> POST_STATE
    POST_STATE --> RESULTS
    RESULTS --> COMPARE --> VALIDATE --> REPORT --> ACTIONS
```

## 6. On-Call Decision Tree

```mermaid
flowchart TD
    ALERT((Alert\nReceived)) --> TYPE{What type\nof alert?}
    
    TYPE -->|Availability Drop| AVAIL_CHECK{Provider\nStatus Page?}
    AVAIL_CHECK -->|Provider Down| SWITCH[Execute: Switch Provider]
    AVAIL_CHECK -->|Provider OK| INFRA[Check Our Infrastructure]
    INFRA -->|Our Issue| ROLLBACK[Execute: Rollback Recent Deploy]
    INFRA -->|Unknown| DEEP[Deep Investigation]
    
    TYPE -->|Quality Degradation| QUALITY_CHECK{Recent\nDeployment?}
    QUALITY_CHECK -->|Yes, Prompt| ROLL_PROMPT[Execute: Rollback Prompt]
    QUALITY_CHECK -->|Yes, Index| ROLL_INDEX[Execute: Rollback Retriever]
    QUALITY_CHECK -->|No| DRIFT[Model Drift Investigation]
    
    TYPE -->|Cost Spike| COST_CHECK{Single User\nor Systemic?}
    COST_CHECK -->|Single User| BLOCK[Execute: Block User]
    COST_CHECK -->|Systemic - Loops| LOWER[Execute: Lower Max Steps]
    COST_CHECK -->|Systemic - Other| COST_INVEST[Cost Investigation]
    
    TYPE -->|Safety Violation| SAFETY_SEV{Severity?}
    SAFETY_SEV -->|Critical: Data Leak| PAUSE[Execute: Pause Write Actions<br/>+ Notify Security + Legal]
    SAFETY_SEV -->|High: Injection| FILTER[Execute: Force Human Approval<br/>+ Block Attacker]
    SAFETY_SEV -->|Medium/Low| MONITOR_SAFETY[Monitor + Ticket]
    
    TYPE -->|Tool Failure| TOOL_CHECK{Which Tool?}
    TOOL_CHECK -->|Single Tool| DISABLE[Execute: Disable Tool]
    TOOL_CHECK -->|MCP Server| MCP[Execute: Disable MCP Server]
    TOOL_CHECK -->|All Tools| INFRA
    
    TYPE -->|Latency Spike| LAT_CHECK{Source?}
    LAT_CHECK -->|Model Slow| SWITCH
    LAT_CHECK -->|VectorDB Slow| VDB[Scale VectorDB / Switch Index]
    LAT_CHECK -->|Tools Slow| DISABLE
```

## 7. AI System Failure Modes

```mermaid
graph TB
    subgraph "Infrastructure Failures"
        IF1[Model Provider Outage]
        IF2[Vector DB Outage]
        IF3[Embedding Service Down]
        IF4[Network Partition]
        IF5[Rate Limit Exhaustion]
    end

    subgraph "Data/Quality Failures"
        DF1[Bad Prompt Deployment]
        DF2[Index Corruption]
        DF3[Embedding Mismatch]
        DF4[Poisoned Documents]
        DF5[Stale Cache]
    end

    subgraph "Behavioral Failures"
        BF1[Runaway Agent Loop]
        BF2[Hallucination Spike]
        BF3[Tool Misuse]
        BF4[Incorrect Escalation]
        BF5[Context Window Overflow]
    end

    subgraph "Security Failures"
        SF1[Prompt Injection]
        SF2[Data Leakage]
        SF3[Tool Permission Exploit]
        SF4[PII Exposure]
        SF5[Cross-Tenant Access]
    end

    subgraph "Impact"
        UNAVAIL[Unavailability]
        DEGRADED[Quality Degradation]
        COST_IMP[Cost Spike]
        SAFETY_IMP[Safety Violation]
        TRUST[Trust Erosion]
    end

    IF1 --> UNAVAIL
    IF2 --> DEGRADED
    IF3 --> DEGRADED
    IF5 --> UNAVAIL

    DF1 --> DEGRADED
    DF2 --> DEGRADED
    DF4 --> SAFETY_IMP

    BF1 --> COST_IMP
    BF2 --> TRUST
    BF3 --> SAFETY_IMP

    SF1 --> SAFETY_IMP
    SF2 --> SAFETY_IMP
    SF2 --> TRUST
    SF5 --> SAFETY_IMP
```

## 8. Postmortem Workflow

```mermaid
flowchart TD
    RESOLVE((Incident\nResolved)) --> SCHEDULE[Schedule Postmortem<br/>Within 48h]
    
    SCHEDULE --> PREPARE[Prepare Data]
    
    subgraph "Preparation"
        PREPARE --> TIMELINE[Compile Timeline<br/>from Incident Log]
        PREPARE --> METRICS_G[Gather Metrics<br/>Before/During/After]
        PREPARE --> LOGS[Collect Relevant Logs]
        PREPARE --> COMMS[Gather Communications]
    end
    
    TIMELINE --> MEETING[Postmortem Meeting]
    METRICS_G --> MEETING
    LOGS --> MEETING
    COMMS --> MEETING
    
    subgraph "Meeting"
        MEETING --> REVIEW_TL[Review Timeline]
        REVIEW_TL --> ROOT[Identify Root Cause<br/>5 Whys Analysis]
        ROOT --> AI_ANALYSIS[AI-Specific Analysis<br/>- Model behavior?<br/>- Data issue?<br/>- Non-determinism?]
        AI_ANALYSIS --> WELL[What Went Well]
        WELL --> WRONG[What Went Wrong]
        WRONG --> ACTIONS_M[Define Action Items<br/>with Owners + Due Dates]
    end
    
    ACTIONS_M --> DOC[Write Postmortem Doc]
    DOC --> REVIEW_DOC[Review with Leadership]
    REVIEW_DOC --> PUBLISH[Publish to Team]
    PUBLISH --> TRACK[Track Action Items]
    
    TRACK --> FOLLOW_UP{Actions\nCompleted?}
    FOLLOW_UP -->|No| REMIND[Remind Owners]
    REMIND --> FOLLOW_UP
    FOLLOW_UP -->|Yes| CLOSE_PM[Close Postmortem]
    
    CLOSE_PM --> UPDATE_RUNBOOK[Update Runbooks]
    CLOSE_PM --> UPDATE_CHAOS[Add Chaos Scenario]
    CLOSE_PM --> UPDATE_SLO[Adjust SLOs if Needed]
    CLOSE_PM --> UPDATE_MONITOR[Add New Monitoring]
```
