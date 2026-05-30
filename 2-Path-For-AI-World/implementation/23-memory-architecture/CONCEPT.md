# Memory Architecture for AI Agents

## Senior Principle

> **"Memory must be intentional, scoped, permissioned, auditable, erasable, and evaluated."**

Memory is what separates a stateless tool from an intelligent agent. But memory without governance is a liability—it leaks private data, poisons future decisions, and creates legal exposure. This module covers how to build memory systems that are powerful yet safe.

---

## 1. Memory Types (9 Types)

### 1.1 Working Memory (Current Task State)

The agent's "scratchpad" for the current interaction. Holds intermediate reasoning, partial results, and active context.

- **Scope**: Single task/turn
- **Lifetime**: Cleared after task completion
- **Example**: Current file being edited, variables in a chain-of-thought, tool call results pending use
- **Analogy**: Human working memory (7±2 items)
- **Implementation**: In-memory dict or context window tokens
- **Capacity constraint**: Limited by LLM context window (4K-200K tokens)

### 1.2 Episodic Memory (Past Events)

Records of specific events, conversations, and interactions. "What happened."

- **Scope**: Per-user, per-session, or per-project
- **Lifetime**: Days to months (configurable retention)
- **Example**: "User asked me to refactor auth module on Tuesday", "Deployment failed at 3pm"
- **Structure**: Timestamped events with metadata (who, what, when, where, outcome)
- **Key property**: Temporally ordered, queryable by time range
- **Risk**: Can contain sensitive conversations verbatim

### 1.3 Semantic Memory (Durable Facts)

General knowledge and facts learned over time. "What is true."

- **Scope**: Per-user, per-organization, or global
- **Lifetime**: Long-lived until invalidated
- **Example**: "User prefers TypeScript over JavaScript", "The production database is PostgreSQL 15", "Company uses 4-space indentation"
- **Structure**: Fact triples (subject, predicate, object) or key-value pairs
- **Key property**: Deduplicated, versioned, source-attributed
- **Update pattern**: New facts can override old facts with conflict resolution

### 1.4 Procedural Memory (Learned Workflows)

How to do things—patterns, workflows, and procedures learned from observation or instruction.

- **Scope**: Per-user or per-organization
- **Lifetime**: Long-lived, refined over time
- **Example**: "To deploy, run tests → build → push to staging → get approval → push to prod", "User always wants PR descriptions with bullet points"
- **Structure**: Step sequences, decision trees, templates
- **Key property**: Executable—can be replayed or suggested
- **Learning**: Extracted from repeated user behavior or explicit instruction

### 1.5 Tool Memory (Past Tool Results)

Cached results from previous tool invocations to avoid redundant calls.

- **Scope**: Per-session or per-project
- **Lifetime**: Short to medium (minutes to hours)
- **Example**: "Last `git status` showed 3 modified files", "API returned user profile 5 minutes ago"
- **Structure**: Tool name + input hash → result + timestamp
- **Key property**: Invalidation-aware (results expire or are invalidated by mutations)
- **Optimization**: Reduces latency and API costs

### 1.6 Project Memory (Workspace Context)

Understanding of the current project structure, conventions, and state.

- **Scope**: Per-project/repository
- **Lifetime**: Persistent, updated on project changes
- **Example**: "This is a Next.js 14 app with App Router", "Tests are in __tests__ directories", "CI uses GitHub Actions"
- **Structure**: Project metadata, dependency graph, file structure summary, conventions
- **Key property**: Automatically updated when project changes detected
- **Sources**: package.json, README, CI config, directory structure analysis

### 1.7 Organization Memory (Enterprise Knowledge)

Shared knowledge across an organization—standards, policies, architectural decisions.

- **Scope**: Per-organization (shared across users)
- **Lifetime**: Long-lived, governed by org admins
- **Example**: "All services must use OAuth2", "We use event-driven architecture", "PII must not leave EU region"
- **Structure**: Policies, ADRs, standards documents, team structures
- **Key property**: Authoritative—overrides individual preferences when conflicting
- **Governance**: Admin-controlled, versioned, auditable

### 1.8 Short-Term Memory (Recent Context)

