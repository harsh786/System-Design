# Real-World Examples: LLM Fundamentals

## 1. How GitHub Copilot Handles Context Window Engineering

### The Context Budget Problem

GitHub Copilot operates within a strict token budget (originally ~8K with Codex, now up to 128K with GPT-4o). The challenge: a typical codebase has millions of lines, but only a fraction fits in the context window.

### Copilot's Context Priority System

```
┌─────────────────────────────────────────────────────────────────┐
│              GitHub Copilot Context Assembly                      │
│              (Priority order, highest first)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Priority 1: Current cursor context (NEVER truncated)            │
│  ├── Current file: lines above and below cursor                  │
│  ├── Current function/class being edited                         │
│  └── Immediate syntax context (open brackets, etc.)              │
│                                                                   │
│  Priority 2: Adjacent context (truncated last)                   │
│  ├── Neighboring functions in same file                          │
│  ├── Import statements (reveal available APIs)                   │
│  └── Type definitions referenced by current code                 │
│                                                                   │
│  Priority 3: Cross-file context (truncated first)                │
│  ├── Recently edited files (recency-weighted)                    │
│  ├── Files open in editor tabs                                   │
│  ├── Files imported by current file                              │
│  └── Files with similar naming patterns                          │
│                                                                   │
│  Priority 4: Repository-level context                            │
│  ├── README / documentation snippets                             │
│  ├── Similar code patterns (via embedding search)                │
│  └── Test files for current module                               │
│                                                                   │
│  Budget allocation (typical for inline completion):              │
│  ├── System prompt + instructions: ~500 tokens                   │
│  ├── Current file context: ~2000 tokens                          │
│  ├── Cross-file context: ~1500 tokens                            │
│  ├── Snippet suggestions from index: ~500 tokens                 │
│  └── Reserved for completion output: ~500 tokens                 │
│  Total: ~5000 tokens per inline completion request               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Truncation Strategy (Jaccard Similarity + Suffix Scoring)

GitHub published research on their approach:

```python
# Simplified version of Copilot's context selection algorithm
def select_context_snippets(
    current_file: str,
    cursor_position: int,
    open_files: list[str],
    repo_index: EmbeddingIndex,
    token_budget: int = 4096
) -> list[ContextSnippet]:
    """Assemble context within token budget using priority scoring."""
    
    snippets = []
    remaining_budget = token_budget - 500  # Reserve for output
    
    # 1. Current file (prefix/suffix around cursor)
    prefix = current_file[:cursor_position]
    suffix = current_file[cursor_position:]
    
    # Take more prefix than suffix (code flows top-down)
    prefix_tokens = min(count_tokens(prefix), int(remaining_budget * 0.4))
    suffix_tokens = min(count_tokens(suffix), int(remaining_budget * 0.1))
    
    # Truncate prefix from the TOP (keep code closest to cursor)
    prefix_truncated = truncate_from_start(prefix, prefix_tokens)
    suffix_truncated = truncate_from_end(suffix, suffix_tokens)
    
    remaining_budget -= (prefix_tokens + suffix_tokens)
    
    # 2. Score cross-file snippets using Jaccard similarity
    candidate_snippets = []
    for file_content in open_files:
        for chunk in split_into_chunks(file_content, chunk_size=20):  # 20 lines
            score = jaccard_similarity(
                set(tokenize(prefix_truncated[-500:])),  # Recent context
                set(tokenize(chunk))
            )
            candidate_snippets.append((chunk, score))
    
    # 3. Also add embedding-based matches from repo index
    query_embedding = embed(prefix_truncated[-200:])
    repo_matches = repo_index.search(query_embedding, top_k=5)
    for match in repo_matches:
        candidate_snippets.append((match.content, match.score * 0.8))  # Slight discount
    
    # 4. Fill remaining budget with highest-scored snippets
    candidate_snippets.sort(key=lambda x: x[1], reverse=True)
    for snippet, score in candidate_snippets:
        snippet_tokens = count_tokens(snippet)
        if snippet_tokens <= remaining_budget:
            snippets.append(snippet)
            remaining_budget -= snippet_tokens
    
    return assemble_prompt(prefix_truncated, suffix_truncated, snippets)
```

### Key Design Decision: Fill-in-the-Middle (FIM)

Copilot uses FIM format rather than standard left-to-right completion:

```
<fim_prefix>
def calculate_total(items):
    subtotal = sum(item.price for item in items)
<fim_suffix>
    return total

