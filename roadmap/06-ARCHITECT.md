# Stage 6: Senior AI/ML Architect

> Duration: 6-12+ months (and truthfully, never complete) | Output: Architecture docs, team leadership, strategic decisions

---

## What Changes at This Level

Everything before this was about building competence. This stage is about
building JUDGMENT. The transition feels different because there's less
"learn X tool" and more "learn to think about systems."

```
The Architect's Job:

1. See the whole board (not just your model)
2. Make decisions that are expensive to reverse (and get them right)
3. Translate business problems into technical architectures
4. Manage complexity across teams and timelines
5. Say "no" to technically cool but strategically wrong ideas
6. Anticipate failures before they happen
7. Make tradeoffs explicit (cost vs latency vs accuracy vs team effort)
```

---

## The Architect's Thinking Framework

```
When someone says "we need an ML system for X", you ask:

┌─────────────────────────────────────────────────────────────────────┐
│  ARCHITECT'S DECISION FRAMEWORK                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. DO WE EVEN NEED ML?                                             │
│     ├── Can rules/heuristics solve 80% of this?                     │
│     ├── Is there enough data to learn from?                         │
│     ├── Is the problem well-defined enough?                         │
│     └── What's the cost of getting it wrong?                        │
│                                                                     │
│  2. WHAT'S THE SIMPLEST THING THAT WORKS?                           │
│     ├── Start with logistic regression / XGBoost                    │
│     ├── Establish a strong baseline before going deep               │
│     ├── Can we use an existing API/service?                         │
│     └── Ship fast, iterate based on real feedback                   │
│                                                                     │
│  3. WHAT ARE THE CONSTRAINTS?                                        │
│     ├── Latency budget (p99 < ___ms)                                │
│     ├── Cost budget (monthly inference cost < $___K)                │
│     ├── Team capacity (who builds this? who maintains it?)          │
│     ├── Data availability (how much? how fresh? how clean?)         │
│     ├── Regulatory (GDPR, HIPAA, EU AI Act, explainability)        │
│     └── Timeline (when must this ship?)                             │
│                                                                     │
│  4. WHAT'S THE 2-YEAR VISION?                                       │
│     ├── Where does this system go next?                             │
│     ├── What adjacent systems will be built?                        │
│     ├── What scale will we reach?                                   │
│     └── What should we NOT build now but prepare for?               │
│                                                                     │
│  5. WHAT CAN GO WRONG?                                              │
│     ├── Data pipeline failures                                       │
│     ├── Model degradation over time                                 │
│     ├── Adversarial inputs / gaming                                 │
│     ├── Bias and fairness issues                                    │
│     ├── Cost explosion at scale                                     │
│     └── Single points of failure                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Month 1-3: System Design for ML

### ML System Design Patterns

```
PATTERN 1: The Prediction Service
─────────────────────────────────
User request → Feature lookup → Model inference → Response

Used for: fraud detection, recommendations, search ranking, pricing
Key decisions: real-time vs batch, feature freshness, fallback strategy

Example architecture:
┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────┐
│  Client  │───▶│  API Gateway │───▶│ Feature Store│───▶│  Model   │
│          │◀───│  (rate limit)│◀───│  (Redis+DWH) │◀───│  Server  │
└──────────┘    └─────────────┘    └──────────────┘    └──────────┘
                                          ▲
                                          │
                                   ┌──────────────┐
                                   │ Batch Feature │
                                   │ Pipeline (DAG)│
                                   └──────────────┘


PATTERN 2: The Content Understanding Pipeline
──────────────────────────────────────────────
Content arrives → Multiple models process → Metadata stored → Powers downstream

Used for: content moderation, search indexing, recommendation features
Key decisions: sync vs async, model composition, cost per item

Example: Video platform
┌──────────┐    ┌──────────────────────────────────────────────────┐
│  Upload  │───▶│  Processing Pipeline                              │
│          │    │  ┌───────┐  ┌────────┐  ┌───────┐  ┌──────────┐│
│          │    │  │ Frame │─▶│ Object │─▶│ Text  │─▶│ Toxicity ││
│          │    │  │Extract│  │ Detect │  │  OCR  │  │ Classify ││
│          │    │  └───────┘  └────────┘  └───────┘  └──────────┘│
│          │    └────────────────────────────────┬─────────────────┘
└──────────┘                                     │
                                                 ▼
                                    ┌───────────────────────┐
                                    │  Metadata Store       │
                                    │  (powers search,      │
                                    │   recommendations,    │
                                    │   moderation)         │
                                    └───────────────────────┘