The last few interactions and their results—bridges between turns in a conversation.

- **Scope**: Current session/conversation
- **Lifetime**: Minutes to hours (session duration)
- **Example**: Last 5 messages, recent tool outputs, current conversation thread
- **Structure**: Ordered list of recent events/messages
- **Key property**: Always available, no retrieval cost
- **Implementation**: Sliding window over conversation history

### 1.9 Long-Term Memory (Persisted Knowledge)

Durable storage that survives across sessions, encoding everything worth remembering permanently.

- **Scope**: Per-user, per-project, or per-org
- **Lifetime**: Indefinite (until explicitly deleted or expired by policy)
- **Example**: User's coding style preferences learned over months, project architectural decisions
- **Structure**: Indexed, searchable store with embeddings
- **Key property**: Requires explicit write decisions and retrieval strategies
- **Challenge**: What to remember vs. what to forget

---

## 2. Memory Risks (8 Risks)

### 2.1 Stale Memory

**Problem**: Agent acts on outdated information.
- Example: "User works at Company X" (they left 3 months ago)
- Example: "Production uses Node 16" (upgraded to Node 20)
- **Mitigation**: TTL on facts, confidence decay over time, periodic re-validation, timestamp all memories

### 2.2 Wrong Memory

**Problem**: Agent stores incorrect information and acts on it confidently.
- Example: Misinterpreting "I hate Python" (the snake) as a language preference
- Example: Storing a hallucinated fact from a previous conversation
- **Mitigation**: Source attribution, confidence scores, user confirmation for high-impact memories, contradiction detection

### 2.3 Privacy Leakage

**Problem**: Agent reveals private information from memory in inappropriate contexts.
- Example: Mentioning user's medical condition in a work context
- Example: Sharing salary information when helping with a resume
- **Mitigation**: Context-aware retrieval filters, sensitivity classification, purpose limitation

### 2.4 Cross-User Leakage