def apply_discount(total, code):
<fim_middle>
```

This gives the model both prefix AND suffix context, dramatically improving accuracy for inserting code in the middle of a file.

---

## 2. How ChatGPT Manages System Prompts, Developer Messages, and Tool Definitions

### Message Priority Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                ChatGPT Message Hierarchy                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Layer 1: Platform System Prompt (OpenAI-controlled)             │
│  ├── Safety guidelines and refusal boundaries                    │
│  ├── Current date/time, model capabilities                       │
│  ├── Tool usage instructions (when tools available)              │
│  └── Output formatting defaults                                  │
│  ~800-1200 tokens                                                │
│                                                                   │
│  Layer 2: Developer System Message (API users set this)          │
│  ├── Role definition ("You are a customer support agent for...")  │
│  ├── Behavioral constraints ("Never discuss competitors")        │
│  ├── Output format requirements ("Always respond in JSON")       │
│  └── Domain knowledge injection                                  │
│  Typical: 200-2000 tokens                                        │
│                                                                   │
│  Layer 3: Tool Definitions (function schemas)                    │
│  ├── Each tool: name, description, parameter JSON schema         │
│  ├── Serialized into prompt as structured text                   │
│  └── Costs tokens! 10 tools ≈ 1000-2000 tokens                  │
│                                                                   │
│  Layer 4: Conversation History                                   │
│  ├── Previous user messages                                      │
│  ├── Previous assistant responses                                │
│  ├── Tool call results                                           │
│  └── TRUNCATED from the middle when budget exceeded              │
│                                                                   │
│  Layer 5: Current User Message                                   │
│  └── The latest user input (NEVER truncated)                     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Token Cost of Tool Definitions (Real Measurements)

```python
# Real token costs measured from OpenAI API (approximate)
tool_token_costs = {
    "simple_function_no_params": 50,      # get_current_time()
    "simple_function_2_params": 90,       # get_weather(city, units)
    "complex_function_5_params": 180,     # search_products(query, category, min_price, max_price, sort)
    "function_with_enum_params": 150,     # set_status(status: "active"|"inactive"|"pending")
    "function_with_nested_object": 250,   # create_order({items: [{sku, qty, ...}], shipping: {...}})
}

# ChatGPT with 15 tools defined:
# Tool definitions alone: ~2500 tokens
# At GPT-4o pricing ($2.50/1M input tokens): $0.00000625 per request just for tool definitions
# At 1M requests/day: $6.25/day just for tool definition tokens
# Multiply by conversation turns: real cost is 10-50x higher
```

### Conversation Truncation Strategy

When conversations exceed the context window, ChatGPT uses this strategy:

```
Conversation: [sys, msg1, msg2, msg3, msg4, msg5, msg6, msg7, msg8]
                                                              ↑ current

If over budget, truncate from oldest (but keep system prompt):
Keep: [sys, ..., msg5, msg6, msg7, msg8]  (recent messages preserved)
Drop: [msg1, msg2, msg3, msg4]  (oldest messages dropped)

BUT: If msg3 contains a tool_call and msg4 contains the tool_result,
     they must be dropped together (orphaned tool results confuse the model)
```

---

## 3. Real Token Cost Analysis: Customer Support Bot at Scale

### Scenario: E-commerce Customer Support (10K conversations/day)

**Company profile:** Mid-size e-commerce, 10,000 customer conversations/day, using GPT-4o

**Conversation characteristics:**
```
Average conversation: 8 turns (4 user + 4 assistant)
Average user message: 50 tokens
Average assistant response: 150 tokens
System prompt: 800 tokens
Tool definitions (5 tools): 600 tokens
RAG context per turn: 500 tokens (product info, order history)

Per-conversation token usage:
├── System prompt (sent every turn): 800 × 4 = 3,200 tokens input
├── Tool definitions (sent every turn): 600 × 4 = 2,400 tokens input
├── RAG context (per turn): 500 × 4 = 2,000 tokens input
├── User messages (accumulating): 50 × (1+2+3+4) = 500 tokens input
├── Assistant messages (accumulating): 150 × (0+1+2+3) = 900 tokens input
├── Total input tokens: ~9,000 tokens
├── Total output tokens: 150 × 4 = 600 tokens
└── Grand total: 9,600 tokens per conversation
```

**Monthly cost calculation (GPT-4o pricing: $2.50/1M input, $10/1M output):**

```
Daily:
├── Input: 10,000 conversations × 9,000 tokens = 90M input tokens
├── Output: 10,000 conversations × 600 tokens = 6M output tokens
├── Input cost: 90M × $2.50/1M = $225/day
├── Output cost: 6M × $10/1M = $60/day
└── Total: $285/day

Monthly: $285 × 30 = $8,550/month

With optimizations applied:
├── Prompt caching (OpenAI feature, 50% discount on cached): -$2,500
├── Conversation summarization after turn 4: -$1,500
├── Semantic cache (40% hit rate): -$2,000
└── Optimized total: ~$2,550/month (70% savings)
```

**Optimization techniques in detail:**

```python
# Optimization 1: Conversation summarization
# After 4 turns, summarize earlier turns to reduce token accumulation

