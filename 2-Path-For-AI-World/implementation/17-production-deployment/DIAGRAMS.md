# Production Deployment Diagrams

## 1. Production System Architecture

```mermaid
graph TB
    subgraph Users
        U[Users/Clients]
    end

    subgraph "Edge Layer"
        CDN[CDN/CloudFront]
        WAF[WAF]
    end

    subgraph "API Layer"
        APIGW[API Gateway]
        AUTH[Auth Service]
        RL[Rate Limiter]
    end

    subgraph "AI Core Services"
        AIGW[AI Gateway]
        ORCH[Agent Orchestrator]
        GUARD[Guardrail Service]
        RET[Retrieval Service]
        TOOL[Tool Service]
    end

    subgraph "Data Layer"
        VDB[(Vector DB<br/>Qdrant)]
        PG[(PostgreSQL<br/>Metadata)]
        REDIS[(Redis<br/>Cache)]
        S3[(S3<br/>Documents)]
    end

    subgraph "External Providers"
        OAI[OpenAI]
        ANT[Anthropic]
        AZ[Azure OpenAI]
    end

    subgraph "Observability"
        OTEL[OpenTelemetry<br/>Collector]
        PROM[Prometheus]
        GRAF[Grafana]
        LANG[Langfuse]
    end

    U --> CDN --> WAF --> APIGW
    APIGW --> AUTH --> RL --> ORCH
    ORCH --> AIGW --> OAI & ANT & AZ
    ORCH --> GUARD
    ORCH --> RET --> VDB
    ORCH --> TOOL
    ORCH --> REDIS
    ORCH --> PG
    RET --> S3
    
    ORCH -.-> OTEL
    AIGW -.-> OTEL
    RET -.-> OTEL
    OTEL --> PROM --> GRAF
    OTEL --> LANG
```

## 2. Kubernetes Deployment Topology

```mermaid
graph TB
    subgraph "EKS Cluster"
        subgraph "General Node Pool (m6i.xlarge)"
            subgraph "ai-production namespace"
                ORCH1[Orchestrator Pod 1]
                ORCH2[Orchestrator Pod 2]
                ORCH3[Orchestrator Pod 3]
                ORCHC[Orchestrator Canary]
                RET1[Retrieval Pod 1]
                RET2[Retrieval Pod 2]
                AIGW1[AI Gateway Pod 1]
                AIGW2[AI Gateway Pod 2]
                GRD1[Guardrail Pod 1]
                GRD2[Guardrail Pod 2]
            end
        end

        subgraph "High-Memory Node Pool (r6i.2xlarge)"
            QD1[Qdrant Pod 0<br/>PVC: 200Gi]
            QD2[Qdrant Pod 1<br/>PVC: 200Gi]
            QD3[Qdrant Pod 2<br/>PVC: 200Gi]
        end

        subgraph "GPU Node Pool (g5.2xlarge)"
            VLLM1[vLLM Pod<br/>Embedding Model]
        end

        subgraph "System"
            ISTIO[Istio Gateway]
            OTEL[OTel Collector]
            ESO[External Secrets<br/>Operator]
        end
    end

    subgraph "AWS Services"
        ALB[Application<br/>Load Balancer]
        SM[Secrets Manager]
        ECR[ECR Registry]
        CW[CloudWatch]
    end

    ALB --> ISTIO
    ISTIO --> ORCH1 & ORCH2 & ORCH3
    ISTIO -.->|5%| ORCHC
    ESO --> SM
    OTEL --> CW
```

## 3. CI/CD Pipeline Flow

```mermaid
flowchart TD
    A[Push to main] --> B[Build & Lint]
    B --> C[Unit Tests]
    C --> D{Tests Pass?}
    D -->|No| FAIL[Notify & Stop]
    D -->|Yes| E[AI Eval - Golden Dataset]
    
    C --> F[Safety Eval]
    C --> G[Security Scan]
    
    E --> H{Eval Score >= Threshold?}
    H -->|No| FAIL
    H -->|Yes| I[Container Build]
    
    F --> J{Safety Pass?}
    J -->|No| FAIL
    J -->|Yes| I
    
    G --> K{No Vulnerabilities?}
    K -->|No| FAIL
    K -->|Yes| I
    
    I --> L[Deploy Staging]
    L --> M[Integration Tests]
    M --> N{Integration Pass?}
    N -->|No| FAIL
    N -->|Yes| O[Canary Deploy 5%]
    
    O --> P[Monitor 15min]
    P --> Q{Metrics OK?}
    Q -->|No| R[Rollback Canary]
    Q -->|Yes| S[Promote to 100%]
    
    R --> T[Create Issue]
    S --> U[Tag Release]
    
    style FAIL fill:#f44,color:#fff
    style S fill:#4a4,color:#fff
    style R fill:#f84,color:#fff
```

## 4. Canary Deployment Progression

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CI as CI/CD
    participant K8s as Kubernetes
    participant Prom as Prometheus
    participant PD as PagerDuty

    Dev->>CI: Merge to main
    CI->>CI: Build, Test, Eval
    CI->>K8s: Deploy canary (1 pod)
    CI->>K8s: Set traffic: 1% canary

    loop Every 60s for 15min
        Prom->>Prom: Collect canary metrics
        CI->>Prom: Check thresholds
    end

    alt Metrics OK
        CI->>K8s: Set traffic: 5% canary
        loop Every 60s for 30min
            CI->>Prom: Check thresholds
        end
        CI->>K8s: Set traffic: 25% canary
        loop Every 60s for 60min
            CI->>Prom: Check thresholds
        end
        CI->>K8s: Full rollout (100%)
        CI->>Dev: ✅ Deployment successful
    else Metrics Degraded
        CI->>K8s: Rollback (0% canary)
        CI->>PD: Alert: Canary failed
        CI->>Dev: ❌ Rollback triggered
    end
