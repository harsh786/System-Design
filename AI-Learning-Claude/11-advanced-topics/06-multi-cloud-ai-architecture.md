# Multi-Cloud AI Architecture

## Why Multi-Cloud for AI?

**Analogy:** Using a single cloud is like shopping at one store — convenient but you're limited to their selection and prices. Multi-cloud is like having memberships at multiple stores — you pick the best product from each.

**Reasons for multi-cloud AI:**
- **Avoid vendor lock-in:** If Azure OpenAI has an outage, fall back to AWS Bedrock
- **Best-of-breed:** Use Azure for OpenAI models, AWS for infrastructure, GCP for Gemini
- **Regulatory compliance:** EU data on EU cloud, US data on US cloud
- **Negotiating leverage:** "We can move workloads" is powerful in pricing discussions
- **Capacity:** During GPU shortages, spread across providers

---

## AI Services by Cloud Provider

| Capability | AWS | Azure | GCP |
|-----------|-----|-------|-----|
| **LLM Platform** | Bedrock | Azure OpenAI | Vertex AI |
| **Model Garden** | Bedrock (Anthropic, Meta) | AI Studio (OpenAI, Meta) | Model Garden (Gemini, Claude) |
| **Vector Search** | OpenSearch | AI Search | Vertex Vector Search |
| **ML Platform** | SageMaker | Azure ML | Vertex AI |
| **Document AI** | Textract | Document Intelligence | Document AI |
| **Speech** | Transcribe/Polly | Speech Services | Speech-to-Text/TTS |
| **Database** | DynamoDB, Aurora | Cosmos DB, SQL | AlloyDB, Firestore |
| **Serverless** | Lambda | Functions | Cloud Run/Functions |
| **Orchestration** | Step Functions | Durable Functions | Workflows |

### Provider Strengths

```mermaid
flowchart TD
    subgraph AWS
        A1[Best infrastructure breadth]
        A2[SageMaker for custom ML]
        A3[Bedrock multi-model access]
    end
    
    subgraph Azure
        B1[OpenAI exclusive partnership]
        B2[Enterprise integration M365]
        B3[Strongest compliance/governance]
    end
    
    subgraph GCP
        C1[Gemini native models]
        C2[Best data/analytics BigQuery]
        C3[Kubernetes leadership GKE]
    end
```

---

## Multi-Cloud Patterns

### Pattern 1: Primary + Fallback

```mermaid
flowchart TD
    A[AI Request] --> B[Primary: Azure OpenAI]
    B --> C{Available?}
    C -->|Yes| D[Return Response]
    C -->|No/Timeout| E[Fallback: AWS Bedrock]
    E --> D
    
    style B fill:#e3f2fd
    style E fill:#fff3e0
```

**Implementation:** Circuit breaker pattern. If primary fails 3 times in 60 seconds, route all traffic to fallback for 5 minutes, then retry primary.

### Pattern 2: Best-of-Breed Per Capability

```
LLM Inference → Azure (OpenAI GPT-4)
Vector Search → AWS (OpenSearch)
Data Pipeline → GCP (BigQuery + Dataflow)
Monitoring → AWS (CloudWatch) + Datadog
```

### Pattern 3: Geographic Distribution

```mermaid
flowchart LR
    subgraph US Region
        A[AWS us-east-1]
        B[US Users]
    end
    
    subgraph EU Region
        C[Azure West Europe]
        D[EU Users - GDPR]
    end
    
    subgraph APAC Region
        E[GCP asia-east1]
        F[APAC Users]
    end
    
    B --> A
    D --> C
    F --> E
```

### Pattern 4: Abstraction Layer

```mermaid
flowchart TD
    A[Application] --> B[Unified AI Gateway]
    
    B --> C[Azure OpenAI]
    B --> D[AWS Bedrock]
    B --> E[GCP Vertex AI]
    B --> F[Self-hosted Ollama]
    
    B --> G[Load Balancer / Router]
    G --> H{Routing Rules}
    H -->|Cost optimization| D
    H -->|Quality priority| C
    H -->|Specific model| E
    
    style B fill:#fff3e0
```

**Tools for abstraction:**
- **LiteLLM:** Unified Python API for 100+ LLM providers
- **OpenRouter:** API gateway for multiple providers
- **Custom gateway:** Your own router with provider-specific adapters

