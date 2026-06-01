# Word Embeddings Deep Dive

## Overview

Word embeddings map discrete words to dense, continuous vector spaces where semantic relationships are preserved geometrically.

```
"king" - "man" + "woman" ≈ "queen"
```

---

## 1. One-Hot Encoding Limitations

```python
import numpy as np

vocab = ["cat", "dog", "fish", "bird"]
# One-hot: each word is a sparse vector of size |V|
one_hot = {word: np.eye(len(vocab))[i] for i, word in enumerate(vocab)}
# "cat"  → [1, 0, 0, 0]
# "dog"  → [0, 1, 0, 0]

# Problems:
# 1. cosine_similarity(cat, dog) = 0  (no semantic info!)
# 2. Dimensionality = vocabulary size (100k+ for real corpora)
# 3. No generalization between similar words
```

---

## 2. Word2Vec

### Core Idea
Learn word vectors such that words in similar contexts have similar vectors.

**Distributional Hypothesis**: "A word is characterized by the company it keeps" — Firth (1957)

### CBOW (Continuous Bag of Words)

```
Context words → Predict center word

Input:  ["the", "cat", "on", "the", "mat"]  (context window=2)
Target: "sat"

Architecture:
  Context words → Average embedding → Hidden layer → Softmax → Predict center
```

### Skip-gram

```
Center word → Predict context words

Input:  "sat"
Target: ["the", "cat", "on", "the", "mat"]

Architecture:
  Center word → Embedding → Hidden layer → Softmax → Predict each context word
```

### Mathematical Formulation (Skip-gram)

```
Objective: Maximize P(context | center)

P(w_o | w_c) = exp(v'_{w_o} · v_{w_c}) / Σ_w exp(v'_w · v_{w_c})

Loss = -log P(w_o | w_c)
     = -v'_{w_o} · v_{w_c} + log Σ_w exp(v'_w · v_{w_c})

Where:
  v_{w_c} = input (center) embedding
  v'_{w_o} = output (context) embedding
```

### Word2Vec from Scratch (NumPy)

```python
import numpy as np

class Word2Vec:
    def __init__(self, vocab_size, embedding_dim, learning_rate=0.01):
        # Two weight matrices: input embeddings and output embeddings
        self.W_in = np.random.randn(vocab_size, embedding_dim) * 0.01
        self.W_out = np.random.randn(embedding_dim, vocab_size) * 0.01
        self.lr = learning_rate
    
    def forward(self, center_idx):
        """Get center word embedding."""
        self.h = self.W_in[center_idx]  # (embedding_dim,)
        self.u = self.W_out.T @ self.h  # (vocab_size,) - raw scores
        self.y_pred = self._softmax(self.u)
        return self.y_pred
    
    def backward(self, center_idx, context_idx):
        """Compute gradients and update weights."""
        # Output gradient
        e = self.y_pred.copy()
        e[context_idx] -= 1  # y_pred - y_true
        
        # Update output weights
        dW_out = np.outer(self.h, e)
        self.W_out -= self.lr * dW_out
        
        # Update input weights
        dh = self.W_out @ e
        self.W_in[center_idx] -= self.lr * dh
    
    def train_pair(self, center_idx, context_idx):
        self.forward(center_idx)
        self.backward(center_idx, context_idx)
        loss = -np.log(self.y_pred[context_idx] + 1e-10)
        return loss
    
    def _softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()
    
    def get_embedding(self, word_idx):
        return self.W_in[word_idx]

# Training loop sketch
# for epoch in range(epochs):
#     for center, context in generate_pairs(corpus, window=5):
#         loss = model.train_pair(center, context)
```

---

## 3. Negative Sampling

Full softmax over |V| is expensive (|V| can be 100k+). Negative sampling approximates it.

```
Instead of: maximize P(context | center) over full vocabulary
Do:         maximize P(context | center) for TRUE pairs
            minimize P(random_word | center) for NEGATIVE samples

Loss = -log σ(v'_{w_o} · v_{w_c}) - Σ_{k negative samples} log σ(-v'_{w_k} · v_{w_c})

Where σ = sigmoid function
```

