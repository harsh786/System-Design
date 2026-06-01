# Jupyter Ecosystem Mastery

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Jupyter Ecosystem                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │Jupyter Notebook │    │   JupyterLab    │                   │
│  │ (Classic, simple)    │ (Full IDE-like) │                   │
│  └─────────────────┘    └─────────────────┘                   │
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌───────────────┐     │
│  │IPython  │ │Nbconvert│ │Papermill │ │  Voila        │     │
│  │(Kernel) │ │(Export) │ │(Params)  │ │ (Dashboards)  │     │
│  └─────────┘ └─────────┘ └──────────┘ └───────────────┘     │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Collaborative: Google Colab │ Kaggle │ Databricks      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Jupyter Notebook vs JupyterLab

| Feature | Notebook | JupyterLab |
|---------|----------|------------|
| Interface | Single document | Multi-tab IDE |
| File browser | Basic | Full sidebar |
| Terminal | No | Yes |
| Extensions | nbextensions | Lab extensions |
| Drag & drop | No | Yes |
| Code console | No | Yes |
| **Recommendation** | Legacy | **Use this** |

```bash
# Installation
pip install jupyterlab notebook ipywidgets

# Launch
jupyter lab          # JupyterLab (recommended)
jupyter notebook     # Classic notebook

# With specific port/no browser
jupyter lab --port 8888 --no-browser

# Remote access
jupyter lab --ip 0.0.0.0 --port 8888 --no-browser --allow-root
```

## Magic Commands

```python
# ============================================================
# LINE MAGICS (% prefix)
# ============================================================

%timeit x = [i**2 for i in range(1000)]    # Time single statement
%time model.fit(X, y)                        # Time once (wall + CPU)
%who                                         # List variables
%whos                                        # Detailed variable info
%pwd                                         # Current directory
%cd /path/to/dir                            # Change directory
%env MY_VAR=value                           # Set environment variable
%load_ext autoreload                        # Load extension
%autoreload 2                               # Auto-reload modules before execution
%matplotlib inline                          # Inline plots
%pip install package                        # Install from notebook
%debug                                      # Post-mortem debugging
%prun function_call()                       # Profile function
%lprun -f my_func my_func()                 # Line profiler (needs line_profiler)
%memit x = [i for i in range(1000000)]      # Memory usage (needs memory_profiler)

# ============================================================
# CELL MAGICS (%% prefix)
# ============================================================

%%time
# Times entire cell
model.fit(X_train, y_train)
predictions = model.predict(X_test)

%%timeit
# Benchmark cell (multiple runs)
result = expensive_operation()

%%writefile script.py
# Writes cell content to file
import pandas as pd
def process():
    pass

%%bash
echo "Run shell commands"
ls -la

%%html
<h1 style="color: blue;">Custom HTML</h1>

%%javascript
alert("Hello from JS");

%%capture output
# Capture cell output (suppress display)
verbose_function()
# Access later: output.stdout, output.stderr

# SQL magic (with ipython-sql)
%load_ext sql
%sql sqlite:///database.db
%%sql
SELECT * FROM users LIMIT 10;
```

## Extensions and Widgets

```python
# ============================================================
# IPYWIDGETS - Interactive Controls
# ============================================================
import ipywidgets as widgets
from IPython.display import display

# Interactive function
from ipywidgets import interact, interactive

@interact(
    n_estimators=(10, 500, 10),
    max_depth=(1, 30, 1),
    criterion=['gini', 'entropy']
)
def train_and_evaluate(n_estimators=100, max_depth=10, criterion='gini'):
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        criterion=criterion
    )
    scores = cross_val_score(model, X, y, cv=5)
    print(f"Accuracy: {scores.mean():.4f} (+/- {scores.std():.4f})")

# Progress bar
from tqdm.notebook import tqdm

for epoch in tqdm(range(100), desc="Training"):
    train_one_epoch()

# Custom widget layout
slider = widgets.FloatSlider(value=0.01, min=0.001, max=0.1, step=0.001,
                             description='Learning Rate:')
dropdown = widgets.Dropdown(options=['adam', 'sgd', 'rmsprop'],
                           description='Optimizer:')
button = widgets.Button(description='Train Model')

output = widgets.Output()

def on_button_click(b):
    with output:
        output.clear_output()
        print(f"Training with lr={slider.value}, opt={dropdown.value}")

button.on_click(on_button_click)
display(widgets.VBox([slider, dropdown, button, output]))
```

### JupyterLab Extensions

```bash
# Essential extensions
pip install jupyterlab-git              # Git integration
pip install jupyterlab_code_formatter   # Code formatting (black, isort)
pip install jupyterlab-lsp              # Language server (autocomplete)
pip install jupyterlab-execute-time     # Cell execution time
pip install jupyterlab-system-monitor   # CPU/RAM monitor
```

## Nbconvert and Presentation

