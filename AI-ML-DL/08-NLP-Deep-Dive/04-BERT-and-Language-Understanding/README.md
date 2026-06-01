# BERT and Language Understanding

## Overview

BERT (Bidirectional Encoder Representations from Transformers) revolutionized NLP by introducing deep bidirectional pre-training, enabling transfer learning across diverse language understanding tasks.

---

## 1. BERT Architecture

```
Input: [CLS] The cat sat on the mat [SEP]

┌──────────────────────────────────────────────┐
│         Transformer Encoder × 12 (base)      │
│                                              │
│  Token Emb + Segment Emb + Position Emb      │
│         ↓                                    │
│  Multi-Head Self-Attention (bidirectional)    │
│         ↓                                    │
│  Feed-Forward Network                        │
│         ↓                                    │
│  Layer Norm + Residual                       │
│         × 12 layers                          │
│         ↓                                    │
│  [CLS] h1  h2  h3  h4  h5  h6  [SEP]       │
│   ↓                                          │
│  Classification head (for [CLS])             │
│  Token heads (for each token)                │
└──────────────────────────────────────────────┘

BERT-base:  12 layers, 768 hidden, 12 heads, 110M params
BERT-large: 24 layers, 1024 hidden, 16 heads, 340M params
```

### Key Innovation: Bidirectional Context

```
GPT (left-to-right):  "The [MASK] sat" → only uses "The" to predict
BERT (bidirectional):  "The [MASK] sat" → uses "The" AND "sat" to predict

This is why BERT excels at understanding but not generation.
```

---

## 2. Pre-training Tasks

### Masked Language Model (MLM)

```
Input:  "The cat [MASK] on the [MASK]"
Target: "The cat  sat  on the  mat"

Strategy: Randomly mask 15% of tokens
  - 80% replaced with [MASK]
  - 10% replaced with random word
  - 10% kept unchanged
  (Prevents model from relying on [MASK] token existing at inference)
```

### Next Sentence Prediction (NSP)

```
Input:  [CLS] Sentence A [SEP] Sentence B [SEP]
Label:  IsNext / NotNext (50/50)

Example (positive):
  A: "The cat sat on the mat"
  B: "It was a fluffy orange cat"    → IsNext

Example (negative):
  A: "The cat sat on the mat"
  B: "Stock prices rose yesterday"   → NotNext

Note: RoBERTa showed NSP doesn't help; removed it.
```

---

## 3. Fine-tuning BERT for Downstream Tasks

```
Pre-trained BERT → Add task-specific head → Fine-tune on labeled data

┌─────────────────────────────────────────┐
│ Task              │ Input        │ Head  │
├─────────────────────────────────────────┤
│ Classification    │ [CLS] output │ Linear│
│ NER (token)       │ Each token   │ Linear│
│ QA (extractive)   │ Each token   │ 2×Lin │
│ Sentence Pair     │ [CLS] of pair│ Linear│
└─────────────────────────────────────────┘
```

### Text Classification

```python
from transformers import BertForSequenceClassification, BertTokenizer, Trainer, TrainingArguments
import torch

# Load pre-trained BERT with classification head
model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

# Tokenize
texts = ["This movie was great!", "Terrible waste of time."]
labels = [1, 0]  # positive, negative

encodings = tokenizer(texts, truncation=True, padding=True, max_length=128, return_tensors='pt')
encodings['labels'] = torch.tensor(labels)

# Fine-tune
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,
    per_device_train_batch_size=16,
    learning_rate=2e-5,        # Key: use small LR for fine-tuning
    weight_decay=0.01,
    warmup_steps=500,
)

# In practice, use a Dataset class and Trainer
# trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
# trainer.train()
```

### Named Entity Recognition

```python
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

model_name = "dslim/bert-base-NER"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForTokenClassification.from_pretrained(model_name)

ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")
results = ner_pipeline("Elon Musk founded SpaceX in Hawthorne, California")
# [{'entity_group': 'PER', 'word': 'Elon Musk', 'score': 0.99},
#  {'entity_group': 'ORG', 'word': 'SpaceX', 'score': 0.99},
#  {'entity_group': 'LOC', 'word': 'Hawthorne, California', 'score': 0.98}]
```

### Question Answering

```python
from transformers import pipeline

qa_pipeline = pipeline("question-answering", model="deepset/bert-base-cased-squad2")

context = """
BERT was developed by Google AI Language team. It was published in 2018.
The model achieved state-of-the-art results on 11 NLP tasks.
"""

answer = qa_pipeline(question="Who developed BERT?", context=context)
# {'answer': 'Google AI Language team', 'score': 0.97, 'start': 22, 'end': 45}

# Architecture: predict start and end token positions
# P(start=i) = softmax(S · h_i)  where S is learned start vector
# P(end=j)   = softmax(E · h_j)  where E is learned end vector
# Answer span = argmax_{i,j where j>=i} P(start=i) * P(end=j)
```

---

## 4. BERT Variants

