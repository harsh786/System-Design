# Sequence Models for NLP

## Overview

Sequence models process ordered data where context and position matter. NLP tasks like translation, summarization, and NER all require understanding sequences.

---

## 1. Language Modeling

### Definition
Predict the next word (or masked word) given context.

```
P(w_1, w_2, ..., w_n) = Π P(w_i | w_1, ..., w_{i-1})
```

### Perplexity

```
Perplexity = 2^{cross-entropy} = 2^{-1/N * Σ log2 P(w_i | context)}

Interpretation:
  - PP = 1: perfect prediction
  - PP = |V|: random guess over vocabulary
  - Lower is better

Example: PP = 50 means the model is "as confused as if choosing from 50 words"
```

```python
import torch
import torch.nn.functional as F

def compute_perplexity(model, tokenizer, text):
    """Compute perplexity of text under a language model."""
    inputs = tokenizer(text, return_tensors='pt')
    with torch.no_grad():
        outputs = model(**inputs, labels=inputs['input_ids'])
    # outputs.loss is cross-entropy
    perplexity = torch.exp(outputs.loss)
    return perplexity.item()

# from transformers import GPT2LMHeadModel, GPT2Tokenizer
# model = GPT2LMHeadModel.from_pretrained('gpt2')
# tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
# print(compute_perplexity(model, tokenizer, "The cat sat on the mat"))  # ~20-50
```

---

## 2. Named Entity Recognition (NER)

### BIO Tagging Scheme

```
Token:   "Barack"  "Obama"  "visited"  "New"   "York"  "yesterday"
Tag:      B-PER    I-PER    O          B-LOC   I-LOC   O

B = Beginning of entity
I = Inside (continuation) of entity
O = Outside (not an entity)

Extended: BIOES (adds E=End, S=Single)
```

### NER with spaCy

```python
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp("Apple is looking at buying U.K. startup for $1 billion")

for ent in doc.ents:
    print(f"{ent.text:20} {ent.label_:10} {ent.start_char}-{ent.end_char}")
# Apple                ORG        0-5
# U.K.                 GPE        27-31
# $1 billion           MONEY      44-54
```

### NER with Transformers (Token Classification)

```python
from transformers import pipeline

ner = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")
results = ner("Hugging Face is based in New York City")
# [{'entity_group': 'ORG', 'word': 'Hugging Face', 'score': 0.99},
#  {'entity_group': 'LOC', 'word': 'New York City', 'score': 0.99}]
```

---

## 3. Part-of-Speech Tagging

```python
import spacy
nlp = spacy.load("en_core_web_sm")
doc = nlp("The quick brown fox jumps over the lazy dog")

for token in doc:
    print(f"{token.text:10} {token.pos_:6} {token.dep_:10}")
# The        DET    det
# quick      ADJ    amod
# brown      ADJ    amod
# fox        NOUN   nsubj
# jumps      VERB   ROOT
# over       ADP    prep
# the        DET    det
# lazy       ADJ    amod
# dog        NOUN   pobj
```

---

## 4. Dependency Parsing

```
Sentence: "The cat sat on the mat"

         sat (ROOT)
        /    \
      cat    on
      /       \
    The      mat
              /
            the

Relations:
  cat → sat  (nsubj: nominal subject)
  The → cat  (det: determiner)
  on → sat   (prep: prepositional modifier)
  mat → on   (pobj: object of preposition)
  the → mat  (det: determiner)
```

```python
# Visualize dependency tree
from spacy import displacy
doc = nlp("The cat sat on the mat")
displacy.render(doc, style="dep")  # renders in browser/notebook
```

---

## 5. Machine Translation (Seq2Seq + Attention)

### Encoder-Decoder Architecture

```
┌─────────────────────────────────────────────────────┐
│ Encoder                    Decoder                   │
│                                                      │
│ "Je suis étudiant" →      → "I am a student"       │
│                                                      │
│ [Je][suis][étudiant]      [I][am][a][student][EOS] │
│   ↓    ↓      ↓            ↑   ↑  ↑    ↑          │
│ LSTM→LSTM→LSTM→[h]    [h]→LSTM→LSTM→LSTM→LSTM      │
│                  └──────┘                            │
│              (context vector)                        │
└─────────────────────────────────────────────────────┘
```

