# Data Collection and Labeling

> "Data is the new oil, but like oil, it's useless if unrefined." — Every ML engineer ever

## 1. The Data Flywheel (Why Data > Algorithms)

### The 80/20 Rule of ML

```
Real ML Engineer's Time Allocation:
┌─────────────────────────────────────────────────────────┐
│ Data Collection & Cleaning          │ 40%               │
│ Data Labeling & Validation          │ 20%               │
│ Feature Engineering                 │ 15%               │
│ Model Training & Tuning             │ 15%               │
│ Deployment & Monitoring             │ 10%               │
└─────────────────────────────────────────────────────────┘
```

### More Data Usually Beats Better Algorithms

| Approach | Accuracy Gain | Cost | Time |
|----------|--------------|------|------|
| More training data (2x) | +2-5% | $$ | Days |
| Better labels (fix noise) | +3-8% | $ | Days |
| Better architecture | +1-3% | Free | Weeks |
| Hyperparameter tuning | +0.5-1% | $ | Hours |
| Ensembling | +1-2% | $$$ | Hours |

**Key insight**: Going from 10K to 100K clean examples almost always beats going from ResNet to a custom architecture.

### Data Quality > Data Quantity

```
10,000 clean labels > 100,000 noisy labels

Quality Issues That Kill Models:
- Label noise (wrong labels): Even 5% noise can drop accuracy 2-3%
- Systematic bias: Model learns the bias, not the task
- Distribution mismatch: Training ≠ Production data
- Stale data: World changes, model doesn't
```

### The Virtuous Data Cycle

```
┌─────────┐     ┌─────────────┐     ┌──────────┐     ┌──────────┐
│ Deploy  │────▶│ Collect New  │────▶│ Label &  │────▶│ Retrain  │
│ Model   │     │ Edge Cases   │     │ Clean    │     │ Improve  │
└─────────┘     └─────────────┘     └──────────┘     └──────────┘
     ▲                                                       │
     └───────────────────────────────────────────────────────┘
     
Key: Log predictions + user corrections → free labels!
```

**Companies that nail this cycle**: Tesla (dashcam data), Google (search clicks), Spotify (skip = bad recommendation).

---

## 2. Data Collection Strategies

### Web Scraping

```python
# Beautiful Soup - simple pages
import requests
from bs4 import BeautifulSoup

def scrape_articles(url_list, delay=1.0):
    """Respectful scraping with rate limiting."""
    import time
    articles = []
    for url in url_list:
        resp = requests.get(url, headers={'User-Agent': 'Research Bot 1.0'})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.find('article').get_text(strip=True)
            articles.append({'url': url, 'text': text})
        time.sleep(delay)  # Be respectful!
    return articles

# Selenium - JavaScript-rendered pages
from selenium import webdriver
from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
driver.get("https://example.com/dynamic-content")
elements = driver.find_elements(By.CLASS_NAME, "data-item")
```

**Ethical/Legal Checklist**:
- [ ] Check robots.txt before scraping
- [ ] Respect rate limits (add delays)
- [ ] Check Terms of Service
- [ ] Don't scrape PII without consent
- [ ] Consider if data is copyrighted
- [ ] Store provenance (where each record came from)

### APIs

```python
# Common data APIs for ML projects
apis = {
    "text": {
        "Reddit": "pushshift.io (historical), PRAW (real-time)",
        "Twitter/X": "Academic Research API (100M tweets/month)",
        "News": "NewsAPI, GDELT, Common Crawl",
        "Wikipedia": "Wikimedia API (structured knowledge)",
    },
    "images": {
        "Flickr": "Creative Commons images with tags",
        "Unsplash": "High-quality photos with metadata",
        "Google Open Images": "9M images, 600 classes",
    },
    "structured": {
        "World Bank": "Economic indicators",
        "Census": "Demographic data",
        "SEC EDGAR": "Financial filings",
    }
}
```

### Public Datasets

| Source | Best For | Size Range |
|--------|----------|------------|
| HuggingFace Datasets | NLP, any | 1K - 1B+ |
| Kaggle | Competitions, tabular | 1K - 100M |
| UCI ML Repository | Classic benchmarks | 100 - 100K |
| Google Dataset Search | Discovery | Varies |
| Government Open Data | Structured/tabular | 1K - 1B |
| Common Crawl | Web text | Petabytes |
| LAION | Images + captions | 5B+ |