### Comparison Table

| Model | Key Change | Parameters | Speed | Performance |
|-------|-----------|------------|-------|-------------|
| BERT-base | Original | 110M | 1× | Baseline |
| RoBERTa | No NSP, more data, longer training | 125M | 1× | +2-3% |
| ALBERT | Factorized embeddings, shared params | 12M | 1.7× | Similar |
| DistilBERT | Knowledge distillation, 6 layers | 66M | 1.6× | 97% of BERT |
| DeBERTa | Disentangled attention + enhanced mask | 140M | 0.9× | SOTA |
| ELECTRA | Replaced token detection (not MLM) | 110M | 1× | Better sample efficiency |

### RoBERTa Improvements

```
1. Remove NSP task
2. Train longer with more data (160GB vs 16GB)
3. Larger batch sizes (8k)
4. Dynamic masking (different mask each epoch vs static)
5. Full sentences without NSP
```

### DistilBERT (Knowledge Distillation)

```
Teacher (BERT-base, 12 layers) → Student (DistilBERT, 6 layers)

Distillation Loss = α * CE(student_logits, hard_labels)
                  + β * KL(student_soft, teacher_soft)
                  + γ * cosine(student_hidden, teacher_hidden)

Result: 40% smaller, 60% faster, retains 97% performance
```

### DeBERTa Key Ideas

```
1. Disentangled Attention: separate content and position embeddings
   Attention(i,j) = Content_i·Content_j + Content_i·Position_j + Position_i·Content_j
   (BERT combines them: (content+position)·(content+position))

2. Enhanced Mask Decoder: add absolute position info in decoding layer
```

---

## 5. Sentence-BERT (SBERT)

```
Problem: BERT for sentence similarity requires O(n²) comparisons
         (feed every pair through BERT)

SBERT Solution: encode each sentence independently → compare embeddings
         Only O(n) BERT passes needed

Architecture:
  ┌─────────┐     ┌─────────┐
  │ BERT    │     │ BERT    │     (shared weights)
  │ + Pool  │     │ + Pool  │
  └────┬────┘     └────┬────┘
       │                │
       u                v
       └───── cos(u,v) ─┘

Training: contrastive learning on NLI datasets (SNLI, MNLI)
  - Positive: entailment pairs
  - Negative: contradiction pairs
```

```python
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

# Encode sentences
sentences = [
    "How do I reset my password?",
    "I forgot my login credentials",
    "What's the weather today?"
]
embeddings = model.encode(sentences)

# Compute pairwise similarity
cos_sim = util.cos_sim(embeddings, embeddings)
print(cos_sim)
# [[1.00, 0.78, 0.12],   ← sentences 0 and 1 are similar
#  [0.78, 1.00, 0.09],
#  [0.12, 0.09, 1.00]]
```

---

## 6. Multi-lingual Models

### mBERT (Multilingual BERT)

```
- Trained on Wikipedia in 104 languages
- Shared WordPiece vocabulary (110k tokens)
- Surprisingly good zero-shot cross-lingual transfer
  (fine-tune on English → works on other languages)
```

### XLM-RoBERTa

```python
from transformers import pipeline

# Cross-lingual sentiment analysis
classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

texts = [
    "This product is amazing!",          # English
    "Ce produit est incroyable!",         # French
    "Dieses Produkt ist erstaunlich!",    # German
]

for text in texts:
    result = classifier(text)
    print(f"{text[:30]:30} → {result[0]['label']}")
```

---

## 7. When to Use BERT vs GPT vs T5

```
┌────────────────────────────────────────────────────────────────┐
│ Model  │ Architecture │ Best For              │ Examples        │
├────────────────────────────────────────────────────────────────┤
│ BERT   │ Encoder only │ Understanding tasks   │ Classification,│
│        │ Bidirectional│ (classification, NER, │ NER, QA, sim.  │
│        │              │  QA, similarity)      │                │
├────────────────────────────────────────────────────────────────┤
│ GPT    │ Decoder only │ Generation tasks      │ Text gen, code,│
│        │ Left-to-right│ (text gen, dialogue,  │ chat, few-shot │
│        │              │  in-context learning) │                │
├────────────────────────────────────────────────────────────────┤
│ T5     │ Enc-Decoder  │ Seq2Seq tasks         │ Translation,   │
│        │ Text-to-text │ (all tasks as text)   │ summarization, │
│        │              │                       │ QA, classify   │
└────────────────────────────────────────────────────────────────┘

Decision Guide:
  - Need to classify/extract? → BERT/RoBERTa
  - Need to generate text? → GPT/LLaMA
  - Need to transform text? → T5/BART
  - Need sentence embeddings? → SBERT
  - Need multilingual? → XLM-R
  - Need efficiency? → DistilBERT/ALBERT
```

---

## 8. Fine-tuning Best Practices

