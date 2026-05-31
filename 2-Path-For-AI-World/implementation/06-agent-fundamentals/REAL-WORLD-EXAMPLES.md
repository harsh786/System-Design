# Agent Fundamentals: Real-World Examples

## Case Study 1: Devin's Observe-Plan-Act Loop

### Background

Devin (by Cognition Labs) is an AI software engineer that autonomously completes coding tasks. It implements a classic observe-plan-act (OPA) loop with persistent state, tool use, and self-correction.

### The Loop in Action

**Task:** "Add pagination to the /api/users endpoint in our Express app"

```
═══ ITERATION 1: OBSERVE ═══
Action: Read project structure
Tools used: [list_directory, read_file("package.json"), read_file("src/routes/users.ts")]
Observations:
  - Express.js + TypeScript project
  - Current /api/users returns all users (no pagination)
  - Using Prisma ORM with PostgreSQL
  - Existing pagination utility in src/utils/pagination.ts (!)
  - Tests exist in tests/routes/users.test.ts

═══ ITERATION 1: PLAN ═══
Plan:
  1. Understand existing pagination utility API
  2. Modify /api/users handler to accept page/limit params
  3. Use existing pagination utility with Prisma
  4. Update tests
  5. Run tests to verify

═══ ITERATION 2: OBSERVE ═══
Action: Read pagination utility
Tools used: [read_file("src/utils/pagination.ts")]
Observations:
  - paginate(query, { page, limit }) → { data, meta: { total, page, lastPage } }
  - Already handles edge cases (page < 1, limit > 100)
  - Returns standardized response format

═══ ITERATION 2: ACT ═══
Action: Modify users route
Tools used: [edit_file("src/routes/users.ts")]
Changes:
  - Added query param parsing: page = parseInt(req.query.page) || 1
  - Added limit parsing: limit = parseInt(req.query.limit) || 20
  - Replaced prisma.user.findMany() with paginate(prisma.user, { page, limit })
  - Updated response to include meta field

═══ ITERATION 3: ACT ═══
Action: Update tests
Tools used: [edit_file("tests/routes/users.test.ts")]
Changes:
  - Added test: "returns paginated results with default page size"
  - Added test: "respects custom page and limit params"
  - Added test: "returns 400 for invalid page number"

═══ ITERATION 4: OBSERVE ═══
Action: Run tests
Tools used: [run_command("npm test")]
Observations:
  - 2 tests pass ✓
  - 1 test fails ✗ — "returns 400 for invalid page number"
  - Error: Expected 400, got 200. The pagination utility silently 
    defaults invalid pages to 1 instead of throwing.

═══ ITERATION 4: PLAN (REPLAN) ═══
Revised plan:
  - Option A: Add validation before calling paginate
  - Option B: Change test expectation to match actual behavior
  - Decision: Option A (explicit validation is better API design)

═══ ITERATION 5: ACT ═══
Action: Add input validation
Tools used: [edit_file("src/routes/users.ts")]
Changes:
  - Added validation: if page < 1 || limit < 1, return 400
  - Added max limit check: if limit > 100, return 400

═══ ITERATION 6: OBSERVE ═══
Action: Run tests again
Tools used: [run_command("npm test")]
Result: All 3 tests pass ✓

═══ COMPLETION ═══
Summary: Added pagination to /api/users using existing utility.
Files modified: 2 (users.ts, users.test.ts)
Total iterations: 6
Total time: 47 seconds
```

### Key Design Patterns in Devin

1. **Observation before action:** Always reads existing code before modifying. Found the pagination utility that a naive agent would have reimplemented.
2. **Replanning on failure:** When the test failed, it didn't blindly retry — it diagnosed *why* and chose between two fix strategies.
3. **Bounded loops:** Maximum 25 iterations per task. If unresolved, escalates to human.
4. **Working memory:** Maintains a scratchpad of discovered facts (e.g., "pagination utility exists at src/utils/pagination.ts") to avoid re-reading files.

---

## Case Study 2: Customer Support Refund Agent at Zappos

### State Machine Design