```bash
# Convert to various formats
jupyter nbconvert --to html notebook.ipynb
jupyter nbconvert --to pdf notebook.ipynb        # Requires LaTeX
jupyter nbconvert --to slides notebook.ipynb     # Reveal.js slides
jupyter nbconvert --to script notebook.ipynb     # .py file
jupyter nbconvert --to markdown notebook.ipynb

# Execute and convert (run all cells)
jupyter nbconvert --execute --to html notebook.ipynb

# Slides with live code
jupyter nbconvert --to slides --post serve notebook.ipynb

# Hide code cells in output
jupyter nbconvert --to html --no-input notebook.ipynb

# Custom template
jupyter nbconvert --to html --template classic notebook.ipynb
```

### Slide Types (in cell metadata)

```json
{
  "slideshow": {
    "slide_type": "slide"      // New slide
                  "subslide"   // Vertical sub-slide
                  "fragment"   // Appears on click
                  "skip"       // Hidden
                  "notes"      // Speaker notes
  }
}
```

## Papermill for Parameterized Notebooks

```python
# ============================================================
# PAPERMILL: Run notebooks with different parameters
# ============================================================

# In your notebook, tag a cell as "parameters":
# (Add tag "parameters" to cell metadata)

# parameters
dataset_path = "data/train.csv"
learning_rate = 0.001
n_estimators = 100
experiment_name = "baseline"
```

```python
# Execute programmatically
import papermill as pm

# Run with different parameters
pm.execute_notebook(
    'template_notebook.ipynb',        # Input
    'output/experiment_lr001.ipynb',  # Output
    parameters={
        'dataset_path': 'data/train.csv',
        'learning_rate': 0.001,
        'n_estimators': 200,
        'experiment_name': 'lr_001'
    }
)

# Batch execution for hyperparameter sweep
from itertools import product

learning_rates = [0.001, 0.01, 0.1]
estimators = [100, 200, 500]

for lr, n_est in product(learning_rates, estimators):
    pm.execute_notebook(
        'train_template.ipynb',
        f'results/experiment_lr{lr}_est{n_est}.ipynb',
        parameters={'learning_rate': lr, 'n_estimators': n_est}
    )
```

```bash
# CLI usage
papermill input.ipynb output.ipynb -p learning_rate 0.01 -p epochs 50

# With YAML parameters file
papermill input.ipynb output.ipynb -f params.yaml
```

## Best Practices for Reproducible Notebooks

### Structure

```
┌──────────────────────────────────────┐
│ Notebook Structure (Top to Bottom)   │
├──────────────────────────────────────┤
│ 1. Title + Description (Markdown)    │
│ 2. Imports (ALL in first code cell)  │
│ 3. Configuration / Parameters        │
│ 4. Data Loading                      │
│ 5. EDA                               │
│ 6. Preprocessing                     │
│ 7. Modeling                          │
│ 8. Evaluation                        │
│ 9. Conclusions (Markdown)            │
└──────────────────────────────────────┘
```

### Rules

```python
# 1. Pin all dependencies
# requirements.txt or first cell:
# !pip install scikit-learn==1.3.0 pandas==2.1.0

# 2. Set random seeds early
import numpy as np
import random
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# 3. Use relative paths
from pathlib import Path
DATA_DIR = Path("../data")
OUTPUT_DIR = Path("../output")

# 4. Restart and run all before sharing
# Kernel → Restart & Run All

# 5. Don't modify data in place across cells
# BAD: df.drop(columns=['col'], inplace=True) spread across cells
# GOOD: Build transformations in functions

# 6. Keep cells short and focused
# Each cell should do ONE thing

# 7. Use functions for repeated operations
def plot_distribution(df, column, ax=None):
    """Reusable plotting function."""
    if ax is None:
        fig, ax = plt.subplots()
    df[column].hist(ax=ax, bins=30)
    ax.set_title(f'Distribution of {column}')
    return ax

# 8. Document assumptions and decisions in markdown cells
```

## Version Control for Notebooks

```bash
# Problem: Notebooks contain output (images, data) → huge diffs

# Solution 1: nbstripout (auto-strip output on commit)
pip install nbstripout
nbstripout --install  # Adds git filter

# Solution 2: .gitattributes
echo "*.ipynb filter=nbstripout" >> .gitattributes

# Solution 3: jupytext (pair with .py file)
pip install jupytext

# Configure in jupyter_notebook_config.py or jupytext.toml:
# [jupytext.toml]
# formats = "ipynb,py:percent"

# This creates notebook.ipynb AND notebook.py
# Version control the .py file, .ipynb in .gitignore
```

```python
# jupytext usage
import jupytext

# Convert notebook to script
jupytext --to py:percent notebook.ipynb

# Sync paired files
jupytext --sync notebook.ipynb

# The .py file uses "percent" format:
# %% [markdown]
# # Title
# %% 
# import pandas as pd
# %%
# df = pd.read_csv('data.csv')
```

### .gitignore for notebooks

```gitignore
# Ignore notebook checkpoints
.ipynb_checkpoints/

# Ignore output notebooks (papermill)
output/*.ipynb

# If using jupytext, ignore .ipynb
# *.ipynb
```

## Collaborative Tools

### Google Colab

