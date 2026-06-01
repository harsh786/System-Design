# NLP Deep Dive

## Evolution of Natural Language Processing

```
Rule-Based (1950s-1990s) → Statistical (1990s-2010s) → Neural (2013-2017) → Transformer (2017-2020) → LLM (2020+)
```

### Timeline

| Era | Key Methods | Limitations |
|-----|-------------|-------------|
| Rule-Based | Regex, grammars, hand-crafted rules | Brittle, doesn't generalize |
| Statistical | HMMs, CRFs, n-grams, Naive Bayes | Feature engineering, sparse data |
| Neural | RNNs, LSTMs, CNNs, Word2Vec | Sequential bottleneck, limited context |
| Transformer | BERT, GPT-2, T5, attention mechanism | Compute-heavy, data-hungry |
| LLM | GPT-4, Claude, LLaMA, in-context learning | Cost, hallucination, alignment |

## NLP Task Taxonomy

```
NLP Tasks
├── Understanding (NLU)
│   ├── Classification (sentiment, intent, topic)
│   ├── Token Classification (NER, POS tagging)
│   ├── Semantic Similarity (STS, paraphrase detection)
│   ├── Question Answering (extractive, abstractive)
│   └── Natural Language Inference (entailment)
├── Generation (NLG)
│   ├── Machine Translation
│   ├── Summarization
│   ├── Dialogue / Chatbot
│   ├── Text Completion
│   └── Creative Writing
├── Information Extraction
│   ├── Named Entity Recognition
│   ├── Relation Extraction
│   ├── Event Extraction
│   └── Knowledge Graph Construction
└── Speech + Language
    ├── ASR (Speech-to-Text)
    ├── TTS (Text-to-Speech)
    └── Spoken Language Understanding
```

## Module Structure

| # | Module | Focus |
|---|--------|-------|
| 01 | [Text Preprocessing & Representations](./01-Text-Preprocessing-and-Representations/) | Cleaning, tokenization, BoW, TF-IDF |
| 02 | [Word Embeddings Deep Dive](./02-Word-Embeddings-Deep-Dive/) | Word2Vec, GloVe, FastText, contextual |
| 03 | [Sequence Models for NLP](./03-Sequence-Models-for-NLP/) | NER, MT, summarization, QA, generation |
| 04 | [BERT & Language Understanding](./04-BERT-and-Language-Understanding/) | BERT, RoBERTa, fine-tuning, variants |
| 05 | [Semantic Search & Vector DBs](./05-Semantic-Search-and-Vector-DBs/) | ANN, HNSW, vector DBs, hybrid search |

## Prerequisites

- Python proficiency
- Linear algebra basics (vectors, matrices, dot products)
- ML fundamentals (gradient descent, loss functions)
- Deep learning basics (backpropagation, neural networks)
- Transformer architecture understanding (see Module 07)

## Key Libraries

```python
# Core NLP
import nltk, spacy, transformers, tokenizers

# Embeddings & Search
import gensim, sentence_transformers, faiss, chromadb

# Deep Learning
import torch, tensorflow
```