```
┌─────────────┐
│ GREETING    │──→ Identify customer + order
└─────────────┘
       │
       ▼
┌─────────────┐
│ UNDERSTAND  │──→ What's the issue? 
└─────────────┘    (return, exchange, complaint, damage)
       │
       ▼
┌─────────────┐
│ VERIFY      │──→ Check order status, return window, item condition
└─────────────┘
       │
       ▼
┌─────────────────┐
│ DETERMINE_ACTION│──→ Policy lookup → eligible actions
└─────────────────┘
       │
       ├──→ [Auto-approve: refund ≤ $75, within 30 days]
       ├──→ [Auto-approve: exchange, item in stock]  
       ├──→ [Escalate: refund > $200, outside window]
       └──→ [Escalate: repeated returns, fraud signals]
              │
              ▼
┌─────────────┐
│ EXECUTE     │──→ Process refund/exchange via tools
└─────────────┘
       │
       ▼
┌─────────────┐
│ CONFIRM     │──→ Confirm with customer, offer anything else
└─────────────┘
```

### Real Conversation with Tool Calls

```
Customer: "Hi, I ordered some running shoes last week but they're too 
          small. Order #ZP-449821. Can I get a refund?"

Agent internal state: GREETING → UNDERSTAND
Agent thinks: Return request, need to verify order and eligibility.

[Tool call: lookup_order(order_id="ZP-449821")]
→ Result: {
    customer: "Sarah M.", 
    item: "Nike Pegasus 40, Size 8",
    price: $129.99,
    ordered: "2024-01-15",
    delivered: "2024-01-18",
    return_window_ends: "2024-02-17"
  }

Agent internal state: VERIFY
Agent thinks: Order found. Price $129.99 (above $75 auto-approve for 
  refund, but within policy for shoes). Return window open. Check 
  return policy for footwear.

[Tool call: check_policy(category="footwear", action="return")]
→ Result: {
    eligible: true,
    conditions: ["unworn", "original box"],
    refund_method: "original payment",
    processing_days: 5-7
  }

Agent internal state: DETERMINE_ACTION
Agent thinks: Eligible for refund. Price $129.99 exceeds $75 
  auto-approve threshold but footwear has special policy allowing 
  up to $200 auto-approve. Proceeding.

Agent response: "Hi Sarah! I can see your Nike Pegasus 40 order from 
  January 15th. I'd be happy to help with a return. Since they're 
  within our 30-day window, you're eligible for a full refund of 
  $129.99. Just to confirm — are the shoes unworn and do you still 
  have the original box?"

Customer: "Yes, I only tried them on inside. Box is fine."

Agent internal state: EXECUTE

[Tool call: initiate_return(order_id="ZP-449821", reason="sizing", 
  refund_amount=129.99, refund_method="original_payment")]
→ Result: {return_label_url: "https://...", return_id: "RT-88291"}

[Tool call: send_email(customer_email="sarah@...", 
  template="return_label", data={return_id: "RT-88291"})]
→ Result: {sent: true}

Agent response: "All set! I've initiated your return and sent a prepaid 
  shipping label to your email. Once we receive the shoes (usually 3-5 
  business days after you ship), your refund of $129.99 will be 
  processed within 5-7 business days to your original payment method.
  
  Would you like me to help you find the right size, or is there 
  anything else I can help with?"

Agent internal state: CONFIRM
```

### Escalation Example

```
Customer: "I want a refund for 12 pairs of shoes I bought over the 
          past 3 months."

[Tool call: lookup_customer_history(customer_id="C-29481")]
→ Result: {
    returns_last_90_days: 9,
    return_rate: 73%,
    fraud_score: 0.82  ← HIGH
  }

Agent internal state: DETERMINE_ACTION → ESCALATE
Agent thinks: High return frequency + fraud score 0.82 exceeds 0.7 
  threshold. Escalating to human agent with context.

[Tool call: escalate_to_human(
  reason="potential_abuse",
  context="12-item return request, 73% return rate, fraud_score 0.82",
  customer_id="C-29481",
  suggested_action="review_account_for_wardrobing"
)]

Agent response: "I'd be happy to help with your returns. Given the 
  number of items, let me connect you with a specialist who can 
  process everything efficiently. One moment please..."
```