### Synthetic Data Generation

```python
# When real data is scarce or sensitive
from sdv.tabular import GaussianCopula  # Synthetic Data Vault

# Learn distribution from real data
model = GaussianCopula()
model.fit(real_data)  # Learn statistical properties
synthetic_data = model.sample(num_rows=10000)

# For text: use LLMs to generate training data
prompt = """Generate 10 customer support tickets about billing issues.
Format: {"text": "...", "category": "billing", "sentiment": "negative"}"""

# For images: use diffusion models
# "A photo of a {defect_type} on a {product}" → training data for QA
```

**When to use synthetic data**:
- Privacy-sensitive domains (healthcare, finance)
- Rare events (fraud, equipment failure)
- New categories with zero examples
- Data augmentation for minority classes

### Active Learning

```python
# Label only the most informative samples
# Saves 50-80% of labeling cost!

def active_learning_loop(model, unlabeled_pool, budget=100):
    """Select most uncertain samples for labeling."""
    while budget > 0:
        # Get model predictions on unlabeled data
        probs = model.predict_proba(unlabeled_pool)
        
        # Uncertainty sampling: pick least confident
        uncertainty = 1 - probs.max(axis=1)
        top_indices = uncertainty.argsort()[-batch_size:]
        
        # Send to human labeler
        labels = human_label(unlabeled_pool[top_indices])
        
        # Add to training set and retrain
        training_set.add(unlabeled_pool[top_indices], labels)
        model.fit(training_set)
        
        budget -= batch_size
```

**Strategies ranked by effectiveness**:
1. **Uncertainty sampling** - label what model is least sure about
2. **Diversity sampling** - label diverse representatives of clusters
3. **Expected model change** - label what would change the model most
4. **Committee disagreement** - label where ensemble models disagree

### Crowdsourcing Platforms

| Platform | Best For | Cost/Label | Quality |
|----------|----------|-----------|---------|
| Amazon MTurk | Simple tasks, large scale | $0.01-0.50 | Variable |
| Scale AI | Production ML, complex | $0.10-5.00 | High |
| Labelbox | Custom workflows | Platform fee | High |
| Surge AI | NLP tasks | $0.05-2.00 | High |
| In-house team | Domain expertise | $$$$ | Highest |

---

## 3. Data Labeling

### Labeling Tools Comparison

| Tool | Type | Best For | Cost |
|------|------|----------|------|
| Label Studio | Open source | Any modality | Free |
| CVAT | Open source | Computer vision | Free |
| Prodigy | Commercial | NLP, active learning | $390+ |
| Labelbox | Platform | Enterprise, collaboration | $$$ |
| Doccano | Open source | Text annotation | Free |
| VGG Image Annotator | Open source | Image segmentation | Free |

### Writing Labeling Guidelines

```markdown
## Example: Sentiment Labeling Guide

### Task: Label customer reviews as Positive, Negative, or Neutral

### Decision Rules (in order of priority):
1. If overall recommendation is clear → use that
2. If mixed → go with the FINAL sentiment expressed
3. If purely factual with no opinion → Neutral

### Examples:
✅ "Great product but shipping was slow" → POSITIVE (overall positive)
✅ "It works fine, nothing special" → NEUTRAL (no strong opinion)
✅ "Started great but broke after a week" → NEGATIVE (final sentiment)

### Edge Cases:
- Sarcasm: Label the INTENDED meaning, not literal
- Questions: Usually NEUTRAL unless rhetorical complaint
- Comparisons: "Better than X but worse than Y" → context needed

### What NOT to do:
❌ Don't infer sentiment from product category
❌ Don't let your personal opinion influence labels
❌ Don't rush — take 5-10 seconds minimum per example
```

### Inter-Annotator Agreement