async def manage_conversation_context(messages: list, max_tokens: int = 8000):
    """Keep conversation within budget by summarizing old messages."""
    current_tokens = count_tokens(messages)
    
    if current_tokens <= max_tokens:
        return messages
    
    # Keep system prompt + last 3 exchanges + current message
    system = messages[0]
    recent = messages[-6:]  # Last 3 user-assistant pairs
    old_messages = messages[1:-6]
    
    # Summarize old messages with a cheap model
    summary = await summarize_with_gpt35(old_messages)  # ~$0.0001
    
    return [
        system,
        {"role": "system", "content": f"Previous conversation summary: {summary}"},
        *recent
    ]

# Optimization 2: Semantic caching with embedding similarity
# Cache responses for semantically similar questions

class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.95):
        self.threshold = similarity_threshold
        self.index = FAISSIndex(dimension=1536)
    
    async def get_or_compute(self, user_message: str, context: dict):
        embedding = await get_embedding(user_message)
        
        # Search for similar previous questions
        matches = self.index.search(embedding, k=1)
        
        if matches and matches[0].score >= self.threshold:
            # Check context similarity too (same order status, same product)
            if self._context_matches(matches[0].metadata, context):
                return matches[0].response  # Cache hit!
        
        # Cache miss - compute response
        response = await call_llm(user_message, context)
        
        # Store for future cache hits
        self.index.add(embedding, {
            "response": response,
            "metadata": context,
            "timestamp": time.time()
        })
        
        return response
```

### Cost Comparison Table (Real production scenarios)

| Scenario | Model | Monthly Volume | Monthly Cost | Cost/Conversation |
|----------|-------|---------------|--------------|-------------------|
| Customer support (basic) | GPT-3.5-turbo | 300K convos | $450 | $0.0015 |
| Customer support (complex) | GPT-4o | 300K convos | $8,550 | $0.0285 |
| Customer support (optimized) | GPT-4o + cache | 300K convos | $2,550 | $0.0085 |
| Code assistant | GPT-4o | 50K sessions | $12,000 | $0.24 |
| Document analysis | GPT-4o | 100K docs | $5,000 | $0.05 |
| RAG chatbot (enterprise) | GPT-4o | 1M queries | $15,000 | $0.015 |

---

## 4. Case Study: Migrating from GPT-3.5 to GPT-4 (Quality vs Cost Tradeoffs)

### Company: "HealthAssist" - Medical Q&A Platform

**Background:** HealthAssist ran a medical information chatbot on GPT-3.5-turbo. After 6 months in production, they identified quality issues that needed GPT-4-level reasoning.

**The problem metrics (GPT-3.5-turbo):**
```
Accuracy on medical fact questions: 78%
Appropriate safety disclaimers: 85% (missed 15% of cases needing "see a doctor")
Hallucination rate on drug interactions: 12%
User satisfaction (thumbs up): 3.2/5
Monthly cost: $2,100 (500K queries/month)
```

**Migration strategy: Tiered approach (not wholesale replacement)**

```
┌─────────────────────────────────────────────────────────────────┐
│              HealthAssist Model Routing Strategy                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User Query → Complexity Classifier (fine-tuned BERT, <5ms)     │
│       │                                                          │
│       ├── Simple (60%): "What are symptoms of cold?"            │
│       │   └── GPT-3.5-turbo ($0.50/1M tokens)                  │
│       │       Sufficient accuracy, fast, cheap                   │
│       │                                                          │
│       ├── Medium (25%): "Can I take ibuprofen with lisinopril?" │
│       │   └── GPT-4o-mini ($0.15/1M tokens)                    │
│       │       Good reasoning, affordable                         │
│       │                                                          │
│       └── Complex (15%): "My labs show elevated ALT with..."    │
│           └── GPT-4o ($2.50/1M tokens)                          │
│               Best reasoning, always adds safety disclaimers     │
│                                                                   │
│  Post-migration metrics:                                         │
│  ├── Overall accuracy: 91% (from 78%)                           │
│  ├── Safety disclaimer coverage: 97% (from 85%)                 │
│  ├── Hallucination rate: 3% (from 12%)                          │
│  ├── User satisfaction: 4.1/5 (from 3.2/5)                     │
│  └── Monthly cost: $3,800 (from $2,100) - 81% increase         │
│      BUT cost per quality-adjusted query decreased              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Complexity classifier training data (how they built the router):**