```python
# Key hyperparameters for BERT fine-tuning
config = {
    "learning_rate": 2e-5,      # Much smaller than training from scratch
    "batch_size": 16,           # or 32
    "epochs": 3,                # 2-4 typically sufficient
    "max_seq_length": 512,      # or 128/256 if shorter texts
    "warmup_ratio": 0.1,        # Linear warmup
    "weight_decay": 0.01,       # L2 regularization
    "scheduler": "linear",      # Linear decay after warmup
}

# Common mistakes:
# 1. Learning rate too high (destroys pre-trained weights)
# 2. Too many epochs (overfitting on small datasets)
# 3. Not using warmup (training instability)
# 4. Ignoring class imbalance (use weighted loss)
```

### Layer-wise Learning Rate Decay

```python
# Lower layers learn general features → smaller LR
# Upper layers learn task-specific → larger LR
def get_optimizer_grouped_parameters(model, base_lr=2e-5, decay=0.95):
    params = []
    for i, layer in enumerate(model.bert.encoder.layer):
        lr = base_lr * (decay ** (11 - i))  # Layer 0 gets smallest LR
        params.append({'params': layer.parameters(), 'lr': lr})
    params.append({'params': model.classifier.parameters(), 'lr': base_lr})
    return params
```

---

## 9. Practical Patterns

### Feature Extraction (Frozen BERT)

```python
# Use BERT as fixed feature extractor (faster, less memory)
from transformers import BertModel
import torch

model = BertModel.from_pretrained('bert-base-uncased')
model.eval()

# Freeze all parameters
for param in model.parameters():
    param.requires_grad = False

# Extract features
with torch.no_grad():
    outputs = model(**inputs)
    features = outputs.last_hidden_state  # Use as input to your own model
```

### Gradual Unfreezing

```python
# Unfreeze layers progressively during training
# Epoch 1: Only classifier
# Epoch 2: + last 2 BERT layers
# Epoch 3: + last 4 BERT layers
# ...

def unfreeze_layers(model, num_layers):
    # Freeze all
    for param in model.bert.parameters():
        param.requires_grad = False
    # Unfreeze top num_layers
    for layer in model.bert.encoder.layer[-num_layers:]:
        for param in layer.parameters():
            param.requires_grad = True
```

---

## 10. BERT Limitations and Solutions

| Limitation | Solution |
|-----------|----------|
| Max 512 tokens | Longformer, BigBird (sparse attention) |
| Slow inference | DistilBERT, quantization, ONNX |
| English-only (base) | mBERT, XLM-R |
| Not for generation | Use GPT/T5 instead |
| Large model size | Pruning, quantization, ALBERT |
| Expensive fine-tuning | Adapters, LoRA, prompt tuning |

### Parameter-Efficient Fine-tuning (PEFT)

```python
from peft import get_peft_model, LoraConfig, TaskType

# LoRA: only train low-rank adaptation matrices
peft_config = LoraConfig(
    task_type=TaskType.SEQ_CLS,
    r=8,                    # rank of adaptation
    lora_alpha=32,
    lora_dropout=0.1,
    target_modules=["query", "value"]  # which attention matrices to adapt
)

model = get_peft_model(base_model, peft_config)
# Trainable params: ~0.5% of total (vs 100% for full fine-tuning)
```

---

## Production Considerations

- **Quantization**: INT8 reduces model size 4× with minimal quality loss
- **ONNX Runtime**: 2-3× inference speedup over PyTorch
- **Batching**: Dynamic batching for throughput; padding to longest in batch
- **Caching**: Cache tokenizer outputs for repeated queries
- **Model selection**: Start with DistilBERT; upgrade to RoBERTa only if needed
- **Monitoring**: Track prediction confidence; flag low-confidence outputs

---

## Exercises

1. Fine-tune BERT on IMDb sentiment classification and compare with DistilBERT
2. Implement a multi-label classifier with BERT for topic classification
3. Build a semantic search system using SBERT embeddings
4. Compare zero-shot cross-lingual transfer of mBERT vs XLM-R on a non-English dataset
5. Apply LoRA fine-tuning and compare training time/memory vs full fine-tuning

## Interview Questions

1. **Why is BERT bidirectional and why does that matter?**
   - Uses masked LM (not autoregressive) so each token attends to both left and right context; critical for understanding tasks where full context needed

2. **Why was NSP removed in RoBERTa?**
   - Empirically didn't help; model learns inter-sentence reasoning from MLM alone; NSP training signal too easy

3. **How does DistilBERT achieve 97% of BERT's performance with 40% fewer parameters?**
   - Knowledge distillation (soft targets from teacher), 6 layers instead of 12, triple loss (distillation + MLM + cosine)

4. **When would you choose feature extraction over fine-tuning?**
   - Very small dataset (avoid overfitting), need fast iteration, limited compute, multiple downstream tasks from same features

5. **Explain the cold-start problem with BERT fine-tuning and how warmup helps.**
   - Initial random classifier head creates large gradients that damage pre-trained weights; warmup uses tiny LR initially, allowing head to stabilize before full learning rate
