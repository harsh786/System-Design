# Platform Team and Organizational Design for AI

## Team Topology for AI Platforms

Borrowing from the "Team Topologies" framework, an AI organization needs four types of teams:

```mermaid
graph TB
    subgraph "Platform Team"
        PT[Builds shared AI infrastructure<br/>Gateway, Registries, Pipelines]
    end

    subgraph "Enabling Team"
        ET[Helps product teams adopt AI<br/>Training, Best practices, Templates]
    end

    subgraph "Product AI Teams"
        PA[Team A: Customer Support AI]
        PB[Team B: Internal Search]
        PC[Team C: Document Analysis]
    end

    subgraph "AI SRE Team"
        SRE[Operates the platform<br/>On-call, Incidents, Capacity]
    end

    PT -->|provides platform| PA & PB & PC
    ET -->|enables| PA & PB & PC
    SRE -->|operates| PT
    PA & PB & PC -->|feedback| PT & ET
```

### Platform Team (Builds Shared Infrastructure)
**Mission:** Build and maintain the AI platform so product teams don't reinvent the wheel.

**Owns:**
- AI Gateway
- Model/Prompt/Tool registries
- Data pipelines and vector infrastructure
- Evaluation framework
- Observability stack
- Cost management

**Analogy:** The platform team is like the city's public works department. They build roads, water systems, and electricity grids. Individual businesses (product teams) use this infrastructure to serve customers.

### Enabling Team (Helps Product Teams Adopt AI)
**Mission:** Accelerate AI adoption across the organization.

**Does:**
- Create templates and starter kits
- Run internal training and workshops
- Review AI architectures from product teams
- Write best-practice guides
- Help teams with their first AI project

**Analogy:** They're the consultants who help you move into a new house. They know all the tricks, have the tools, and get you productive fast.

### Product AI Teams (Build Features Using the Platform)
**Mission:** Deliver AI-powered features to end users.

**Does:**
- Build domain-specific AI applications
- Write prompts and evaluation sets for their domain
- Define data sources and quality requirements
- Own the user experience

**Analogy:** Restaurants that use the city's water and electricity to serve food. They focus on the food (product), not the plumbing (platform).

### AI SRE Team (Operates the Platform)
**Mission:** Keep the AI platform running reliably.

**Does:**
- On-call rotation for AI infrastructure
- Incident response and post-mortems
- Capacity planning and scaling
- Cost optimization
- Performance tuning

## Roles in an AI Platform Team

| Role | Responsibility | Key Skills |
|------|---------------|------------|
| **AI Architect** | System design, technical strategy, ADRs | Broad AI knowledge, system design, trade-off analysis |
| **ML Engineers** | Model integration, fine-tuning, evaluation | Python, ML frameworks, evaluation methodology |
| **Data Engineers** | Pipelines, data quality, vector management | ETL, streaming, databases, data modeling |
| **Platform Engineers** | Gateway, APIs, infrastructure | Go/Rust/Python, K8s, distributed systems |
| **SRE** | Reliability, monitoring, incident response | Observability, on-call, capacity planning |
| **Security Engineer** | PII, access control, threat modeling | AppSec, compliance, cryptography |
| **Product Manager** | Prioritization, roadmap, stakeholder management | Technical PM skills, AI literacy |

### Minimum Viable Team (Startup / Early Stage)
- 1 AI Architect (part-time, also codes)
- 2 Full-stack engineers (build everything)
- 1 Data engineer (pipelines)
Total: 3-4 people

### Growth Stage Team
- 1 AI Architect
- 3 Platform engineers (gateway, APIs)
- 2 ML engineers (evaluation, optimization)
- 2 Data engineers (pipelines, quality)
- 1 SRE
Total: 9-10 people

### Enterprise Team
- 2 AI Architects (strategy + hands-on)
- 5 Platform engineers
- 3 ML engineers
- 3 Data engineers
- 2 SREs
- 1 Security engineer
- 1 Product manager
Total: 17-18 people

## Conway's Law Applied to AI

> "Organizations design systems that mirror their communication structures." — Melvin Conway

**Implication for AI:**