```python
# They labeled 5000 queries with complexity level based on:
# 1. Does GPT-3.5 get it right? (if yes → simple)
# 2. Does it require multi-step reasoning? (if yes → complex)
# 3. Does it involve drug interactions or contraindications? (if yes → medium/complex)

training_examples = [
    ("What causes headaches?", "simple"),
    ("Is 120/80 blood pressure normal?", "simple"),
    ("Can I take metformin with alcohol?", "medium"),
    ("What are alternatives to SSRIs for anxiety?", "medium"),
    ("I have stage 3 CKD, elevated potassium, and my doctor wants to start ACE inhibitor...", "complex"),
    ("My child has fever 103F for 3 days with rash...", "complex"),
]

# Classifier: Fine-tuned DistilBERT (67M params, <5ms inference)
# Accuracy of routing: 94% (measured by human review of 500 random queries)
# Cost of classifier: negligible ($0.02/month on CPU)
```

---

## 5. Temperature/Sampling Strategy Examples from Production Systems

### Real Temperature Settings by Use Case

```python
PRODUCTION_TEMPERATURE_CONFIGS = {
    # === DETERMINISTIC TASKS (temperature = 0) ===
    "data_extraction": {
        "temperature": 0,
        "top_p": 1,
        "use_case": "Extracting structured data from documents",
        "example_companies": ["Stripe (receipt parsing)", "Plaid (bank statement parsing)"],
        "rationale": "Same input must always produce same output. No creativity needed."
    },
    "code_translation": {
        "temperature": 0,
        "top_p": 1,
        "use_case": "Converting code between languages",
        "example_companies": ["GitHub Copilot (for deterministic refactors)"],
        "rationale": "Correctness > creativity. Temperature 0 = greedy decoding."
    },
    "classification": {
        "temperature": 0,
        "top_p": 1,
        "use_case": "Categorizing support tickets, sentiment analysis",
        "example_companies": ["Intercom", "Zendesk AI"],
        "rationale": "Same ticket should always get same category."
    },
    
    # === LOW CREATIVITY (temperature = 0.1-0.3) ===
    "summarization": {
        "temperature": 0.1,
        "top_p": 0.9,
        "use_case": "Summarizing meeting notes, documents",
        "example_companies": ["Otter.ai", "Notion AI"],
        "rationale": "Slight variation acceptable, but should stay factual."
    },
    "customer_support": {
        "temperature": 0.3,
        "top_p": 0.9,
        "use_case": "Generating support responses",
        "example_companies": ["Klarna (automated support)", "Intercom Fin"],
        "rationale": "Needs to sound natural (not robotic) but stay on-script."
    },
    
    # === MEDIUM CREATIVITY (temperature = 0.5-0.7) ===
    "code_generation": {
        "temperature": 0.5,
        "top_p": 0.95,
        "use_case": "Writing new code from descriptions",
        "example_companies": ["GitHub Copilot (suggestions)", "Cursor"],
        "rationale": "Multiple valid solutions exist. Want variety across suggestions."
    },
    "email_drafting": {
        "temperature": 0.7,
        "top_p": 0.9,
        "use_case": "Drafting professional emails",
        "example_companies": ["Gmail Smart Compose (at higher creativity settings)"],
        "rationale": "Natural language variation expected. User will edit anyway."
    },
    
    # === HIGH CREATIVITY (temperature = 0.8-1.2) ===
    "creative_writing": {
        "temperature": 1.0,
        "top_p": 0.95,
        "use_case": "Marketing copy, blog posts, creative content",
        "example_companies": ["Jasper AI", "Copy.ai"],
        "rationale": "Want diverse, surprising outputs. User picks best option."
    },
    "brainstorming": {
        "temperature": 1.2,
        "top_p": 1.0,
        "use_case": "Generating diverse ideas, alternative approaches",
        "example_companies": ["Miro AI", "FigJam AI brainstorming"],
        "rationale": "Maximize diversity. Better to have wild ideas than repetitive ones."
    },
}
```

### Advanced Pattern: Dynamic Temperature (Used by Cursor)

```python
# Cursor adjusts temperature based on context
def get_dynamic_temperature(context: dict) -> float:
    """Cursor-style dynamic temperature selection."""
    
    # Completing a function signature → be deterministic
    if context["is_completing_signature"]:
        return 0.0
    
    # Filling in obvious boilerplate → low creativity
    if context["is_boilerplate_pattern"]:
        return 0.1
    
    # Writing implementation logic → medium
    if context["is_function_body"]:
        return 0.4
    
    # Writing comments/docs → slightly higher
    if context["is_comment_or_docstring"]:
        return 0.5
    
    # Chat/explain mode → natural language
    if context["is_chat_mode"]:
        return 0.7
    
    return 0.3  # Default
```

---

## 6. How Companies Handle Structured Outputs in Production

### Banking: Transaction Categorization (JPMorgan-style pattern)