```python
from sklearn.metrics import cohen_kappa_score
import numpy as np

def measure_agreement(annotator1_labels, annotator2_labels):
    """Measure labeling consistency between annotators."""
    kappa = cohen_kappa_score(annotator1_labels, annotator2_labels)
    
    # Interpretation
    # < 0.20: Poor
    # 0.21 - 0.40: Fair
    # 0.41 - 0.60: Moderate
    # 0.61 - 0.80: Substantial
    # 0.81 - 1.00: Almost perfect
    
    print(f"Cohen's Kappa: {kappa:.3f}")
    
    # For multiple annotators, use Fleiss' Kappa
    # from statsmodels.stats.inter_rater import fleiss_kappa
    return kappa

# Target: Kappa > 0.7 before trusting labels for training
```

### Quality Control Strategies

```python
# 1. Gold Standard Questions (honeypots)
def insert_gold_questions(task_batch, gold_items, ratio=0.1):
    """Insert known-answer items to catch bad annotators."""
    n_gold = int(len(task_batch) * ratio)
    gold_sample = random.sample(gold_items, n_gold)
    mixed = task_batch + gold_sample
    random.shuffle(mixed)
    return mixed

# 2. Majority Voting
def majority_vote(annotations, min_agreement=0.6):
    """Take label agreed upon by majority of annotators."""
    from collections import Counter
    counts = Counter(annotations)
    top_label, top_count = counts.most_common(1)[0]
    agreement = top_count / len(annotations)
    if agreement >= min_agreement:
        return top_label, agreement
    return None, agreement  # Send for re-labeling

# 3. Annotator Scoring
def score_annotators(annotator_responses, gold_answers):
    """Track per-annotator accuracy on gold questions."""
    scores = {}
    for annotator_id, responses in annotator_responses.items():
        correct = sum(r == g for r, g in zip(responses, gold_answers))
        scores[annotator_id] = correct / len(gold_answers)
    # Remove annotators below threshold
    return {k: v for k, v in scores.items() if v > 0.85}
```

### Weak Supervision (Snorkel)

```python
# Programmatic labeling with labeling functions
from snorkel.labeling import labeling_function, LFApplier, LabelModel

SPAM = 1
NOT_SPAM = 0
ABSTAIN = -1

@labeling_function()
def lf_contains_buy(x):
    return SPAM if "buy now" in x.text.lower() else ABSTAIN

@labeling_function()
def lf_short_text(x):
    return NOT_SPAM if len(x.text) > 200 else ABSTAIN

@labeling_function()
def lf_has_url(x):
    return SPAM if "http" in x.text else ABSTAIN

@labeling_function()
def lf_keyword_list(x):
    spam_words = ["free", "winner", "click here", "limited time"]
    if any(w in x.text.lower() for w in spam_words):
        return SPAM
    return ABSTAIN

# Combine noisy labels into probabilistic labels
lfs = [lf_contains_buy, lf_short_text, lf_has_url, lf_keyword_list]
applier = LFApplier(lfs=lfs)
L_train = applier.apply(df_train)

label_model = LabelModel(cardinality=2)
label_model.fit(L_train)
probabilistic_labels = label_model.predict_proba(L_train)
```

### Zero-Shot Labeling with LLMs

```python
import openai

def llm_label_batch(texts, task_description, categories):
    """Use GPT to generate labels (verify with human spot-checks!)."""
    prompt = f"""Task: {task_description}
Categories: {categories}
    
Label each text. Return JSON array of labels.

Texts:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(texts))}"""
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0  # Deterministic
    )
    return parse_labels(response)

# Cost estimation for LLM labeling:
# GPT-4: ~$0.01-0.05 per label (depends on text length)
# GPT-3.5: ~$0.001-0.005 per label
# Human expert: ~$0.10-5.00 per label
# BUT: Always validate LLM labels on a sample!
```

### Cost Estimation by Task Type

| Task | Human Cost | LLM Cost | Time/Label |
|------|-----------|----------|------------|
| Binary classification | $0.02-0.10 | $0.001-0.01 | 5-10s |
| Multi-class (5-10) | $0.05-0.20 | $0.005-0.02 | 10-20s |
| Named Entity Recognition | $0.10-0.50 | $0.01-0.05 | 20-60s |
| Bounding boxes | $0.05-0.30 | N/A | 15-30s |
| Segmentation masks | $0.50-5.00 | N/A | 1-5 min |
| Translation | $0.05-0.20/word | $0.001/word | Varies |
| Conversational | $1.00-10.00 | $0.05-0.50 | 5-30 min |