### Attention Mechanism (Bahdanau)

```
For each decoder step t:
  1. Score: e_{t,i} = score(s_t, h_i)    (alignment between decoder state and each encoder hidden)
  2. Attention weights: α_{t,i} = softmax(e_{t,i})
  3. Context: c_t = Σ α_{t,i} * h_i
  4. Output: combine c_t with decoder state s_t
```

```python
# Modern translation with transformers
from transformers import pipeline

translator = pipeline("translation_en_to_fr", model="Helsinki-NLP/opus-mt-en-fr")
result = translator("Machine learning is transforming the world")
# [{'translation_text': "L'apprentissage automatique transforme le monde"}]
```

---

## 6. Text Summarization

### Extractive vs Abstractive

```
Original: "The cat sat on the mat. It was a warm day. The sun was shining brightly."

Extractive: "The cat sat on the mat. The sun was shining brightly."
            (selects existing sentences)

Abstractive: "A cat rested on a mat on a sunny day."
            (generates new text)
```

### Extractive (TextRank)

```python
# TextRank: graph-based ranking (like PageRank for sentences)
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

parser = PlaintextParser.from_string(text, Tokenizer("english"))
summarizer = TextRankSummarizer()
summary = summarizer(parser.document, sentences_count=3)
```

### Abstractive (T5 / BART)

```python
from transformers import pipeline

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
text = """Long article text here..."""
summary = summarizer(text, max_length=130, min_length=30, do_sample=False)
print(summary[0]['summary_text'])
```

---

## 7. Question Answering

### Types

| Type | Input | Output | Example Model |
|------|-------|--------|---------------|
| Extractive | Context + Question | Span from context | BERT-QA |
| Abstractive | Context + Question | Generated answer | T5, GPT |
| Open-domain | Question only | Answer (retrieval + reading) | RAG, DPR |

### Extractive QA

```python
from transformers import pipeline

qa = pipeline("question-answering", model="deepset/roberta-base-squad2")

context = """
The Amazon rainforest produces approximately 20% of the world's oxygen.
It spans across 9 countries and covers 5.5 million square kilometers.
"""

result = qa(question="How much oxygen does the Amazon produce?", context=context)
# {'answer': 'approximately 20%', 'score': 0.95, 'start': 39, 'end': 56}
```

### Open-Domain QA (Retriever-Reader)

```
Question → Retriever (find relevant docs) → Reader (extract answer from docs)

Modern: RAG (Retrieval-Augmented Generation)
  Question → Dense Retriever → Top-k passages → LLM generates answer
```

---

## 8. Text Generation

### Decoding Strategies

```python
from transformers import GPT2LMHeadModel, GPT2Tokenizer

model = GPT2LMHeadModel.from_pretrained('gpt2')
tokenizer = GPT2Tokenizer.from_pretrained('gpt2')

input_ids = tokenizer.encode("The future of AI is", return_tensors='pt')

# Greedy: always pick highest probability token
greedy = model.generate(input_ids, max_length=50, do_sample=False)

# Beam search: keep top-k sequences at each step
beam = model.generate(input_ids, max_length=50, num_beams=5, no_repeat_ngram_size=2)

# Top-k sampling: sample from top k tokens
topk = model.generate(input_ids, max_length=50, do_sample=True, top_k=50)

# Nucleus (top-p) sampling: sample from smallest set with cumulative prob >= p
nucleus = model.generate(input_ids, max_length=50, do_sample=True, top_p=0.92)

# Temperature: controls randomness (lower=more deterministic, higher=more random)
temp = model.generate(input_ids, max_length=50, do_sample=True, temperature=0.7)
```

### Temperature Intuition

