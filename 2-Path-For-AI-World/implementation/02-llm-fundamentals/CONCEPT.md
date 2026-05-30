# LLM Fundamentals — AI Architect Deep Dive

## 1. Transformer Architecture (Architect Level)

### 1.1 The Attention Mechanism

The transformer's core innovation is **self-attention**: every token attends to every other token in a sequence, learning which relationships matter.

**Scaled Dot-Product Attention:**
```
Attention(Q, K, V) = softmax(QK^T / √d_k) V
```

- **Q (Query):** "What am I looking for?"
- **K (Key):** "What do I contain?"
- **V (Value):** "What information do I provide?"
- **√d_k scaling:** Prevents dot products from growing too large with high dimensionality, which would push softmax into regions with vanishing gradients.

**Multi-Head Attention** runs multiple attention computations in parallel, each with different learned projections. This lets the model attend to different relationship types simultaneously (syntactic, semantic, positional).

**Architectural implication:** Attention is O(n²) in sequence length. This is why context windows have hard limits and why architectures like Mamba (state-space models) and ring attention exist.

### 1.2 Positional Encoding

Transformers have no inherent notion of order. Positional encoding injects sequence position:

- **Sinusoidal (original):** Fixed mathematical patterns. Generalizes poorly to unseen lengths.
- **Learned positional embeddings:** Trained with the model. Limited to training-time max length.
- **RoPE (Rotary Position Embeddings):** Encodes position as rotations in embedding space. Used by LLaMA, Mistral. Allows length extrapolation.
- **ALiBi (Attention with Linear Biases):** Adds a linear bias to attention scores based on distance. Used by MPT, BLOOM.

**Architect decision:** RoPE-based models are generally preferred for applications needing context length flexibility. ALiBi is simpler but less expressive.

### 1.3 Tokenization

Tokenization converts raw text into integer sequences the model processes.

**Key algorithms:**
- **BPE (Byte Pair Encoding):** Iteratively merges the most frequent byte pairs. Used by GPT models (via `tiktoken`).
- **SentencePiece:** Language-agnostic, operates on raw Unicode. Used by LLaMA, Gemini.
- **WordPiece:** Similar to BPE but uses likelihood-based merging. Used by BERT.

**Architect implications:**
- Different models have different tokenizers — you CANNOT assume token counts transfer between models.
- Code, non-English languages, and special characters tokenize less efficiently (more tokens per semantic unit).
- Token count directly determines cost and latency.
- A "word" is typically 1.3 tokens in English, but can be 3-5 tokens in CJK languages.

### 1.4 Feed-Forward Networks & Layer Norms

Each transformer layer has:
1. Multi-head attention → residual connection → layer norm
2. Feed-forward network (2-layer MLP with GeLU activation) → residual connection → layer norm

The FFN is where factual knowledge is primarily stored. The attention layers handle relational/contextual reasoning.

### 1.5 Decoder-Only vs Encoder-Decoder

- **Decoder-only (GPT, Claude, LLaMA):** Causal attention mask. Each token only attends to previous tokens. Dominant for generation.
- **Encoder-decoder (T5, original Transformer):** Encoder sees full input bidirectionally, decoder generates autoregressively. Better for translation-like tasks but more complex to serve.

---

## 2. Tokens and Tokenization