---

## Case Study 3: Cursor's Code Editing Agent

### Bounded Loops with Undo Capability

Cursor's AI code editor implements agents with strict safety rails:

```
Configuration:
  max_file_edits_per_turn: 5
  max_lines_changed_per_file: 200
  undo_buffer: last 10 actions
  human_confirmation_triggers:
    - deleting more than 20 lines
    - modifying files outside current directory
    - running shell commands
    - modifying config files (.env, package.json, tsconfig)
```

### Real Interaction Pattern

```
User: "Refactor the UserService class to use dependency injection 
       instead of direct instantiation"

Agent plan:
  1. Read UserService to understand current structure
  2. Identify dependencies (direct `new` calls)
  3. Create interface for each dependency
  4. Modify constructor to accept interfaces
  5. Update all call sites
  6. Run type checker

Agent execution:
  Step 1: Read src/services/UserService.ts (no confirmation needed)
  Step 2: Found 3 direct instantiations:
    - new DatabaseClient()
    - new EmailService()  
    - new CacheManager()
  Step 3: Creating interfaces...
    [CONFIRM? Creating new file: src/interfaces/IDatabase.ts] → User: ✓
    [CONFIRM? Creating new file: src/interfaces/IEmailService.ts] → User: ✓
    [CONFIRM? Creating new file: src/interfaces/ICacheManager.ts] → User: ✓
  Step 4: Modifying UserService constructor...
    [Shows diff preview, 45 lines changed] → User: ✓
  Step 5: Updating call sites...
    [CONFIRM? Modifying 7 files] → User: ✓
    Files: app.ts, tests/user.test.ts, services/index.ts, ...
  Step 6: Running tsc --noEmit...
    Result: 2 type errors in tests/user.test.ts
    
  Step 7 (self-correction): Fixing test file...
    [Shows diff: updating test to use mock implementations]
    Result: tsc passes ✓

UNDO available: "Undo all 10 changes" or "Undo last change only"
```

### Why Human Confirmation Matters

Cursor found that without confirmation gates:
- 3.2% of agent actions caused unintended side effects
- 0.8% required manual git reset to recover from
- Most common failure: modifying a file the user didn't intend to change

With confirmation gates:
- Users reject 7% of proposed actions (catching mistakes early)
- Recovery actions (undo) used only 0.4% of the time
- User trust score: 4.7/5 (vs 3.9/5 without gates)

---

## Agent Autonomy Levels in Practice

### L1 — Full Supervision (JPMorgan Chase, Trading Operations)

```
Context: AI agent assists traders with order preparation

Every action requires human approval:
  Agent: "Based on the alpha signal, I recommend buying 50,000 shares 
          of AAPL at limit $178.50. Shall I prepare this order?"
  Human: "Approved" or "Modify to 30,000 shares" or "Reject"

  Agent: "Order prepared. Ready to submit to exchange?"
  Human: "Submit"

Why L1: Regulatory requirement (SEC Rule 15c3-5 requires pre-trade 
  risk checks by qualified humans). Single trade errors can cost 
  millions. Latency tolerance: minutes (not HFT).

Approval rate: 87% (agent recommendations are good, but 13% get modified)
Value: Saves 20 minutes of manual order preparation per trade
```

### L3 — Batch Approval (Series A Startup, DevOps Agent)

```
Context: AI agent manages infrastructure changes

Agent operates freely within guardrails, reports batch results:
  
  Morning report:
  "Overnight actions taken (auto-approved within policy):
    ✓ Scaled web tier from 3 to 5 pods (CPU > 70% for 10min)
    ✓ Rotated 2 expiring TLS certificates  
    ✓ Applied 3 non-breaking dependency updates (patch versions)
    ✓ Cleared 47GB of old log files
    
  Actions requiring your approval:
    ? Upgrade PostgreSQL 15.2 → 15.4 (minor version, but DB)
    ? Scale down ML training cluster (idle 48h, saves $340/day)
    ? Investigate: unusual spike in 5xx errors at 3:42 AM (resolved itself)"

  Human reviews batch, approves/rejects pending items.

Why L3: Startup moves fast, can't have human approval for every 
  auto-scale event. But database changes and cost decisions need review.

Guardrails:
  - Auto-approve: scaling within 2x, certificate rotation, patch updates
  - Require approval: database changes, >$100/day cost changes, security events
  - Hard block: production data deletion, network policy changes, IAM modifications
```