---

## 4. Data Quality Assessment

### The Data Quality Framework

```python
import pandas as pd
import numpy as np

class DataQualityReport:
    def __init__(self, df):
        self.df = df
        self.issues = []
    
    def check_completeness(self):
        """Missing values analysis."""
        missing = self.df.isnull().sum()
        missing_pct = (missing / len(self.df)) * 100
        
        for col in self.df.columns:
            if missing_pct[col] > 5:
                self.issues.append({
                    'type': 'completeness',
                    'column': col,
                    'severity': 'high' if missing_pct[col] > 30 else 'medium',
                    'detail': f'{missing_pct[col]:.1f}% missing'
                })
        return missing_pct
    
    def check_duplicates(self):
        """Exact and near-duplicate detection."""
        exact_dupes = self.df.duplicated().sum()
        dupe_rate = exact_dupes / len(self.df)
        if dupe_rate > 0.01:
            self.issues.append({
                'type': 'duplicates',
                'severity': 'high' if dupe_rate > 0.1 else 'medium',
                'detail': f'{exact_dupes} exact duplicates ({dupe_rate:.1%})'
            })
        return exact_dupes
    
    def check_class_balance(self, target_col):
        """Class distribution analysis."""
        counts = self.df[target_col].value_counts()
        imbalance_ratio = counts.max() / counts.min()
        if imbalance_ratio > 10:
            self.issues.append({
                'type': 'class_imbalance',
                'severity': 'high',
                'detail': f'Imbalance ratio: {imbalance_ratio:.1f}:1'
            })
        return counts
    
    def check_outliers(self, numeric_cols=None):
        """IQR-based outlier detection."""
        if numeric_cols is None:
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        
        outlier_counts = {}
        for col in numeric_cols:
            Q1, Q3 = self.df[col].quantile([0.25, 0.75])
            IQR = Q3 - Q1
            outliers = ((self.df[col] < Q1 - 1.5*IQR) | 
                       (self.df[col] > Q3 + 1.5*IQR)).sum()
            if outliers / len(self.df) > 0.05:
                outlier_counts[col] = outliers
        return outlier_counts
    
    def generate_report(self):
        """Print summary report."""
        print("=" * 60)
        print("DATA QUALITY REPORT")
        print("=" * 60)
        print(f"Rows: {len(self.df):,} | Columns: {len(self.df.columns)}")
        print(f"Issues found: {len(self.issues)}")
        for issue in sorted(self.issues, key=lambda x: x['severity']):
            icon = "🔴" if issue['severity'] == 'high' else "🟡"
            print(f"  {icon} [{issue['type']}] {issue.get('column', '')} - {issue['detail']}")
```

### Quick Quality Checklist

- [ ] **Completeness**: No column has >30% missing values (or has clear strategy for handling)
- [ ] **No duplicates**: <1% exact duplicates
- [ ] **Class balance**: No worse than 10:1 (or using appropriate techniques)
- [ ] **Consistent types**: Each column has expected dtype
- [ ] **Valid ranges**: Numeric values within expected bounds
- [ ] **Temporal validity**: No future dates in historical data
- [ ] **Label accuracy**: Spot-check 100+ labels manually → >95% correct
- [ ] **Distribution match**: Training data resembles production data

---

## 5. Data Versioning and Management

### DVC (Data Version Control)

```bash
# Setup
pip install dvc
dvc init
dvc remote add -d storage s3://my-bucket/dvc-store

# Track data files
dvc add data/training_v1.csv
git add data/training_v1.csv.dvc data/.gitignore
git commit -m "Add training data v1"
dvc push

# Create new version
# ... modify data ...
dvc add data/training_v1.csv
git add data/training_v1.csv.dvc
git commit -m "Training data v2: added 5K samples"
dvc push

# Switch between versions
git checkout v1.0
dvc checkout
```

### Data Management Best Practices