### 2.1 Token Counting in Practice

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")
tokens = enc.encode("Hello, world!")
print(len(tokens))  # 4 tokens
```

### 2.2 Cost Implications

| Model | Input $/1M tokens | Output $/1M tokens | Context Window |
|-------|-------------------|---------------------|----------------|
| GPT-4o | $2.50 | $10.00 | 128K |
| GPT-4o-mini | $0.15 | $0.60 | 128K |
| Claude 3.5 Sonnet | $3.00 | $15.00 | 200K |
| Claude 3.5 Haiku | $0.80 | $4.00 | 200K |
| Gemini 1.5 Pro | $1.25 | $5.00 | 2M |

**Architect rules of thumb:**
- Output tokens cost 3-5x input tokens (because generation is sequential)
- A typical RAG retrieval chunk (500 words) ≈ 650 tokens
- System prompts are paid on EVERY request — keep them tight
- Caching (prompt caching) can reduce input costs by 50-90%

### 2.3 Tokenization Edge Cases

- **Whitespace matters:** " hello" and "hello" are different tokens
- **Numbers:** "123456" may be split into multiple tokens unpredictably
- **Code:** Indentation consumes tokens (tabs vs spaces matters economically at scale)
- **JSON keys:** Repeated keys in structured output waste tokens

---

## 3. Context Windows

### 3.1 Current Landscape

- GPT-4o: 128K tokens
- Claude 3.5: 200K tokens
- Gemini 1.5 Pro: 2M tokens
- LLaMA 3.1: 128K tokens

### 3.2 Effective Context vs Stated Context

Models degrade on long contexts. Research shows:
- **Lost in the middle:** Information in the middle of long contexts is recalled worse than at the beginning or end.
- **Effective attention** drops significantly beyond 32K tokens for most models.
- Gemini and Claude handle long contexts better than GPT empirically.

### 3.3 Strategies for Handling Context Limits

1. **Chunking + RAG:** Split documents, retrieve relevant chunks only.
2. **Summarization chains:** Summarize earlier context, keep recent context verbatim.
3. **Sliding window:** Keep most recent N tokens, summarize the rest.
4. **Hierarchical summarization:** Tree of summaries at different granularities.
5. **Context compression:** Tools like LLMLingua that compress prompts while preserving meaning.

### 3.4 Context Engineering

Context engineering is the art of deciding **what goes into the context window and in what order.**

**Principles:**
- **Recency bias:** Put the most important instructions at the END (closest to generation).
- **Primacy effect:** Opening instructions are also well-attended.
- **Relevance filtering:** Only include information the model needs for THIS specific generation.
- **Deduplication:** Never repeat the same information in different forms.

---

## 4. Temperature, Top-p, Top-k

### 4.1 Temperature

Controls randomness in the probability distribution over next tokens.

- **T=0:** Greedy decoding. Always picks highest probability token. Deterministic output.
- **T=0.1-0.3:** Near-deterministic. Good for factual Q&A, code generation, structured output.
- **T=0.7-0.9:** Balanced creativity. Good for creative writing, brainstorming.
- **T=1.0+:** High randomness. Rarely useful in production.

### 4.2 Top-p (Nucleus Sampling)

Only consider tokens whose cumulative probability reaches p.

- **top_p=0.1:** Very focused. Only top few tokens considered.
- **top_p=0.9:** Most tokens in play. More diverse.
- **top_p=1.0:** All tokens considered (just temperature controls diversity).

### 4.3 Top-k

Only consider the top k most probable tokens.

- Simpler than top_p but less adaptive (doesn't account for varying distribution shapes).
- Mostly used in open-source model inference (vLLM, TGI).

### 4.4 Architect Guidelines

| Use Case | Temperature | Top-p | Notes |
|----------|-------------|-------|-------|
| JSON extraction | 0 | 1.0 | Deterministic, reproducible |
| Code generation | 0-0.2 | 0.95 | Low creativity, high precision |
| Conversational | 0.7 | 0.9 | Natural variety |
| Creative writing | 0.9 | 0.95 | Maximum diversity |
| Classification | 0 | 1.0 | Must be deterministic |

**Never set both temperature=0 AND top_p<1 simultaneously** — it's redundant and can cause unexpected behavior in some APIs.

---

## 5. System Prompts vs User Prompts vs Developer Instructions

### 5.1 System Prompt

Sets the model's persona, constraints, and behavioral boundaries. Persists across turns.

```
You are a financial analyst assistant. You MUST:
- Never provide specific investment advice
- Always cite data sources
- Respond in structured markdown
```

### 5.2 User Prompt

The end-user's actual query. Untrusted input that may contain prompt injection attempts.

### 5.3 Developer Instructions (Anthropic-specific)

Claude supports a separate `developer` message type that sits between system and user, allowing platform developers to set instructions that are distinct from both system behavior and user input.

### 5.4 Security Hierarchy

```
System prompt (highest privilege)
  → Developer instructions
    → User prompt (lowest privilege, untrusted)
