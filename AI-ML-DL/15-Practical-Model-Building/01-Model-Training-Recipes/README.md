# Model Training Recipes

> A cookbook of step-by-step recipes for training models across common task types.
> Not theory — pure actionable steps with exact hyperparameters and full code.

---

## Recipe 1: Image Classification

**Timeline:** 2-4 hours (pretrained), 1-2 days (from scratch)
**Hardware:** Single GPU (8GB+ VRAM), or CPU for small datasets (<5K images)

### Step 1: Data — ImageFolder Structure

```python
# Option A: ImageFolder (simplest)
# data/
#   train/
#     cat/  img001.jpg, img002.jpg ...
#     dog/  img001.jpg, img002.jpg ...
#   val/
#     cat/ ...
#     dog/ ...

from torchvision import datasets
from torch.utils.data import DataLoader

train_dataset = datasets.ImageFolder('data/train', transform=train_transform)
val_dataset = datasets.ImageFolder('data/val', transform=val_transform)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=4, pin_memory=True)
val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False, num_workers=4, pin_memory=True)

# Option B: CSV + image paths
import pandas as pd
from torch.utils.data import Dataset
from PIL import Image

class CSVImageDataset(Dataset):
    def __init__(self, csv_path, img_dir, transform=None):
        self.df = pd.read_csv(csv_path)
        self.img_dir = img_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img = Image.open(f"{self.img_dir}/{row['filename']}").convert('RGB')
        if self.transform:
            img = self.transform(img)
        return img, row['label']
```

### Step 2: Augmentations

```python
from torchvision import transforms

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])
```

### Step 3: Model — Pretrained ResNet50

```python
import torch
import torch.nn as nn
from torchvision import models

model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)

# Freeze backbone (optional, for small datasets)
for param in model.parameters():
    param.requires_grad = False

# Replace classifier
num_classes = 10
model.fc = nn.Sequential(
    nn.Dropout(0.3),
    nn.Linear(model.fc.in_features, num_classes)
)

# Unfreeze last few layers for fine-tuning
for param in model.layer4.parameters():
    param.requires_grad = True

model = model.cuda()
```

### Step 4-6: Loss, Optimizer, Scheduler

```python
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

optimizer = torch.optim.AdamW([
    {'params': model.layer4.parameters(), 'lr': 1e-4},  # backbone: lower LR
    {'params': model.fc.parameters(), 'lr': 1e-3},       # head: higher LR
], weight_decay=0.01)

scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=[1e-4, 1e-3],
    epochs=30, steps_per_epoch=len(train_loader)
)
```

### Step 7: Training Loop

```python
from tqdm import tqdm

best_val_loss = float('inf')
patience, patience_counter = 5, 0

for epoch in range(30):
    # Train
    model.train()
    train_loss = 0
    for images, labels in tqdm(train_loader):
        images, labels = images.cuda(), labels.cuda()
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        scheduler.step()
        train_loss += loss.item()

    # Validate
    model.eval()
    val_loss, correct, total = 0, 0, 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.cuda(), labels.cuda()
            outputs = model(images)
            val_loss += criterion(outputs, labels).item()
            correct += (outputs.argmax(1) == labels).sum().item()
            total += labels.size(0)

    val_loss /= len(val_loader)
    val_acc = correct / total
    print(f"Epoch {epoch}: train_loss={train_loss/len(train_loader):.4f}, val_loss={val_loss:.4f}, val_acc={val_acc:.4f}")

    # Early stopping
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), 'best_model.pth')
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= patience:
            print("Early stopping!")
            break
```

### Step 8: Evaluate

```python
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np

model.load_state_dict(torch.load('best_model.pth'))
model.eval()

all_preds, all_labels = [], []
with torch.no_grad():
    for images, labels in val_loader:
        outputs = model(images.cuda())
        all_preds.extend(outputs.argmax(1).cpu().numpy())
        all_labels.extend(labels.numpy())

print(classification_report(all_labels, all_preds, target_names=train_dataset.classes))
```

### Step 9: Export

