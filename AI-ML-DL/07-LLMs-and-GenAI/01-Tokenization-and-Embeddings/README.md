# Tokenization and Embeddings

## Why Tokenization Matters

Neural networks operate on numbers, not text. Tokenization is the bridge between human language and mathematical computation. Every LLM interaction starts here — the quality of tokenization directly impacts model performance, cost, and behavior.

```
"Hello, world!" → [15496, 11, 995, 0] → Neural Network → [next token probabilities]
```

**Key insight**: The tokenizer defines the model's "alphabet." A model can only understand and generate sequences of tokens from its vocabulary. If a word isn't in the vocabulary, it gets split into sub-pieces.

## The Tokenization Spectrum

```
┌─────────────────────────────────────────────────────────────────────┐
│  Character-level          Subword-level              Word-level     │
│  ←─────────────────────────────────────────────────────────────→    │
│                                                                      │
│  Vocab: ~256              Vocab: 32K-100K            Vocab: 100K+   │
│  Sequences: very long     Sequences: moderate        Sequences: short│
│  No OOV                   Rare OOV                   Many OOV       │
│  Slow training            Sweet spot ✓               Poor generalize│
└─────────────────────────────────────────────────────────────────────┘
```

### Character-Level Tokenization

Every character is a token. Vocabulary is tiny (~256 for UTF-8 bytes).

```python
text = "Hello"
tokens = list(text)  # ['H', 'e', 'l', 'l', 'o']
```

**Pros**: No out-of-vocabulary words, tiny vocab
**Cons**: Sequences become very long (expensive attention), harder to learn long-range dependencies

### Word-Level Tokenization

Split on whitespace and punctuation. Each word is a token.

```python
text = "The cat sat on the mat"
tokens = text.split()  # ['The', 'cat', 'sat', 'on', 'the', 'mat']
```

**Pros**: Intuitive, short sequences
**Cons**: Huge vocabulary, can't handle typos/new words (OOV problem), morphology ignored

### Subword Tokenization (The Winner)

The industry standard. Frequently used words stay whole; rare words get split into meaningful subpieces.

```
"unhappiness" → ["un", "happiness"]  or  ["un", "happi", "ness"]
"tokenization" → ["token", "ization"]
"ChatGPT" → ["Chat", "G", "PT"]
```

## BPE (Byte Pair Encoding)

The most widely used tokenization algorithm. Used by GPT-2, GPT-3, GPT-4, Llama, etc.

### Algorithm Step-by-Step

```
Input corpus: "low low low low low lowest lowest newer newer newer wider wider wider"

Step 0: Start with character-level vocabulary + end-of-word token
  Vocabulary: {l, o, w, e, s, t, n, r, i, d, _}
  
  Representation:
  "l o w _"     × 5
  "l o w e s t _" × 2
  "n e w e r _"   × 3
  "w i d e r _"   × 3

Step 1: Count all adjacent pairs
  (l, o): 7    (o, w): 7    (w, _): 5    (w, e): 2
  (e, s): 2   (s, t): 2    (t, _): 2    (n, e): 3
  (e, w): 3   (w, e): 2    (e, r): 6    (r, _): 6
  (w, i): 3   (i, d): 3    (d, e): 3

Step 2: Merge most frequent pair → (l, o) → "lo"  [count: 7]
  "lo w _"       × 5
  "lo w e s t _" × 2
  "n e w e r _"  × 3
  "w i d e r _"  × 3

Step 3: Merge most frequent pair → (lo, w) → "low"  [count: 7]
  "low _"        × 5
  "low e s t _"  × 2
  "n e w e r _"  × 3
  "w i d e r _"  × 3

Step 4: Merge (e, r) → "er"  [count: 6]
  "low _"        × 5
  "low e s t _"  × 2
  "n e w er _"   × 3
  "w i d er _"   × 3

... continue until desired vocab size reached
```

### Python Implementation of BPE from Scratch

