# Chain-of-Thought Reasoning

## The "Show Your Work" Analogy

Remember math class? Your teacher didn't just want the answer — they wanted to see your work. Why?
- It catches errors mid-reasoning
- It ensures you actually understand the problem
- It produces more reliable answers

Chain-of-Thought (CoT) prompting applies the same principle to LLMs: **force the model to reason step-by-step before giving a final answer.**

## Standard Prompting vs CoT

```mermaid
graph TD
    subgraph Standard["Standard Prompting"]
        A1[Question] --> A2[Answer]
    end
    
    subgraph CoT["Chain-of-Thought"]
        B1[Question] --> B2[Step 1: Understand]
        B2 --> B3[Step 2: Break down]
        B3 --> B4[Step 3: Solve parts]
        B4 --> B5[Step 4: Combine]
        B5 --> B6[Final Answer]
    end
```

**Standard:**
```
Q: If a store has 3 shelves with 8 books each, and 2 shelves with 5 books each, how many books total?
A: 34
```

**Chain-of-Thought:**
```
Q: If a store has 3 shelves with 8 books each, and 2 shelves with 5 books each, how many books total?
A: Let me work through this step by step.
- 3 shelves × 8 books = 24 books
- 2 shelves × 5 books = 10 books
- Total: 24 + 10 = 34 books
The answer is 34.
```

Same answer here, but CoT dramatically improves accuracy on harder problems where the model would otherwise "guess."

## Zero-Shot CoT

The simplest trick in prompt engineering. Just append: **"Let's think step by step."**

```
Q: A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. 
   How much does the ball cost?

Let's think step by step.
```

Without CoT, models often answer "$0.10" (wrong — the intuitive but incorrect answer).
With CoT, models reason through the algebra and get "$0.05" (correct).

**Other zero-shot CoT triggers:**
- "Let's think step by step."
- "Let's work through this carefully."
- "Before answering, reason about each part."
- "Think about this step by step before giving your final answer."

## Few-Shot CoT

Provide examples that include the reasoning process:

```
Q: Roger has 5 tennis balls. He buys 2 cans of 3 tennis balls each. How many does he have now?
A: Roger starts with 5 balls. 2 cans × 3 balls = 6 new balls. 5 + 6 = 11.
The answer is 11.

Q: The cafeteria had 23 apples. They used 20 for lunch and bought 6 more. How many do they have?
A: Started with 23. Used 20, so 23 - 20 = 3 remaining. Bought 6 more: 3 + 6 = 9.
The answer is 9.

Q: {user_question}
A:
```

The model learns the *pattern of reasoning*, not just the format.

## When CoT Helps vs Doesn't

| Task Type | CoT Benefit | Why |
|-----------|-------------|-----|
| Math/arithmetic | **High** | Prevents skipping steps |
| Logic puzzles | **High** | Forces systematic exploration |
| Multi-step reasoning | **High** | Maintains coherence across steps |
| Code debugging | **High** | Traces execution flow |
| Simple classification | **Low/None** | Overthinking simple tasks adds noise |
| Creative writing | **Low** | Reasoning can kill creativity |
| Factual recall | **None** | Either knows it or doesn't |
| Translation | **Low** | Mostly pattern matching |

**Rule:** CoT helps when the problem has multiple steps, hidden complexity, or when the intuitive answer is often wrong.

## Tree-of-Thought (ToT)

Instead of one reasoning chain, explore multiple paths:

```mermaid
graph TD
    Q[Problem] --> P1[Path 1: Approach A]
    Q --> P2[Path 2: Approach B]
    Q --> P3[Path 3: Approach C]
    
    P1 --> E1[Evaluate: Dead end]
    P2 --> E2[Evaluate: Promising]
    P3 --> E3[Evaluate: Promising]
    
    E2 --> P2a[Continue Path 2]
    E3 --> P3a[Continue Path 3]
    
    P2a --> F[Final: Best answer from Path 2]
```

```python
TREE_OF_THOUGHT_PROMPT = """
Consider this problem: {problem}

Generate 3 different approaches to solve it:

Approach 1: {generate}
Approach 2: {generate}  
Approach 3: {generate}

Evaluate each approach:
- Which is most likely correct?
- Which has the fewest assumptions?
- Which can be verified?

Select the best approach and solve completely.
"""
```