PATTERN 3: The Retrieval + Generation System (RAG at Scale)
────────────────────────────────────────────────────────────
Query → Retrieval → Reranking → Generation → Response

Used for: enterprise search, customer support, knowledge bases
Key decisions: embedding model, chunking strategy, generation model, grounding

Example:
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐
│  Query   │───▶│ Embed +  │───▶│   Rerank     │───▶│ Generate │
│          │    │ Retrieve │    │ (cross-enc.) │    │  (LLM)   │
│          │    │ (ANN)    │    │              │    │          │
└──────────┘    └──────────┘    └──────────────┘    └──────────┘
                      │                                    │
                      ▼                                    ▼
               ┌──────────────┐                   ┌──────────────┐
               │ Vector Index  │                   │ Guardrails + │
               │ + BM25 Index  │                   │ Citations    │
               └──────────────┘                   └──────────────┘


PATTERN 4: The Training Platform
─────────────────────────────────
Data versioned → Features computed → Models trained → Best promoted → Deployed

Used for: companies with many ML models (Uber, Airbnb, Netflix scale)
Key decisions: shared compute, model reuse, standardization vs flexibility

PATTERN 5: The Multi-Model Orchestration
──────────────────────────────────────────
Single request triggers multiple models that collaborate

Used for: autonomous driving, complex agents, multi-step reasoning
Key decisions: model dependencies, failure handling, latency budget allocation

Example: Autonomous agent
┌──────────────────────────────────────────────────────────────┐
│  Orchestrator                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │  Planning    │───▶│  Execution   │───▶│  Verification  │  │
│  │  (LLM)      │    │  (Tool Use)  │    │  (Eval Model)  │  │
│  └─────────────┘    └──────────────┘    └────────────────┘  │
│         ▲                    │                    │           │
│         └────────────────────┴────────────────────┘           │
│                        (feedback loop)                        │
└──────────────────────────────────────────────────────────────┘
```

### How to Practice System Design

```
Method: Design a system in 45-60 minutes (interview style)

1. Clarify requirements (5 min)
   - What's the user-facing behavior?
   - Scale: how many users, how many requests, how much data?
   - Latency: what's acceptable?
   - Accuracy: what's the cost of a wrong prediction?

2. High-level architecture (10 min)
   - Draw the boxes and arrows
   - Identify data flow
   - Identify computational requirements

3. Dive deep on 2-3 components (20 min)
   - Model selection and training strategy
   - Serving architecture
   - Data pipeline

4. Handle edge cases and failures (10 min)
   - What happens when a model is wrong?
   - What happens under load?
   - What happens when data is late/missing?

5. Discuss tradeoffs and alternatives (5 min)
   - Why this approach over alternatives?
   - What would you change at 10x scale?
```

### System Design Practice Problems

Do these on a whiteboard or blank page. 45 minutes each.

```
BEGINNER:
├── Design a spam classifier system (Gmail scale)
├── Design a movie recommendation system (Netflix)
├── Design an image classification service (moderation)
└── Design a search ranking system (Bing/Google simplified)

INTERMEDIATE:
├── Design a real-time fraud detection system (Stripe)
├── Design a news feed ranking system (Twitter/X)
├── Design an LLM-powered customer support system
├── Design a visual search system (Pinterest)
├── Design an ad click prediction system (at scale)
└── Design a content moderation pipeline (YouTube)

