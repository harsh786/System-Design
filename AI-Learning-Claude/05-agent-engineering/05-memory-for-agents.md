# Memory for Agents

## The "Goldfish Problem"

Without memory, every LLM call starts from zero. The agent forgets:
- What it already tried (repeats failed approaches)
- What the user said earlier (asks the same questions)
- What it learned (re-discovers facts every session)

This is the **goldfish problem** — every 3 seconds is a fresh start. Memory gives agents continuity, learning, and personalization.

---

## Memory Types

```mermaid
graph TD
    M[Agent Memory] --> W[Working Memory]
    M --> ST[Short-Term Memory]
    M --> LT[Long-Term Memory]
    
    LT --> E[Episodic Memory]
    LT --> S[Semantic Memory]
    LT --> P[Procedural Memory]
    
    W -.->|"Current context window"| W
    ST -.->|"Session-scoped"| ST
    E -.->|"Specific events"| E
    S -.->|"Facts & knowledge"| S
    P -.->|"Learned patterns"| P
```

### Working Memory (Context Window)

The LLM's immediate context — messages in the current conversation. Limited by the model's context window (128K tokens for GPT-4).

**Analogy**: Your desk. Only what's in front of you right now.

### Short-Term Memory (Session)

Information stored for the duration of a session but not persisted. Variables, intermediate results, conversation summaries.

**Analogy**: A whiteboard in a meeting room. Erased after the meeting.

### Long-Term Memory (Persistent)

Information that survives across sessions. Stored in external systems.

**Analogy**: Filing cabinets, notebooks, your company wiki.

---

## Long-Term Memory Subtypes

| Type | What It Stores | Example | Storage |
|------|---------------|---------|---------|
| **Episodic** | Specific past events | "Last Tuesday, user complained about slow search" | Event log / vector DB |
| **Semantic** | Facts and knowledge | "User prefers Python over JavaScript" | Knowledge graph / DB |
| **Procedural** | How to do things | "When user says 'deploy', run these 5 steps" | Prompt templates / rules |

### Episodic Memory
```
Event: 2024-01-15 14:30
Context: User asked to debug API endpoint
Action: Found N+1 query problem in /users endpoint
Outcome: Fixed with eager loading, 10x speedup
Lesson: Check for N+1 queries when API is slow
```

### Semantic Memory
```
User Preferences:
- Language: Python
- Framework: FastAPI
- Style: Concise code, minimal comments
- Testing: Pytest with fixtures
```

### Procedural Memory
```
Deployment Procedure:
1. Run tests → 2. Build Docker image → 3. Push to ECR → 4. Update ECS service
If tests fail: stop and report, never deploy broken code
```

---

## Memory Storage Approaches

| Approach | Best For | Limitations |
|----------|----------|-------------|
| **In-context** (system prompt) | Critical always-needed info | Limited space, expensive |
| **Vector store** | Semantic search over large memory | Can retrieve irrelevant items |
| **Database (SQL/NoSQL)** | Structured, queryable facts | Needs schema design |
| **Knowledge graph** | Relationships between entities | Complex to build and maintain |
| **File system** | Documents, code, artifacts | Slow retrieval for large sets |

### Architecture Example

```mermaid
flowchart TD
    A[Agent receives query] --> B[Retrieve relevant memories]
    
    B --> C[Vector DB: Similar past conversations]
    B --> D[User DB: Preferences and profile]
    B --> E[Knowledge Graph: Entity relationships]
    
    C --> F[Compose context]
    D --> F
    E --> F
    
    F --> G[LLM generates response]
    G --> H[Store new memories]
    
    H --> C
    H --> D
```

---

## Memory Retrieval: What to Remember and When

Not all memories are relevant. Retrieving too much = context overflow. Too little = goldfish.

**Retrieval strategies**:

1. **Recency** — Most recent interactions first
2. **Relevance** — Semantically similar to current query (vector search)
3. **Importance** — High-impact events (errors, user preferences, decisions)
4. **Frequency** — Often-referenced information