```python
# ONNX export
model.eval()
dummy = torch.randn(1, 3, 224, 224).cuda()
torch.onnx.export(model, dummy, "model.onnx", input_names=['image'], output_names=['logits'])

# TorchScript
scripted = torch.jit.script(model)
scripted.save("model_scripted.pt")
```

### Common Mistakes
- Not using the SAME normalization at inference as training
- Forgetting to set model.eval() (affects BatchNorm and Dropout)
- Using too large a learning rate when fine-tuning (destroys pretrained weights)
- Not shuffling training data

### If It's Not Working
- Val accuracy stuck at random: check labels are correct, print a batch
- Training acc 100% but val acc low: reduce model capacity, add augmentation
- Loss stuck: try lr=1e-4, then 1e-5, verify data pipeline

---

## Recipe 2: Text Classification (Sentiment/Topic)

**Timeline:** 1-3 hours with pretrained transformers
**Hardware:** Single GPU (8GB+), can work on CPU for small datasets

### Step 1: Data

```python
import pandas as pd
from sklearn.model_selection import train_test_split

df = pd.read_csv('data.csv')  # columns: 'text', 'label'
print(f"Classes: {df['label'].value_counts()}")

train_df, val_df = train_test_split(df, test_size=0.2, stratify=df['label'], random_state=42)
```

### Step 2-3: Tokenize & Model

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from torch.utils.data import Dataset, DataLoader

model_name = "distilbert-base-uncased"  # Fast and good enough for most tasks
tokenizer = AutoTokenizer.from_pretrained(model_name)
num_labels = df['label'].nunique()
model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)

class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=128):
        self.encodings = tokenizer(texts.tolist(), truncation=True,
                                   padding='max_length', max_length=max_len,
                                   return_tensors='pt')
        self.labels = torch.tensor(labels.tolist())

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {k: v[idx] for k, v in self.encodings.items()}, self.labels[idx]

train_dataset = TextDataset(train_df['text'], train_df['label'], tokenizer)
val_dataset = TextDataset(val_df['text'], val_df['label'], tokenizer)

train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
```

### Step 4-7: Train with HuggingFace Trainer (recommended)

```python
from transformers import Trainer, TrainingArguments
from datasets import Dataset as HFDataset

# Convert to HuggingFace datasets format
def tokenize_fn(examples):
    return tokenizer(examples['text'], truncation=True, padding='max_length', max_length=128)

train_hf = HFDataset.from_pandas(train_df[['text', 'label']])
val_hf = HFDataset.from_pandas(val_df[['text', 'label']])
train_hf = train_hf.map(tokenize_fn, batched=True)
val_hf = val_hf.map(tokenize_fn, batched=True)

training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,               # Transformers overfit fast!
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    learning_rate=2e-5,               # Key: small LR for pretrained
    weight_decay=0.01,
    warmup_ratio=0.1,                 # 10% warmup
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    fp16=True,                        # Mixed precision
)

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    return {
        'f1': f1_score(labels, preds, average='weighted'),
        'precision': precision_score(labels, preds, average='weighted'),
        'recall': recall_score(labels, preds, average='weighted'),
    }

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_hf,
    eval_dataset=val_hf,
    compute_metrics=compute_metrics,
)

trainer.train()
```

### Step 8: Evaluate

```python
results = trainer.evaluate()
print(results)

# Detailed per-class metrics
predictions = trainer.predict(val_hf)
preds = predictions.predictions.argmax(-1)
print(classification_report(val_df['label'], preds))
```

### Common Mistakes
- Learning rate too high (>5e-5) destroys pretrained weights
- Training too many epochs (>5) causes severe overfitting
- Not using warmup — first steps can be unstable
- Tokenizing with wrong max_length (too short truncates, too long wastes memory)
- Forgetting to handle class imbalance (use class weights in loss)

### If It's Not Working
- F1 stuck at 0: check label encoding matches model output order
- Loss not decreasing: lr=2e-5 is standard; try 5e-5 or 1e-5
- OOM: reduce batch_size or max_length, enable gradient_checkpointing
- Overfitting after epoch 1: more dropout, fewer epochs, more data

---

## Recipe 3: Tabular Data (Regression/Classification)

**Timeline:** 2-6 hours including feature engineering
**Hardware:** CPU is fine for most tabular problems

### Step 1-2: Load & EDA

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv('data.csv')
print(df.info())
print(df.describe())
print(f"Missing values:\n{df.isnull().sum()}")
print(f"Target distribution:\n{df['target'].value_counts()}")

# Identify column types
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
print(f"Numeric: {len(numeric_cols)}, Categorical: {len(categorical_cols)}")

# Correlations
plt.figure(figsize=(12, 8))
sns.heatmap(df[numeric_cols].corr(), annot=True, cmap='coolwarm')
plt.savefig('correlations.png')
```