---

## Challenges

### 1. Data Residency and Transfer

```
Problem: Your data is in AWS S3, your AI model is in Azure.
Cost: Data transfer between clouds = $0.02-0.09/GB
Latency: Cross-cloud adds 20-100ms
Compliance: Some data cannot legally cross borders
```

**Solution:** Replicate critical data to each cloud, or process data where it lives.

### 2. Inconsistent APIs

```python
# Azure OpenAI
client = AzureOpenAI(azure_endpoint="...", api_version="2024-02-01")

# AWS Bedrock  
client = boto3.client('bedrock-runtime')
response = client.invoke_model(modelId="anthropic.claude-3-sonnet...")

# GCP Vertex AI
model = GenerativeModel("gemini-1.5-pro")
response = model.generate_content("...")
```

Three completely different APIs for the same operation. This is why abstraction layers exist.

### 3. Credential Management

Each cloud has its own identity system:
- AWS: IAM roles, access keys
- Azure: Entra ID, managed identities
- GCP: Service accounts, workload identity

**Solution:** Use a secrets manager (HashiCorp Vault) that works across clouds.

### 4. Cost Tracking

```
Problem: "How much did our AI spend last month?"
Reality: Invoices from 3 clouds, different billing models,
         different units, different billing cycles.
```

**Solution:** Unified cost management (CloudHealth, Spot.io) + tagging strategy across all clouds.

### 5. Network Latency Between Clouds

```
Same region, same cloud: ~1ms
Same region, different cloud: ~5-20ms  
Different region, same cloud: ~50-150ms
Different region, different cloud: ~100-300ms
```

---

## The Abstraction Layer Pattern (In Detail)

```python
# Unified interface - application code never touches provider SDKs directly

class AIGateway:
    def complete(self, messages, model="default", **kwargs):
        provider = self.router.select_provider(model, kwargs)
        
        try:
            return provider.complete(messages, **kwargs)
        except ProviderError:
            fallback = self.router.get_fallback(provider)
            return fallback.complete(messages, **kwargs)
    
    def embed(self, texts, model="default"):
        provider = self.router.select_provider(model, task="embedding")
        return provider.embed(texts)
```

**Routing strategies:**
- **Cost:** Send to cheapest available provider
- **Latency:** Send to fastest responding provider
- **Quality:** Send to highest-quality model
- **Load:** Distribute across providers to avoid rate limits
- **Compliance:** Route based on data classification

---

## Vendor Exit Strategy

Design for portability from day one:

1. **Abstract provider APIs** — never call cloud SDKs directly from business logic
2. **Use open formats** — ONNX for models, OpenTelemetry for observability
3. **Containerize everything** — Docker + Kubernetes work on all clouds
4. **Store data in portable formats** — Parquet, not proprietary formats
5. **Document dependencies** — know exactly what you use from each cloud
6. **Test migration regularly** — run the same workload on two clouds quarterly

---

## Multi-Cloud AI Topology

```mermaid
flowchart TB
    subgraph Application Layer
        A[Web App] --> B[AI Gateway / LiteLLM]
    end
    
    subgraph Routing Layer
        B --> C{Router}
        C -->|GPT-4| D[Azure OpenAI]
        C -->|Claude| E[AWS Bedrock]
        C -->|Gemini| F[GCP Vertex AI]
        C -->|Local/Private| G[Self-hosted]
    end
    
    subgraph Data Layer
        H[Primary: AWS S3] ---|Replicate| I[Azure Blob]
        H ---|Replicate| J[GCP GCS]
    end
    
    subgraph Observability
        K[OpenTelemetry Collector]
        D --> K
        E --> K
        F --> K
        G --> K
        K --> L[Unified Dashboard]
    end
```

---

## Key Takeaways

1. **Multi-cloud is about resilience and choice**, not using everything everywhere
2. **Start with primary + fallback** — simplest pattern with highest value
3. **Abstraction layers** (LiteLLM, custom gateway) are essential — never call providers directly
4. **Data gravity wins** — process data where it lives, don't move it unnecessarily
5. **Credential management** is the hardest operational problem in multi-cloud
6. **Design for exit** from day one — assume you'll want to switch providers
7. **Most teams start single-cloud** and add a second cloud for specific capabilities or resilience

---

## Next Steps

