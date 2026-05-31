# Agent Frameworks Comparison

## Why Use a Framework?

Building agents from scratch means implementing:
- Tool calling loops
- Memory management
- State persistence
- Error handling and retries
- Observability and tracing
- Multi-agent coordination

Frameworks give you these for free. But they also constrain you.

**The trade-off**: Faster start vs. less control.

---

## Framework Comparison

| Framework | Approach | Best For | Complexity | Production-Ready |
|-----------|----------|----------|-----------|-----------------|
| **LangGraph** | Graph-based state machines | Complex flows with cycles, branching | High | Yes |
| **OpenAI Agents SDK** | Simple, opinionated agents | Quick prototypes, OpenAI-native | Low | Growing |
| **AutoGen** | Multi-agent conversations | Research, multi-agent chat | Medium | Experimental |
| **CrewAI** | Role-based agent teams | Team simulations, pipeline tasks | Medium | Growing |
| **LlamaIndex** | Data/retrieval-focused | RAG agents, data Q&A | Medium | Yes |
| **PydanticAI** | Type-safe, dependency-injected | Production Python apps | Medium | Yes |
| **Haystack** | Pipeline-based components | Modular NLP pipelines | Medium | Yes |
| **DSPy** | Programmatic prompt optimization | Research, prompt tuning | High | Research |

---

## Detailed Breakdown

### LangGraph
- **Philosophy**: Agents as state machines with graph-based control flow
- **Strength**: Cycles, conditional branching, persistence, human-in-the-loop
- **Weakness**: Steep learning curve, complex abstractions
- **Use when**: You need precise control over agent flow with checkpointing

### OpenAI Agents SDK
- **Philosophy**: Minimal, convention-over-configuration
- **Strength**: Simple API, built-in handoffs, tracing
- **Weakness**: OpenAI-only, limited customization
- **Use when**: You want to ship fast with OpenAI models

### AutoGen (Microsoft)
- **Philosophy**: Agents as conversational participants
- **Strength**: Multi-agent conversations, code execution
- **Weakness**: Hard to control in production, chatty
- **Use when**: Research, prototyping multi-agent interactions

### CrewAI
- **Philosophy**: Agents as team members with roles
- **Strength**: Intuitive role-based design, delegation
- **Weakness**: Less flexible for non-team patterns
- **Use when**: Your task naturally maps to a team of specialists

### LlamaIndex
- **Philosophy**: Connect LLMs to your data
- **Strength**: Best-in-class data ingestion, retrieval, RAG
- **Weakness**: Less suited for non-data tasks
- **Use when**: Your agent primarily queries and reasons over data

### PydanticAI
- **Philosophy**: Type-safe agents with dependency injection
- **Strength**: Python-native, testable, structured outputs
- **Weakness**: Newer, smaller community
- **Use when**: You value type safety and testability in production

### Haystack
- **Philosophy**: Modular pipeline components
- **Strength**: Composable, well-documented, model-agnostic
- **Weakness**: Less agent-focused, more pipeline-focused
- **Use when**: You need modular NLP pipelines with agent capabilities

### DSPy
- **Philosophy**: Programs, not prompts — optimize automatically
- **Strength**: Automatic prompt optimization, reproducible
- **Weakness**: Steep learning curve, research-oriented
- **Use when**: You want to programmatically optimize prompts/pipelines

---

## Decision Matrix

| Factor | LangGraph | OpenAI SDK | AutoGen | CrewAI | LlamaIndex | PydanticAI |
|--------|-----------|-----------|---------|--------|------------|-----------|
| Learning curve | Hard | Easy | Medium | Easy | Medium | Medium |
| Production use | ✅ | Growing | ⚠️ | Growing | ✅ | ✅ |
| Model-agnostic | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Multi-agent | ✅ | Basic | ✅ | ✅ | Limited | Limited |
| Observability | ✅ | ✅ | Limited | Limited | ✅ | ✅ |
| Community size | Large | Large | Large | Medium | Large | Small |
| Flexibility | High | Low | Medium | Medium | Medium | High |

---

## When to Build from Scratch

Build your own when:

1. **Your flow is simple** — A while loop with tool calls is 50 lines of code
2. **Framework overhead > value** — More time fighting the framework than building
3. **Performance is critical** — Frameworks add latency (serialization, state management)
4. **You need full control** — Custom retry logic, streaming, error handling
5. **Vendor lock-in is unacceptable** — Frameworks couple you to their abstractions
6. **Production at scale** — Many teams end up replacing frameworks with custom code

**Production truth**: Most successful production agents are simple loops with careful engineering, not framework-heavy architectures.

---

## Framework Lock-in Risks