### L5 — Full Autonomy (Research Lab, Paper Exploration Agent)

```
Context: AI agent explores research papers and synthesizes findings

Agent operates with no approval gates:
  
  User (Monday): "Explore the latest work on constitutional AI and 
  summarize key findings by Friday"
  
  Agent (autonomously over 5 days):
    - Searched Semantic Scholar: 847 papers mentioning "constitutional AI"
    - Filtered to 2023-2024: 156 papers
    - Read abstracts, selected 34 most relevant
    - Full-text analyzed 34 papers
    - Identified 5 research clusters
    - Synthesized 12-page report with citations
    - Generated comparison table of approaches
    - Identified 3 open research questions
    - Sent weekly progress update on Wednesday
    
  Friday delivery: Complete research synthesis

Why L5: No real-world consequences. Agent can't break anything. 
  Worst case: wasted compute on irrelevant papers. Cost ceiling: ~$15.
  Value of human interruption: near zero (human can't judge paper 
  relevance faster than the agent).
```

---

## Agent Improvement Loop: Ramp's Expense Agent (62% → 89%)

### Month 1: Baseline (62% task success)

**System:** Agent classifies expenses, checks policy compliance, and auto-approves/rejects expense reports.

**Failure analysis (sample of 500 failed tasks):**
```
Failure type                          | % of failures
─────────────────────────────────────────────────────
Misclassified expense category        | 31%
Didn't check correct policy version   | 22%
Hallucinated policy rules             | 18%
Couldn't parse receipt image          | 15%
Timeout on complex multi-line reports | 14%
```

### Month 2: Targeted Fixes (62% → 76%)

**Lever 1 — Better prompting for classification (+8%):**
- Added 50 few-shot examples of tricky categorizations
- "Client dinner at hotel restaurant" → Entertainment (not Travel)
- "Uber to airport" → Travel (not Transportation)

**Lever 2 — Grounded policy retrieval (+4%):**
- Replaced "policy knowledge in prompt" with RAG over policy documents
- Eliminated hallucinated policy rules entirely

**Lever 3 — Structured receipt parsing (+2%):**
- Switched from GPT-4V raw to specialized receipt OCR (Veryfi API) + GPT-4 for interpretation
- Receipt parsing accuracy: 71% → 94%

### Month 3: Systemic Improvements (76% → 89%)

**Lever 4 — Timeout fixes (+5%):**
- Multi-line expense reports were hitting 30s timeout
- Solution: Process line items in parallel, then aggregate
- Max processing time reduced from 45s to 12s

**Lever 5 — Confidence-based routing (+4%):**
- Instead of always deciding, agent now routes low-confidence cases to humans
- Threshold: confidence < 0.75 → human review
- Agent handles 82% of reports; human handles 18%
- But the 82% it handles, it gets right 93% of the time

**Lever 6 — Feedback loop (+4%):**
- When humans override agent decisions, those cases become training examples
- Monthly fine-tuning on accumulated corrections
- Category: "client gifts" accuracy went from 45% to 88% after 200 corrections

### Improvement Timeline

```
Month 1: 62% ──── baseline
Month 2: 76% ──── prompting + RAG + better tools
Month 3: 89% ──── routing + feedback + parallelization

Key insight: The biggest gains came from NOT trying to make the agent 
handle everything. Routing 18% of cases to humans and nailing the 
remaining 82% was better than trying to get 100% automation at 75% accuracy.
```

---

## Tool Calling Patterns: Real Production Schemas

### Slack Tool (from an internal ops agent)

