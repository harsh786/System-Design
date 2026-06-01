# Text Preprocessing and Representations

## Overview

Text preprocessing transforms raw text into numerical representations suitable for ML models. This is the foundation of any NLP pipeline.

```
Raw Text → Cleaning → Tokenization → Normalization → Representation → Model
```

---

## 1. Text Cleaning

### Unicode Handling

```python
import unicodedata
import re

def normalize_unicode(text):
    """Normalize unicode to NFC form and remove control characters."""
    # NFC: canonical decomposition followed by canonical composition
    text = unicodedata.normalize('NFC', text)
    # Remove control characters
    text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C')
    return text

# Handle common issues
text = "café naïve résumé"  # accented characters
text_ascii = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
# Output: "cafe naive resume"
```

### HTML/URL/Email Removal

```python
import re

def clean_text(text):
    """Remove HTML tags, URLs, emails, and special patterns."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '[URL]', text)
    # Remove emails
    text = re.sub(r'\S+@\S+\.\S+', '[EMAIL]', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove special characters (keep alphanumeric and basic punctuation)
    text = re.sub(r'[^\w\s.,!?;:\'-]', '', text)
    return text

# Example
raw = "<p>Visit https://example.com or email me@test.com!</p>"
print(clean_text(raw))
# Output: "Visit [URL] or [EMAIL]!"
```

### Contraction Expansion

```python
CONTRACTIONS = {
    "won't": "will not", "can't": "cannot", "n't": " not",
    "'re": " are", "'s": " is", "'d": " would",
    "'ll": " will", "'ve": " have", "'m": " am"
}

def expand_contractions(text):
    for contraction, expansion in CONTRACTIONS.items():
        text = text.replace(contraction, expansion)
    return text
```

---

## 2. Tokenization

### Word Tokenization

```python
import nltk
from nltk.tokenize import word_tokenize, TreebankWordTokenizer

text = "Dr. Smith's car isn't worth $1,000.50 in N.Y."

# NLTK
tokens = word_tokenize(text)
# ['Dr.', 'Smith', "'s", 'car', "is", "n't", 'worth', '$', '1,000.50', 'in', 'N.Y', '.']

# Simple whitespace (naive)
tokens_simple = text.split()
# Loses punctuation handling
```

### Subword Tokenization (BPE)

```
Byte-Pair Encoding Algorithm:
1. Start with character-level vocabulary
2. Count all adjacent pairs
3. Merge most frequent pair into new token
4. Repeat until vocabulary size reached

Example: "lowest" → ["low", "est"]  (if "low" and "est" are learned merges)
         "lower" → ["low", "er"]
```

```python
from tokenizers import Tokenizer, models, trainers, pre_tokenizers

# Train BPE tokenizer
tokenizer = Tokenizer(models.BPE())
tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
trainer = trainers.BpeTrainer(vocab_size=30000, special_tokens=["[PAD]", "[UNK]", "[CLS]", "[SEP]"])
tokenizer.train(files=["corpus.txt"], trainer=trainer)

# Encode
output = tokenizer.encode("Tokenization is fascinating")
print(output.tokens)  # ['Token', 'ization', 'is', 'fasci', 'nating']
```

### WordPiece (used by BERT)

```python
from transformers import BertTokenizer

tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
tokens = tokenizer.tokenize("unbelievable")
# ['un', '##bel', '##ie', '##va', '##ble']
# '##' prefix means continuation of previous token
```

### SentencePiece (language-agnostic)

```python
import sentencepiece as spm

# Train
spm.SentencePieceTrainer.train(
    input='corpus.txt',
    model_prefix='sp_model',
    vocab_size=32000,
    model_type='unigram'  # or 'bpe'
)

# Use
sp = spm.SentencePieceProcessor(model_file='sp_model.model')
tokens = sp.encode("Hello world", out_type=str)
# ['▁Hello', '▁world']  # ▁ represents space
```

---

## 3. Stopword Removal, Stemming, Lemmatization