```
logits = [2.0, 1.0, 0.5]

T=1.0: softmax([2, 1, 0.5])   = [0.51, 0.19, 0.11]  (normal)
T=0.5: softmax([4, 2, 1])     = [0.84, 0.11, 0.05]  (more peaked/deterministic)
T=2.0: softmax([1, 0.5, 0.25])= [0.39, 0.24, 0.18]  (more uniform/creative)
```

---

## 9. Dialogue Systems

### Architecture

```
┌────────────────────────────────────────────┐
│            Dialogue System                  │
├────────────────────────────────────────────┤
│ NLU (Understanding)                        │
│   - Intent detection                       │
│   - Slot filling                           │
│   - Entity extraction                      │
├────────────────────────────────────────────┤
│ Dialogue Manager                           │
│   - State tracking                         │
│   - Policy (what action to take)           │
├────────────────────────────────────────────┤
│ NLG (Generation)                           │
│   - Template-based or neural generation    │
│   - Response selection                     │
└────────────────────────────────────────────┘
```

### Modern Approach: End-to-End with LLMs

```python
from transformers import pipeline

chatbot = pipeline("text-generation", model="microsoft/DialoGPT-medium")

conversation_history = ""
while True:
    user_input = input("You: ")
    conversation_history += f"User: {user_input}\nBot:"
    response = chatbot(conversation_history, max_length=1000, pad_token_id=50256)
    bot_reply = response[0]['generated_text'].split("Bot:")[-1].strip()
    conversation_history += f" {bot_reply}\n"
    print(f"Bot: {bot_reply}")
```

---

## 10. Evaluation Metrics for NLP Tasks

| Task | Metric | Description |
|------|--------|-------------|
| Language Model | Perplexity | Lower = better predictions |
| NER | F1 (entity-level) | Exact entity match |
| Translation | BLEU | N-gram overlap with reference |
| Summarization | ROUGE-L | Longest common subsequence |
| QA | Exact Match / F1 | Token overlap with answer |
| Generation | Human eval, BERTScore | Semantic similarity |

```python
# BLEU score
from nltk.translate.bleu_score import sentence_bleu

reference = [["the", "cat", "sat", "on", "the", "mat"]]
candidate = ["the", "cat", "is", "on", "the", "mat"]
score = sentence_bleu(reference, candidate)
print(f"BLEU: {score:.4f}")  # ~0.66

# ROUGE
from rouge_score import rouge_scorer
scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)
scores = scorer.score("The cat sat on the mat", "The cat is on the mat")
```

---

## Production Considerations

- **Latency**: Autoregressive generation is slow; use speculative decoding, KV caching
- **Hallucination**: Ground generation with retrieved context (RAG)
- **Safety**: Add output filters, use RLHF-aligned models
- **Multilingual**: Use mBART, NLLB for translation; XLM-R for understanding
- **Evaluation**: Automated metrics correlate poorly with quality; use LLM-as-judge

---

## Exercises

1. Implement a bigram language model and compute perplexity on held-out text
2. Train a CRF-based NER model on CoNLL-2003 and compare with BERT-NER
3. Build an extractive QA system using BERT and evaluate on SQuAD
4. Implement beam search from scratch for a seq2seq model
5. Create a simple RAG pipeline: embed documents → retrieve → generate answer

## Interview Questions

1. **Why is BLEU score criticized for evaluating generation quality?**
   - Only measures n-gram overlap, ignores meaning, penalizes valid paraphrases, doesn't capture fluency

2. **How does beam search differ from greedy decoding, and when does it fail?**
   - Explores multiple hypotheses; fails with repetition, generic outputs; nucleus sampling often better for open-ended generation

3. **Explain the difference between extractive and abstractive summarization trade-offs.**
   - Extractive: faithful but choppy; Abstractive: fluent but may hallucinate

4. **How would you handle multi-turn context in a dialogue system?**
   - Concatenate history (truncate old turns), use memory modules, or fine-tune with dialogue datasets

5. **What is the exposure bias problem in seq2seq models?**
   - Training uses teacher forcing (ground truth inputs); inference uses model's own predictions. Mismatch causes error accumulation. Fix: scheduled sampling, reinforcement learning
