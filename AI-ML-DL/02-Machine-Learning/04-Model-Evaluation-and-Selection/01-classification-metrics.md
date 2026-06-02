# Classification Metrics

## Confusion Matrix

```
                    Predicted
                 Pos        Neg
Actual  Pos  [ TP=90  │  FN=10 ]   ← Type II Error (Miss)
        Neg  [ FP=20  │  TN=880]   ← Type I Error (False Alarm)
```

---

## Core Metrics

```
Accuracy  = (TP + TN) / (TP + TN + FP + FN) = (90+880)/1000 = 97%
Precision = TP / (TP + FP) = 90/110 = 81.8%   "Of predicted positive, how many correct?"
Recall    = TP / (TP + FN) = 90/100 = 90%      "Of actual positive, how many found?"
F1 Score  = 2·P·R / (P+R) = 85.7%              Harmonic mean of P and R
Specificity = TN / (TN + FP) = 880/900 = 97.8% "Of actual negative, how many correct?"

F-beta:   = (1+β²)·P·R / (β²·P + R)
  β=0.5 → weights precision more
  β=2   → weights recall more
```

### When Accuracy Fails

```
Dataset: 950 negative, 50 positive
Model predicts ALL negative:
  Accuracy = 950/1000 = 95%  ← Looks great!
  Recall = 0/50 = 0%         ← Actually useless!
  Precision = undefined

LESSON: Never use accuracy alone for imbalanced data.
```

---

## Precision-Recall Tradeoff

```
Lower threshold → More Positive predictions → Higher Recall, Lower Precision
Higher threshold → Fewer Positive predictions → Lower Recall, Higher Precision

There is NO free lunch: improving one hurts the other.
```

### Which Metric for Which Business Problem?

| Problem | Optimize | Why |
|---------|----------|-----|
| Spam filter | **Precision** | Don't lose important email (FP costly) |
| Cancer detection | **Recall** | Don't miss cancer (FN costly) |
| Fraud detection | **Recall** (with precision floor) | Don't miss fraud, but too many alerts = fatigue |
| Search ranking | **Precision@K** | Show relevant results at top |
| Content moderation | **Recall** | Don't let harmful content through |
| Customer churn | **F1 or F2** | Balance: don't miss churners, don't annoy loyal ones |

---

## ROC Curve and AUC

```
ROC: True Positive Rate (Recall) vs False Positive Rate at all thresholds

TPR (Recall)
    1│        ·····───────
     │      ··
     │    ··     ROC curve
     │   ·
     │  ·
     │ ·        Random (diagonal)
     │·       
    0│─────────────────── 
     0    FPR          1

AUC = Area Under ROC Curve
- AUC = 1.0: Perfect
- AUC = 0.5: Random
- AUC < 0.5: Worse than random (flip predictions)
```

### PR Curve

```
Precision-Recall curve: more informative for imbalanced data

Precision
    1│──╲
     │    ╲
     │      ╲────╲
     │            ╲
     │             ╲
    0└──────────────── Recall
     0                1

Baseline PR-AUC = positive class fraction (e.g., 0.01 for 1% positive)
```

### ROC-AUC vs PR-AUC: When to Use Which

| Scenario | Use | Why |
|----------|-----|-----|
| Balanced classes | ROC-AUC | Standard, well-understood |
| Rare positive class (<10%) | PR-AUC | ROC can be misleadingly optimistic |
| Care about both classes | ROC-AUC | Considers FPR and TPR |
| Care mainly about positives | PR-AUC | Directly measures positive class performance |

---

## Multi-Class Metrics

### Averaging Strategies

```
For K classes:

Macro-average: F1_macro = (1/K) Σ F1ₖ
  → Treats all classes equally (good when all classes matter)

Micro-average: Pool all TP/FP/FN globally, compute single F1
  → Dominated by majority class (= accuracy for multiclass)

Weighted-average: F1_weighted = Σ (nₖ/N) × F1ₖ
  → Accounts for class frequency
```