| Risk | Description |
|------|-------------|
| **Abstraction mismatch** | Framework's model doesn't match your needs |
| **Upgrade pain** | Breaking changes between versions |
| **Debugging opacity** | Hard to debug through framework layers |
| **Performance ceiling** | Framework overhead becomes bottleneck |
| **Migration cost** | Switching frameworks = rewrite |
| **Abandoned framework** | Small frameworks may lose maintainers |

---

## The "Framework Paradox"

> Frameworks make the easy things effortless and the hard things impossible.

- **Day 1**: "Wow, I built an agent in 20 lines!"
- **Day 30**: "How do I customize the retry logic? Why is it calling tools in this order?"
- **Day 90**: "I'm fighting the framework more than building my product."
- **Day 180**: "Let's rewrite this from scratch with just the OpenAI SDK."

This isn't always the case — some frameworks (LangGraph, PydanticAI) are designed for production flexibility. But be aware of the pattern.

---

## Recommendation by Use Case

| Use Case | Recommendation |
|----------|---------------|
| Quick prototype | OpenAI Agents SDK or CrewAI |
| Production single-agent | PydanticAI or custom code |
| Production multi-agent | LangGraph or custom code |
| RAG/data agent | LlamaIndex |
| Research/experimentation | AutoGen or DSPy |
| Enterprise with compliance | LangGraph (best observability) |

---

## Key Takeaways

- Frameworks trade control for speed-to-prototype
- No single framework is "best" — it depends on your needs
- For production, simpler is almost always better
- Evaluate: lock-in risk, debugging experience, community, production-readiness
- Don't be afraid to build from scratch — an agent loop is just a while loop
- The OpenAI API itself IS a framework for simple agents

---

