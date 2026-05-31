# Zero-Shot and Few-Shot Prompting

## The "Show, Don't Just Tell" Principle

Think of it like teaching a new employee:
- **Zero-shot:** "Classify these support tickets by urgency." (Just the instruction)
- **One-shot:** "Here's an example of a high-urgency ticket: [example]. Now classify these."
- **Few-shot:** "Here are 5 classified tickets showing each urgency level. Now classify these."

The more examples you show, the more the model understands *what you actually mean* — not just what you literally said.

## Zero-Shot Prompting

Give instructions only. No examples. Rely on the model's pre-training.

```
Classify the following customer review as positive, negative, or neutral:

Review: "The product arrived on time but the packaging was damaged. The item itself works fine."

Classification:
```

**When it works well:**
- Simple, well-defined tasks
- Newer, more capable models (GPT-4, Claude 3.5)
- Standard formats the model has seen millions of times
- When you need diverse/creative outputs

**When it fails:**
- Ambiguous definitions (what does "urgent" mean to YOU?)
- Custom formats the model hasn't seen
- Edge cases where your definition differs from common usage

## One-Shot Prompting

One example sets the pattern. Surprisingly powerful.

```
Extract the action items from meeting notes.

Example:
Input: "We need to update the landing page by Friday. Sarah will handle the copy."
Output: [{"task": "Update landing page", "assignee": "Sarah", "deadline": "Friday"}]

Now extract from:
Input: "John mentioned we should revisit the pricing model. No timeline set yet."
Output:
```

## Few-Shot Prompting

Multiple examples create a robust pattern. The model infers the "rule" from examples.

```
Classify the intent of customer messages:

Message: "I can't log into my account" → Intent: account_access
Message: "How much does the pro plan cost?" → Intent: pricing_inquiry  
Message: "Cancel my subscription immediately" → Intent: cancellation
Message: "Your product is amazing, love it!" → Intent: feedback_positive
Message: "The API returns 500 errors" → Intent: technical_issue

Message: "I want to upgrade to enterprise" → Intent:
```

## How Many Examples is Optimal?

```mermaid
graph LR
    A[0 examples] -->|"Baseline"| B[Zero-shot accuracy]
    C[1-3 examples] -->|"Biggest jump"| D[Significant improvement]
    E[4-8 examples] -->|"Diminishing returns"| F[Marginal improvement]
    G[8+ examples] -->|"Plateau/waste"| H[No further gain, wasted tokens]
```

| Shot Count | Best For | Trade-off |
|-----------|----------|-----------|
| 0 (zero) | Simple tasks, creative work | No token cost, but less control |
| 1-2 | Format demonstration | Minimal cost, shows structure |
| 3-5 | Classification, extraction | Sweet spot for most tasks |
| 5-8 | Complex/ambiguous tasks | Higher cost, diminishing returns |
| 8+ | Rarely justified | Better to fine-tune at this point |

**Research finding:** 3-5 examples typically capture 90%+ of the benefit. Beyond that, you're burning tokens for marginal gains.

## Example Selection Strategies

### 1. Diverse Examples (Cover the Space)
Don't show 5 examples that are all the same category. Cover the range:

```
# BAD: All positive examples
"Great product!" → positive
"Love it!" → positive
"Amazing quality" → positive

# GOOD: Cover all categories + edge cases
"Great product!" → positive
"Terrible experience" → negative
"It's okay, nothing special" → neutral
"The worst thing I've ever bought, but customer service was helpful" → mixed
"" → invalid_input
```

### 2. Edge-Case Examples (Show the Hard Ones)
Models handle obvious cases well. Show them the tricky ones:

```
# These are the cases that trip up the model:
"I'm not unhappy with it" → positive (double negative)
"Could be worse" → neutral (backhanded)
"10/10 would NOT recommend" → negative (sarcasm)
```

### 3. Representative Examples (Match the Distribution)
If 80% of your real inputs are technical questions, most examples should be technical questions.

## The Order of Examples Matters

Models exhibit **recency bias** — the last examples have more influence.

```mermaid
graph TD
    A[Example Order Strategy] --> B[Put hardest examples last]
    A --> C[Put most common category last]
    A --> D[End with the category closest to your expected input]
    A --> E[Shuffle order to test for bias]
```

**Experiment:** If classifying mostly negative reviews, put a negative example last. If the task is ambiguous, put the edge case last to prime the model.