```python
from collections import Counter, defaultdict

def get_stats(vocab):
    """Count frequency of adjacent pairs in vocabulary."""
    pairs = defaultdict(int)
    for word, freq in vocab.items():
        symbols = word.split()
        for i in range(len(symbols) - 1):
            pairs[(symbols[i], symbols[i+1])] += freq
    return pairs

def merge_vocab(pair, vocab):
    """Merge all occurrences of a pair in the vocabulary."""
    new_vocab = {}
    bigram = ' '.join(pair)
    replacement = ''.join(pair)
    for word, freq in vocab.items():
        new_word = word.replace(bigram, replacement)
        new_vocab[new_word] = freq
    return new_vocab

def learn_bpe(corpus, num_merges):
    """Learn BPE merges from a corpus."""
    # Initialize: split words into characters + end-of-word marker
    vocab = {}
    for word, freq in Counter(corpus.split()).items():
        vocab[' '.join(list(word)) + ' _'] = freq
    
    merges = []
    for i in range(num_merges):
        pairs = get_stats(vocab)
        if not pairs:
            break
        best_pair = max(pairs, key=pairs.get)
        vocab = merge_vocab(best_pair, vocab)
        merges.append(best_pair)
        print(f"Merge {i+1}: {best_pair} → {''.join(best_pair)}")
    
    return merges, vocab

# Example
corpus = "low low low low low lowest lowest newer newer newer wider wider wider"
merges, final_vocab = learn_bpe(corpus, num_merges=10)
print("\nFinal vocabulary:")
for word, freq in sorted(final_vocab.items(), key=lambda x: -x[1]):
    print(f"  {word}: {freq}")
```

### Encoding New Text with Learned BPE

```python
def encode_bpe(text, merges):
    """Encode text using learned BPE merges."""
    # Start with characters
    tokens = list(text) + ['_']
    
    # Apply merges in order
    for pair in merges:
        i = 0
        new_tokens = []
        while i < len(tokens):
            if i < len(tokens) - 1 and (tokens[i], tokens[i+1]) == pair:
                new_tokens.append(tokens[i] + tokens[i+1])
                i += 2
            else:
                new_tokens.append(tokens[i])
                i += 1
        tokens = new_tokens
    
    return tokens

# Example
encoded = encode_bpe("lowest", merges)
print(encoded)  # e.g., ['low', 'est_'] depending on merges learned
```

## WordPiece (Used in BERT)

Similar to BPE but uses a different scoring metric for selecting merges.

**Key difference**: Instead of raw frequency, WordPiece selects the pair that maximizes the likelihood of the training data:

```
score(pair) = freq(pair) / (freq(first) × freq(second))
```

This prefers pairs where the individual pieces rarely occur alone — they gain more information by being merged.

```python
# WordPiece uses ## prefix for continuation tokens
"tokenization" → ["token", "##ization"]
"embedding"    → ["em", "##bed", "##ding"]
"unhappiness"  → ["un", "##happy", "##ness"]
```

## SentencePiece (Language-Agnostic)

Treats the input as a raw byte stream — no pre-tokenization step. Works for any language without needing language-specific rules.

```
Key features:
- Treats space as a special character (▁ = beginning of word)
- No pre-tokenization needed (works on raw text)
- Supports both BPE and Unigram algorithms
- Used by: Llama, T5, ALBERT, XLNet
```

```python
import sentencepiece as spm

# Train
spm.SentencePieceTrainer.train(
    input='corpus.txt',
    model_prefix='my_tokenizer',
    vocab_size=32000,
    model_type='bpe'  # or 'unigram'
)

# Use
sp = spm.SentencePieceProcessor(model_file='my_tokenizer.model')
tokens = sp.encode("Hello world", out_type=str)
# ['▁Hello', '▁world']
ids = sp.encode("Hello world")
# [8774, 296]
```

## Unigram Tokenization

Opposite approach to BPE: starts with a large vocabulary and iteratively removes tokens.

```
Algorithm:
1. Start with a large vocabulary (all substrings up to max length)
2. Compute loss (negative log-likelihood) of corpus with current vocab
3. For each token, compute how much loss would increase if removed
4. Remove tokens that increase loss the least (keep most useful ones)
5. Repeat until desired vocab size reached
```

## Tiktoken (OpenAI's Tokenizer)

OpenAI's fast BPE tokenizer implementation, used for GPT-3.5, GPT-4.

```python
import tiktoken

# Get encoder for a specific model
enc = tiktoken.encoding_for_model("gpt-4")

# Encode
tokens = enc.encode("Hello, world!")
print(tokens)       # [9906, 11, 1917, 0]
print(len(tokens))  # 4

# Decode
text = enc.decode(tokens)
print(text)  # "Hello, world!"

# Count tokens (for cost estimation)
def count_tokens(text, model="gpt-4"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

# Token inspection
for token_id in tokens:
    print(f"{token_id} → '{enc.decode([token_id])}'")
```