```json
{
  "name": "slack_send_message",
  "description": "Send a message to a Slack channel or user. Use for notifications, updates, and team communication.",
  "parameters": {
    "type": "object",
    "properties": {
      "channel": {
        "type": "string",
        "description": "Channel name (e.g., '#engineering') or user ID (e.g., 'U024BE7LH')"
      },
      "message": {
        "type": "string",
        "description": "Message text. Supports Slack markdown."
      },
      "thread_ts": {
        "type": "string",
        "description": "Thread timestamp to reply in a thread. Omit for new message."
      },
      "blocks": {
        "type": "array",
        "description": "Rich message blocks (Block Kit format). Use for structured messages."
      }
    },
    "required": ["channel", "message"]
  }
}
```

### Jira Tool (from a project management agent)

```json
{
  "name": "jira_create_issue",
  "parameters": {
    "type": "object",
    "properties": {
      "project_key": {"type": "string", "description": "e.g., 'ENG', 'INFRA'"},
      "issue_type": {"type": "string", "enum": ["Bug", "Story", "Task", "Epic"]},
      "summary": {"type": "string", "maxLength": 255},
      "description": {"type": "string", "description": "Jira markdown format"},
      "priority": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
      "assignee": {"type": "string", "description": "Atlassian account ID"},
      "labels": {"type": "array", "items": {"type": "string"}},
      "story_points": {"type": "integer", "minimum": 1, "maximum": 21}
    },
    "required": ["project_key", "issue_type", "summary"]
  }
}
```

### SQL Tool (with safety constraints)

```json
{
  "name": "execute_sql",
  "description": "Execute a read-only SQL query against the analytics database. CANNOT modify data.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "SELECT query only. INSERT/UPDATE/DELETE/DROP will be rejected."
      },
      "database": {
        "type": "string",
        "enum": ["analytics", "reporting"],
        "description": "Target database. Production DB not accessible."
      },
      "timeout_seconds": {
        "type": "integer",
        "default": 30,
        "maximum": 120
      },
      "row_limit": {
        "type": "integer",
        "default": 1000,
        "maximum": 10000
      }
    },
    "required": ["query"]
  }
}
```

### GitHub Tool (from a code review agent)

```json
{
  "name": "github_create_pull_request",
  "parameters": {
    "type": "object", 
    "properties": {
      "repo": {"type": "string", "description": "owner/repo format"},
      "title": {"type": "string"},
      "body": {"type": "string", "description": "PR description in markdown"},
      "head": {"type": "string", "description": "Source branch"},
      "base": {"type": "string", "description": "Target branch", "default": "main"},
      "draft": {"type": "boolean", "default": false},
      "reviewers": {"type": "array", "items": {"type": "string"}},
      "labels": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["repo", "title", "head"]
  }
}
```

### Calendar Tool (from a scheduling agent)

```json
{
  "name": "calendar_find_availability",
  "parameters": {
    "type": "object",
    "properties": {
      "attendees": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Email addresses of required attendees"
      },
      "duration_minutes": {"type": "integer", "minimum": 15, "maximum": 480},
      "date_range": {
        "type": "object",
        "properties": {
          "start": {"type": "string", "format": "date"},
          "end": {"type": "string", "format": "date"}
        }
      },
      "preferences": {
        "type": "object",
        "properties": {
          "preferred_times": {"type": "string", "enum": ["morning", "afternoon", "any"]},
          "avoid_back_to_back": {"type": "boolean"},
          "timezone": {"type": "string"}
        }
      }
    },
    "required": ["attendees", "duration_minutes", "date_range"]
  }
}
```

---

## Agent Failure Modes: Top 5 in Production

### Failure Mode 1: Infinite Loops (23% of production failures)

**What happens:** Agent gets stuck repeating the same action because it doesn't detect lack of progress.

**Real example:** A coding agent kept running `npm test`, seeing a failure, making the same incorrect fix, running tests again — 14 times before timeout.

**Detection:**
```python
def detect_loop(action_history, window=5):
    recent = action_history[-window:]
    # Check if same tool called with same/similar params
    unique_actions = set((a.tool, hash(str(a.params))) for a in recent)
    if len(unique_actions) <= 2 and len(recent) >= window:
        return True  # Stuck in loop
    return False
```

**Prevention:**
- Track action history; if same action repeated 3x, force a different approach
- Implement "reflection" step after 3 iterations: "Am I making progress?"
- Hard cap on iterations (typically 10-25 depending on task complexity)