ADVANCED:
├── Design a self-driving perception system
├── Design a multi-tenant ML platform (shared across 50 teams)
├── Design a real-time pricing system (Uber surge pricing)
├── Design an AI agent system with tool use
├── Design a multimodal search system (text + image + video)
└── Design a recommendation system that handles cold-start gracefully
```

**Resources:**

| Resource | Why | Link |
|----------|-----|------|
| "Designing ML Systems" - Chip Huyen | THE bible for ML system design | Book (2022) |
| "Designing Data-Intensive Applications" - Kleppmann | General systems, required reading | Book |
| ML System Design Interview (Pham/Nguyen) | Practice problems with solutions | Book |
| Stanford CS329S: ML Systems Design | Chip Huyen's Stanford course | https://stanford-cs329s.github.io/ |
| Eugene Yan's blog (Applied ML) | Senior ML eng thinking | https://eugeneyan.com/ |
| Netflix Tech Blog | ML at scale | https://netflixtechblog.com/ |
| Uber Engineering Blog | ML infra | https://www.uber.com/blog/engineering/ |
| Google Research Blog | Cutting edge systems | https://ai.googleblog.com/ |

---

## Month 4-6: Architecture Decisions & Tradeoffs

### The Tradeoff Matrix (What Architects Actually Decide)

```
┌────────────────────┬─────────────────────────────────────────────────────┐
│ Decision           │ Tradeoffs                                            │
├────────────────────┼─────────────────────────────────────────────────────┤
│ Real-time vs Batch │ Latency vs cost vs complexity                       │
│ Build vs Buy       │ Control vs speed vs maintenance burden              │
│ Single vs Multi    │ Specialization vs overhead vs flexibility           │
│   model            │                                                     │
│ On-prem vs Cloud   │ Cost (long-term) vs flexibility vs compliance      │
│ Custom vs OSS vs   │ Fit vs effort vs vendor lock-in                    │
│   managed          │                                                     │
│ Accuracy vs Speed  │ More compute vs user experience                    │
│ Simple vs Complex  │ Maintainability vs performance ceiling             │
│ Centralized vs     │ Consistency vs team autonomy                       │
│   Federated ML     │                                                     │
│ Retrain frequency  │ Freshness vs compute cost vs stability             │
│ Model size         │ Accuracy vs latency vs cost vs deployment target   │
└────────────────────┴─────────────────────────────────────────────────────┘
```

### Technology Strategy (What to Standardize, What to Leave Flexible)

```
STANDARDIZE (enforce across all teams):
├── Experiment tracking tool (everyone uses W&B/MLflow)
├── Model registry and versioning
├── Deployment pipeline (CI/CD)
├── Monitoring and alerting
├── Data catalog and lineage
├── Security and access control
└── Cost reporting

LEAVE FLEXIBLE (let teams choose):
├── Framework (PyTorch vs TensorFlow vs JAX)
├── Model architecture (team knows their domain best)
├── Hyperparameter tuning approach
├── Feature engineering methods
└── Programming language for non-serving code