## Comparison Table of Tokenizers

| Tokenizer | Algorithm | Used By | Vocab Size | Special Features |
|-----------|-----------|---------|-----------|-----------------|
| BPE (GPT) | Byte-level BPE | GPT-2/3/4, Llama | 50K-100K | Handles any byte sequence |
| WordPiece | Likelihood-based | BERT, DistilBERT | 30K | ## continuation prefix |
| SentencePiece | BPE or Unigram | T5, Llama, ALBERT | 32K | Language-agnostic, ▁ prefix |
| Unigram | Subtractive | XLNet, ALBERT | 32K | Probabilistic, multiple segmentations |
| Tiktoken | BPE (optimized) | GPT-3.5, GPT-4 | 100K | Fast Rust implementation |

## Token Vocabulary Size Tradeoffs

```
Small vocab (8K-16K):              Large vocab (64K-200K):
+ Smaller embedding matrix          + Shorter sequences (cheaper attention)
+ Better generalization              + More words are single tokens
+ Less memory                        + Better for multilingual
- Longer sequences                   - Larger embedding matrix
- More compute in attention          - Rare tokens poorly trained
- Words split awkwardly              - More memory

Sweet spot: 32K-100K (most modern LLMs)
```

## How Tokenization Affects Model Behavior

### The "Strawberry" Problem

```python
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4")

# "strawberry" is tokenized as:
tokens = enc.encode("strawberry")
for t in tokens:
    print(enc.decode([t]), end=" | ")
# "str" | "aw" | "berry" |

# The model never "sees" individual letters!
# When asked "How many r's in strawberry?" it struggles because
# 'r' appears across token boundaries: st[r]aw + be[r][r]y
# The model processes ['str', 'aw', 'berry'] — not individual characters
```

### Coding Performance

```python
# Well-tokenized (common patterns = single tokens):
enc.encode("def ")       # [755]  — single token!
enc.encode("return ")    # [693]  — single token!
enc.encode("self.")      # [726]  — single token!

# Poorly-tokenized (unusual syntax splits badly):
enc.encode("AbstractFactoryBuilderImpl")  # Many tokens — uncommon word
```

### Multilingual Issues

```python
# English is efficient (trained on mostly English data):
len(enc.encode("Hello, how are you?"))  # 6 tokens

# Other languages use more tokens for same meaning:
len(enc.encode("こんにちは、お元気ですか？"))  # 11 tokens (Japanese)
len(enc.encode("Hola, ¿cómo estás?"))    # 7 tokens (Spanish)

# This means: non-English text is MORE EXPENSIVE (more tokens = more cost)
# and uses more of the context window
```

## Token Embeddings

Once text is tokenized into IDs, each ID is mapped to a dense vector (embedding).

```
Token ID: 9906 ("Hello") → Embedding: [0.023, -0.451, 0.112, ..., 0.067]
                                        ←─── d_model dimensions ───→
                                              (e.g., 4096 for GPT-3)
```

### Embedding Matrix

```python
import torch
import torch.nn as nn

vocab_size = 50257   # GPT-2 vocabulary
d_model = 768        # embedding dimension

# The embedding matrix: shape [vocab_size, d_model]
token_embeddings = nn.Embedding(vocab_size, d_model)

# Look up embeddings for token IDs
token_ids = torch.tensor([9906, 11, 1917, 0])  # "Hello, world!"
embeddings = token_embeddings(token_ids)
print(embeddings.shape)  # torch.Size([4, 768])
```

### Positional Embeddings

Transformers have no inherent notion of position. Positional embeddings tell the model WHERE each token is in the sequence.

```python
# Learned positional embeddings (GPT-2)
max_seq_len = 1024
position_embeddings = nn.Embedding(max_seq_len, d_model)

positions = torch.arange(len(token_ids))
pos_embeds = position_embeddings(positions)

# Final input to transformer:
input_embeds = token_embeddings(token_ids) + position_embeddings(positions)
```

**Types of positional encoding:**

| Method | Used By | Key Property |
|--------|---------|-------------|
| Sinusoidal (fixed) | Original Transformer | Generalizes to unseen lengths |
| Learned absolute | GPT-2 | Simple, limited to training length |
| RoPE (Rotary) | Llama, GPT-NeoX | Encodes relative position, extrapolates |
| ALiBi | BLOOM | Linear bias, good extrapolation |