```python
def retrieve_memories(query, user_id, max_tokens=2000):
    # Combine multiple retrieval strategies
    recent = get_recent_memories(user_id, limit=5)
    relevant = vector_search(query, user_id, top_k=5)
    important = get_high_importance_memories(user_id, limit=3)
    
    # Deduplicate and rank
    all_memories = deduplicate(recent + relevant + important)
    ranked = rank_by_combined_score(all_memories)
    
    # Fit within token budget
    return truncate_to_tokens(ranked, max_tokens)
```

---

## Memory Management

### Forgetting (Necessary!)

Not everything should be remembered forever:
- Outdated information (old preferences, stale data)
- Low-importance interactions ("ok", "thanks")
- Superseded facts (old address after user moves)

### Summarization

As conversations grow, summarize older parts:
```
[Messages 1-50: Summary] User onboarded, set up Python project,
configured FastAPI with PostgreSQL, deployed to AWS.
[Messages 51-100: Full detail kept]
```

### Consolidation

Periodically merge and clean memories:
- Combine fragmented facts into coherent profiles
- Resolve contradictions (latest preference wins)
- Extract patterns from episodic memories → semantic knowledge

---

## Memory Safety

| Concern | Mitigation |
|---------|-----------|
| **PII storage** | Encrypt, minimize, auto-expire |
| **Right to forget** | Implement memory deletion API |
| **Memory poisoning** | Validate before storing; don't trust all inputs |
| **Cross-user leakage** | Strict memory isolation per user |
| **Stale info** | TTL (time-to-live) on memories |
| **Context injection** | Sanitize retrieved memories before injecting |

---

## Practical Memory Architecture

```
┌──────────────────────────────────────────────┐
│                 AGENT LAYER                    │
├──────────────────────────────────────────────┤
│  Working Memory: Current messages (in-context)│
│  ┌──────────────────────────────────────┐    │
│  │ System prompt + last N messages      │    │
│  └──────────────────────────────────────┘    │
├──────────────────────────────────────────────┤
│  Memory Manager                              │
│  - Decides what to store                     │
│  - Decides what to retrieve                  │
│  - Handles summarization                     │
│  - Enforces privacy rules                    │
├──────────────────────────────────────────────┤
│  Storage Layer                               │
│  ┌────────┐ ┌──────────┐ ┌──────────────┐  │
│  │Vector  │ │ User DB  │ │ Knowledge    │  │
│  │Store   │ │(profiles)│ │ Graph        │  │
│  └────────┘ └──────────┘ └──────────────┘  │
└──────────────────────────────────────────────┘
```

---

## Key Takeaways

- Without memory, agents are goldfish — they forget everything between calls
- Six memory types: working, short-term, episodic, semantic, procedural, long-term
- Retrieval is as important as storage — retrieve only what's relevant
- Memory must be managed: summarization, forgetting, consolidation
- Privacy and safety: encrypt PII, support deletion, isolate per user
- The memory manager is a critical architectural component

---

## Staff-Level: Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| Unbounded memory (grows forever) | Costs explode (vector DB storage + retrieval tokens), retrieval quality degrades as noise increases | Set memory budgets: max N items per type, TTL on entries, periodic garbage collection |
| No memory relevance filtering | Agent retrieves 20 irrelevant memories, wastes context window, confuses reasoning | Score relevance before injection; only inject top-K with similarity > threshold (e.g., 0.75) |
| Storing hallucinated "facts" | Agent "remembers" something it made up → reinforces hallucinations across sessions | Validate before storing: only store tool outputs, user-confirmed facts, or high-confidence extractions |
| Shared memory without access control | User A's data leaks into User B's context; compliance nightmare | Strict tenant isolation; memory keys include user_id; never query across users |
| Storing everything verbatim | "ok", "thanks", "hmm" clog memory with noise | Filter by information density: only store memories that contain actionable facts or decisions |
| No memory versioning | User updates preference but old version persists → contradictions | Upsert pattern: new fact on same key replaces old; keep audit trail separately |