- Multi-cloud patterns combine naturally with [MLOps Integration](./07-mlops-integration.md) for unified operations
- Consider [Edge AI](./05-edge-and-on-device-ai.md) as another "cloud" in your topology

---

## Anti-Patterns

### 1. Multi-Cloud for Its Own Sake

**What goes wrong:** Team adopts multi-cloud because "it's best practice" without a specific driver. Result: 3x operational complexity, 3x the expertise needed, 2x the cost, slower delivery, more failure modes — all for theoretical resilience they've never needed.

**Reality check questions:**
- Has your primary cloud had an outage affecting you in the last 2 years?
- Do you have the team to operate across multiple clouds? (Each cloud needs specialists)
- Is the portability cost worth more than the single-cloud discount?

**Fix:** Start single-cloud. Add a second cloud only when you have a specific, quantifiable reason (regulatory, specific service unavailable, proven reliability need).

### 2. Different Patterns Per Cloud (Inconsistent)

**What goes wrong:** AWS team uses one architecture pattern, Azure team uses another. No shared learnings, no portable skills, debugging requires cloud-specific expertise. Incident response is fragmented.

**Fix:**
- Define canonical patterns that work across clouds (e.g., "all services are containers, all use OpenTelemetry")
- Cloud-specific implementations of shared interfaces
- Shared runbooks with cloud-specific sections
- Cross-cloud architecture reviews

### 3. No Abstraction Layer

**What goes wrong:** Business logic directly calls `boto3`, `azure-sdk`, or `google-cloud` clients. Switching providers means rewriting application code. Testing requires actual cloud resources.

**Fix:**
- Provider-specific code lives in adapter/infrastructure layer only
- Business logic talks to interfaces, not implementations
- Can swap providers by changing config, not code
- Enables local testing with mock providers

### 4. Vendor-Specific Features Everywhere

**What goes wrong:** Team uses Azure Durable Functions orchestration, AWS Step Functions expressions, GCP-specific IAM patterns in core logic. Each feature creates a migration barrier. Switching cost grows exponentially over time.

**When vendor-specific IS acceptable:**
- Commodity infrastructure (compute, storage) — easy to replace
- Non-differentiating features where the switching cost is truly low

**When to avoid vendor-specific:**
- Core business logic and orchestration
- Data storage formats (use Parquet, not proprietary)
- Observability (use OpenTelemetry, not cloud-native only)
- Identity (consider cross-cloud identity federation)

---

## Key Trade-offs

### Multi-Cloud (Resilient, Complex) vs Single-Cloud (Simple, Risk)

| Factor | Multi-Cloud | Single-Cloud |
|--------|-------------|--------------|
| Resilience | High (survive provider outage) | Low (single point of failure) |
| Operational complexity | 3x+ (three sets of everything) | Baseline |
| Team expertise needed | Broad (specialists per cloud) | Deep (one cloud mastery) |
| Cost | Higher (no volume discounts, data transfer) | Lower (committed use discounts) |
| Vendor negotiation | Strong ("we can leave") | Weak (switching cost is leverage for them) |
| Time to market | Slower (abstractions, compatibility) | Faster (use native features freely) |
| Best for | Large enterprises, regulated industries | Startups, small-medium teams |

**Decision:** Single-cloud until you hit one of these triggers:
1. Regulatory requirement mandates geographic/provider diversity
2. A specific service is only available on another cloud (e.g., Azure OpenAI)
3. You've experienced outages with real business impact
4. You're large enough to have dedicated platform teams per cloud

### Portability Overhead vs Vendor Optimization

```
Spectrum:
  Full portability ←————————————————→ Full vendor optimization
  (everything abstracted,              (use every cloud-native feature,
   runs anywhere,                       maximum performance,
   slower to build,                     fastest to build,
   may miss optimizations)              impossible to migrate)
```

**Practical middle ground:**
- Abstract at the AI/LLM layer (use LiteLLM or similar) — high portability value, low cost
- Go native for infrastructure (compute, networking) — low portability value, high optimization benefit
- Abstract data formats (Parquet, ONNX) — moderate effort, high long-term value
- Go native for managed services you'd never self-host — the time savings outweigh lock-in risk

**Rule of thumb:** Abstract where switching is likely (model providers change fast). Go native where switching is unlikely (you won't move your entire database next year).