### Step 3: Preprocessing

```python
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer

# Split FIRST (avoid data leakage!)
X = df.drop('target', axis=1)
y = df['target']
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Numeric: impute + scale
num_imputer = SimpleImputer(strategy='median')
scaler = StandardScaler()
X_train[numeric_cols] = scaler.fit_transform(num_imputer.fit_transform(X_train[numeric_cols]))
X_val[numeric_cols] = scaler.transform(num_imputer.transform(X_val[numeric_cols]))

# Categorical: impute + encode
cat_imputer = SimpleImputer(strategy='most_frequent')
X_train[categorical_cols] = cat_imputer.fit_transform(X_train[categorical_cols])
X_val[categorical_cols] = cat_imputer.transform(X_val[categorical_cols])

# Label encode (for tree models) or one-hot (for linear models)
label_encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    X_train[col] = le.fit_transform(X_train[col].astype(str))
    X_val[col] = le.transform(X_val[col].astype(str))
    label_encoders[col] = le
```

### Step 4: Feature Engineering

```python
# Interaction features
for i, col1 in enumerate(numeric_cols[:5]):
    for col2 in numeric_cols[i+1:6]:
        X_train[f'{col1}_x_{col2}'] = X_train[col1] * X_train[col2]
        X_val[f'{col1}_x_{col2}'] = X_val[col1] * X_val[col2]

# Aggregation features (if grouping makes sense)
# X_train['category_mean_target'] = X_train.groupby('category')['feature'].transform('mean')

# Date features (if date columns exist)
# df['day_of_week'] = df['date'].dt.dayofweek
# df['month'] = df['date'].dt.month
# df['is_weekend'] = df['date'].dt.dayofweek >= 5
```

### Step 5-6: Model & Tuning

```python
import xgboost as xgb
from sklearn.model_selection import cross_val_score
import optuna

# Baseline
baseline_model = xgb.XGBClassifier(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric='logloss',
    early_stopping_rounds=50,
)

baseline_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)
print(f"Baseline score: {baseline_model.score(X_val, y_val):.4f}")

# Bayesian optimization with Optuna
def objective(trial):
    params = {
        'n_estimators': 1000,
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
    }
    model = xgb.XGBClassifier(**params, random_state=42, eval_metric='logloss',
                               early_stopping_rounds=50)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model.score(X_val, y_val)

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)
print(f"Best params: {study.best_params}")
print(f"Best score: {study.best_value:.4f}")
```

### Step 7-8: Evaluate & Ensemble

```python
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.ensemble import StackingClassifier, RandomForestClassifier
from lightgbm import LGBMClassifier

# Cross-validation
scores = cross_val_score(baseline_model, X_train, y_train, cv=5, scoring='accuracy')
print(f"CV Score: {scores.mean():.4f} ± {scores.std():.4f}")

# Stacking ensemble
estimators = [
    ('xgb', xgb.XGBClassifier(**study.best_params, n_estimators=500, random_state=42)),
    ('lgbm', LGBMClassifier(n_estimators=500, random_state=42)),
    ('rf', RandomForestClassifier(n_estimators=500, random_state=42)),
]

stack = StackingClassifier(estimators=estimators, final_estimator=xgb.XGBClassifier(),
                           cv=5, n_jobs=-1)
stack.fit(X_train, y_train)
print(f"Stacking score: {stack.score(X_val, y_val):.4f}")
```

### Common Mistakes
- Preprocessing BEFORE splitting (data leakage!)
- Not handling missing values properly
- Ignoring feature importance after training
- Using one-hot encoding with high-cardinality categoricals (use target encoding instead)
- Not checking for target leakage

