# Agent Frameworks - Deep Comparison & Selection Guide

## Framework Landscape Overview

The agent framework ecosystem has exploded in 2024-2025. Each framework occupies a different niche, from thin orchestration layers to opinionated full-stack agent platforms. Understanding the tradeoffs is critical—choosing the wrong framework can lock you into abstractions that fight your use case.

### The Fundamental Question

Before choosing a framework, ask: **Do I even need one?**

Most production AI systems are simpler than framework marketing suggests. A well-structured Python application with direct LLM API calls, explicit state management, and good error handling often outperforms framework-laden alternatives in maintainability and debuggability.

---

## Framework Deep Dive

### 1. LangGraph (by LangChain)

**Philosophy**: Agent workflows as directed graphs with explicit state machines.

**Core Concepts**:
- State is a TypedDict flowing through the graph
- Nodes are functions that transform state
- Edges (including conditional) define control flow
- Built-in persistence via checkpointers
- Human-in-the-loop as first-class concept

**Strengths**:
- Explicit control flow—you can SEE the agent's decision paths
- State is typed and inspectable at every step
- Persistence/resumability built-in (critical for production)
- Supports parallel branches, subgraphs, map-reduce
- LangGraph Platform provides deployment infrastructure
- Good streaming support
- Excellent for complex, multi-step workflows

**Weaknesses**:
- Tied to LangChain ecosystem (langchain-core types)
- Verbose for simple agents
- Graph definition can get complex for dynamic workflows
- Debugging graph execution requires understanding internals
- Version churn (LangChain ecosystem moves fast)
- Overhead for simple request-response patterns

**Best For**: Complex multi-step agents, workflows requiring human approval, long-running processes, agents needing durable state.

**Production Readiness**: 8/10 — LangGraph Platform exists, checkpointing works, but ecosystem instability remains a concern.

---

### 2. OpenAI Agents SDK (formerly Swarm)

**Philosophy**: Minimal, opinionated SDK for multi-agent systems with handoffs.

**Core Concepts**:
- Agents have instructions + tools
- Handoffs transfer control between agents
- Guardrails validate inputs/outputs
- Tracing built-in
- Runner manages execution loop

**Strengths**:
- Extremely simple API surface
- Native OpenAI integration (best token efficiency with OpenAI models)
- Handoff pattern is elegant for specialization
- Built-in tracing/observability
- Guardrails are first-class
- Minimal boilerplate
- Type-safe tool definitions

**Weaknesses**:
- OpenAI-only (vendor lock-in)
- Limited state management (no built-in persistence)
- No built-in graph/workflow visualization
- Less flexible for non-agent patterns
- Young ecosystem, limited community extensions
- No native RAG integration

**Best For**: Multi-agent systems using OpenAI models, customer service routing, task delegation patterns.

**Production Readiness**: 7/10 — Simple and reliable, but limited persistence and OpenAI-only constraint.

---

### 3. LlamaIndex

**Philosophy**: Data-aware AI applications—connect LLMs to your data.

**Core Concepts**:
- Indices over data (vector, list, keyword, knowledge graph)
- Query engines that understand data structure
- Tools that wrap query engines
- Agents that orchestrate tools
- Data connectors for 100+ sources

**Strengths**:
- Best-in-class RAG and data integration
- Excellent for data-heavy applications
- Query engine abstraction is powerful
- Sub-question decomposition built-in
- Great for building data analysts/researchers
- Comprehensive data connector ecosystem
- Good hybrid search support

**Weaknesses**:
- Agent capabilities are secondary to data features
- Less flexible for non-data workflows
- Can be over-abstracted for simple retrieval
- Memory management can be opaque
- Performance overhead from abstraction layers
- Less suitable for pure orchestration

**Best For**: Data-intensive agents, research assistants, document Q&A, knowledge base agents.

**Production Readiness**: 7/10 — Mature for RAG, less proven for complex agent workflows.

---

### 4. Microsoft AutoGen