## Self-Consistency

Generate the same problem N times with temperature > 0, then pick the most common answer:

```mermaid
graph LR
    Q[Question] --> R1[Run 1: Answer A]
    Q --> R2[Run 2: Answer A]
    Q --> R3[Run 3: Answer B]
    Q --> R4[Run 4: Answer A]
    Q --> R5[Run 5: Answer A]
    
    R1 --> V[Vote: A wins 4-1]
    R2 --> V
    R3 --> V
    R4 --> V
    R5 --> V
```

**Implementation:**
```python
import collections

answers = []
for _ in range(5):
    response = call_llm(prompt, temperature=0.7)
    answer = extract_final_answer(response)
    answers.append(answer)

# Majority vote
most_common = collections.Counter(answers).most_common(1)[0][0]
```

**Trade-off:** 5x the API calls = 5x the cost. Use for high-stakes decisions only.

## Program-of-Thought (PoT)

Instead of reasoning in natural language, have the model write code to solve the problem:

```
Q: A store sells widgets at $4.50 each with a 15% bulk discount for orders over 100 units.
   Tax is 8.25%. What's the total for 150 widgets?

Instead of reasoning in text, write Python code to calculate:
```

```python
units = 150
price_per_unit = 4.50
subtotal = units * price_per_unit  # 675.00
discount = subtotal * 0.15  # 101.25 (bulk discount)
after_discount = subtotal - discount  # 573.75
tax = after_discount * 0.0825  # 47.33
total = after_discount + tax  # 621.08
```

**Why PoT is powerful:** Natural language reasoning can accumulate errors. Code is precise and executable — you can actually run it to verify.

## Combining Techniques

```mermaid
graph TD
    A[Complex Problem] --> B{Simple enough?}
    B -->|Yes| C[Zero-shot]
    B -->|No| D{Have examples?}
    D -->|Yes| E[Few-shot CoT]
    D -->|No| F[Zero-shot CoT]
    E --> G{High stakes?}
    F --> G
    G -->|Yes| H[Self-consistency × 5]
    G -->|No| I[Single pass]
    H --> J{Involves calculation?}
    I --> J
    J -->|Yes| K[Program-of-Thought verification]
    J -->|No| L[Return answer]
```

## Why This Matters for an Architect

1. **Accuracy vs. latency trade-off.** CoT produces longer outputs (more tokens, more time). Architect must decide where accuracy justifies the cost.
2. **Self-consistency multiplies costs.** 5 runs × a complex prompt = significant budget at scale. Reserve for critical paths.
3. **Observability.** CoT reasoning chains are invaluable for debugging — you can see *why* the model made a mistake. Design systems to log reasoning.
4. **Hybrid approaches.** Use PoT for calculations, CoT for logic, zero-shot for simple tasks. Route dynamically based on query complexity.
5. **User experience.** Streaming CoT reasoning gives users confidence the system is "thinking" — a UX consideration.

## Key Takeaways

- "Let's think step by step" is a free accuracy boost for complex tasks
- CoT helps with math, logic, and multi-step reasoning
- Self-consistency trades cost for reliability
- Program-of-Thought is superior for calculations
- Don't use CoT for simple tasks — it adds latency without benefit
- Log reasoning chains for debugging and observability

---

## Staff Architect: Anti-Patterns

| Anti-Pattern | Why It's Harmful | Fix |
|-------------|-----------------|-----|
| **Forcing CoT on simple tasks** | Adds 2-5x output tokens (latency + cost) for tasks where the model already achieves >95% accuracy without reasoning | Profile task complexity; only enable CoT when zero-shot accuracy is below threshold |
| **Not extracting the final answer** | Reasoning output mixed with the answer makes downstream parsing unreliable; systems that expect a clean answer break | Always use a delimiter: "Therefore, the final answer is: X" or structured output after reasoning |
| **CoT on models too small to benefit** | Models <7B parameters often produce incoherent reasoning that degrades rather than improves accuracy | Test CoT benefit empirically per model; smaller models may do better with direct few-shot |
| **Unbounded reasoning length** | Without length guidance, models can produce pages of circular reasoning, burning tokens | Add "Reason in 3-5 concise steps" or set max_tokens for the reasoning portion |
| **Using CoT as a crutch for bad prompts** | If the base instruction is ambiguous, CoT amplifies confusion — the model reasons its way to wrong answers confidently | Fix the instruction clarity first, then add CoT only if multi-step reasoning is genuinely needed |
| **No observability on reasoning quality** | Logging only the final answer means you can't diagnose *why* the model failed | Log full reasoning chains; build dashboards that flag reasoning patterns preceding failures |