### Failure Mode 2: Tool Misuse (19% of production failures)

**What happens:** Agent calls the right tool with wrong parameters, or wrong tool entirely.

**Real example:** Agent called `delete_file("src/index.ts")` when it meant to call `edit_file("src/index.ts", ...)`. The file was deleted instead of modified.

**Detection:**
- Pre-execution validation of parameters against schemas
- Semantic check: does this action align with the stated plan?
- "Destructive action" classifier on tool calls

**Prevention:**
- Destructive tools require explicit confirmation
- Parameter validation with helpful error messages
- Provide tool usage examples in the system prompt
- Implement "dry run" mode for dangerous operations

### Failure Mode 3: Context Window Overflow (18% of production failures)

**What happens:** Agent accumulates too much context from observations, loses track of its goal, starts producing incoherent or contradictory actions.

**Real example:** After reading 15 files to understand a codebase, the agent's context was 90% file contents. It forgot the original task and started "improving" unrelated code.

**Detection:**
```python
def check_context_health(context_tokens, task_description_tokens):
    ratio = task_description_tokens / context_tokens
    if ratio < 0.01:  # Task is <1% of context
        return "context_overflow_risk"
    return "healthy"
```

**Prevention:**
- Summarize observations instead of storing raw content
- Sliding window: keep last N observations, summarize older ones
- Hierarchical memory: full detail for current step, summaries for previous steps
- Periodic "goal reminder" injection into context

### Failure Mode 4: Premature Termination (22% of production failures)

**What happens:** Agent declares task complete when it's only partially done.

**Real example:** Agent was asked to "add error handling to all API endpoints." It added try-catch to 3 of 12 endpoints and declared success.

**Detection:**
- Verification step: "Does my output satisfy ALL requirements in the original task?"
- Automated checks: run tests, check coverage, validate against acceptance criteria
- Checklist matching: compare completed items against decomposed task list

**Prevention:**
- Require explicit verification step before completion
- Task decomposition with checklist tracking
- Post-completion validation tool (e.g., run tests, check lint)
- Human review gate for complex tasks

### Failure Mode 5: Hallucinated Tool Results (18% of production failures)

**What happens:** Agent "imagines" it called a tool and proceeds based on fabricated results, OR misinterprets actual tool output.

**Real example:** Agent believed it had successfully deployed code (no actual deploy tool was called) and reported "deployment complete" to the user.

**Detection:**
- Verify every tool call has a corresponding result in the execution log
- Cross-check: agent's claimed state vs actual system state
- Output validation: did the tool actually return what the agent claims?

**Prevention:**
- Structured tool execution with mandatory result parsing
- Never let the agent "skip" tool calls in reasoning
- State verification after critical actions
- Clear separation between "planning to do X" and "X was done"

---

## ReAct vs Plan-then-Execute: When Each Wins

### Benchmark Data (SWE-bench Lite, 300 tasks)

| Pattern | Success Rate | Avg Steps | Avg Tokens | Avg Time |
|---------|-------------|-----------|------------|----------|
| ReAct | 27% | 8.3 | 42,000 | 3.2 min |
| Plan-then-Execute | 31% | 6.1 | 38,000 | 2.8 min |
| Hybrid (Plan + ReAct for execution) | 36% | 7.2 | 45,000 | 3.5 min |

### When ReAct Wins

**Task type: Exploratory/diagnostic problems where the path isn't clear upfront**

Example: "Why is this test failing?"
```
ReAct approach (natural fit):
  Think: I need to understand what the test does
  Act: Read test file
  Observe: Test checks user authentication
  Think: Let me look at the auth implementation
  Act: Read auth module
  Observe: Found a typo in token validation
  Think: This is likely the bug
  Act: Fix typo
  Observe: Test passes ✓
```

ReAct excels here because each observation informs the next action. A plan would be premature — you don't know what's wrong until you look.

**Benchmark by task type:**
```
Debugging tasks: ReAct 34%, Plan-then-Execute 22%
Configuration tasks: ReAct 29%, Plan-then-Execute 38%
Feature implementation: ReAct 19%, Plan-then-Execute 35%
Refactoring: ReAct 22%, Plan-then-Execute 31%
```