**Philosophy**: Multi-agent conversation as the primitive.

**Core Concepts**:
- Agents communicate via messages
- GroupChat orchestrates multi-agent conversations
- Agents can be LLM-based, tool-based, or human proxies
- Conversation patterns define workflow

**Strengths**:
- Natural multi-agent collaboration patterns
- Human-in-the-loop via UserProxyAgent
- Code execution built-in (Docker-sandboxed)
- Good for research/exploration tasks
- Flexible conversation topologies
- Strong Microsoft backing

**Weaknesses**:
- Conversation-centric model doesn't fit all patterns
- Can be unpredictable (agents talking in circles)
- Less deterministic than graph-based approaches
- Debugging multi-agent conversations is hard
- v0.2 → v0.4 breaking changes show instability
- Resource-intensive (multiple LLM calls per turn)

**Best For**: Research tasks, collaborative problem-solving, code generation with execution, brainstorming.

**Production Readiness**: 5/10 — Great for research, risky for production due to unpredictability.

---

### 5. CrewAI

**Philosophy**: Role-based agent teams with defined processes.

**Core Concepts**:
- Agents have roles, goals, backstories
- Tasks define what agents do
- Crews orchestrate agent teams
- Processes (sequential, hierarchical) control flow
- Tools are shared across agents

**Strengths**:
- Intuitive role-based mental model
- Easy to prototype multi-agent systems
- Good for content creation workflows
- Simple API for common patterns
- Built-in delegation between agents

**Weaknesses**:
- Less control over execution details
- Role/backstory abstraction can be limiting
- Limited state management
- Less suitable for data-heavy workloads
- Debugging agent interactions is difficult
- Performance overhead from role-playing prompts
- Limited persistence/resumability

**Best For**: Content generation pipelines, research teams, marketing workflows, prototyping.

**Production Readiness**: 4/10 — Good for demos, risky for production workloads.

---

### 6. PydanticAI

**Philosophy**: Type-safe, Pythonic agent framework—agents as typed functions.

**Core Concepts**:
- Agents return typed Pydantic models
- Dependencies injected cleanly
- System prompts are dynamic (functions)
- Tools are typed functions with dependency injection
- Result validators enforce output structure

**Strengths**:
- Excellent type safety
- Clean, Pythonic API
- Model-agnostic (works with any LLM provider)
- Dependency injection is powerful for testing
- Result validation built-in
- Lightweight—doesn't try to do everything
- Great developer experience

**Weaknesses**:
- No built-in workflow/graph orchestration
- No persistence layer
- No multi-agent patterns built-in
- Relatively new, smaller community
- Limited to single agent interactions
- No streaming of intermediate steps

**Best For**: Type-safe single-agent applications, structured output generation, API integrations needing validation.

**Production Readiness**: 6/10 — Excellent code quality, but limited orchestration features.

---

### 7. Haystack (by deepset)

**Philosophy**: Production-grade NLP/LLM pipelines as composable components.

**Core Concepts**:
- Pipelines of connected components
- Components have typed inputs/outputs
- Built-in document stores and retrievers
- Pipeline serialization (YAML)
- Branching and routing in pipelines

**Strengths**:
- Production-oriented from day one
- Excellent pipeline serialization/versioning
- Strong document processing capabilities
- Good evaluation framework
- Clean component interface
- Type-safe connections
- Good for batch processing

**Weaknesses**:
- Pipeline paradigm doesn't fit all agent patterns
- Less flexible for dynamic, reactive agents
- Steeper learning curve for custom components
- Smaller community than LangChain ecosystem
- Limited multi-agent support
- Less LLM-agent-focused, more pipeline-focused

**Best For**: Production NLP pipelines, document processing, structured RAG systems, batch AI workflows.

**Production Readiness**: 8/10 — Built for production, excellent engineering quality.

---

### 8. DSPy

**Philosophy**: Programming (not prompting) LLM systems—optimizable modules.