## When Zero-Shot Outperforms Few-Shot

With modern models (GPT-4o, Claude 3.5 Sonnet), zero-shot sometimes wins because:

1. **Examples can constrain creativity** — if you need diverse outputs, examples create a "template lock"
2. **Misleading examples confuse** — bad examples are worse than no examples
3. **Token budget** — examples consume context that could hold more relevant information
4. **Well-known tasks** — for standard tasks (translation, summarization), the model already knows the format

**Rule of thumb:** Start with zero-shot. Add examples only when output quality is insufficient or inconsistent.

## Practical Examples

### Classification (Sentiment)

```python
# Zero-shot
prompt = "Classify as positive/negative/neutral: '{text}'"

# Few-shot (3 examples)
prompt = """Classify sentiment:
"Best purchase ever!" → positive
"Broke after one day" → negative  
"It does what it says" → neutral

"{text}" →"""
```

### Extraction (Entities)

```python
# Few-shot extraction
prompt = """Extract entities from text as JSON.

Text: "Apple CEO Tim Cook announced the iPhone 15 in Cupertino on September 12."
Entities: {"people": ["Tim Cook"], "orgs": ["Apple"], "products": ["iPhone 15"], "locations": ["Cupertino"], "dates": ["September 12"]}

Text: "Microsoft acquired Activision for $69 billion in October 2023."
Entities: {"people": [], "orgs": ["Microsoft", "Activision"], "products": [], "locations": [], "dates": ["October 2023"]}

Text: "{user_text}"
Entities:"""
```

### Transformation (Reformatting)

```python
# Few-shot style transfer
prompt = """Rewrite formal text as casual Slack messages:

Formal: "Please be advised that the deployment scheduled for this evening has been postponed to tomorrow morning."
Casual: "Heads up — tonight's deploy is pushed to tomorrow AM 👍"

Formal: "We regret to inform you that the requested feature will not be included in the upcoming release cycle."
Casual: "Bad news — that feature didn't make the cut for this release. Next sprint maybe?"

Formal: "{formal_text}"
Casual:"""
```

## Why This Matters for an Architect

1. **Cost vs. quality trade-off.** Few-shot uses more tokens (= more money). Architect must decide: is the quality improvement worth the cost at scale?
2. **Example management is infrastructure.** In production, examples should be stored, versioned, and selected dynamically — not hardcoded.
3. **Testing strategy.** You need evaluation datasets to measure whether adding examples actually improves YOUR specific use case.
4. **Scalability.** At 1M requests/day, 5 extra examples per request = billions of extra tokens. Design accordingly.
5. **Dynamic few-shot.** Advanced systems retrieve the most relevant examples from a database based on the input (semantic similarity). This is a production architecture decision.

## Key Takeaways

- Start zero-shot, add examples only when needed
- 3-5 diverse examples is the sweet spot
- Include edge cases in your examples
- Order matters — put the most relevant example last
- Modern models need fewer examples than older ones
- In production, examples should be dynamically selected, not hardcoded

---

## Staff Architect: Anti-Patterns

| Anti-Pattern | Why It's Harmful | Fix |
|-------------|-----------------|-----|
| **Too many examples consuming context** | 10+ examples at 200 tokens each = 2K tokens wasted per request; at scale this costs thousands in unnecessary spend and may push out actually relevant context | Cap at 3-5 examples; measure marginal accuracy gain per example added |
| **Examples that don't match production distribution** | If real inputs are messy/informal but examples are clean/formal, the model learns the wrong pattern | Sample examples from actual production inputs, not hand-crafted ideal cases |
| **Cherry-picked examples** | Selecting only "easy" examples that the model would already handle correctly teaches nothing | Include examples that represent the *hard* cases — ambiguous inputs, edge cases, format violations |
| **Same examples for every query** | Static examples may be irrelevant to the current input, wasting context and potentially confusing the model | Implement dynamic few-shot: retrieve semantically similar examples per query |
| **Examples with inconsistent format** | If examples show slightly different output structures, the model interpolates unpredictably | Enforce strict format consistency across all examples; validate with a linter |
| **Not measuring example ROI** | Adding examples "because more is better" without measuring whether accuracy actually improves | A/B test zero-shot vs N-shot on your eval set; only keep examples that measurably improve metrics |

## Staff Architect: Decision Framework — Zero-Shot vs Few-Shot