```

## 5. Rollback Decision Tree

```mermaid
flowchart TD
    A[Quality Degradation Detected] --> B{Which component changed?}
    
    B -->|Prompt Change| C[Rollback Prompt ConfigMap]
    B -->|Model Change| D[Rollback AI Gateway Config]
    B -->|Retriever Change| E[Rollback Collection Version]
    B -->|Code Change| F[Rollback K8s Deployment]
    B -->|Multiple| G[Composite Rollback]
    
    C --> C1[kubectl set configmap<br/>prompt-configs -> v_prev]
    C1 --> C2[Pods reload prompts<br/>via volume mount]
    C2 --> V{Verify Recovery}
    
    D --> D1[Update AI Gateway<br/>routing config]
    D1 --> D2[Switch to previous<br/>model version]
    D2 --> V
    
    E --> E1[Update COLLECTION_NAME<br/>env var]
    E1 --> E2[Rolling restart of<br/>retrieval service]
    E2 --> V
    
    F --> F1[kubectl rollout undo<br/>deployment/service]
    F1 --> V
    
    G --> G1[Load previous<br/>deployment bundle]
    G1 --> G2[Rollback all components<br/>to bundle state]
    G2 --> V
    
    V -->|Recovered| H[✅ Close Incident]
    V -->|Still Degraded| I[Escalate to<br/>On-Call Engineer]
    
    style C1 fill:#ffa,color:#000
    style D1 fill:#ffa,color:#000
    style E1 fill:#ffa,color:#000
    style F1 fill:#ffa,color:#000
    style H fill:#4a4,color:#fff
    style I fill:#f44,color:#fff
```

## 6. Multi-Environment Strategy

```mermaid
graph LR
    subgraph "Development"
        DEV_CODE[Code] --> DEV_TEST[Unit Tests]
        DEV_TEST --> DEV_EVAL[Quick Eval<br/>10 samples]
        DEV_ENV[Environment:<br/>- GPT-3.5<br/>- In-memory VDB<br/>- 1 replica<br/>- Synthetic data]
    end

    subgraph "Staging"
        STG_DEPLOY[Deploy] --> STG_EVAL[Full Eval<br/>500 samples]
        STG_EVAL --> STG_SAFETY[Safety Eval]
        STG_SAFETY --> STG_INTEG[Integration Tests]
        STG_ENV[Environment:<br/>- GPT-4o<br/>- Qdrant single<br/>- 2 replicas<br/>- Anonymized data]
    end

    subgraph "Production"
        PRD_CANARY[Canary 5%] --> PRD_MONITOR[Monitor]
        PRD_MONITOR --> PRD_FULL[Full Rollout]
        PRD_ENV[Environment:<br/>- GPT-4o<br/>- Qdrant cluster<br/>- 5+ replicas<br/>- Real data]
    end

    DEV_EVAL -->|PR Merge| STG_DEPLOY
    STG_INTEG -->|Approval| PRD_CANARY
```

## 7. Infrastructure Architecture

```mermaid
graph TB
    subgraph "AWS Region (us-east-1)"
        subgraph "VPC (10.0.0.0/16)"
            subgraph "Public Subnets"
                ALB[Application<br/>Load Balancer]
                NAT[NAT Gateway]
            end
            
            subgraph "Private Subnet AZ-A"
                EKS_A[EKS Node]
                RDS_A[(Aurora<br/>Primary)]
                REDIS_A[(Redis<br/>Primary)]
            end
            
            subgraph "Private Subnet AZ-B"
                EKS_B[EKS Node]
                RDS_B[(Aurora<br/>Reader)]
                REDIS_B[(Redis<br/>Replica)]
            end
            
            subgraph "Private Subnet AZ-C"
                EKS_C[EKS Node]
                REDIS_C[(Redis<br/>Replica)]
            end
        end
        
        S3[(S3<br/>Documents)]
        SM[Secrets<br/>Manager]
        KMS[KMS]
        ECR[ECR]
        CW[CloudWatch]
    end
    
    INET[Internet] --> ALB
    ALB --> EKS_A & EKS_B & EKS_C
    EKS_A & EKS_B & EKS_C --> NAT --> INET
    EKS_A --> RDS_A & REDIS_A & S3
    EKS_B --> RDS_B & REDIS_B & S3
    SM --> KMS
```

## 8. Deployment Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Pending: Bundle created
    
    Pending --> Building: CI triggered
    Building --> Testing: Build success
    Building --> Failed: Build failure
    
    Testing --> Evaluating: Tests pass
    Testing --> Failed: Tests fail
    
    Evaluating --> Approved: Eval pass + Safety pass
    Evaluating --> Failed: Eval below threshold
    
    Approved --> Staging: Auto-deploy
    Staging --> IntegrationTesting: Deploy success
    Staging --> Failed: Deploy failure
    
    IntegrationTesting --> ReadyForProd: Integration pass
    IntegrationTesting --> Failed: Integration fail
    
    ReadyForProd --> Canary1Pct: Manual approval
    Canary1Pct --> Canary5Pct: Metrics OK (15min)
    Canary1Pct --> RolledBack: Metrics degraded
    
    Canary5Pct --> Canary25Pct: Metrics OK (30min)
    Canary5Pct --> RolledBack: Metrics degraded
    
    Canary25Pct --> FullRollout: Metrics OK (60min)
    Canary25Pct --> RolledBack: Metrics degraded
    
    FullRollout --> [*]: Complete
    RolledBack --> [*]: Incident created
    Failed --> [*]: Notification sent
```