```python
def negative_sampling_loss(center_emb, context_emb, neg_embs):
    """
    center_emb: (d,) embedding of center word
    context_emb: (d,) embedding of true context word
    neg_embs: (k, d) embeddings of k negative samples
    """
    # Positive: push center and context together
    pos_score = sigmoid(np.dot(context_emb, center_emb))
    pos_loss = -np.log(pos_score + 1e-10)
    
    # Negative: push center and negatives apart
    neg_scores = sigmoid(-neg_embs @ center_emb)
    neg_loss = -np.sum(np.log(neg_scores + 1e-10))
    
    return pos_loss + neg_loss

def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

# Negative sampling distribution: P(w) ∝ freq(w)^(3/4)
# The 3/4 power smooths the distribution (gives rare words more chance)
```

---

## 4. GloVe (Global Vectors)

### Key Insight
Encode word co-occurrence statistics directly into the objective.

```
Co-occurrence matrix X: X_ij = count of word j appearing in context of word i

Objective: minimize Σ_{i,j} f(X_ij) * (w_i · w̃_j + b_i + b̃_j - log X_ij)²

Where:
  f(x) = (x/x_max)^α if x < x_max, else 1  (weighting function)
  w_i, w̃_j = word and context vectors
  b_i, b̃_j = bias terms
```

```python
# GloVe captures ratios of co-occurrence probabilities
# P(ice | solid) / P(ice | gas) = high     → related to "solid"
# P(steam | solid) / P(steam | gas) = low   → related to "gas"
# P(water | solid) / P(water | gas) ≈ 1     → related to both
# P(random | solid) / P(random | gas) ≈ 1   → related to neither

from gensim.models import KeyedVectors
# Load pre-trained GloVe
glove = KeyedVectors.load_word2vec_format('glove.6B.300d.w2v.txt')
print(glove.most_similar('king'))
```

### Word2Vec vs GloVe

| Aspect | Word2Vec | GloVe |
|--------|----------|-------|
| Training | Local context windows | Global co-occurrence matrix |
| Method | Predictive (neural) | Count-based (matrix factorization) |
| Scalability | Better for streaming | Needs full corpus upfront |
| Performance | Similar | Similar (task-dependent) |

---

## 5. FastText (Subword Embeddings)

```
Key innovation: represent words as sum of character n-gram embeddings

"where" with n=3: <wh, whe, her, ere, re>, <where>
                   (angle brackets = word boundaries)

Embedding("where") = Σ embeddings of all its character n-grams

Benefits:
  - Handles OOV words (compose from character n-grams)
  - Better for morphologically rich languages
  - "unhappiness" gets info from "un", "happy", "ness"
```

```python
from gensim.models import FastText

# Train FastText
model = FastText(sentences=corpus, vector_size=100, window=5, 
                 min_count=1, sg=1, min_n=3, max_n=6)

# Can get vectors for OOV words!
vector = model.wv["unseen_word_xyz"]  # composed from subword n-grams
```

---

## 6. Contextual Embeddings

### The Problem with Static Embeddings
```
"bank" → single vector (regardless of "river bank" vs "bank account")
```

### ELMo (Embeddings from Language Models)

```
Architecture: 2-layer bidirectional LSTM
- Forward LSTM:  reads left-to-right
- Backward LSTM: reads right-to-left
- Combine all layers with learned weights per task

ELMo(word) = γ * Σ_j s_j * h_j   (weighted sum of all layer representations)
```

### BERT Embeddings (Contextual)

