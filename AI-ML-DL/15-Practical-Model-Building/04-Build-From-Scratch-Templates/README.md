# Build-From-Scratch Templates

> Complete, runnable ML templates. Copy, modify, ship.

These templates are designed to be **copied and modified** for your specific problem.
Each one runs as-is with built-in datasets, then you swap in your own data.

---

## Available Templates

| Template | File | Dependencies | Use When |
|----------|------|-------------|----------|
| Image Classification | `template_image_classification.py` | torch, torchvision | Classifying images into categories |
| Tabular ML | `template_tabular.py` | numpy, pandas, sklearn | Structured data (CSV, databases) |
| Text Classification | `template_text_classification.py` | numpy, pandas, sklearn | Classifying text documents |

---

## How to Use These Templates

### Step 1: Run as-is
```bash
python template_tabular.py          # Works immediately with built-in data
python template_text_classification.py
python template_image_classification.py
```

### Step 2: Find the "MODIFY THIS" comments
Each template has clearly marked sections:
```python
# ========== MODIFY THIS: Your data loading ==========
# ========== MODIFY THIS: Your preprocessing ==========
# ========== MODIFY THIS: Your model config ==========
```

### Step 3: Swap in your data and adjust

---

## Which Template Should I Use?

```
What kind of data do you have?
│
├── Images (photos, scans, screenshots)
│   └── template_image_classification.py
│       Then consider: transfer learning (see ../05-Transfer-Learning-Cookbook/)
│
├── Tabular (CSV, spreadsheet, database rows)
│   └── template_tabular.py
│       Columns with numbers, categories, dates → this is your template
│
├── Text (documents, reviews, emails, tickets)
│   └── template_text_classification.py
│       For more accuracy: add BERT fine-tuning (optional section included)
│
├── Time series
│   └── Start with template_tabular.py + feature engineering
│       Add lag features, rolling stats, then use tree models
│
└── Multiple types (text + numbers, images + metadata)
    └── Start with the dominant type, add features from others
```

---

## Design Principles

1. **Runs immediately** — uses built-in/downloadable datasets
2. **Self-contained** — single file, no complex project structure needed
3. **Heavily commented** — explains WHY, not just what
4. **Graceful degradation** — handles missing optional dependencies
5. **Production patterns** — includes saving, loading, evaluation
6. **Modifiable** — clear markers for what to change

---

## After These Templates

Once you outgrow these templates:
- **Need more accuracy?** → See `../05-Transfer-Learning-Cookbook/`
- **Need to deploy?** → See `../06-Deployment-Patterns/` (coming soon)
- **Need to scale?** → See distributed training guides
- **Need experiment tracking?** → Add MLflow/W&B (2-3 lines of code)