```python
# Banking requires 100% schema compliance - can't have malformed JSON
# in production transaction processing

from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Optional
import json

class TransactionCategory(str, Enum):
    GROCERIES = "groceries"
    DINING = "dining"
    TRANSPORTATION = "transportation"
    UTILITIES = "utilities"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    SHOPPING = "shopping"
    INCOME = "income"
    TRANSFER = "transfer"
    OTHER = "other"

class TransactionAnalysis(BaseModel):
    category: TransactionCategory
    subcategory: Optional[str] = Field(None, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)
    merchant_normalized: str = Field(max_length=100)
    is_recurring: bool
    recurring_frequency: Optional[str] = None  # "monthly", "weekly", etc.
    
    @validator("recurring_frequency")
    def validate_recurring(cls, v, values):
        if values.get("is_recurring") and v is None:
            raise ValueError("recurring_frequency required when is_recurring=True")
        return v

# Production approach: OpenAI structured outputs with Pydantic schema
async def categorize_transaction(description: str, amount: float) -> TransactionAnalysis:
    """Production transaction categorization with guaranteed schema compliance."""
    
    response = await openai_client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "Categorize this bank transaction."},
            {"role": "user", "content": f"Transaction: {description}, Amount: ${amount}"}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "transaction_analysis",
                "strict": True,  # Guarantees schema compliance
                "schema": TransactionAnalysis.model_json_schema()
            }
        },
        temperature=0  # Deterministic categorization
    )
    
    # Parse with Pydantic validation (belt AND suspenders)
    result = TransactionAnalysis.model_validate_json(
        response.choices[0].message.content
    )
    
    return result


# Fallback for when LLM fails: Rule-based categorization
MERCHANT_RULES = {
    "walmart": TransactionCategory.GROCERIES,
    "uber": TransactionCategory.TRANSPORTATION,
    "netflix": TransactionCategory.ENTERTAINMENT,
    "cvs": TransactionCategory.HEALTHCARE,
}

def rule_based_fallback(description: str) -> TransactionAnalysis:
    """Deterministic fallback when LLM is unavailable."""
    description_lower = description.lower()
    for merchant, category in MERCHANT_RULES.items():
        if merchant in description_lower:
            return TransactionAnalysis(
                category=category,
                confidence=0.7,  # Lower confidence for rule-based
                merchant_normalized=merchant.title(),
                is_recurring=False
            )
    return TransactionAnalysis(
        category=TransactionCategory.OTHER,
        confidence=0.3,
        merchant_normalized=description[:50],
        is_recurring=False
    )
```

### Healthcare: Clinical Note Structuring (Epic/Cerner-style)

```python
# Healthcare has additional constraints:
# 1. HIPAA compliance (no PII in logs)
# 2. Audit trail required
# 3. Must flag uncertainty (never present uncertain info as fact)
# 4. Regulatory requirement: human review for any clinical decision support

class ClinicalExtraction(BaseModel):
    """Schema for extracting structured data from clinical notes.
    Used by EHR systems to auto-populate patient records."""
    
    chief_complaint: str
    symptoms: list[Symptom]
    vitals_mentioned: list[Vital]
    medications_mentioned: list[Medication]
    assessment: Optional[str]
    plan: Optional[str]
    
    # Uncertainty tracking (regulatory requirement)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    uncertain_fields: list[str] = Field(
        default_factory=list,
        description="Fields where extraction was uncertain"
    )
    requires_human_review: bool = Field(
        default=True,
        description="Always true for clinical decision support"
    )

class Symptom(BaseModel):
    name: str
    duration: Optional[str]
    severity: Optional[str] = Field(None, pattern="^(mild|moderate|severe)$")
    onset: Optional[str]

class Medication(BaseModel):
    name: str
    dosage: Optional[str]
    frequency: Optional[str]
    route: Optional[str]
    is_new_prescription: Optional[bool]  # Distinguishes current vs newly prescribed
```

---

## 7. Real-World Function Calling Patterns

### Notion AI: Document-Aware Tool Calling