---

## Staff-Level: Trade-offs

### Memory Size vs Retrieval Quality

| Large Memory (100K+ entries) | Small Memory (<1K entries) |
|-----------------------------|-----------------------------|
| More knowledge available | Faster retrieval, less noise |
| Higher storage costs | Lower costs |
| Retrieval precision drops | Every memory is high-value |
| Needs sophisticated ranking | Simple top-K works fine |

### Episodic vs Semantic Memory

| Episodic (events) | Semantic (facts) |
|-------------------|-----------------|
| "On Jan 5, user reported bug X" | "User prefers Python" |
| Rich context, time-stamped | Compressed, general |
| Useful for debugging, continuity | Useful for personalization |
| Grows linearly with interactions | Grows sublinearly (facts consolidate) |

### Persistence vs Privacy

| Full Persistence | Ephemeral/Limited |
|-----------------|-------------------|
| Better personalization over time | GDPR/privacy compliant by default |
| Users feel "known" | No risk of stale data |
| Higher liability | Users must re-state preferences |

---

## Staff-Level: Real Implementation Patterns

### How ChatGPT/Claude Implement Conversation Memory
- **Within session**: Full conversation in context window (working memory)
- **Cross-session** (ChatGPT Memory): Extracts key facts → stores as semantic memory → injects relevant facts into system prompt
- **Pattern**: LLM-as-memory-extractor — after each conversation, a separate LLM call identifies "memorizable facts" and upserts them

### How Coding Agents (Cursor, Devin, OpenCode) Implement Project Memory
- **Codebase indexing**: Embed files/functions into vector store; retrieve relevant code on each query
- **Session memory**: Track what files were edited, what errors occurred, what was tried
- **Rules/preferences**: `.cursorrules`, `AGENTS.md` — static procedural memory loaded every session
- **Pattern**: Hierarchical retrieval — static rules always loaded + dynamic retrieval for code context

### Key Difference
- **Chat assistants**: Memory is about the USER (preferences, history, relationships)
- **Coding agents**: Memory is about the PROJECT (codebase structure, conventions, past decisions)
- **Both**: Need garbage collection, relevance filtering, and bounded growth

---

## Memory System Selection Framework

| Use Case | Memory Type | Storage | Cost Driver |
|----------|-------------|---------|-------------|
| Remember user preferences | Long-term semantic | Vector DB | Storage + retrieval queries |
| Track conversation context | Short-term (buffer) | In-context window | Token cost per request |
| Learn from past mistakes | Episodic | Vector DB + metadata | Embedding + retrieval |
| Follow project conventions | Procedural (static) | File system (loaded at init) | Context window space |
| Cache expensive computations | Working memory | Redis/KV store | Memory + TTL management |

## Memory Cost at Scale

```
Cost model per user:
  Semantic memory:  ~100 memories × 1536d × 4 bytes = 600KB storage per user
  Retrieval cost:   ~3 queries/session × $0.0001/query = $0.0003/session
  Embedding cost:   ~5 new memories/session × 500 tokens × $0.00002 = $0.00005/session

At 1M users:
  Storage: 600GB vector storage (~$150/month on managed DB)
  Retrieval: 3M queries/day = ~$300/month
  Embedding: 5M embeddings/day = ~$50/month
  Total: ~$500/month for memory infrastructure at 1M users

Scaling concern: Not storage cost — it's RELEVANCE DECAY.
  More memories → more noise in retrieval → worse agent behavior
  Solution: Decay scores, consolidation (merge similar memories), hard caps per category
```

**Staff insight**: The biggest memory cost isn't dollars — it's quality degradation. A memory system that never forgets eventually poisons retrieval with irrelevant or contradictory information. Implement aggressive pruning early.