```

**Architect principle:** Never trust user input. Always validate outputs regardless of prompt instructions. System prompts are NOT security boundaries — they are behavioral guidelines that can be circumvented.

---

## 6. Few-Shot Prompting

### 6.1 Design Patterns

**Basic few-shot:**
```
Classify the sentiment:
"I love this!" → positive
"Terrible experience" → negative
"It was okay" → neutral
"The product exceeded expectations" → ?
```

**Structured few-shot:**
```
Input: { "text": "revenue grew 15%", "domain": "finance" }
Output: { "sentiment": "positive", "confidence": 0.92, "entities": ["revenue"] }

Input: { "text": "layoffs announced", "domain": "finance" }
Output: { "sentiment": "negative", "confidence": 0.88, "entities": ["layoffs"] }
```

### 6.2 Best Practices

- **3-5 examples** is the sweet spot (diminishing returns beyond 5)
- **Cover edge cases** in your examples (not just happy paths)
- **Match the distribution** — if 70% of real inputs are X, examples should reflect that
- **Order matters** — put the most similar example last (closest to the query)
- **Negative examples** are as important as positive ones

### 6.3 When to Use Few-Shot vs Fine-Tuning

| Criteria | Few-shot | Fine-tuning |
|----------|----------|-------------|
| Data available | < 100 examples | 100+ examples |
| Latency budget | Flexible | Tight (no prompt overhead) |
| Task complexity | Moderate | High/specialized |
| Update frequency | High (change prompts anytime) | Low (retraining needed) |
| Cost | Higher per-call (more tokens) | Lower per-call, higher upfront |

---

## 7. Structured Outputs

### 7.1 Approaches

1. **Prompt-based:** Ask the model to output JSON. Unreliable without validation.
2. **JSON mode:** API-level guarantee of valid JSON (OpenAI, Anthropic). No schema enforcement.
3. **Structured outputs (schema-enforced):** Constrained decoding ensures output matches a JSON schema exactly.
4. **Tool/function calling:** Schema-enforced via the tool calling mechanism.

### 7.2 Constrained Decoding

The model's logits are masked at each generation step to only allow tokens that would produce valid output per the schema. This guarantees structural validity but NOT semantic correctness.

### 7.3 Architect Decisions

- **Always use schema-enforced structured outputs** when available. Prompt-based JSON is fragile.
- **Pydantic models** are the standard way to define schemas in Python.
- **Handle edge cases:** `null` values, empty arrays, optional fields.
- **Schema complexity matters:** Deeply nested schemas with many optional fields may confuse the model.

---

## 8. Function/Tool Calling

### 8.1 How It Works Internally

1. Tools are described in the system context as JSON schemas.
2. The model generates a special "tool call" token sequence instead of text.
3. The API parses this into a structured tool call object.
4. Your code executes the tool and returns the result.
5. The result is fed back as a "tool" message for the model to synthesize.

### 8.2 Schema Design Principles

- **Descriptive names:** `search_documents` not `search`
- **Detailed descriptions:** The model uses these to decide WHEN to call the tool
- **Typed parameters:** Use enums for constrained values
- **Required vs optional:** Only require what's necessary
- **Keep schemas small:** Models perform worse with 20+ tools

### 8.3 Parallel Tool Calling

Models can emit multiple tool calls in a single turn. Your orchestrator must:
- Execute them concurrently (if independent)
- Handle partial failures gracefully
- Return all results in the correct order

### 8.4 Tool Call Patterns

- **Single tool:** Simple lookup/action
- **Sequential tools:** Output of tool A feeds into tool B
- **Parallel tools:** Independent operations
- **Recursive/agentic:** Model decides next tool based on previous results

---

## 9. Streaming Responses

### 9.1 Server-Sent Events (SSE)

The standard protocol for streaming LLM responses:

```
data: {"choices":[{"delta":{"content":"Hello"}}]}
data: {"choices":[{"delta":{"content":" world"}}]}
data: [DONE]
```

### 9.2 When to Stream

| Stream | Don't Stream |
|--------|-------------|
| Chat interfaces (TTFB matters) | Structured output (need complete JSON) |
| Long-form generation | Tool calling (need complete call) |
| Real-time UX | Batch processing |
| Any user-facing response | Internal pipeline steps |

### 9.3 Streaming with Tool Calls

Tool calls are accumulated across chunks. You only execute when the tool call is complete (signaled by a finish reason or a complete JSON object).

### 9.4 Backpressure

If the consumer is slower than the producer, implement backpressure:
- Buffer chunks with a max buffer size
- Drop connection if buffer overflows
- Use async generators in Python

---

## 10. Reasoning Models vs Completion Models

### 10.1 Completion Models (GPT-4o, Claude 3.5 Sonnet)

- Trained to predict next token
- Fast inference
- Good at: following instructions, retrieval, structured output
- Token-efficient

### 10.2 Reasoning Models (o1, o3, Claude with extended thinking)

- Trained with reinforcement learning on chain-of-thought
- Use "thinking tokens" before answering (not billed the same way by all providers)
- Good at: math, logic, complex multi-step problems, code debugging
- Slower, more expensive per query
- **Cannot be steered with system prompts as effectively**

### 10.3 Architect Decision Framework

Use reasoning models when:
- Problem requires multi-step logical deduction
- Accuracy matters more than latency
- Task involves planning or strategy
- Mathematical or formal reasoning is needed

Use completion models when:
- Latency is critical (< 2s)
- Task is well-defined and pattern-matchable
- Structured output is needed
- Cost per query matters

---

## 11. Small vs Large Models

### 11.1 Model Tiers

| Tier | Examples | Use Cases |
|------|----------|-----------|
| Frontier | GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro | Complex reasoning, nuanced generation |
| Mid-tier | GPT-4o-mini, Claude 3.5 Haiku, Gemini Flash | Most production tasks |
| Small | Phi-3, Mistral 7B, LLaMA 3.1 8B | Classification, extraction, simple tasks |
| Tiny | DistilBERT, TinyLLaMA | Embeddings, binary classification |

### 11.2 Routing Decisions

**Complexity-based routing:**
1. Classify incoming query complexity (use a small model or heuristic)
2. Route simple queries to cheap/fast models
3. Route complex queries to frontier models
4. Implement fallback: if small model confidence < threshold, escalate

**Cost optimization math:**
- If 80% of queries can be handled by a model that's 20x cheaper, you save 76% of LLM costs.

---

## 12. Multimodal Models

### 12.1 Vision Capabilities

- **Image understanding:** GPT-4o, Claude 3.5, Gemini can process images
- **Use cases:** Document extraction, chart reading, UI understanding, visual QA
- **Limitations:** Spatial reasoning is weak, counting is unreliable, text in images may be misread
- **Cost:** Images are converted to tokens (a 1024x1024 image ≈ 765 tokens in GPT-4o)

### 12.2 Audio Capabilities

- **Speech-to-text:** Whisper (OpenAI), Gemini native audio
- **Text-to-speech:** OpenAI TTS, ElevenLabs
- **Native audio understanding:** Gemini 1.5 can process audio directly without transcription

### 12.3 Architect Considerations

- Multimodal input increases latency significantly
- Image resolution settings affect both quality and cost
- For high-volume image processing, consider dedicated vision models (Florence-2, etc.)

---

## 13. Hallucination

### 13.1 Causes

1. **Training data gaps:** Model confabulates when it lacks knowledge
2. **Pattern completion bias:** Model continues patterns even when factually wrong
3. **Instruction-following conflicts:** Trying to be helpful overrides uncertainty
4. **Long context degradation:** Information retrieval degrades with context length
5. **Ambiguous prompts:** Under-specified queries get confident but wrong answers

### 13.2 Detection Strategies

- **Self-consistency:** Ask the same question N times; inconsistent answers signal hallucination
- **Citation verification:** Ask model to cite sources, verify they exist
- **Factual grounding:** Compare against known facts (RAG-based verification)
- **Confidence calibration:** Ask model for confidence; low confidence correlates with hallucination
- **Entailment checking:** Use NLI models to verify claims against source docs

### 13.3 Mitigation

1. **RAG (Retrieval Augmented Generation):** Ground responses in retrieved documents
2. **Constrained generation:** Limit outputs to known valid values
3. **Temperature=0:** Reduces but does not eliminate hallucination
4. **Explicit uncertainty:** Instruct model to say "I don't know"
5. **Post-generation validation:** Verify factual claims programmatically
6. **Smaller scope:** More specific questions hallucinate less

---

## 14. Context Engineering

### 14.1 What Goes In the Context

```
┌─────────────────────────────────────────┐
│ System Prompt (behavioral instructions)  │ ~500-2000 tokens
├─────────────────────────────────────────┤
│ Tool Definitions                         │ ~200-500 tokens per tool
├─────────────────────────────────────────┤
│ Retrieved Context (RAG chunks)           │ ~1000-4000 tokens
├─────────────────────────────────────────┤
│ Conversation History                     │ Variable
├─────────────────────────────────────────┤
│ Current User Message                     │ Variable
└─────────────────────────────────────────┘
```

### 14.2 Ordering Strategy

1. System prompt FIRST (sets behavioral frame)
2. Tool definitions (available capabilities)
3. Relevant context (RAG results, most relevant first)
4. Conversation history (oldest to newest)
5. User message LAST (freshest attention)

### 14.3 Compression Techniques

- **Summarize old turns:** Replace verbatim history with summaries
- **Drop tool results:** After synthesis, remove raw tool outputs
- **Deduplicate:** If RAG returns overlapping chunks, merge them
- **Truncate selectively:** Keep recent turns verbatim, compress older ones

---

## 15. Model Comparison Methodology

### 15.1 Evaluation Dimensions

1. **Quality:** Task accuracy, coherence, instruction following
2. **Latency:** Time to first token (TTFT), tokens per second (TPS), total time
3. **Cost:** Input/output token pricing, caching discounts
4. **Reliability:** Uptime, rate limits, error rates
5. **Safety:** Refusal rates, harmful output frequency
6. **Context handling:** Performance degradation with context length

### 15.2 Benchmarking Best Practices

- Use YOUR actual workload, not public benchmarks
- Minimum 100 test cases per evaluation dimension
- Blind evaluation (human judges don't know which model produced output)
- Statistical significance testing (paired t-test or bootstrap)
- Track over time (models get updated, perf can regress)

---

## 16. Provider Differences

### 16.1 OpenAI

- **Strengths:** Best tool calling, structured outputs, ecosystem maturity
- **Weaknesses:** Less transparent, occasional quality regressions
- **Unique:** Batch API (50% discount, 24h SLA), assistants API, real-time API

### 16.2 Anthropic (Claude)

- **Strengths:** Longest context (200K), best instruction following, most steerable, extended thinking
- **Weaknesses:** Slower, more expensive, smaller ecosystem
- **Unique:** Developer messages, prompt caching, constitutional AI safety

### 16.3 Google (Gemini)

- **Strengths:** 2M context window, native multimodal, cheapest at scale
- **Weaknesses:** Less consistent quality, API stability concerns
- **Unique:** Grounding with Google Search, native audio/video processing

### 16.4 Open Source (LLaMA, Mistral, Qwen)

- **Strengths:** Full control, no data sharing, custom fine-tuning, self-hosting
- **Weaknesses:** Operational burden, lower quality than frontier closed models
- **Unique:** Quantization options, custom inference optimization, no rate limits

### 16.5 Architect Decision Matrix

| Factor | Choose Closed Model | Choose Open Source |
|--------|--------------------|--------------------|
| Data sensitivity | Low-medium | High (regulated industries) |
| Scale | < 1M requests/day | > 1M requests/day (cost crossover) |
| Customization | Standard tasks | Domain-specific fine-tuning needed |
| Latency | Acceptable (50-500ms) | Ultra-low (< 50ms needed) |
| Team expertise | Limited ML ops | Strong ML engineering team |