```python
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer

# Stopwords
stop_words = set(stopwords.words('english'))
tokens = ["the", "cats", "are", "running", "quickly"]
filtered = [w for w in tokens if w.lower() not in stop_words]
# ['cats', 'running', 'quickly']

# Stemming (crude, rule-based suffix stripping)
stemmer = PorterStemmer()
print(stemmer.stem("running"))   # "run"
print(stemmer.stem("studies"))   # "studi"  ← not a real word!
print(stemmer.stem("happiness")) # "happi"

# Lemmatization (dictionary-based, returns real words)
lemmatizer = WordNetLemmatizer()
print(lemmatizer.lemmatize("running", pos='v'))  # "run"
print(lemmatizer.lemmatize("studies", pos='n'))   # "study"
print(lemmatizer.lemmatize("better", pos='a'))    # "good"
```

### Comparison

| Method | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| Stemming | Fast | Lower (not real words) | Search indexing |
| Lemmatization | Slower | Higher (real words) | Text analysis, understanding |

---

## 4. N-grams and Language Models

```python
from collections import Counter
from nltk import ngrams

text = "the cat sat on the mat"
tokens = text.split()

# Generate n-grams
bigrams = list(ngrams(tokens, 2))
# [('the', 'cat'), ('cat', 'sat'), ('sat', 'on'), ('on', 'the'), ('the', 'mat')]

trigrams = list(ngrams(tokens, 3))
# [('the', 'cat', 'sat'), ('cat', 'sat', 'on'), ...]

# Simple bigram language model
def bigram_probability(corpus_tokens):
    """P(w_n | w_{n-1}) = count(w_{n-1}, w_n) / count(w_{n-1})"""
    bigram_counts = Counter(ngrams(corpus_tokens, 2))
    unigram_counts = Counter(corpus_tokens)
    
    probs = {}
    for (w1, w2), count in bigram_counts.items():
        probs[(w1, w2)] = count / unigram_counts[w1]
    return probs

# Perplexity: PP(W) = 2^{-1/N * sum(log2 P(w_i | context))}
# Lower perplexity = better model
```

---

## 5. Bag of Words (BoW)

```python
from sklearn.feature_extraction.text import CountVectorizer

corpus = [
    "the cat sat on the mat",
    "the dog sat on the log",
    "cats and dogs are friends"
]

vectorizer = CountVectorizer()
X = vectorizer.fit_transform(corpus)

print(vectorizer.get_feature_names_out())
# ['and', 'are', 'cat', 'cats', 'dog', 'dogs', 'friends', 'log', 'mat', 'on', 'sat', 'the']
print(X.toarray())
# [[0,0,1,0,0,0,0,0,1,1,1,2],
#  [0,0,0,0,1,0,0,1,0,1,1,2],
#  [1,1,0,1,0,1,1,0,0,0,0,0]]
```

**Limitations of BoW:**
- Loses word order ("dog bites man" = "man bites dog")
- High dimensionality (vocabulary size)
- Sparse representations
- No semantic meaning

---

## 6. TF-IDF (Term Frequency - Inverse Document Frequency)

```
TF(t, d) = count(t in d) / total_terms_in_d
IDF(t, D) = log(N / df(t))   where N = total docs, df(t) = docs containing t
TF-IDF(t, d, D) = TF(t, d) × IDF(t, D)
```

```python
from sklearn.feature_extraction.text import TfidfVectorizer

corpus = [
    "machine learning is great",
    "deep learning is a subset of machine learning",
    "natural language processing uses machine learning"
]

tfidf = TfidfVectorizer()
X = tfidf.fit_transform(corpus)

# Get feature importance for a document
feature_names = tfidf.get_feature_names_out()
doc_0_scores = dict(zip(feature_names, X.toarray()[0]))
sorted_scores = sorted(doc_0_scores.items(), key=lambda x: x[1], reverse=True)
# "great" will have high TF-IDF (unique to doc 0)
# "machine", "learning" will have lower TF-IDF (appear in all docs)
```

### TF-IDF Variants