**Core Concepts**:
- Signatures define input/output of LLM calls
- Modules compose signatures into programs
- Optimizers automatically tune prompts/few-shot examples
- Metrics evaluate program quality
- Assertions enforce constraints

**Strengths**:
- Eliminates manual prompt engineering
- Automatic optimization of prompts
- Composable, testable modules
- Metric-driven development
- Reproducible results
- Works across LLM providers
- Academic rigor in design

**Weaknesses**:
- Steep learning curve (different paradigm)
- Less intuitive for simple use cases
- Optimization requires good metrics and data
- Less suitable for interactive agents
- Limited real-time/streaming support
- Community is research-oriented
- Not designed for stateful workflows

**Best For**: Complex NLP pipelines needing optimization, research, systems where prompt quality matters, batch processing.

**Production Readiness**: 6/10 — Powerful but requires expertise and good evaluation data.

---

## Comparison Matrix

| Criteria | LangGraph | OpenAI SDK | LlamaIndex | AutoGen | CrewAI | PydanticAI | Haystack | DSPy |
|----------|-----------|------------|------------|---------|--------|------------|----------|------|
| **State Management** | Excellent | Minimal | Moderate | Minimal | Minimal | None | Good | None |
| **Persistence** | Built-in | None | Via stores | None | None | None | Pipeline serial | None |
| **Multi-Agent** | Subgraphs | Handoffs | Limited | Core feature | Core feature | None | Limited | Modules |
| **Type Safety** | TypedDict | Good | Moderate | Moderate | Weak | Excellent | Good | Signatures |
| **Observability** | LangSmith | Built-in | LlamaTrace | Limited | Limited | Logfire | Good | Limited |
| **Human-in-Loop** | Excellent | Manual | Manual | UserProxy | Limited | Manual | Manual | None |
| **RAG Integration** | Via LC | Manual | Excellent | Manual | Tools | Manual | Excellent | Modules |
| **Model Agnostic** | Yes | No (OpenAI) | Yes | Yes | Yes | Yes | Yes | Yes |
| **Learning Curve** | Medium | Low | Medium | Medium | Low | Low | Medium | High |
| **Production Ready** | 8/10 | 7/10 | 7/10 | 5/10 | 4/10 | 6/10 | 8/10 | 6/10 |
| **Community Size** | Large | Growing | Large | Medium | Medium | Small | Medium | Small |
| **Streaming** | Good | Good | Limited | Limited | None | Limited | Limited | None |
| **Testing** | Moderate | Easy | Moderate | Hard | Hard | Excellent | Good | Good |

---

## Framework Selection Decision Tree

```
START: What are you building?
│
├─ Simple single-agent with tools?
│  ├─ Need type safety? → PydanticAI
│  ├─ Using OpenAI only? → OpenAI Agents SDK
│  └─ Need flexibility? → No framework (direct API)
│
├─ Multi-step workflow with state?
│  ├─ Need persistence/resumability? → LangGraph
│  ├─ Need human approval steps? → LangGraph
│  └─ Simple linear pipeline? → Haystack or No framework
│
├─ Data-intensive agent (RAG, research)?
│  ├─ Multiple data sources? → LlamaIndex
│  ├─ Document processing pipeline? → Haystack
│  └─ Need query decomposition? → LlamaIndex
│
├─ Multi-agent collaboration?
│  ├─ Deterministic routing needed? → LangGraph
│  ├─ Open-ended research? → AutoGen
│  ├─ Role-based team (content)? → CrewAI
│  └─ Specialist handoff? → OpenAI Agents SDK
│
├─ Need prompt optimization?
│  └─ → DSPy
│
└─ Production NLP pipeline?
   └─ → Haystack
```

---

## When to Use NO Framework

**Use no framework when**:

1. **Simple request-response**: Single LLM call with tool use → direct API call
2. **Predictable workflow**: Linear steps with no branching → simple Python functions
3. **Maximum control needed**: Medical, financial, safety-critical → explicit code
4. **Performance-critical**: Every millisecond matters → direct API, no middleware
5. **Team doesn't know the framework**: Learning curve > value added
6. **Prototype/MVP**: Validate the idea first, add framework later
7. **Single model provider**: Framework's model-agnostic value is wasted

**The "No Framework" pattern**:
```python
# Often this is all you need:
class Agent:
    def __init__(self, model, tools, system_prompt):
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
    
    async def run(self, user_input, max_turns=10):
        messages = [{"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_input}]
        for _ in range(max_turns):
            response = await self.model.chat(messages)
            if response.tool_calls:
                results = await self.execute_tools(response.tool_calls)
                messages.extend(results)
            else:
                return response.content
        raise MaxTurnsExceeded()
```

---

## Framework Abstraction Risks

### The Abstraction Tax

1. **Debugging opacity**: When things fail inside framework internals, stack traces are 20 levels deep
2. **Version coupling**: Framework updates break your code; you're at their mercy
3. **Performance overhead**: Every abstraction layer adds latency (10-50ms per layer)
4. **Mental model mismatch**: Framework's model vs. your problem → forced contortions
5. **Lock-in**: Rewriting away from a framework is expensive (often full rewrite)
6. **Hidden behavior**: Frameworks do things you don't expect (retry logic, prompt injection, token management)

### Signs You Chose Wrong

- Fighting the framework more than using it
- Overriding/monkey-patching framework internals
- Most code is framework boilerplate, not business logic
- Can't explain what happens between your input and the LLM call
- Performance is unacceptable and you can't optimize
- Testing requires mocking 5+ framework classes

---

## Migration Strategies

### From LangChain → LangGraph
- Keep LangChain for LLM/tool interfaces
- Replace chains with graph nodes
- Add explicit state management
- Incremental: one chain → one subgraph at a time

### From Any Framework → No Framework
1. Map framework concepts to plain Python equivalents
2. Extract business logic from framework wrappers
3. Implement thin LLM client wrapper
4. Add explicit state management
5. Build minimal orchestration loop
6. Migrate one agent/workflow at a time

### From No Framework → LangGraph
1. Define state TypedDict from existing state
2. Convert functions to node functions
3. Map control flow to edges
4. Add checkpointer for persistence
5. Test graph produces same results as original

---

## Framework Evaluation Criteria (Weighted)

When evaluating for YOUR use case, score each criterion:

| Criterion | Weight | Questions to Ask |
|-----------|--------|-----------------|
| **State Management** | High | Can I inspect/modify state at any point? Is state typed? |
| **Durability/Persistence** | High | Can workflows survive restarts? Can I resume from any step? |
| **Human-in-Loop** | Medium-High | Can I pause for approval? Can humans modify agent state? |
| **Observability** | High | Can I trace every LLM call? Can I see token usage? Costs? |
| **Testing** | High | Can I unit test nodes? Can I mock LLM calls? Deterministic tests? |
| **Type Safety** | Medium | Will my IDE catch errors? Are inputs/outputs validated? |
| **Community** | Medium | Can I find answers? Are there examples? Is it maintained? |
| **Performance** | Medium | What's the overhead? Can I optimize hot paths? |
| **Extensibility** | Medium | Can I add custom components? Can I escape the framework? |
| **Model Flexibility** | Low-High | Can I swap models? Use multiple providers? (depends on strategy) |

---

## Recommendation Summary

| Scenario | Recommendation |
|----------|---------------|
| Startup MVP | No framework → add later |
| Enterprise workflow automation | LangGraph |
| Customer service bot | OpenAI Agents SDK |
| Research/data analyst agent | LlamaIndex |
| Content generation pipeline | CrewAI (prototype) → LangGraph (production) |
| Document processing at scale | Haystack |
| Type-safe API agent | PydanticAI |
| Academic research on agents | AutoGen or DSPy |
| Performance-critical production | No framework |
| Multi-model strategy | LangGraph or PydanticAI |