THE MIDDLE GROUND (guide but don't enforce):
├── Serving infrastructure (offer a default, allow exceptions)
├── Feature store (offer shared, allow team-specific)
├── Data processing (recommend Spark/Beam, don't mandate)
└── Cloud services (prefer managed, allow raw compute)
```

---

## Month 7-9: Leadership and Communication

### Technical Leadership (Not People Management)

```
What a Senior Architect does day-to-day:
├── Monday: Review architecture proposals from 3 teams
├── Tuesday: Deep-dive on performance issue in production
├── Wednesday: Write design doc for new platform capability
├── Thursday: Interview senior ML engineers, mentor junior staff
├── Friday: Research spike on new technology, present findings
├── Ongoing: PR reviews, design reviews, on-call escalation

Skills to develop:
├── Writing
│   ├── Design documents (problem, options, recommendation, tradeoffs)
│   ├── Architecture Decision Records (ADRs)
│   ├── RFCs (Request for Comments)
│   ├── Post-mortems (blameless, actionable)
│   └── Technical blog posts (internal and external)
├── Communication
│   ├── Explain ML to non-technical stakeholders
│   ├── Present tradeoffs clearly (not just your recommendation)
│   ├── Say "I don't know, but here's how I'd find out"
│   ├── Disagree constructively with data
│   └── Run effective design reviews
├── Mentoring
│   ├── Help others grow (not do their work for them)
│   ├── Code/design review as teaching moments
│   ├── Create learning paths for your team
│   └── Delegate INTERESTING work (not just grunt work)
└── Strategy
    ├── Technology radar (what to adopt, what to hold)
    ├── Build vs buy analysis
    ├── Hiring plan (what skills does the team need?)
    ├── Technical debt prioritization
    └── Roadmap input (what's feasible, what's not)
```

### The Design Document Template

```markdown
# Design: [System Name]

## Context and Problem Statement
What is the problem? Why does it need solving now?

## Requirements
- Functional: What must it do?
- Non-functional: Scale, latency, cost, reliability targets
- Constraints: Regulatory, timeline, team

## Options Considered
### Option A: [Name]
- Description
- Pros
- Cons
- Estimated effort

### Option B: [Name]
- Same structure

### Option C: [Name]
- Same structure

## Recommendation
Which option and WHY. Be specific about tradeoffs.

## Architecture
Diagram + explanation of components.

## Data Flow
How data moves through the system.

## Failure Modes
What can go wrong? How do we handle each?

## Migration Plan
How do we get from current state to this?

## Success Metrics
How do we know this is working?

## Open Questions
What don't we know yet?
```

---

## Month 10-12: Staying Current (Forever)

### The Architect's Learning System

```
Weekly:
├── Read 3-5 papers (skim many, deep-read 1-2)
├── Follow ML Twitter/X (curated list of researchers)
├── Read 2-3 blog posts from industry (Netflix, Google, Uber, Meta)
└── Experiment with one new tool/technique

Monthly:
├── Deep-dive into one topic area
├── Write a blog post or internal tech talk
├── Evaluate one new tool against current stack
├── Review and update team's technical roadmap
└── Attend 1-2 meetups or watch conference talks

Quarterly:
├── Reassess technology choices
├── Identify gaps in team's capabilities
├── Prototype one forward-looking technology
├── Update architecture diagrams
└── Run a post-mortem on biggest production issues

Annually:
├── Major technology strategy review
├── Conference attendance (NeurIPS, ICML, or industry conf)
├── Update personal learning roadmap
├── Publish 2-3 substantial pieces (blog, talk, paper)
└── Mentor 2-3 people into senior roles
```

### What to Watch (The Next 3-5 Years)

```
Highly Likely to Matter:
├── Multimodal models (vision + language + audio unified)
├── Smaller, faster models (efficiency over scale)
├── AI agents and tool use (autonomous systems)
├── RAG as infrastructure (not a pattern, a platform)
├── Edge AI (on-device, privacy-preserving)
├── AI regulation (EU AI Act, others following)
└── Synthetic data for training

Probably Important:
├── World models (Sora-style video understanding)
├── Neuro-symbolic AI (neural + logic combined)
├── Continuous learning (models that update without retraining)
├── Federated learning (train across organizations)
└── Quantum ML (long-term, but watch)

Overhyped (be skeptical):
├── AGI timelines (nobody knows)
├── "Just scale it" (hitting diminishing returns)
├── Any tool claiming to replace engineers
└── Blockchain + AI (almost always unnecessary)
```

---

## The Architect Portfolio

By the end of this stage, your GitHub / portfolio should contain:

```
PUBLIC PRESENCE:
├── GitHub: 10+ substantial projects spanning the whole stack
├── Blog: 15+ technical posts (design decisions, paper reviews, tutorials)
├── Talks: 3-5 conference/meetup presentations
├── Open source: Meaningful contributions to 2-3 projects
└── One "signature project" that shows end-to-end system thinking

DESIGN ARTIFACTS (can be anonymized):
├── 3-5 system design documents
├── Architecture Decision Records
├── Post-mortem writeups
└── Technology evaluation reports

BREADTH OF KNOWLEDGE (demonstrated):
├── Can design systems spanning NLP, CV, and tabular
├── Can make cloud architecture decisions
├── Can estimate costs for proposals
├── Can identify risks and failure modes
├── Can lead technical direction for a team of 5-15
└── Can bridge the gap between research and production
```

---

## Stage 6 Completion Criteria (a.k.a. "Am I an Architect?")

- [ ] Can design an ML system in 45 min whiteboard session with clear tradeoffs
- [ ] Have designed and shipped at least 2 production systems used by real people
- [ ] Can write a design doc that convinces skeptical senior engineers
- [ ] Can estimate cost, latency, and capacity for a proposed system
- [ ] Can identify when ML is NOT the right solution
- [ ] Have mentored at least 2 engineers into more senior roles
- [ ] Can explain any ML concept to a non-technical executive
- [ ] Have published technical content that others reference
- [ ] Can evaluate new technology without hype bias
- [ ] Can make "boring" technology decisions that work at scale

---

## Final Words

The Senior AI/ML Architect role isn't a destination. It's a way of thinking.
The specific technologies will change every 2-3 years. What won't change:

- Systems thinking (everything connects to everything)
- First principles reasoning (derive answers, don't memorize them)
- Intellectual honesty (admit uncertainty, verify assumptions)
- Communication clarity (complex ideas, simple explanations)
- Pragmatism (perfect is the enemy of shipped)

The best architects I've seen aren't the smartest people in the room.
They're the ones who make everyone else more effective. Build that skill
and the title will follow.