### RoPE (Rotary Position Embeddings)

```
Key idea: Encode position by ROTATING the embedding vectors.
- Token at position i gets rotated by angle i×θ
- The dot product between two tokens naturally encodes their RELATIVE distance
- This means attention is translation-invariant

Used by: Llama, Llama 2, Mistral, Qwen, most modern open models
Benefit: Can extrapolate to longer sequences than trained on
```

## Embedding Dimensions and Their Meaning

```
Model           d_model    Parameters
─────────────────────────────────────
GPT-2 Small     768       117M
GPT-2 Large    1280       774M
GPT-3          12288      175B
Llama 2 7B     4096       7B
Llama 2 70B    8192       70B
GPT-4 (est.)   ~12288    ~1.8T (MoE)
```

**What do dimensions represent?** Each dimension captures some learned feature — syntax, semantics, style, factual knowledge. No single dimension has a clear interpretation, but together they form a rich representation space where:

- Similar words are nearby (king ≈ queen)
- Analogies are linear (king - man + woman ≈ queen)
- Semantic relationships are preserved

## Real-World Production Considerations

1. **Token counting for cost**: Every API call charges per token (input + output)
2. **Context window management**: Tokenize to check if you'll exceed limits
3. **Prompt optimization**: Shorter prompts = fewer tokens = lower cost
4. **Multilingual apps**: Budget 2-3x more tokens for non-English languages
5. **Consistent tokenization**: Always use the same tokenizer as the model

```python
# Cost estimation helper
def estimate_cost(prompt, response_tokens=500, model="gpt-4"):
    enc = tiktoken.encoding_for_model(model)
    input_tokens = len(enc.encode(prompt))
    
    # GPT-4 pricing (example, check current prices)
    input_cost = input_tokens * 0.03 / 1000
    output_cost = response_tokens * 0.06 / 1000
    
    return {
        "input_tokens": input_tokens,
        "estimated_output_tokens": response_tokens,
        "estimated_cost": f"${input_cost + output_cost:.4f}"
    }
```

## Interview Questions

1. **Why do LLMs use subword tokenization instead of word-level?**
   - Handles OOV, keeps vocab manageable, captures morphology

2. **Explain the BPE algorithm in 3 sentences.**
   - Start with characters. Count adjacent pairs. Merge the most frequent pair. Repeat until vocab size reached.

3. **Why does GPT struggle with counting letters in words?**
   - Tokenization splits words into subwords; the model never processes individual characters.

4. **What's the difference between BPE and WordPiece?**
   - BPE merges by raw frequency; WordPiece merges by likelihood gain (normalized by individual frequencies).

5. **How do positional embeddings work and why are they needed?**
   - Transformers are permutation-invariant; positional embeddings inject sequence order information.

6. **What is RoPE and why is it preferred over learned absolute positions?**
   - Rotary embeddings encode relative position via rotation, enabling length extrapolation.

7. **How does vocabulary size affect model performance and cost?**
   - Larger vocab = shorter sequences (cheaper attention) but larger embedding matrix and memory.

## Exercises

### Exercise 1: Implement BPE
Implement the BPE algorithm from scratch and train it on a small corpus. Verify that common words remain whole while rare words are split.

### Exercise 2: Token Cost Calculator
Write a function that takes a prompt and calculates the cost for different models (GPT-4, GPT-3.5, Claude). Account for system prompt, user message, and estimated response.

### Exercise 3: Tokenizer Comparison
Tokenize the same multilingual text with tiktoken, SentencePiece, and HuggingFace tokenizers. Compare token counts and observe how each handles non-English text.

### Exercise 4: The Strawberry Experiment
Ask an LLM to count characters in various words. Identify which words it gets wrong and explain why based on tokenization boundaries.

## Common Pitfalls

1. **Assuming 1 word = 1 token**: On average, 1 token ≈ 0.75 words in English
2. **Ignoring tokenization in evaluation**: BLEU/ROUGE scores depend on tokenization
3. **Not accounting for special tokens**: BOS, EOS, padding tokens consume context
4. **Mixing tokenizers**: Using GPT-2 tokenizer to count tokens for GPT-4 gives wrong results
5. **Forgetting token limits in production**: Always validate input length before API calls