```python
# Notion AI uses function calling to interact with the user's workspace
# Key pattern: Tools are contextual (available tools change based on current page type)

NOTION_AI_TOOLS = {
    # Always available
    "search_workspace": {
        "description": "Search across all pages in the user's Notion workspace",
        "parameters": {
            "query": {"type": "string"},
            "filters": {
                "type": "object",
                "properties": {
                    "page_type": {"enum": ["page", "database", "wiki"]},
                    "date_range": {"type": "string"},
                    "created_by": {"type": "string"}
                }
            }
        }
    },
    
    # Available when editing a page
    "insert_content": {
        "description": "Insert content at cursor position or end of page",
        "parameters": {
            "content": {"type": "string", "description": "Markdown content to insert"},
            "position": {"enum": ["cursor", "end", "beginning"]},
            "block_type": {"enum": ["paragraph", "heading", "bullet", "numbered", "code", "callout"]}
        }
    },
    
    # Available when in a database view
    "query_database": {
        "description": "Query the current database with filters and sorts",
        "parameters": {
            "database_id": {"type": "string"},
            "filter": {"type": "object"},
            "sort": {"type": "array"}
        }
    },
    "create_database_entry": {
        "description": "Add a new row to the current database",
        "parameters": {
            "properties": {"type": "object"}
        }
    }
}

# Key architectural decision: Notion sends ONLY relevant tools per context
# This reduces token cost and improves accuracy

def get_tools_for_context(context: dict) -> list:
    """Notion's contextual tool selection."""
    tools = [NOTION_AI_TOOLS["search_workspace"]]  # Always available
    
    if context["current_view"] == "page_editor":
        tools.append(NOTION_AI_TOOLS["insert_content"])
    elif context["current_view"] == "database":
        tools.append(NOTION_AI_TOOLS["query_database"])
        tools.append(NOTION_AI_TOOLS["create_database_entry"])
    
    # Limit to max 8 tools (measured: accuracy drops above 10 tools)
    return tools[:8]
```

### Cursor: Multi-Step Code Editing with Tool Calling

```python
# Cursor uses function calling for its "apply" feature
# Pattern: Plan-then-execute with tool calls

CURSOR_TOOLS = [
    {
        "name": "edit_file",
        "description": "Apply an edit to a file. Use search/replace blocks.",
        "parameters": {
            "file_path": {"type": "string"},
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "search": {"type": "string", "description": "Exact text to find"},
                        "replace": {"type": "string", "description": "Text to replace with"}
                    }
                }
            }
        }
    },
    {
        "name": "create_file",
        "description": "Create a new file with content",
        "parameters": {
            "file_path": {"type": "string"},
            "content": {"type": "string"}
        }
    },
    {
        "name": "read_file",
        "description": "Read a file's contents",
        "parameters": {
            "file_path": {"type": "string"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"}
        }
    },
    {
        "name": "run_terminal_command",
        "description": "Run a shell command",
        "parameters": {
            "command": {"type": "string"},
            "working_directory": {"type": "string"}
        }
    }
]

# Cursor's multi-turn tool calling pattern:
# Turn 1: Model calls read_file to understand context
# Turn 2: Model calls edit_file with precise changes
# Turn 3: Model calls run_terminal_command to verify (tests/lint)
# Turn 4: If tests fail, model calls edit_file again to fix

# Key insight: Cursor limits tool call depth to 5 turns to prevent
# infinite loops (model keeps editing and failing)
```

### GitHub Copilot Chat: Tool Calling for @workspace Commands

```python
# When user types @workspace in Copilot Chat, it triggers tool calls
# to search the repository

COPILOT_WORKSPACE_TOOLS = [
    {
        "name": "semantic_search",
        "description": "Search repository code by semantic meaning",
        "parameters": {
            "query": {"type": "string"},
            "file_pattern": {"type": "string", "description": "Glob pattern like '*.py'"},
            "max_results": {"type": "integer", "default": 10}
        }
    },
    {
        "name": "find_references",
        "description": "Find all references to a symbol",
        "parameters": {
            "symbol": {"type": "string"},
            "file_path": {"type": "string"}
        }
    },
    {
        "name": "get_file_structure",
        "description": "Get the outline/structure of a file (classes, functions)",
        "parameters": {
            "file_path": {"type": "string"}
        }
    }
]

# Pattern: Copilot makes MULTIPLE tool calls in parallel
# Example user query: "How does authentication work in this repo?"
#
# Model response (parallel tool calls):
# 1. semantic_search(query="authentication login middleware")
# 2. semantic_search(query="JWT token verification")  
# 3. find_references(symbol="authenticate", file_path="src/")
#
# All three execute in parallel, results aggregated, then model synthesizes answer
```

---

## 8. Streaming Architecture at Scale

### How ChatGPT Handles Millions of Concurrent Streams

**Architecture overview:**

```
┌─────────────────────────────────────────────────────────────────┐
│              ChatGPT Streaming Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Client (Browser/App)                                            │
│  └── EventSource / WebSocket connection                          │
│       │                                                          │
│  CloudFlare (CDN/DDoS protection)                               │
│       │                                                          │
│  Load Balancer (L7, sticky sessions per conversation)            │
│       │                                                          │
│  API Gateway (rate limiting, auth, request routing)              │
│       │                                                          │
│  Stream Coordinator Service                                      │
│  ├── Maintains SSE connection to client                         │
│  ├── Manages backpressure (if client can't consume fast enough) │
│  ├── Handles reconnection (client drops, resume from token N)   │
│  └── Buffers tokens for batch delivery (reduces overhead)       │
│       │                                                          │
│  Inference Cluster (GPU nodes)                                   │
│  ├── Generates tokens one at a time                             │
│  ├── Pushes to stream coordinator via internal gRPC stream      │
│  └── Multiple models share GPU via continuous batching           │
│                                                                   │
│  Key metrics:                                                    │
│  ├── Time to first token (TTFT): ~300-800ms (model dependent)  │
│  ├── Inter-token latency: ~30-50ms (GPT-4o)                    │
│  ├── Concurrent streams per GPU node: 50-200                    │
│  └── Total concurrent streams globally: millions                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Server-Sent Events (SSE) format used by OpenAI:**

```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Production streaming client with reconnection (real pattern):**