```mermaid
graph TD
    A[New Task] --> B{Model is GPT-4/Claude 3.5+?}
    B -->|Yes| C{Task is standard?<br/>classification, summary, translation}
    B -->|No| F[Use few-shot 3-5 examples]
    C -->|Yes| D{Output format matters?}
    C -->|No| F
    D -->|No| E[Zero-shot is sufficient]
    D -->|Yes| G[1-2 examples for format only]
    F --> H{Accuracy still insufficient?}
    H -->|Yes| I{Budget allows?}
    I -->|Yes| J[Dynamic few-shot with retrieval]
    I -->|No| K[Consider fine-tuning instead]
    H -->|No| L[Ship it]
```

| Factor | Favors Zero-Shot | Favors Few-Shot |
|--------|-----------------|-----------------|
| Model capability | Strong (GPT-4o, Claude 3.5) | Weak (GPT-3.5, small models) |
| Task type | Standard/well-known | Custom/domain-specific |
| Input diversity | Highly varied inputs | Consistent input patterns |
| Cost sensitivity | High volume, cost matters | Low volume, accuracy matters |
| Output format | Flexible | Must be exact |
| Latency requirements | Strict latency SLA | Accuracy > speed |

## Staff Architect: Dynamic Few-Shot Architecture

Static few-shot hardcodes examples. **Dynamic few-shot** retrieves the most relevant examples per query at runtime.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class DynamicFewShotSelector:
    """Retrieve semantically similar examples for each query."""
    
    def __init__(self, example_bank: list[dict], model_name="all-MiniLM-L6-v2"):
        self.encoder = SentenceTransformer(model_name)
        self.examples = example_bank
        self.embeddings = self.encoder.encode([ex["input"] for ex in example_bank])
    
    def select(self, query: str, k: int = 3) -> list[dict]:
        query_embedding = self.encoder.encode([query])
        similarities = np.dot(self.embeddings, query_embedding.T).flatten()
        top_indices = similarities.argsort()[-k:][::-1]
        return [self.examples[i] for i in top_indices]

# Usage
selector = DynamicFewShotSelector(example_bank=load_examples_from_db())
relevant_examples = selector.select(user_query, k=3)
prompt = build_prompt_with_examples(relevant_examples, user_query)
```

### When to Use Dynamic Few-Shot

| Scenario | Static Few-Shot | Dynamic Few-Shot |
|----------|----------------|------------------|
| < 10 distinct input patterns | Sufficient | Overkill |
| 100+ distinct input patterns | Examples won't cover space | Essential for coverage |
| Domain with evolving categories | Requires prompt updates | Add new examples to bank without changing prompt logic |
| Multi-tenant with different needs | One-size-fits-all | Per-tenant example banks |
| Latency-sensitive | No retrieval overhead | Adds 10-50ms for embedding + search |

### Production Considerations
- **Example bank size:** 100-1000 examples is typical; beyond that, clustering/deduplication needed
- **Embedding model:** Use a small, fast model (MiniLM) — not your main LLM
- **Cache:** Cache embeddings; recompute only when example bank changes
- **Diversity:** After retrieving top-K by similarity, optionally re-rank for diversity (avoid K examples from same cluster)
- **Monitoring:** Track which examples get selected most/least to identify gaps in coverage

---

## Staff Decision: When to Move from Few-Shot to Fine-Tuning

Few-shot prompting has limits. Here's when to graduate to fine-tuning:

| Signal | Few-Shot Still Works | Time to Fine-Tune |
|--------|:-------------------:|:-----------------:|
| Examples needed | 3-5 sufficient | 8+ and still inconsistent |
| Token cost of examples | < 20% of total prompt | > 40% of total prompt |
| Output format consistency | > 90% parse rate | < 85% even with examples |
| Task complexity | Standard patterns | Highly specialized domain |
| Volume | < 100K requests/day | > 500K requests/day (cost of examples dominates) |
| Quality bar | "Good enough" | Must be near-perfect |

**The crossover calculation:**
```
Few-shot cost  = (base_prompt + N_examples × tokens_per_example) × price × volume
Fine-tune cost = training_cost + (base_prompt_only × price × volume)

If few-shot_cost - fine-tune_cost > fine-tune training cost within 30 days → fine-tune
```

**Rule of thumb:** If you're spending >$5K/month on example tokens alone, fine-tuning likely pays for itself within one month.