```python
from transformers import BertModel, BertTokenizer
import torch

tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertModel.from_pretrained('bert-base-uncased')

# Same word, different context
sentences = ["I went to the bank to deposit money",
             "The river bank was muddy"]

for sent in sentences:
    inputs = tokenizer(sent, return_tensors='pt')
    with torch.no_grad():
        outputs = model(**inputs)
    # outputs.last_hidden_state: (1, seq_len, 768)
    # Each token gets a DIFFERENT vector depending on context!
    bank_idx = tokenizer.encode(sent).index(tokenizer.encode("bank")[1])
    bank_embedding = outputs.last_hidden_state[0, bank_idx]
    print(f"'bank' embedding shape: {bank_embedding.shape}")  # (768,)
```

---

## 7. Sentence Embeddings

### Mean Pooling

```python
def mean_pooling(token_embeddings, attention_mask):
    """Average all token embeddings (ignoring padding)."""
    mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size())
    sum_embeddings = torch.sum(token_embeddings * mask_expanded, dim=1)
    sum_mask = mask_expanded.sum(dim=1).clamp(min=1e-9)
    return sum_embeddings / sum_mask
```

### [CLS] Token

```python
# BERT's [CLS] token embedding (first token)
cls_embedding = outputs.last_hidden_state[:, 0, :]  # (batch, 768)
# Note: raw [CLS] is NOT a good sentence embedding without fine-tuning!
```

### Sentence-BERT (SBERT)

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

sentences = ["The cat sits on the mat", "A feline rests on a rug"]
embeddings = model.encode(sentences)

# Cosine similarity
from sklearn.metrics.pairwise import cosine_similarity
sim = cosine_similarity([embeddings[0]], [embeddings[1]])
print(f"Similarity: {sim[0][0]:.4f}")  # ~0.75 (semantically similar)
```

```
SBERT Architecture (Siamese Network):
  Sentence A → BERT → Mean Pool → Embedding_A ─┐
                                                 ├── Cosine Similarity / Loss
  Sentence B → BERT → Mean Pool → Embedding_B ─┘

Training: contrastive loss or triplet loss on sentence pairs
```

---

## 8. Embedding Evaluation

### Intrinsic Evaluation

```python
# Word analogy task: king - man + woman = ?
from gensim.models import KeyedVectors

model = KeyedVectors.load_word2vec_format('GoogleNews-vectors-negative300.bin', binary=True)

# Analogy: a is to b as c is to ?
result = model.most_similar(positive=['woman', 'king'], negative=['man'], topn=1)
# [('queen', 0.7118)]

# Word similarity benchmarks (correlation with human ratings)
# Datasets: SimLex-999, WordSim-353, MEN
```

### Embedding Arithmetic Examples

```python
# Semantic relationships encoded as vector offsets
print(model.most_similar(positive=['paris', 'germany'], negative=['france']))
# → 'berlin'

print(model.most_similar(positive=['bigger', 'cold'], negative=['big']))
# → 'colder'

print(model.most_similar(positive=['queen', 'man'], negative=['woman']))
# → 'king'
```

---

## 9. Embedding Visualization

```python
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import numpy as np

words = ['king', 'queen', 'man', 'woman', 'prince', 'princess',
         'cat', 'dog', 'fish', 'bird', 'lion', 'tiger']
vectors = np.array([model[w] for w in words])

# t-SNE reduction to 2D
tsne = TSNE(n_components=2, random_state=42, perplexity=5)
vectors_2d = tsne.fit_transform(vectors)

plt.figure(figsize=(10, 8))
for i, word in enumerate(words):
    plt.scatter(vectors_2d[i, 0], vectors_2d[i, 1])
    plt.annotate(word, (vectors_2d[i, 0]+0.5, vectors_2d[i, 1]+0.5))
plt.title("Word Embedding Visualization (t-SNE)")
plt.show()

# UMAP (faster, preserves more global structure)
# import umap
# reducer = umap.UMAP(n_components=2)
# vectors_2d = reducer.fit_transform(vectors)
```

---

## 10. Transfer Learning with Pre-trained Embeddings

```python
import torch
import torch.nn as nn