```python
import httpx
import json
import asyncio
from dataclasses import dataclass

@dataclass
class StreamConfig:
    max_reconnect_attempts: int = 3
    reconnect_delay_base: float = 1.0
    read_timeout: float = 60.0  # Long timeout for slow generation
    buffer_size: int = 10  # Batch N tokens before yielding (reduces overhead)

async def stream_completion_production(
    messages: list,
    config: StreamConfig = StreamConfig()
) -> AsyncIterator[str]:
    """Production-grade streaming with reconnection and error handling."""
    
    tokens_received = 0
    full_response = ""
    attempt = 0
    
    while attempt < config.max_reconnect_attempts:
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    json={
                        "model": "gpt-4o",
                        "messages": messages,
                        "stream": True,
                        "stream_options": {"include_usage": True}  # Get token counts
                    },
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    timeout=httpx.Timeout(
                        connect=5.0,
                        read=config.read_timeout,
                        write=5.0,
                        pool=5.0
                    )
                ) as response:
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("retry-after", "5"))
                        await asyncio.sleep(retry_after)
                        attempt += 1
                        continue
                    
                    response.raise_for_status()
                    
                    buffer = []
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            if buffer:
                                yield "".join(buffer)
                            return
                        
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        
                        if content:
                            buffer.append(content)
                            tokens_received += 1
                            full_response += content
                            
                            # Yield in batches to reduce overhead
                            if len(buffer) >= config.buffer_size:
                                yield "".join(buffer)
                                buffer = []
                    
                    return  # Stream completed normally
                    
        except httpx.ReadTimeout:
            # Model is taking too long - might be overloaded
            attempt += 1
            delay = config.reconnect_delay_base * (2 ** attempt)
            await asyncio.sleep(delay)
            
        except httpx.RemoteProtocolError:
            # Connection dropped mid-stream
            attempt += 1
            # On reconnect, we can't resume - must restart
            # (This is a limitation of SSE over HTTP/1.1)
            # For true resumability, need WebSocket or HTTP/2
            
    raise StreamingError(f"Failed after {config.max_reconnect_attempts} attempts")
```

### Continuous Batching (How inference servers maximize GPU utilization)

```
Traditional batching (wasteful):
Request 1: [████████░░░░░░░░]  (short response, GPU idle after)
Request 2: [████████████████]  (long response)
Request 3: [██████░░░░░░░░░░]  (short response, GPU idle after)
↑ All three must wait for the longest to finish before new batch starts

Continuous batching (used by vLLM, TensorRT-LLM, TGI):
Request 1: [████████]  → done, slot freed
Request 4:          [███████████]  → fills the freed slot immediately
Request 2: [████████████████]
Request 3: [██████]  → done, slot freed
Request 5:        [████████████████]  → fills the freed slot
↑ New requests join as soon as slots free up. GPU never idle.

Result: 2-4x throughput improvement for the same hardware
vLLM reports: up to 24x throughput vs naive HuggingFace serving
```

---

## 9. Model Selection Decision Examples from Real Projects

### Decision Framework Used in Practice

```
┌─────────────────────────────────────────────────────────────────┐
│              Model Selection Decision Matrix                      │
├──────────────┬──────────┬──────────┬──────────┬────────────────┤
│ Factor       │ Weight   │ GPT-4o   │ Claude   │ Llama 3 (self) │
├──────────────┼──────────┼──────────┼──────────┼────────────────┤
│ Quality      │ 30%      │ 9/10     │ 9/10    │ 7/10           │
│ Latency      │ 20%      │ 7/10     │ 7/10    │ 9/10           │
│ Cost         │ 20%      │ 5/10     │ 6/10    │ 9/10           │
│ Data Privacy │ 15%      │ 4/10     │ 4/10    │ 10/10          │
│ Reliability  │ 10%      │ 8/10     │ 8/10    │ 7/10           │
│ Customizable │ 5%       │ 3/10     │ 2/10    │ 10/10          │
├──────────────┼──────────┼──────────┼──────────┼────────────────┤
│ Score        │          │ 6.85     │ 6.85    │ 8.45           │
└──────────────┴──────────┴──────────┴──────────┴────────────────┘
↑ This company chose self-hosted Llama due to data privacy requirements
  (European healthcare company, strict GDPR)
```