### When Plan-then-Execute Wins

**Task type: Well-defined tasks with predictable steps**

Example: "Add a new REST endpoint for /api/products with CRUD operations"
```
Plan-then-Execute approach (natural fit):
  Plan:
    1. Create Product model (schema)
    2. Create ProductController with CRUD methods
    3. Add routes to router
    4. Add validation middleware
    5. Write tests
    6. Run tests
  
  Execute each step sequentially (no need to re-plan unless failure)
```

Plan-then-Execute excels here because the steps are predictable from the task description alone. ReAct would waste tokens "thinking" between obvious steps.

### The Hybrid Approach (Production Recommendation)

```
Phase 1 — Plan: Generate high-level plan (3-7 steps)
Phase 2 — Execute with ReAct: For each plan step, use ReAct loop
  - If step succeeds → next step
  - If step fails → ReAct to diagnose and fix
  - If 3+ failures → replan from current state
```

This captures Plan-then-Execute's efficiency for predictable work while retaining ReAct's adaptability when things go wrong.

---

## Agent Memory Patterns: Personal Assistant at Mem.ai

### Memory Architecture

```
┌─────────────────────────────────┐
│ Working Memory (current session) │ ← Conversation context
├─────────────────────────────────┤
│ Short-term Memory (7 days)       │ ← Recent interactions, pending tasks
├─────────────────────────────────┤
│ Long-term Memory (persistent)    │ ← User preferences, facts, patterns
├─────────────────────────────────┤
│ Episodic Memory (indexed)        │ ← Past conversations, searchable
└─────────────────────────────────┘
```

### Real Memory Operations

**Learning a preference:**
```
Session 12 (January):
  User: "Schedule my dentist appointment but not on Wednesdays, 
         I have standup all morning"
  
  Agent extracts: {
    fact: "User has standup meetings on Wednesday mornings",
    confidence: 0.9,
    source: "explicit statement",
    category: "schedule_preferences"
  }
  → Stored in long-term memory

Session 47 (March):
  User: "Find a time for a 1:1 with my manager next week"
  
  Agent recalls: "User has standup on Wednesday mornings"
  Agent action: Excludes Wednesday AM from proposed slots without 
    needing to be reminded
```

**Accumulating preferences over time:**
```
Session 5:  "Book me a flight" → User chose window seat → stored
Session 11: "Book me a flight" → User chose window seat again → confidence ↑
Session 19: "Book me a flight" → Agent proactively: "Window seat as usual?"
Session 23: "Actually I want aisle this time" → stores exception, 
            keeps window as default but confidence slightly reduced

Memory state:
{
  "flight_seat_preference": {
    "default": "window",
    "confidence": 0.85,
    "exceptions": ["2024-03-15: chose aisle (long-haul flight)"],
    "last_confirmed": "2024-02-28"
  }
}
```

### Memory Retrieval Strategy

```python
def recall_relevant_memories(current_query, user_id):
    # 1. Semantic search over long-term memory
    semantic_matches = vector_search(
        query=current_query,
        collection=f"user_{user_id}_longterm",
        top_k=10
    )
    
    # 2. Recency-weighted episodic search
    recent_episodes = search_episodes(
        query=current_query,
        user_id=user_id,
        decay_factor=0.95,  # Recent episodes weighted higher
        top_k=5
    )
    
    # 3. Always-include facts (high-importance preferences)
    pinned = get_pinned_facts(user_id)  # e.g., dietary restrictions, timezone
    
    # 4. Combine and deduplicate
    memories = deduplicate(semantic_matches + recent_episodes + pinned)
    
    # 5. Fit within context budget (max 2000 tokens for memory)
    return truncate_to_budget(memories, max_tokens=2000)
```

### Memory Challenges in Production

| Challenge | Solution |
|-----------|----------|
| Contradictory memories | Keep most recent, mark old as "superseded" |
| Stale preferences | Periodic confirmation ("Still prefer window seats?") |
| Privacy-sensitive info | Encryption at rest, user can view/delete any memory |
| Memory bloat | Consolidation: merge similar facts, archive low-access memories |
| False memories | Only store with confidence > 0.7, require 2+ confirmations for important prefs |