```python
# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Upload files
from google.colab import files
uploaded = files.upload()

# Download files
files.download('model.h5')

# Install packages
!pip install -q transformers

# GPU info
!nvidia-smi

# Use secrets (Colab secrets feature)
from google.colab import userdata
api_key = userdata.get('OPENAI_API_KEY')

# Form fields (interactive parameters)
#@title Model Configuration
learning_rate = 0.001  #@param {type:"number"}
model_type = "resnet50"  #@param ["resnet50", "vgg16", "efficientnet"]
use_augmentation = True  #@param {type:"boolean"}
```

### Kaggle Notebooks

```python
# Access Kaggle datasets
import kaggle
# Data is at /kaggle/input/dataset-name/

# Use Kaggle secrets
from kaggle_secrets import UserSecretsClient
secrets = UserSecretsClient()
api_key = secrets.get_secret("my_api_key")

# GPU: Settings → Accelerator → GPU T4 x2
# TPU: Settings → Accelerator → TPU v3-8
```

## Integration with MLflow/W&B

### MLflow

```python
import mlflow
import mlflow.sklearn

# Set experiment
mlflow.set_experiment("my_experiment")

# Auto-logging
mlflow.sklearn.autolog()
model.fit(X_train, y_train)

# Manual logging
with mlflow.start_run(run_name="experiment_v1"):
    mlflow.log_params({
        'n_estimators': 100,
        'max_depth': 10,
        'learning_rate': 0.01
    })
    
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    
    mlflow.log_metrics({
        'accuracy': accuracy_score(y_test, predictions),
        'f1': f1_score(y_test, predictions, average='macro')
    })
    
    # Log model
    mlflow.sklearn.log_model(model, "model")
    
    # Log artifacts (plots, data)
    mlflow.log_artifact('confusion_matrix.png')

# MLflow UI
# !mlflow ui --port 5000
```

### Weights & Biases (W&B)

```python
import wandb

wandb.init(
    project="my-project",
    config={
        "learning_rate": 0.001,
        "architecture": "ResNet50",
        "epochs": 100,
    }
)

# Log metrics during training
for epoch in range(100):
    train_loss = train_one_epoch()
    val_loss = validate()
    wandb.log({
        "epoch": epoch,
        "train_loss": train_loss,
        "val_loss": val_loss,
    })

# Log images, tables, plots
wandb.log({"predictions": wandb.Image(fig)})
wandb.log({"pr_curve": wandb.plot.pr_curve(y_true, y_scores)})

# Finish
wandb.finish()
```

## Notebook to Production Pipeline

```
Development Flow:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Notebook   │───▶│   Scripts    │───▶│  Production  │
│  (Explore)   │    │ (Refactor)   │    │  (Deploy)    │
└──────────────┘    └──────────────┘    └──────────────┘
     EDA               src/                Docker/K8s
     Prototype         tests/              CI/CD
     Visualize         config/             Monitoring
```

### Step 1: Refactor notebook to modules

```python
# src/data.py - Extract data loading
def load_data(path: str) -> pd.DataFrame:
    """Load and validate dataset."""
    df = pd.read_csv(path)
    assert not df.empty, "Dataset is empty"
    return df

# src/features.py - Extract feature engineering
def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature engineering pipeline."""
    df = df.copy()
    df['age_bucket'] = pd.cut(df['age'], bins=[0, 25, 45, 65, 100])
    return df

# src/model.py - Extract model training
def train_model(X, y, config):
    """Train model with given config."""
    pipeline = Pipeline([...])
    pipeline.fit(X, y)
    return pipeline

# src/evaluate.py - Extract evaluation
def evaluate_model(model, X_test, y_test):
    """Compute all metrics."""
    predictions = model.predict(X_test)
    return {
        'accuracy': accuracy_score(y_test, predictions),
        'f1': f1_score(y_test, predictions, average='macro')
    }
```

### Step 2: Create entry point

```python
# train.py
import argparse
from src.data import load_data
from src.features import create_features
from src.model import train_model
from src.evaluate import evaluate_model

def main(args):
    df = load_data(args.data_path)
    df = create_features(df)
    X_train, X_test, y_train, y_test = split(df)
    model = train_model(X_train, y_train, vars(args))
    metrics = evaluate_model(model, X_test, y_test)
    save_model(model, args.output_path)
    print(metrics)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', required=True)
    parser.add_argument('--output-path', default='model.joblib')
    parser.add_argument('--learning-rate', type=float, default=0.01)
    main(parser.parse_args())
```

### Step 3: Containerize

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY train.py .
ENTRYPOINT ["python", "train.py"]
```

## Anti-Patterns

```
DON'T:
- Run cells out of order and rely on hidden state
- Use absolute paths (/Users/me/data/...)
- Leave credentials in cells
- Commit notebooks with large outputs
- Use notebooks as production code
- Have 100+ cells in one notebook
- Import inside loops or deep in notebook

DO:
- Restart & Run All before sharing
- Use relative paths and config files
- Use environment variables for secrets
- Strip output or use jupytext
- Refactor to .py modules for production
- Split into focused notebooks (EDA, training, evaluation)
- All imports at the top
```