### Real Decision Examples

**Decision 1: Legal Contract Review Startup**

```
Requirements:
- Analyze 50-page contracts for risk clauses
- Must handle 128K+ token documents
- Accuracy is paramount (legal liability)
- Budget: $20K/month for AI inference
- Volume: 500 contracts/day

Evaluated:
├── GPT-4o (128K context): Excellent quality, but $15/contract at full context = $7,500/day = too expensive
├── Claude 3.5 Sonnet (200K context): Fits entire contracts, $8/contract = $4,000/day = still expensive  
├── Approach chosen: Chunked processing with GPT-4o-mini + GPT-4o verification
│   ├── Step 1: Split contract into sections (by heading) 
│   ├── Step 2: GPT-4o-mini screens each section for risk indicators ($0.10/contract)
│   ├── Step 3: GPT-4o deep-analyzes only flagged sections ($2/contract average)
│   └── Total cost: ~$2.10/contract = $1,050/day = $31,500/month
│       → Over budget! 
├── Final approach: Claude 3.5 Haiku for screening + Claude 3.5 Sonnet for analysis
│   └── Total: $1.20/contract = $600/day = $18,000/month ✓
```

**Decision 2: Real-time Game NPC Dialogue (Gaming Company)**

```
Requirements:
- Generate NPC dialogue in <200ms (player immersion)
- 10,000 concurrent players generating dialogue
- Creative, varied responses (not repetitive)
- Content safety (no inappropriate content in game rated E)
- Budget: $50K/month

Analysis:
├── API models (GPT-4o, Claude): 500-2000ms latency = TOO SLOW for real-time
├── GPT-4o-mini via API: 300-500ms = still too slow
├── Self-hosted Llama 3 8B on A100: ~80ms per response ✓
│   ├── 8 A100 GPUs handle 10K concurrent with continuous batching
│   ├── Cost: 8 × $3/hr = $24/hr = $17,280/month ✓
│   ├── Fine-tuned on game's lore and dialogue style
│   └── Content safety: Custom RLHF alignment + output filter
├── Chosen: Self-hosted fine-tuned Llama 3 8B
│   ├── Latency: 60-100ms ✓
│   ├── Cost: $17K/month ✓
│   ├── Full control over content and behavior ✓
│   └── No dependency on external API availability ✓

Tradeoff accepted: Lower quality than GPT-4 for NPC dialogue,
but players don't need PhD-level reasoning for "Welcome to my shop, adventurer!"
```

**Decision 3: Enterprise Knowledge Base (Fortune 500)**

```
Requirements:
- Answer employee questions about company policies
- Must cite sources (page, section)
- Cannot hallucinate (compliance requirement)
- 50,000 employees, ~5,000 queries/day
- Data cannot leave company network (regulatory)
- Must support 12 languages

Evaluated:
├── Azure OpenAI (GPT-4o): Data stays in tenant, GDPR compliant ✓
│   ├── But: $12K/month, dependent on Azure availability
├── Self-hosted Llama 3 70B: Full control, but 70B needs 4+ GPUs
│   ├── Quality gap on multilingual: fails for Japanese, Korean
├── Hybrid chosen:
│   ├── Azure OpenAI GPT-4o for query understanding + answer generation
│   │   (data stays within Azure tenant, BAA signed)
│   ├── Self-hosted embedding model (multilingual-e5-large) for retrieval
│   │   (embeddings don't contain reconstructable data)
│   ├── Guardrails: Only answer from retrieved context, refuse if no match
│   └── Cost: Azure OpenAI $8K + GPU for embeddings $3K = $11K/month
```

**Decision 4: Startup MVP - "Ship Fast" Selection**

```
Requirements:
- Build AI feature in 2 weeks
- Prove product-market fit before optimizing
- Small team (2 engineers)
- Budget: "whatever it costs for first 1000 users"

Decision: GPT-4o via API, no self-hosting, no optimization

Rationale:
- Zero infrastructure to maintain
- Best quality = best user experience for PMF testing
- Cost at 1000 users: ~$500/month (negligible vs engineer time)
- Can always optimize later if product works

Anti-pattern avoided: Don't prematurely optimize AI infrastructure
before proving the product works. Many startups waste months building
"scalable" AI infrastructure for a product nobody wants.

Migration plan (if product succeeds):
- Month 1-3: GPT-4o API (prove PMF)
- Month 4-6: Add caching + prompt optimization (reduce cost 50%)
- Month 7-12: Evaluate fine-tuning or smaller models (reduce cost 80%)
- Month 12+: Self-host if scale justifies ($100K+/month API spend)
```