---

## Cost of Agent Loops: Real Token Usage Data

### Benchmark Setup

Tested the same 100 tasks (mix of coding, research, and data analysis) with different iteration budgets:

### Token Usage by Loop Length

```
3-step agent (budget: 3 iterations max):
  Average tokens per task: 12,400
  Task success rate: 54%
  Cost per task (GPT-4): $0.37
  Cost per SUCCESSFUL task: $0.69

5-step agent (budget: 5 iterations max):
  Average tokens per task: 24,800
  Task success rate: 73%
  Cost per task (GPT-4): $0.74
  Cost per SUCCESSFUL task: $1.01

10-step agent (budget: 10 iterations max):
  Average tokens per task: 48,200
  Task success rate: 82%
  Cost per task (GPT-4): $1.45
  Cost per SUCCESSFUL task: $1.77

15-step agent (budget: 15 iterations max):
  Average tokens per task: 67,100
  Task success rate: 84%
  Cost per task (GPT-4): $2.01
  Cost per SUCCESSFUL task: $2.39
```

### Diminishing Returns Analysis

```
Steps 1-3:   +54% success (18% per step)     ← highest ROI
Steps 4-5:   +19% success (9.5% per step)    ← good ROI  
Steps 6-10:  +9% success (1.8% per step)     ← diminishing
Steps 11-15: +2% success (0.4% per step)     ← rarely worth it
```

### Token Breakdown by Step

```
Step 1: ~4,000 tokens (system prompt + task + first observation)
Step 2: ~3,500 tokens (accumulated context + new action/observation)
Step 3: ~3,800 tokens (context growing)
Step 4: ~4,200 tokens
Step 5: ~4,800 tokens (context now significant)
...
Step 10: ~7,200 tokens (context dominates, observations summarized)
```

**Key insight:** Token cost grows super-linearly because each step must include all prior context. A 10-step agent uses ~4x more tokens than a 3-step agent, not 3.3x.

### Cost Optimization Strategies

1. **Adaptive budgets:** Easy tasks get 3 steps, hard tasks get 10
   ```python
   def estimate_budget(task):
       complexity = classify_complexity(task)  # simple/medium/complex
       return {"simple": 3, "medium": 5, "complex": 10}[complexity]
   ```

2. **Context compression:** Summarize observations older than 3 steps
   - Reduces step 10 from ~7,200 to ~4,500 tokens
   - Total savings: ~30% for long-running agents

3. **Early termination:** Stop if confidence > 0.95 or if verification passes
   - Average steps for successful tasks: 4.2 (vs 7.1 without early termination)

4. **Model routing:** Use GPT-3.5 for observation/tool-calling steps, GPT-4 only for planning and synthesis
   - Cost reduction: 60% with only 3% accuracy drop

### Production Recommendation

```
Default configuration:
  - Budget: 7 steps (captures 80% of value at reasonable cost)
  - Context compression: After step 4
  - Early termination: When task verification passes
  - Model routing: GPT-3.5 for tools, GPT-4 for reasoning
  - Expected cost: ~$0.45/task at GPT-4 rates
  - Expected success: ~78%
```

---

## Summary: Agent Design Decision Matrix

```
┌────────────────────┬───────────────┬────────────────┬───────────────┐
│ Decision           │ Low-risk app  │ Medium-risk    │ High-risk     │
├────────────────────┼───────────────┼────────────────┼───────────────┤
│ Autonomy level     │ L3-L5         │ L2-L3          │ L1            │
│ Loop budget        │ 3-5 steps     │ 5-7 steps      │ 7-10 steps    │
│ Human gates        │ None/batch    │ Destructive    │ Every action  │
│ Failure handling   │ Retry + log   │ Retry + alert  │ Stop + alert  │
│ Memory             │ Session only  │ Short-term     │ Full audit    │
│ Pattern            │ ReAct         │ Hybrid         │ Plan+Execute  │
│ Acceptable error   │ <10%          │ <5%            │ <1%           │
└────────────────────┴───────────────┴────────────────┴───────────────┘
```