## Staff-Level: Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| Choosing framework by hype not requirements | LangChain has 80K stars but you need a simple 50-line loop — now you have 200 dependencies | List your actual requirements first, THEN evaluate which tool (or no tool) fits |
| Deep framework coupling (can't swap) | Your business logic is tangled with LangChain chains → migrating to anything else is a rewrite | Keep framework at the edges; core logic should be framework-agnostic functions |
| Using framework for simple cases | 3 files, 500 lines of framework config for something achievable in 40 lines of raw API calls | If your agent is: single model, <5 tools, linear flow → raw SDK is better |
| Updating framework without testing | LangChain 0.1→0.2 broke half the APIs; CrewAI changes patterns between minors | Pin versions, have integration tests, update deliberately |
| Using multiple frameworks together | LangChain for memory + LlamaIndex for RAG + CrewAI for agents = dependency hell | Pick ONE primary framework; supplement with raw code for gaps |

---

## Staff-Level: Trade-offs Table

| Dimension | LangGraph | LlamaIndex | Semantic Kernel | PydanticAI | Raw SDK |
|-----------|-----------|-----------|----------------|-----------|---------|
| **Batteries included** | High | High (data) | High (.NET) | Medium | None |
| **Weight/Dependencies** | Heavy | Heavy | Medium | Light | Minimal |
| **Learning curve** | Steep | Medium | Medium | Low | Lowest |
| **Production hardening** | Good | Good | Enterprise | Good | You build it |
| **Flexibility** | High (graphs) | Medium | Medium | High | Total |
| **Lock-in risk** | Medium | Medium | Low (MS backing) | Low | None |
| **Best ecosystem** | Python | Python | .NET/Python/Java | Python | Any |
| **Multi-model support** | Yes | Yes | Yes | Yes | Manual |

---

## Staff-Level: When to Use a Framework vs Build Custom

### Use a Framework When:
1. **Prototyping** — You need a working demo in hours, not days
2. **Standard patterns** — Your use case matches the framework's happy path exactly
3. **Team velocity** — Junior devs can be productive faster with framework abstractions
4. **Built-in observability** — LangSmith, Arize, etc. integration saves weeks of build

### Build Custom When:
1. **Production at scale** — You need control over every retry, timeout, and token
2. **Performance-critical** — Framework serialization/deserialization adds 50-200ms per step
3. **Simple agent** — Your agent is a while loop + 5 tools; a framework adds complexity, not value
4. **Long-term maintenance** — You'll maintain this for years; frameworks break between versions
5. **Unique patterns** — Your agent flow doesn't map to any framework's model

### The Staff Decision Framework:
```
Is your agent loop simple (linear, <5 tools, single model)?
  YES → Raw SDK (OpenAI, Anthropic, etc.)
  NO  → Continue...

Are you prototyping or going to production?
  PROTOTYPE → Framework (fastest to demo)
  PRODUCTION → Continue...

Does a framework match your exact pattern?
  YES → Use it, but isolate business logic from framework code
  NO  → Build custom; fighting a framework costs more than building from scratch

Will this run at scale (>10K requests/day)?
  YES → Build custom or use minimal framework (PydanticAI)
  NO  → Framework is fine; maintenance cost is manageable
```

**The uncomfortable truth**: Most teams start with a framework, hit its limits at month 3-6, and either live with the constraints or rewrite. Knowing this upfront lets you make an informed bet.

---

## 2024-2025 Framework Landscape Update

### New/Evolved Entrants

| Framework | Focus | Maturity | Key Differentiator |
|-----------|-------|----------|-------------------|
| **OpenAI Agents SDK** | OpenAI-native agents | Production | Handoffs, guardrails, tracing built-in; vendor lock-in |
| **PydanticAI** | Type-safe agents | Growing | Pydantic-native, dependency injection, model-agnostic |
| **LangGraph** | Stateful workflows | Mature | Graph-based control flow, persistence, human-in-loop |
| **CrewAI** | Multi-agent teams | Popular | Role-based agents, easy multi-agent; less flexible |
| **Mastra** | TypeScript agents | Early | TS-first, framework for AI features in apps |
| **Agno (ex-PhiData)** | Fast multi-modal agents | Growing | Speed-focused, multi-modal, built-in memory |
| **Google ADK** | Google ecosystem | New (2025) | Multi-agent, A2A protocol support |
| **Smolagents** (HF) | Minimal, code agents | Niche | Code-writing agents, lightweight |

### What Changed Since 2023

```
Then: LangChain dominated, everything was chains
Now:  Graph-based (LangGraph), code-first (PydanticAI), vendor-native (OpenAI SDK)

Key shifts:
1. Chains → Graphs: Non-linear control flow won (cycles, conditionals, branches)
2. Magic → Explicit: Developers rejected hidden abstractions; prefer seeing what's happening
3. Monolithic → Composable: Pick a framework for orchestration, bring your own everything else
4. Python-only → Multi-language: TypeScript frameworks maturing (Mastra, Vercel AI SDK)
5. Single-agent → Multi-agent primitives: Handoffs, delegation, shared state becoming first-class
```

## Framework Selection Decision Tree (2025)

```
What's your primary language?
├── TypeScript → Vercel AI SDK (simple) or Mastra (complex)
├── Python ↓
│
What's your agent complexity?
├── Single agent, 1-3 tools → Raw SDK calls (OpenAI/Anthropic) or PydanticAI
├── Single agent, complex tool orchestration → PydanticAI or OpenAI Agents SDK
├── Multi-step workflow with state → LangGraph
├── Multi-agent with roles → CrewAI (simple) or LangGraph (complex)
├── Need vendor portability → PydanticAI (model-agnostic by design)
│
Are you locked to one provider?
├── OpenAI only → OpenAI Agents SDK (best DX for that ecosystem)
├── Anthropic only → Raw Claude SDK + tool_use (framework adds little value)
├── Multi-provider → PydanticAI or LangGraph
│
What's your team's experience?
├── New to agents → CrewAI or OpenAI Agents SDK (lowest learning curve)
├── Experienced, want control → PydanticAI or custom
├── Already on LangChain → Migrate to LangGraph (incremental path)
```

## Migration Strategies Between Frameworks

### Common Migration Paths

**LangChain → LangGraph**:
- Incremental: Replace chain-by-chain with graph nodes
- Keep LangChain's document loaders/retrievers, replace orchestration layer
- Timeline: 2-4 weeks for medium complexity

**LangChain → PydanticAI/Custom**:
- Rewrite (not incremental): Abstractions too different
- Extract your tool implementations (these are portable)
- Rewrite orchestration from scratch
- Timeline: 1-2 weeks for simple agents, 4-8 weeks for complex

**Any framework → OpenAI Agents SDK**:
- Only viable if you're OpenAI-exclusive
- Concept mapping: tools → tools, chains → handoffs, memory → context
- Warning: You lose multi-provider flexibility

### Migration Checklist

1. **Inventory**: List all tools, prompts, state management, and integrations
2. **Portable vs. coupled**: Identify what's framework-specific vs. reusable
3. **Test suite first**: Write integration tests against current behavior BEFORE migrating
4. **Parallel run**: Run old and new side-by-side, compare outputs
5. **Incremental rollout**: Migrate one agent/workflow at a time, not big-bang

### What's Actually Portable Between Frameworks

```
Portable (keep these clean):
  ✓ Tool implementations (pure functions with clear inputs/outputs)
  ✓ Prompt templates (text is text)
  ✓ Evaluation datasets and metrics
  ✓ External integrations (DB connections, API clients)

NOT portable (will be rewritten):
  ✗ Orchestration logic (framework-specific graph/chain definitions)
  ✗ Memory/state management (each framework has its own approach)
  ✗ Streaming/callback handlers
  ✗ Framework-specific middleware/hooks
```

**Staff advice**: Treat your framework as a replaceable orchestration layer. Keep tool logic, prompts, and evaluation suites independent. The teams that survive framework churn are those who kept their business logic decoupled.