### If It's Not Working
- Score barely above baseline: feature engineering is key for tabular
- Overfitting: reduce max_depth, increase min_child_weight, subsample
- Slow training: reduce n_estimators, use GPU with `tree_method='gpu_hist'`

---

## Recipe 4: Time Series Forecasting

**Timeline:** 4-8 hours (multiple model comparison)
**Hardware:** CPU sufficient for most time series

### Step 1: Data Preparation

```python
import pandas as pd
import numpy as np

df = pd.read_csv('timeseries.csv', parse_dates=['date'])
df = df.sort_values('date').reset_index(drop=True)

# Check for gaps
date_diffs = df['date'].diff()
print(f"Expected frequency: {date_diffs.mode()[0]}")
print(f"Gaps found: {(date_diffs != date_diffs.mode()[0]).sum()}")

# Fill gaps if needed
full_range = pd.date_range(df['date'].min(), df['date'].max(), freq='D')
df = df.set_index('date').reindex(full_range).interpolate().reset_index()
df.columns = ['date', 'value']
```

### Step 2: Feature Engineering

```python
def create_time_features(df, target_col='value', lags=[1,7,14,28]):
    df = df.copy()

    # Lag features
    for lag in lags:
        df[f'lag_{lag}'] = df[target_col].shift(lag)

    # Rolling statistics
    for window in [7, 14, 30]:
        df[f'rolling_mean_{window}'] = df[target_col].shift(1).rolling(window).mean()
        df[f'rolling_std_{window}'] = df[target_col].shift(1).rolling(window).std()

    # Calendar features
    df['day_of_week'] = df['date'].dt.dayofweek
    df['month'] = df['date'].dt.month
    df['day_of_month'] = df['date'].dt.day
    df['is_weekend'] = (df['date'].dt.dayofweek >= 5).astype(int)
    df['quarter'] = df['date'].dt.quarter

    # Cyclical encoding
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

    return df.dropna()

df_feat = create_time_features(df)
```

### Step 3: Temporal Split (NEVER random!)

```python
# 80/20 temporal split
split_idx = int(len(df_feat) * 0.8)
train = df_feat.iloc[:split_idx]
test = df_feat.iloc[split_idx:]

feature_cols = [c for c in train.columns if c not in ['date', 'value']]
X_train, y_train = train[feature_cols], train['value']
X_test, y_test = test[feature_cols], test['value']
```

### Step 4: Baseline

```python
# Naive: last value
naive_pred = test['value'].shift(1).fillna(method='ffill')
naive_mae = np.abs(y_test - naive_pred).mean()

# Seasonal naive: value from same day last week
seasonal_pred = test['value'].shift(7).fillna(method='ffill')
seasonal_mae = np.abs(y_test - seasonal_pred).mean()

print(f"Naive MAE: {naive_mae:.2f}")
print(f"Seasonal Naive MAE: {seasonal_mae:.2f}")
```

### Step 5: Models

```python
# --- Prophet ---
from prophet import Prophet

prophet_df = df[['date', 'value']].rename(columns={'date': 'ds', 'value': 'y'})
prophet_train = prophet_df.iloc[:split_idx]
prophet_test = prophet_df.iloc[split_idx:]

m = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
m.fit(prophet_train)
forecast = m.predict(prophet_test[['ds']])
prophet_mae = np.abs(prophet_test['y'].values - forecast['yhat'].values).mean()

# --- Gradient Boosting ---
import lightgbm as lgb

lgb_model = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, max_depth=6)
lgb_model.fit(X_train, y_train)
lgb_pred = lgb_model.predict(X_test)
lgb_mae = np.abs(y_test - lgb_pred).mean()

# --- LSTM ---
import torch
import torch.nn as nn

class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

# Prepare sequences
def create_sequences(data, seq_length=30):
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i:i+seq_length])
        y.append(data[i+seq_length])
    return np.array(X), np.array(y)

values = df['value'].values.reshape(-1, 1)
from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
scaled = scaler.fit_transform(values)
X_seq, y_seq = create_sequences(scaled, seq_length=30)

print(f"Prophet MAE: {prophet_mae:.2f}, LightGBM MAE: {lgb_mae:.2f}")
```