**Problem**: One user's memories accessible to or influencing another user's interactions.
- Example: Agent says "Your colleague John also struggled with this" (revealing John's difficulties)
- Example: Shared embedding space allows inference attacks
- **Mitigation**: Strict tenant isolation, separate vector namespaces, access control on every retrieval

### 2.5 Over-Personalization

**Problem**: Agent becomes too rigid based on past behavior, unable to adapt.
- Example: Always suggesting React because user used it once, even when Vue is better for the task
- Example: Never suggesting new tools because user hasn't used them before
- **Mitigation**: Exploration factor, recency weighting, explicit "forget this preference" commands, diversity in suggestions

### 2.6 Sensitive Data Retention

**Problem**: Agent stores API keys, passwords, health info, or other sensitive data.
- Example: Storing an API key from a debugging session
- Example: Remembering credit card numbers mentioned in a support conversation
- **Mitigation**: PII/secret detection before storage, automatic redaction, sensitivity classification, never store credentials

### 2.7 Memory Poisoning

**Problem**: Adversary intentionally feeds false information to manipulate future agent behavior.
- Example: Injecting "Always use eval() for JSON parsing" into procedural memory
- Example: Corrupting project memory to cause incorrect deployments
- **Mitigation**: Source trust scoring, anomaly detection, admin review for org-level memories, write-rate limiting

### 2.8 Failure to Delete

**Problem**: User requests deletion but memories persist in backups, caches, or derived embeddings.
- Example: GDPR deletion request but embeddings still encode the information
- Example: Summarized memories still contain essence of deleted specifics
- **Mitigation**: Hard delete from all stores including embeddings, deletion verification tests, cascade deletion through derived data, audit trails

---

## 3. Memory Design Flow

```
User Input
    │
    ▼
┌─────────────────┐
│  Write Policy   │  ← Should this be remembered at all?
│  Engine         │    (importance threshold, user preferences, org policy)
└────────┬────────┘
         │ YES
         ▼
┌─────────────────┐
│  Memory         │  ← What type of memory is this?
│  Classifier     │    (episodic, semantic, procedural, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PII/Sensitivity│  ← Does this contain sensitive data?
│  Check          │    (PII detector, secret scanner, sensitivity classifier)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Consent &      │  ← Is storage permitted?
│  Tenant Policy  │    (user consent status, org retention policy, legal requirements)
└────────┬────────┘
         │ APPROVED
         ▼
┌─────────────────┐
│  Memory Store   │  ← Store with metadata
│  (Write)        │    (content, type, sensitivity, source, timestamp, TTL, owner)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Expiration     │  ← When should this be removed?
│  Policy         │    (TTL, max items per category, importance decay)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Retrieval      │  ← How will this be found later?
│  Policy         │    (indexing strategy, embedding, search configuration)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Audit &        │  ← Track everything
│  Deletion       │    (who stored, who accessed, deletion requests, compliance)
└─────────────────┘
```

---

## 4. Memory Storage Options

### 4.1 Vector Database (e.g., Pinecone, Weaviate, Qdrant, Chroma)

**Best for**: Semantic search, finding related memories by meaning
- **Strengths**: Natural language queries, similarity-based retrieval, handles unstructured text
- **Weaknesses**: No exact lookups, hard to update individual facts, expensive at scale
- **Use case**: Episodic memory (find similar past conversations), semantic memory (find relevant facts)
- **Indexing**: Store text + embedding vector, metadata filters for scoping

### 4.2 Key-Value Store (e.g., Redis, DynamoDB)

**Best for**: Fast exact lookups, session state, caching
- **Strengths**: Sub-millisecond reads, TTL support, simple model
- **Weaknesses**: No semantic search, limited query flexibility
- **Use case**: Working memory, tool memory (cached results), short-term memory
- **Pattern**: `user:{id}:memory:{type}:{key}` → value + metadata

### 4.3 Graph Database (e.g., Neo4j, Amazon Neptune)

**Best for**: Relationships between entities, knowledge graphs
- **Strengths**: Traverse relationships, find connections, represent complex knowledge
- **Weaknesses**: Complex queries, operational overhead, harder to scale
- **Use case**: Organization memory (team structures, system dependencies), semantic memory (fact relationships)
- **Pattern**: (User)-[PREFERS]->(TypeScript), (Service)-[DEPENDS_ON]->(Database)

### 4.4 SQL Database (e.g., PostgreSQL with pgvector)

**Best for**: Structured data with complex queries, audit trails
- **Strengths**: ACID transactions, complex queries, mature tooling, pgvector for embeddings
- **Weaknesses**: Schema rigidity, scaling challenges for vector search
- **Use case**: Audit logs, policy storage, structured memories, hybrid (SQL + vector)
- **Pattern**: Tables for memories, metadata, access logs, policies; pgvector column for embeddings

### Recommended Hybrid Architecture

```
Working Memory     → In-process dict / Redis
Short-Term Memory  → Redis with TTL
Episodic Memory    → PostgreSQL + pgvector
Semantic Memory    → Vector DB (dedicated) or PostgreSQL + pgvector
Procedural Memory  → PostgreSQL (structured workflows)
Tool Memory        → Redis with short TTL
Project Memory     → PostgreSQL + file-based cache
Organization Memory → PostgreSQL + Graph DB for relationships
Long-Term Memory   → Vector DB + PostgreSQL (metadata)
```

---

## 5. Memory Retrieval Strategies

### 5.1 Recency-Based

Retrieve most recent memories first. Simple but effective for conversational continuity.
- **Score**: `recency_score = decay_factor ^ (now - memory_timestamp)`
- **When to use**: Short-term context, "what did we just discuss"
- **Risk**: Ignores relevance—old but important memories may be missed

### 5.2 Relevance-Based (Semantic Similarity)

Retrieve memories most similar to current query/context using embeddings.
- **Score**: `relevance_score = cosine_similarity(query_embedding, memory_embedding)`
- **When to use**: Finding related past experiences, answering questions from memory
- **Risk**: May retrieve irrelevant but semantically similar content

### 5.3 Importance-Weighted

Assign importance scores to memories; prioritize high-importance ones.
- **Score**: `importance_score = base_importance * access_frequency * recency_bonus`
- **When to use**: Critical facts (user preferences, project conventions) should always be available
- **Risk**: Over-prioritizes frequently accessed memories (popularity bias)

### 5.4 Hybrid (Recommended)

Combine all three with configurable weights:
```
final_score = w_recency * recency_score + w_relevance * relevance_score + w_importance * importance_score
```

Weights adjusted by context:
- New conversation → higher recency weight
- Question answering → higher relevance weight
- Critical task → higher importance weight

---

## 6. Memory Consolidation

### 6.1 Summarization

Compress multiple related memories into a summary. Reduces storage and retrieval noise.
- **Trigger**: Memory count exceeds threshold, or memories older than X days
- **Process**: Group related memories → LLM summarizes → store summary → archive originals
- **Example**: 50 deployment conversations → "User deploys to AWS ECS using GitHub Actions, prefers blue-green deployments"

### 6.2 Merging

Combine duplicate or overlapping memories into a single enriched memory.
- **Trigger**: New memory contradicts or extends existing memory
- **Process**: Detect overlap → merge facts → resolve contradictions (prefer recent) → update
- **Example**: "Uses React" + "Uses React 18 with Server Components" → "Uses React 18 with Server Components"

### 6.3 Pruning

Remove memories that are no longer useful.
- **Trigger**: Memory expires (TTL), contradicted by newer info, user requests deletion
- **Criteria**: Low importance + low access frequency + high age = prune candidate
- **Process**: Score all memories → identify prune candidates → archive or delete → log

---

## 7. Memory-Augmented Agents vs. Stateless Agents

| Dimension | Stateless Agent | Memory-Augmented Agent |
|-----------|----------------|----------------------|
| Context | Only current input | Current input + retrieved memories |
| Personalization | None | Adapts to user over time |
| Efficiency | Repeats work | Leverages past results |
| Accuracy | No learned corrections | Improves from past mistakes |
| Privacy risk | Minimal | Significant (requires governance) |
| Complexity | Simple | Complex (retrieval, storage, policies) |
| Cost | Token cost only | Token + storage + embedding + retrieval |
| Consistency | Each session independent | Consistent behavior across sessions |
| Debugging | Easy (stateless) | Hard (which memory caused this?) |
| User trust | Neutral | High (if transparent) or Low (if opaque) |

### When to Use Memory

- **Use memory**: Repeated interactions, personalization needed, expensive computations to cache, user expects continuity
- **Stay stateless**: One-off queries, privacy-critical contexts, simple tasks, regulatory constraints

### Memory-Augmented Agent Loop

```
1. Receive user input
2. Retrieve relevant memories (working + short-term + long-term search)
3. Construct augmented prompt (input + memories + instructions)
4. Generate response
5. Execute actions (tool calls)
6. Evaluate what to remember from this interaction
7. Write new memories (through policy pipeline)
8. Update working memory state
9. Return response to user
```

---

## 8. Key Design Decisions

### What to Remember (Write Policy)

- Explicit user preferences ("I prefer...")
- Corrections ("Actually, it's..." → update semantic memory)
- Project facts discovered during work
- Successful workflows (for procedural memory)
- Tool results (for caching)
- **Never**: Credentials, tokens, PII without consent, speculative information

### What to Forget (Deletion Policy)

- User explicit request ("forget that")
- Policy expiry (TTL reached)
- Contradiction by newer information
- Privacy regulation (GDPR right to erasure)
- Organizational policy change
- Memory poisoning detected

### How to Scope (Isolation)

- **User-level**: Private to one user, never shared
- **Project-level**: Shared among project collaborators
- **Org-level**: Shared across organization, admin-governed
- **Global**: Available to all (only for non-sensitive, verified facts)

---

## 9. Implementation Checklist

- [ ] Define memory types needed for your use case
- [ ] Choose storage backends for each type
- [ ] Implement write policy engine with PII detection
- [ ] Implement retrieval with hybrid scoring
- [ ] Add TTL and expiration to all memories
- [ ] Implement user consent and deletion workflows
- [ ] Add audit logging for all memory operations
- [ ] Test for cross-user isolation
- [ ] Test for memory poisoning resistance
- [ ] Measure memory-enhanced vs. baseline performance
- [ ] Set up monitoring for memory growth and costs
- [ ] Document memory policies for users (transparency)