```yaml
# data_catalog.yaml - Document every dataset
datasets:
  customer_reviews_v3:
    description: "Product reviews with sentiment labels"
    source: "Internal review system + Trustpilot API"
    size: "2.3M rows, 1.2GB"
    schema:
      - name: review_text
        type: string
        nullable: false
      - name: rating
        type: int
        range: [1, 5]
      - name: sentiment
        type: categorical
        values: [positive, negative, neutral]
        labeling_method: "weak supervision + human review"
    splits:
      train: 1.8M (78%)
      val: 230K (10%)
      test: 270K (12%)
    known_issues:
      - "Reviews before 2020 have inconsistent sentiment labels"
      - "Non-English reviews (~3%) not filtered"
    created: "2024-03-15"
    owner: "ml-team@company.com"
```

### Schema Validation

```python
import pandera as pa

# Define expected schema
schema = pa.DataFrameSchema({
    "user_id": pa.Column(int, nullable=False, unique=False),
    "text": pa.Column(str, pa.Check.str_length(min_value=1)),
    "label": pa.Column(str, pa.Check.isin(["pos", "neg", "neutral"])),
    "timestamp": pa.Column(pa.DateTime, nullable=False),
    "score": pa.Column(float, pa.Check.in_range(0, 1)),
})

# Validate data before training
validated_df = schema.validate(raw_df)  # Raises on failure
```

---

## 6. Legal and Ethical Considerations

### Decision Framework

```
Is this data legal and ethical to use?

1. SOURCE CHECK:
   ├── Public domain / CC0? → ✅ Use freely
   ├── Creative Commons (CC-BY, etc.)? → ✅ Follow license terms
   ├── Copyrighted? → ⚠️ Need license or fair use analysis
   └── Scraped from website? → Check ToS and robots.txt

2. PRIVACY CHECK:
   ├── Contains PII? → Must anonymize or get consent
   ├── Contains faces? → Need consent in EU/IL/etc.
   ├── Health data? → HIPAA compliance needed
   └── Children's data? → COPPA compliance needed

3. BIAS CHECK:
   ├── Representative of target population?
   ├── Historical biases that could be learned?
   └── Underrepresented groups in data?
```

### PII Detection and Anonymization

```python
import re

PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
}

def detect_pii(text):
    """Scan text for PII patterns."""
    found = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            found[pii_type] = matches
    return found

def anonymize(text):
    """Replace PII with placeholders."""
    for pii_type, pattern in PII_PATTERNS.items():
        text = re.sub(pattern, f'[{pii_type.upper()}_REDACTED]', text)
    return text
```

### GDPR Compliance Checklist

- [ ] **Lawful basis**: Have legal basis for processing (consent, legitimate interest, etc.)
- [ ] **Purpose limitation**: Data used only for stated purpose
- [ ] **Data minimization**: Collect only what's needed
- [ ] **Storage limitation**: Delete when no longer needed
- [ ] **Right to erasure**: Can remove individual's data on request
- [ ] **Data Protection Impact Assessment**: Completed for high-risk processing
- [ ] **Records of processing**: Documented what data is processed and why

---

## Quick Reference: Data Collection Decision Matrix

| Scenario | Best Approach | Cost | Timeline |
|----------|--------------|------|----------|
| Need 100K labeled images | Public dataset + fine-tune | $ | Days |
| Need domain-specific NLP data | Scrape + weak supervision | $$ | 1-2 weeks |
| Need sensitive/private data | Synthetic generation | $$ | 1-2 weeks |
| Have model, want to improve | Active learning from prod | $ | Ongoing |
| Need perfect labels, small set | Expert annotators | $$$ | 2-4 weeks |
| Need large labels, budget | Crowdsource + QC | $$ | 1-2 weeks |
| Zero labeled data, have LLM | Zero-shot LLM labeling + validate | $ | Days |

---

## Summary: The Data Practitioner's Creed

1. **Start with public data** — don't reinvent the wheel
2. **Measure label quality** — Kappa > 0.7 or don't trust it
3. **Version everything** — you will need to reproduce results
4. **Automate labeling where possible** — weak supervision + active learning
5. **Monitor data drift** — models rot when data changes
6. **Respect privacy and law** — it's not optional
7. **Document provenance** — future you will thank present you