### Step 6-7: Walk-Forward Validation

```python
def walk_forward_validation(df, model_fn, train_size=365, test_size=30, step=30):
    """Sliding window backtest"""
    predictions, actuals = [], []

    for start in range(0, len(df) - train_size - test_size, step):
        train = df.iloc[start:start + train_size]
        test = df.iloc[start + train_size:start + train_size + test_size]

        model = model_fn()
        X_tr = train[feature_cols]
        y_tr = train['value']
        model.fit(X_tr, y_tr)

        pred = model.predict(test[feature_cols])
        predictions.extend(pred)
        actuals.extend(test['value'].values)

    mae = np.mean(np.abs(np.array(actuals) - np.array(predictions)))
    mape = np.mean(np.abs((np.array(actuals) - np.array(predictions)) / np.array(actuals))) * 100
    return mae, mape

mae, mape = walk_forward_validation(
    df_feat, lambda: lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05)
)
print(f"Walk-forward MAE: {mae:.2f}, MAPE: {mape:.1f}%")
```

### Common Mistakes
- Random train/test split (causes future data leakage!)
- Using features that won't be available at prediction time
- Not comparing against naive baselines
- Ignoring seasonality in feature engineering
- Overfitting to recent patterns without testing on different periods

### If It's Not Working
- Worse than naive: check for look-ahead bias, simplify features
- High variance across time periods: your model is overfit to patterns that don't persist
- Spikes/anomalies: add anomaly detection preprocessing

---

## Recipe 5: Object Detection

**Timeline:** 4-8 hours with pretrained model
**Hardware:** GPU required (16GB+ recommended for training)

### Step 1: Data in YOLO Format

```
# YOLO format: one .txt per image
# Each line: class_id center_x center_y width height (all normalized 0-1)
# data/
#   images/
#     train/ img001.jpg ...
#     val/ img001.jpg ...
#   labels/
#     train/ img001.txt ...
#     val/ img001.txt ...
```

### Step 2-3: Fine-tune YOLOv8

```python
from ultralytics import YOLO

# Load pretrained
model = YOLO('yolov8m.pt')  # nano/small/medium/large/xlarge

# Train
results = model.train(
    data='dataset.yaml',    # paths to images and class names
    epochs=100,
    imgsz=640,
    batch=16,
    lr0=0.01,              # initial LR
    lrf=0.01,              # final LR factor
    warmup_epochs=3,
    augment=True,
    mosaic=1.0,            # mosaic augmentation
    mixup=0.1,
    patience=20,           # early stopping
)

# dataset.yaml:
# path: ./data
# train: images/train
# val: images/val
# names:
#   0: person
#   1: car
#   2: bicycle
```

### Step 4: Augmentations (with box transforms)

```python
# If using custom pipeline with Albumentations:
import albumentations as A

transform = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(p=0.3),
    A.RandomResizedCrop(640, 640, scale=(0.5, 1.0)),
    A.GaussNoise(p=0.2),
], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))

# IMPORTANT: augmentations must transform bounding boxes too!
transformed = transform(image=image, bboxes=bboxes, class_labels=labels)
```

### Step 5: Evaluate

```python
# Validate
metrics = model.val()
print(f"mAP@0.5: {metrics.box.map50:.4f}")
print(f"mAP@0.5:0.95: {metrics.box.map:.4f}")

# Inference
results = model.predict('test_image.jpg', conf=0.25, iou=0.45)
results[0].show()
```

### Common Mistakes
- Annotations off by a few pixels (check visually!)
- Very small objects: increase imgsz to 1280
- Class imbalance: use focal loss or oversample rare classes
- Not augmenting boxes along with images
- Too few training images per class (<100 is risky)

### If It's Not Working
- mAP very low: verify annotations are correct, visualize 20 random samples
- Lots of false positives: increase conf threshold, add hard negatives
- Missing small objects: use larger input size, use P2 detection head

---

## Recipe 6: Recommendation System

**Timeline:** 4-8 hours
**Hardware:** CPU for collaborative filtering, GPU for deep models