## Staff Architect: Trade-offs

| Dimension | Without CoT | With CoT | Decision Point |
|-----------|------------|----------|---------------|
| **Latency** | 100-300ms (short output) | 500ms-3s (long reasoning) | Real-time UX (<500ms) → skip CoT |
| **Cost** | 1x output tokens | 3-10x output tokens | High-volume tasks (>100K/day) → cost-prohibitive for CoT |
| **Accuracy (complex)** | 40-70% on multi-step problems | 80-95% on same problems | If accuracy gain justifies the cost, use CoT |
| **Accuracy (simple)** | 95%+ on classification | 94-96% (no gain, sometimes noise) | Simple binary/multi-class → skip CoT |
| **Debuggability** | Black box — wrong answer, no explanation | Full audit trail of reasoning | Regulated industries / high-stakes → always use CoT for auditability |
| **Streaming UX** | Fast first token | Shows "thinking" process to users | User-facing apps can stream reasoning for perceived responsiveness |

### When CoT Actively Hurts

1. **Very simple classification** — "Is this email spam?" Adding reasoning introduces false uncertainty
2. **Pattern matching tasks** — Translation, formatting, simple extraction — model just needs to apply a learned pattern
3. **High-temperature creative tasks** — Reasoning constrains creative output into a logical box
4. **Time-critical systems** — Fraud detection, real-time bidding where latency = money

## Staff Architect: o1/o3 and Built-In Reasoning Models

### The Paradigm Shift

OpenAI's o1 and o3 models have **chain-of-thought built into the model architecture**. The model reasons internally before responding — you don't need to prompt for it.

```python
# OLD approach (GPT-4): You add CoT to the prompt
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": f"Think step by step.\n\n{problem}"}]
)

# NEW approach (o1/o3): Reasoning is automatic — DON'T add CoT prompts
response = client.chat.completions.create(
    model="o3",
    messages=[{"role": "user", "content": problem}]  # No "think step by step" needed
)
```

### Implications for Prompt Design with Reasoning Models

| Aspect | Traditional Models (GPT-4, Claude) | Reasoning Models (o1, o3) |
|--------|-----------------------------------|---------------------------|
| CoT trigger | Must be prompted explicitly | Built-in; prompting it is redundant/wasteful |
| System prompt | Supports full system prompts | Limited/no system prompt support (o1) |
| Temperature | Adjustable | Fixed at 1 (o1) |
| Streaming | Full streaming support | May not stream reasoning tokens |
| Cost model | Pay for visible reasoning tokens | Pay for hidden "thinking" tokens (often more expensive) |
| Best for | Tasks where you control reasoning depth | Hard problems where exhaustive internal reasoning wins |

### Architectural Decision: When to Use Which

```mermaid
graph TD
    A[Task] --> B{Requires deep reasoning?<br/>Math, code, complex logic}
    B -->|Yes| C{Budget allows o1/o3 pricing?}
    C -->|Yes| D[Use o1/o3 — let model reason internally]
    C -->|No| E[Use GPT-4/Claude + explicit CoT prompt]
    B -->|No| F{Needs any reasoning?}
    F -->|Yes| G[Use standard model + lightweight CoT]
    F -->|No| H[Use standard model, zero-shot, no CoT]
```

### Key Lesson
The trend is toward models handling reasoning internally. **Your job as an architect shifts from "how to make models reason" to "when to pay for reasoning and when to skip it."** CoT becomes a cost/quality knob, not a universal best practice.