```
Siloed Org:                          Unified Org:
┌──────────┐ ┌──────────┐           ┌─────────────────────┐
│ Team A   │ │ Team B   │           │  AI Platform Team   │
│ Own LLM  │ │ Own LLM  │           │  Shared Gateway     │
│ Own Data │ │ Own Data │           │  Shared Data Layer  │
│ Own Eval │ │ Own Eval │           └─────────────────────┘
└──────────┘ └──────────┘                    │
                                    ┌────────┼────────┐
Result: Duplicated effort,          │ Team A │ Team B │
inconsistent quality,               │(product│(product│
no shared learning                  │ logic) │ logic) │
                                    └────────┴────────┘
                                    Result: Shared infra,
                                    consistent quality,
                                    cross-team learning
```

**If your org is siloed, your AI will be siloed.** You'll end up with 5 different AI gateways, 5 different evaluation approaches, and 5 different data pipelines — all slightly broken in different ways.

## Build vs Buy Decisions

| Component | Build When | Buy When |
|-----------|-----------|----------|
| **AI Gateway** | Custom routing logic needed, strict data control | Standard features suffice, speed to market |
| **Vector DB** | Almost never build | Always buy (Pinecone, Weaviate, pgvector) |
| **Evaluation** | Custom domain metrics needed | Standard NLP metrics suffice |
| **Observability** | Never build from scratch | Langfuse, LangSmith, Datadog |
| **Data Pipelines** | Custom connectors needed | Standard sources (use Airbyte, Fivetran) |
| **Prompt Registry** | Deep workflow integration | Standalone usage (use Humanloop) |

**The golden rule:** Build what differentiates you. Buy everything else.

## Skills Matrix

What skills does your team need?

| Skill | Platform | Enabling | Product AI | SRE |
|-------|----------|----------|------------|-----|
| Prompt engineering | Medium | High | High | Low |
| System design | High | Medium | Medium | Medium |
| Python/Go | High | Medium | High | Medium |
| Kubernetes | High | Low | Low | High |
| Data engineering | High | Medium | Medium | Low |
| ML/evaluation | Medium | High | High | Low |
| Security | High | Medium | Low | Medium |
| Communication | Medium | High | Medium | Low |

## Organizational Change Management

AI adoption requires cultural change, not just technical change:

### 1. Executive Sponsorship
AI platform needs C-level support. Without it, teams won't adopt the platform — they'll keep doing their own thing.

### 2. Incentive Alignment
- Don't penalize teams for using the platform (even if slower initially)
- Reward platform contributions (shared tools, eval datasets)
- Make platform adoption the path of least resistance

### 3. Education Programs
- "AI Fundamentals" for all engineers
- "AI Platform 101" for teams starting AI projects
- "Advanced AI Architecture" for tech leads
- Regular demos of what the platform enables

### 4. Inner Source Model
- Platform code is visible to all teams
- Product teams can contribute back
- Platform team reviews and merges contributions
- Shared ownership increases adoption

### 5. Success Stories
- Publicize wins: "Team X shipped in 2 weeks using the platform (vs 3 months before)"
- Share metrics: "Platform saved $500K in duplicate infrastructure this quarter"

## Maturity-Based Team Evolution

```mermaid
graph LR
    A[Phase 1<br/>3-4 people<br/>Build gateway + basic pipeline] --> B[Phase 2<br/>6-8 people<br/>Add registries + eval framework]
    B --> C[Phase 3<br/>10-15 people<br/>Add enabling team + SRE]
    C --> D[Phase 4<br/>15-20 people<br/>Full platform org]
```

| Phase | Team Size | Focus | Duration |
|-------|-----------|-------|----------|
| **1. Foundation** | 3-4 | Gateway, basic pipeline, first use case | 3-6 months |
| **2. Standardize** | 6-8 | Registries, evaluation, observability | 6-12 months |
| **3. Scale** | 10-15 | Enable multiple teams, SRE practices | 6-12 months |
| **4. Optimize** | 15-20 | Self-service, automation, cost optimization | Ongoing |

## Key Takeaways

1. **Start with a platform team of 3-4** — don't wait until you "need" a big team
2. **The enabling team is as important as the platform team** — adoption > features
3. **Conway's Law is real** — org structure determines AI architecture quality
4. **Build what differentiates, buy everything else** — don't build vector DBs
5. **Cultural change is harder than technical change** — invest in education and incentives
6. **Grow the team with maturity** — don't hire 20 people on day one
7. **Product teams own their AI quality** — the platform enables, it doesn't guarantee