### Collaborative Filtering (Matrix Factorization)

```python
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

# User-item interaction matrix
# rows=users, cols=items, values=ratings/interactions
interactions = pd.read_csv('interactions.csv')  # user_id, item_id, rating
user_item = interactions.pivot(index='user_id', columns='item_id', values='rating').fillna(0)
sparse_matrix = csr_matrix(user_item.values)

# SVD
svd = TruncatedSVD(n_components=50, random_state=42)
user_factors = svd.fit_transform(sparse_matrix)
item_factors = svd.components_.T

# Predict for user
def recommend(user_idx, n=10):
    scores = user_factors[user_idx] @ item_factors.T
    already_seen = sparse_matrix[user_idx].nonzero()[1]
    scores[already_seen] = -np.inf
    top_items = np.argsort(scores)[::-1][:n]
    return top_items

# --- Using Surprise library ---
from surprise import SVD, Dataset, Reader, accuracy
from surprise.model_selection import cross_validate

reader = Reader(rating_scale=(1, 5))
data = Dataset.load_from_df(interactions[['user_id', 'item_id', 'rating']], reader)

model = SVD(n_factors=100, n_epochs=20, lr_all=0.005, reg_all=0.02)
results = cross_validate(model, data, measures=['RMSE', 'MAE'], cv=5)
print(f"RMSE: {results['test_rmse'].mean():.4f}")
```

### Content-Based Filtering

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Item features (descriptions, tags, etc.)
items = pd.read_csv('items.csv')  # item_id, description, category, tags
tfidf = TfidfVectorizer(max_features=5000, stop_words='english')
item_vectors = tfidf.fit_transform(items['description'])

# Find similar items
def get_similar_items(item_idx, n=10):
    sims = cosine_similarity(item_vectors[item_idx], item_vectors).flatten()
    sims[item_idx] = -1  # exclude self
    return np.argsort(sims)[::-1][:n]

# Recommend based on user history
def recommend_content(user_history_idxs, n=10):
    user_profile = item_vectors[user_history_idxs].mean(axis=0)
    sims = cosine_similarity(user_profile, item_vectors).flatten()
    for idx in user_history_idxs:
        sims[idx] = -1
    return np.argsort(sims)[::-1][:n]
```

### Common Mistakes
- Cold start problem: new users/items have no interactions (use content-based fallback)
- Popularity bias: most recommendations are just popular items
- Not evaluating beyond accuracy (diversity, novelty, coverage matter)
- Implicit vs explicit feedback confusion (clicks != ratings)

### If It's Not Working
- All users getting same recommendations: normalize ratings per user
- Poor diversity: add diversity penalty or MMR re-ranking
- Slow for large catalogs: use approximate nearest neighbors (FAISS)

---

## Quick Reference: Starting Hyperparameters

| Task | LR | Batch Size | Epochs | Key Setting |
|------|-----|-----------|--------|-------------|
| Image Classification (finetune) | 1e-3 head, 1e-4 backbone | 32-64 | 20-50 | OneCycleLR |
| Text Classification | 2e-5 | 16-32 | 3-5 | Linear warmup 10% |
| Tabular (XGBoost) | 0.1 | N/A | 500 (early stop) | max_depth=6 |
| Time Series (LightGBM) | 0.05 | N/A | 300-500 | lag features |
| Object Detection (YOLO) | 0.01 | 16 | 100 | patience=20 |
| Recommendation (SVD) | 0.005 | N/A | 20 | n_factors=100 |

---

## Universal Training Checklist

```
Before training:
□ Data loaded correctly? (print batch, visualize samples)
□ Labels correct? (spot check 10-20 samples manually)
□ Train/val/test split done properly? (no leakage)
□ Preprocessing fit on train only?
□ Baseline model score established?

During training:
□ Loss decreasing on train?
□ Val metrics tracked every epoch?
□ Best model checkpointed?
□ Learning rate schedule working?
□ GPU utilization >80%?

After training:
□ Evaluated on held-out test set?
□ Per-class/segment metrics checked?
□ Error analysis done? (what does it get wrong?)
□ Model exported and tested in inference mode?
□ Results reproducible? (set all seeds)
```