**Use macro** when all classes equally important (even rare ones).
**Use weighted** when majority class performance matters more.
**Use micro** when you want a single number equivalent to accuracy.

---

## Code for All Metrics

```python
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
    roc_auc_score, roc_curve, precision_recall_curve,
    average_precision_score
)

# Basic metrics
print(f"Accuracy:  {accuracy_score(y_true, y_pred):.4f}")
print(f"Precision: {precision_score(y_true, y_pred):.4f}")
print(f"Recall:    {recall_score(y_true, y_pred):.4f}")
print(f"F1:        {f1_score(y_true, y_pred):.4f}")

# Full report
print(classification_report(y_true, y_pred))

# Confusion matrix
cm = confusion_matrix(y_true, y_pred)
print(f"TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}")

# ROC-AUC (needs probabilities)
auc = roc_auc_score(y_true, y_proba)
fpr, tpr, thresholds = roc_curve(y_true, y_proba)

# PR-AUC
pr_auc = average_precision_score(y_true, y_proba)
precision, recall, thresholds = precision_recall_curve(y_true, y_proba)

# Multi-class
f1_macro = f1_score(y_true, y_pred, average='macro')
f1_weighted = f1_score(y_true, y_pred, average='weighted')
roc_auc_ovr = roc_auc_score(y_true, y_proba_multi, multi_class='ovr')
```

### From-Scratch Implementation

```python
class BinaryMetrics:
    def __init__(self, y_true, y_pred):
        self.tp = np.sum((y_true == 1) & (y_pred == 1))
        self.fp = np.sum((y_true == 0) & (y_pred == 1))
        self.fn = np.sum((y_true == 1) & (y_pred == 0))
        self.tn = np.sum((y_true == 0) & (y_pred == 0))
    
    def precision(self): return self.tp / (self.tp + self.fp + 1e-10)
    def recall(self):    return self.tp / (self.tp + self.fn + 1e-10)
    def f1(self):
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r + 1e-10)
    def mcc(self):
        num = self.tp * self.tn - self.fp * self.fn
        den = np.sqrt((self.tp+self.fp)*(self.tp+self.fn)*(self.tn+self.fp)*(self.tn+self.fn))
        return num / (den + 1e-10)
```

---

## Matthews Correlation Coefficient (MCC)

Most balanced metric for binary classification, even with imbalanced classes:

```
MCC = (TP·TN - FP·FN) / √((TP+FP)(TP+FN)(TN+FP)(TN+FN))

Range: [-1, +1]
- MCC = +1: Perfect
- MCC = 0: Random
- MCC = -1: Completely wrong
```

**Use MCC when:** Imbalanced data AND you want a single balanced metric that accounts for all four quadrants of the confusion matrix.

---

## Common Mistakes

1. **Using accuracy on imbalanced data** — use F1, PR-AUC, or MCC instead
2. **Comparing AUC without confidence intervals** — always bootstrap or use DeLong test
3. **Optimizing threshold on test set** — find threshold on validation, apply to test
4. **Ignoring class-specific performance** — always check per-class metrics
5. **Using ROC-AUC with very imbalanced data** — PR-AUC is more informative

---

## Interview Questions

**Q: You have 99% accuracy but stakeholders are unhappy. What's wrong?**
Likely imbalanced classes (e.g., 99% negative). Model predicts majority class always. Look at recall for minority class, use F1 or PR-AUC.

**Q: When would you use F2 over F1?**
When recall matters more than precision (FN more costly than FP). F2 weights recall 2x more. Example: cancer screening — missing a case is worse than a false alarm.

**Q: How do you choose a classification threshold?**
1. Business cost: minimize C_FP × FP + C_FN × FN
2. Precision-recall curve: find point meeting minimum precision/recall requirement
3. F1-optimal threshold: maximize F1 on validation set
4. Youden's J: maximize TPR - FPR (point furthest from diagonal on ROC)