| Variant | Formula | Use Case |
|---------|---------|----------|
| Sublinear TF | 1 + log(tf) | Reduces impact of high-frequency terms |
| Smooth IDF | log(1 + N/(1 + df)) | Avoids division by zero |
| BM25 | Complex saturation formula | Information retrieval (better than raw TF-IDF) |

---

## 7. Text Normalization for Different Languages

```python
# Chinese: needs word segmentation (no spaces)
import jieba
text_cn = "自然语言处理很有趣"
tokens_cn = list(jieba.cut(text_cn))
# ['自然语言', '处理', '很', '有趣']

# Japanese: multiple scripts (hiragana, katakana, kanji)
# Use MeCab or fugashi

# Arabic: right-to-left, morphologically rich
# Use CAMeL Tools or Farasa

# German: compound words need decomposition
# "Donaudampfschifffahrt" → "Donau" + "dampf" + "schiff" + "fahrt"
```

---

## 8. Regular Expressions for NLP

```python
import re

# Extract entities
text = "Call 555-1234 or email john@example.com by 2024-01-15"

phone = re.findall(r'\d{3}-\d{4}', text)      # ['555-1234']
email = re.findall(r'\S+@\S+\.\w+', text)     # ['john@example.com']
date = re.findall(r'\d{4}-\d{2}-\d{2}', text) # ['2024-01-15']

# Sentence splitting (handle abbreviations)
def split_sentences(text):
    """Split on period/question/exclamation followed by space and capital."""
    return re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

# Tokenize with regex
def regex_tokenize(text):
    """Match words, numbers, and punctuation separately."""
    return re.findall(r"\w+(?:'\w+)?|[^\w\s]", text)
```

---

## 9. Complete Preprocessing Pipeline

```python
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

class TextPreprocessor:
    def __init__(self, lowercase=True, remove_stopwords=True, lemmatize=True):
        self.lowercase = lowercase
        self.remove_stopwords = remove_stopwords
        self.lemmatize = lemmatize
        self.stop_words = set(stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()
    
    def preprocess(self, text):
        # Clean
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        
        if self.lowercase:
            text = text.lower()
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Remove stopwords
        if self.remove_stopwords:
            tokens = [t for t in tokens if t not in self.stop_words]
        
        # Lemmatize
        if self.lemmatize:
            tokens = [self.lemmatizer.lemmatize(t) for t in tokens]
        
        return tokens

# Usage
pp = TextPreprocessor()
result = pp.preprocess("The cats were running quickly towards the houses!")
# ['cat', 'running', 'quickly', 'towards', 'house']
```

---

## Production Considerations

- **Tokenizer consistency**: Use same tokenizer for training and inference
- **Language detection**: Route to appropriate pipeline (use `langdetect` or `fasttext`)
- **Encoding issues**: Always decode to UTF-8, handle BOM markers
- **Performance**: Use spaCy for production (C-optimized), NLTK for prototyping
- **Vocabulary management**: Handle OOV (out-of-vocabulary) tokens gracefully
- **Reproducibility**: Pin tokenizer versions (especially for subword tokenizers)

---

## Exercises

1. Build a preprocessing pipeline that handles mixed-language text (English + Spanish)
2. Implement BPE tokenization from scratch (without libraries)
3. Compare TF-IDF vectors for 3 documents and find the most similar pair
4. Write a regex-based tokenizer that correctly handles contractions, URLs, and emojis
5. Implement add-k smoothing for a bigram language model and compute perplexity

## Interview Questions

1. **Why is subword tokenization preferred over word-level for modern NLP?**
   - Handles OOV words, reduces vocabulary size, captures morphology, language-agnostic

2. **When would you NOT remove stopwords?**
   - Sentiment analysis ("not good"), question answering, machine translation, language modeling

3. **What's the difference between TF-IDF and BM25?**
   - BM25 adds term frequency saturation and document length normalization

4. **How does SentencePiece differ from BPE?**
   - Language-agnostic (treats input as raw bytes), doesn't require pre-tokenization

5. **What preprocessing would you skip for a transformer-based model?**
   - Stemming, lemmatization, stopword removal — the model learns these implicitly