# Load pre-trained embeddings into PyTorch
def load_pretrained_embeddings(word2idx, embedding_path, embedding_dim=300):
    """Load GloVe/Word2Vec embeddings for your vocabulary."""
    embeddings = np.random.randn(len(word2idx), embedding_dim) * 0.01
    
    with open(embedding_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            word = parts[0]
            if word in word2idx:
                embeddings[word2idx[word]] = np.array(parts[1:], dtype=np.float32)
    
    return torch.FloatTensor(embeddings)

# Use in model
class TextClassifier(nn.Module):
    def __init__(self, pretrained_embeddings, num_classes, freeze=True):
        super().__init__()
        self.embedding = nn.Embedding.from_pretrained(
            pretrained_embeddings, freeze=freeze  # freeze=True: don't update embeddings
        )
        self.fc = nn.Linear(pretrained_embeddings.shape[1], num_classes)
    
    def forward(self, x):
        emb = self.embedding(x)         # (batch, seq_len, dim)
        pooled = emb.mean(dim=1)        # (batch, dim)
        return self.fc(pooled)          # (batch, num_classes)
```

---

## 11. Domain-Specific Embeddings

| Domain | Model | Training Data |
|--------|-------|---------------|
| Biomedical | BioWordVec | PubMed + MIMIC-III |
| Clinical | ClinicalBERT | Clinical notes |
| Finance | FinBERT | Financial news + reports |
| Legal | LegalBERT | Legal documents |
| Scientific | SciBERT | Semantic Scholar papers |

```python
# Using domain-specific embeddings
from transformers import AutoModel, AutoTokenizer

# FinBERT for financial text
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModel.from_pretrained("ProsusAI/finbert")

text = "The company reported strong quarterly earnings growth"
inputs = tokenizer(text, return_tensors="pt")
outputs = model(**inputs)
# These embeddings understand financial context better than generic BERT
```

---

## Summary Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│ Method     │ Context │ OOV    │ Training   │ Dimensions │ Year     │
├─────────────────────────────────────────────────────────────────────┤
│ One-hot    │ None    │ No     │ None       │ |V|        │ -        │
│ Word2Vec   │ Static  │ No     │ Local ctx  │ 100-300    │ 2013     │
│ GloVe      │ Static  │ No     │ Global     │ 50-300     │ 2014     │
│ FastText   │ Static  │ Yes    │ Subword    │ 100-300    │ 2016     │
│ ELMo       │ Dynamic │ No     │ biLSTM LM  │ 1024       │ 2018     │
│ BERT       │ Dynamic │ Yes*   │ Transformer│ 768-1024   │ 2018     │
│ SBERT      │ Dynamic │ Yes*   │ Siamese    │ 384-768    │ 2019     │
└─────────────────────────────────────────────────────────────────────┘
* Via subword tokenization
```

---

## Exercises

1. Train Word2Vec on a custom corpus using gensim and find interesting analogies
2. Implement the GloVe weighting function f(x) and explain why the 3/4 power is used in negative sampling
3. Compare cosine similarity of "bank" in financial vs geographical contexts using BERT
4. Build a simple document retrieval system using TF-IDF vs SBERT embeddings
5. Fine-tune sentence-transformers on a domain-specific paraphrase dataset

## Interview Questions

1. **Why does Word2Vec use two embedding matrices (W_in and W_out)?**
   - Separate representations for center and context roles; final embedding is typically W_in (or average of both)

2. **How does negative sampling approximate the full softmax?**
   - Converts multi-class classification into k+1 binary classifications; approximates the partition function

3. **When would FastText significantly outperform Word2Vec?**
   - Morphologically rich languages (Turkish, Finnish), rare words, misspellings, domain-specific terminology

4. **Why is raw BERT [CLS] a poor sentence embedding?**
   - Not trained for sentence-level similarity; tokens collapse into anisotropic space; SBERT fixes with contrastive training

5. **How do you handle domain shift when using pre-trained embeddings?**
   - Fine-tune on domain data, train domain-specific embeddings, use adaptive methods, or continued pre-training
