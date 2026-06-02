# Dataset Handling Patterns

> The practical "how do I load my data" guide for every data type.

Every pattern includes complete, runnable code with memory optimization and common pitfalls.

---

## Pattern 1: Image Data

### Directory Structure (ImageFolder Convention)

```
data/
├── train/
│   ├── cats/
│   │   ├── img_001.jpg
│   │   └── img_002.jpg
│   └── dogs/
│       ├── img_003.jpg
│       └── img_004.jpg
├── val/
│   ├── cats/
│   └── dogs/
└── test/
    ├── cats/
    └── dogs/
```

### Complete PyTorch Image Pipeline

```python
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import os

# === Standard augmentation pipelines ===

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],  # ImageNet stats
                         std=[0.229, 0.224, 0.225]),
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# === Option A: ImageFolder (simplest) ===

from torchvision.datasets import ImageFolder

train_dataset = ImageFolder(root='data/train', transform=train_transform)
val_dataset = ImageFolder(root='data/val', transform=val_transform)

train_loader = DataLoader(
    train_dataset,
    batch_size=32,
    shuffle=True,
    num_workers=4,        # Parallel data loading
    pin_memory=True,      # Faster GPU transfer
    prefetch_factor=2,    # Prefetch 2 batches per worker
    persistent_workers=True,  # Don't restart workers each epoch
)

# === Option B: CSV + image paths (more flexible) ===

class ImageDatasetFromCSV(Dataset):
    """Load images from CSV with columns: filepath, label."""
    
    def __init__(self, csv_path, img_dir, transform=None):
        import pandas as pd
        self.df = pd.read_csv(csv_path)
        self.img_dir = img_dir
        self.transform = transform
        self.label_map = {label: idx for idx, label 
                         in enumerate(sorted(self.df['label'].unique()))}
    
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = os.path.join(self.img_dir, row['filepath'])
        
        # Load image
        image = Image.open(img_path).convert('RGB')
        
        if self.transform:
            image = self.transform(image)
        
        label = self.label_map[row['label']]
        return image, label


# === Option C: Large datasets with memory mapping ===

class StreamingImageDataset(Dataset):
    """For datasets too large to list in memory."""
    
    def __init__(self, root_dir, transform=None):
        self.transform = transform
        # Store only paths, not images
        self.samples = []
        for class_idx, class_name in enumerate(sorted(os.listdir(root_dir))):
            class_dir = os.path.join(root_dir, class_name)
            if os.path.isdir(class_dir):
                for fname in os.listdir(class_dir):
                    if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        self.samples.append((os.path.join(class_dir, fname), class_idx))
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        path, label = self.samples[idx]
        # Load only when accessed (lazy loading)
        image = Image.open(path).convert('RGB')
        if self.transform:
            image = self.transform(image)
        return image, label
```

### Common Mistakes - Images

```python
# ❌ WRONG: Loading all images into memory
all_images = [Image.open(p) for p in paths]  # OOM on large datasets

# ✅ RIGHT: Lazy loading in __getitem__

# ❌ WRONG: Same transform for train and val
# You're augmenting validation data — inflating metrics!

# ✅ RIGHT: Separate transforms (no augmentation for val/test)

# ❌ WRONG: Forgetting to convert to RGB
img = Image.open(path)  # Could be RGBA, grayscale, palette

# ✅ RIGHT: Always convert
img = Image.open(path).convert('RGB')

# ❌ WRONG: Not handling corrupt images
# ✅ RIGHT: Wrap in try/except, skip bad files
def __getitem__(self, idx):
    try:
        return self._load(idx)
    except (OSError, IOError):
        # Return next valid image
        return self.__getitem__((idx + 1) % len(self))
```

---

## Pattern 2: Text Data

### Complete HuggingFace Text Pipeline

```python
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer
import pandas as pd

class TextClassificationDataset(Dataset):
    """Standard text classification dataset."""
    
    def __init__(self, texts, labels, tokenizer_name='bert-base-uncased', max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_length,
            padding='max_length',       # Pad to max_length
            truncation=True,            # Truncate if longer
            return_tensors='pt',
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'label': torch.tensor(self.labels[idx], dtype=torch.long),
        }

# Usage
df = pd.read_csv('data/reviews.csv')
dataset = TextClassificationDataset(
    texts=df['text'].tolist(),
    labels=df['label'].tolist(),
)
loader = DataLoader(dataset, batch_size=16, shuffle=True)
```

### Dynamic Batching (Bucket by Length)

```python
from torch.utils.data import Sampler
import numpy as np

class BucketBatchSampler(Sampler):
    """Group similar-length sequences to minimize padding waste.
    
    Can save 30-50% of compute by reducing padding tokens.
    """
    
    def __init__(self, lengths, batch_size, shuffle=True):
        self.batch_size = batch_size
        self.shuffle = shuffle
        # Sort indices by length
        self.sorted_indices = np.argsort(lengths)
        # Create batches of similar lengths
        self.batches = [
            self.sorted_indices[i:i + batch_size]
            for i in range(0, len(self.sorted_indices), batch_size)
        ]
    
    def __iter__(self):
        if self.shuffle:
            np.random.shuffle(self.batches)
        for batch in self.batches:
            yield batch.tolist()
    
    def __len__(self):
        return len(self.batches)

# Usage with dynamic padding collate function
def collate_dynamic_padding(batch):
    """Pad to longest sequence in batch (not global max)."""
    input_ids = [item['input_ids'] for item in batch]
    attention_masks = [item['attention_mask'] for item in batch]
    labels = torch.tensor([item['label'] for item in batch])
    
    # Pad to max length IN THIS BATCH
    input_ids = torch.nn.utils.rnn.pad_sequence(input_ids, batch_first=True)
    attention_masks = torch.nn.utils.rnn.pad_sequence(attention_masks, batch_first=True)
    
    return {'input_ids': input_ids, 'attention_mask': attention_masks, 'label': labels}

# Combine
lengths = [len(text.split()) for text in df['text']]
sampler = BucketBatchSampler(lengths, batch_size=32)
loader = DataLoader(dataset, batch_sampler=sampler, collate_fn=collate_dynamic_padding)
```

### Handling Long Documents (Chunking)

```python
def chunk_long_document(text, tokenizer, max_length=512, overlap=50):
    """Split long documents into overlapping chunks."""
    tokens = tokenizer.encode(text, add_special_tokens=False)
    
    chunks = []
    stride = max_length - overlap - 2  # Account for [CLS] and [SEP]
    
    for i in range(0, len(tokens), stride):
        chunk = tokens[i:i + max_length - 2]
        chunks.append(chunk)
        if i + max_length - 2 >= len(tokens):
            break
    
    return chunks

# At inference: aggregate chunk predictions
# Options: max-pool, mean-pool, or majority vote across chunks
```

### Common Mistakes - Text

```python
# ❌ WRONG: Tokenizing in __init__ (wastes memory for large datasets)
self.encodings = [tokenizer(t) for t in texts]  # Stores all in RAM

# ✅ RIGHT: Tokenize in __getitem__ (lazy, but slower)
# Or: pre-tokenize and save to disk with datasets library

# ❌ WRONG: Fixed padding to 512 for short texts
# Wastes 80% of compute if average length is 50 tokens

# ✅ RIGHT: Dynamic padding to batch max length

# ❌ WRONG: Not handling special characters / encoding issues
# ✅ RIGHT:
text = text.encode('utf-8', errors='replace').decode('utf-8')
```

---

## Pattern 3: Tabular Data

### Complete sklearn Pipeline

```python
import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split

# Load data
df = pd.read_csv('data/customers.csv')

# Define column types
numeric_features = ['age', 'income', 'account_balance', 'num_transactions']
categorical_features = ['gender', 'region', 'plan_type']
ordinal_features = ['education']  # Has natural order
target = 'churn'

# === Complete preprocessing pipeline ===

numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler()),
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
])

ordinal_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('encoder', OrdinalEncoder(categories=[
        ['high_school', 'bachelors', 'masters', 'phd']
    ])),
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('cat', categorical_transformer, categorical_features),
        ('ord', ordinal_transformer, ordinal_features),
    ],
    remainder='drop',  # Drop columns not specified
)

# === Train/Val/Test Split (stratified) ===

X = df.drop(columns=[target])
y = df[target]

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
)

# === Fit on train only, transform all ===

X_train_processed = preprocessor.fit_transform(X_train)
X_val_processed = preprocessor.transform(X_val)      # No fit!
X_test_processed = preprocessor.transform(X_test)    # No fit!

# === Full pipeline with model ===
from sklearn.ensemble import GradientBoostingClassifier

full_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', GradientBoostingClassifier(n_estimators=100)),
])

full_pipeline.fit(X_train, y_train)
score = full_pipeline.score(X_val, y_val)
```

### Feature Engineering for Tabular

```python
def engineer_features(df):
    """Common tabular feature engineering patterns."""
    df = df.copy()
    
    # Interaction features
    df['income_per_age'] = df['income'] / (df['age'] + 1)
    
    # Binning continuous features
    df['age_group'] = pd.cut(df['age'], bins=[0, 25, 35, 50, 65, 100],
                             labels=['young', 'adult', 'middle', 'senior', 'elderly'])
    
    # Date features
    if 'signup_date' in df.columns:
        df['signup_date'] = pd.to_datetime(df['signup_date'])
        df['days_since_signup'] = (pd.Timestamp.now() - df['signup_date']).dt.days
        df['signup_month'] = df['signup_date'].dt.month
        df['signup_dayofweek'] = df['signup_date'].dt.dayofweek
    
    # Aggregation features (if group data exists)
    if 'user_id' in df.columns:
        user_stats = df.groupby('user_id').agg(
            total_spend=('amount', 'sum'),
            avg_spend=('amount', 'mean'),
            num_orders=('order_id', 'nunique'),
        ).reset_index()
        df = df.merge(user_stats, on='user_id', how='left')
    
    return df
```

### Common Mistakes - Tabular

```python
# ❌ WRONG: Fitting preprocessor on entire dataset (data leakage!)
preprocessor.fit(X_all)

# ✅ RIGHT: Fit ONLY on training data
preprocessor.fit(X_train)

# ❌ WRONG: One-hot encoding high cardinality features
# 10,000 unique cities → 10,000 columns

# ✅ RIGHT: Use target encoding or embeddings for high cardinality
from category_encoders import TargetEncoder
encoder = TargetEncoder(cols=['city'])
encoder.fit(X_train, y_train)

# ❌ WRONG: Dropping rows with missing values silently
df.dropna(inplace=True)  # Might drop 30% of your data

# ✅ RIGHT: Analyze missing patterns, then impute strategically
```

---

## Pattern 4: Time Series Data

### Complete Time Series DataLoader

```python
import numpy as np
import pandas as pd
from torch.utils.data import Dataset, DataLoader
import torch

class TimeSeriesDataset(Dataset):
    """Sliding window dataset for time series forecasting."""
    
    def __init__(self, data, sequence_length=60, forecast_horizon=1, 
                 feature_cols=None, target_col='close'):
        """
        Args:
            data: DataFrame with datetime index, sorted chronologically
            sequence_length: Number of past timesteps as input
            forecast_horizon: Number of future timesteps to predict
        """
        self.seq_len = sequence_length
        self.horizon = forecast_horizon
        
        if feature_cols is None:
            feature_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        
        self.features = data[feature_cols].values.astype(np.float32)
        self.targets = data[target_col].values.astype(np.float32)
        
        # Normalize (fit on training portion only!)
        self.feature_mean = self.features.mean(axis=0)
        self.feature_std = self.features.std(axis=0) + 1e-8
        self.features = (self.features - self.feature_mean) / self.feature_std
        
        self.target_mean = self.targets.mean()
        self.target_std = self.targets.std() + 1e-8
        self.targets = (self.targets - self.target_mean) / self.target_std
    
    def __len__(self):
        return len(self.features) - self.seq_len - self.horizon + 1
    
    def __getitem__(self, idx):
        x = self.features[idx:idx + self.seq_len]
        y = self.targets[idx + self.seq_len:idx + self.seq_len + self.horizon]
        return torch.tensor(x), torch.tensor(y)

# === CRITICAL: Temporal split (NO shuffle!) ===

def temporal_train_val_test_split(df, train_ratio=0.7, val_ratio=0.15):
    """Split time series chronologically. NEVER shuffle time series."""
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    
    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]
    
    return train_df, val_df, test_df

# Usage
df = pd.read_csv('data/stock_prices.csv', parse_dates=['date'], index_col='date')
df = df.sort_index()  # Ensure chronological order!

train_df, val_df, test_df = temporal_train_val_test_split(df)

# Fit normalization on train only
train_dataset = TimeSeriesDataset(train_df, sequence_length=60)

# Apply TRAIN stats to val/test (no data leakage)
val_dataset = TimeSeriesDataset(val_df, sequence_length=60)
# Override normalization stats:
val_dataset.feature_mean = train_dataset.feature_mean
val_dataset.feature_std = train_dataset.feature_std
val_dataset.target_mean = train_dataset.target_mean
val_dataset.target_std = train_dataset.target_std
val_dataset.features = (val_df[feature_cols].values - train_dataset.feature_mean) / train_dataset.feature_std

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=False)  # NO SHUFFLE!
val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False)
```

### Feature Engineering for Time Series

```python
def create_time_features(df):
    """Standard time series feature engineering."""
    df = df.copy()
    
    # Lag features
    for lag in [1, 7, 14, 30]:
        df[f'lag_{lag}'] = df['value'].shift(lag)
    
    # Rolling statistics
    for window in [7, 14, 30]:
        df[f'rolling_mean_{window}'] = df['value'].rolling(window).mean()
        df[f'rolling_std_{window}'] = df['value'].rolling(window).std()
    
    # Calendar features
    if isinstance(df.index, pd.DatetimeIndex):
        df['hour'] = df.index.hour
        df['dayofweek'] = df.index.dayofweek
        df['month'] = df.index.month
        df['is_weekend'] = df.index.dayofweek >= 5
    
    # Drop rows with NaN from lag/rolling (beginning of series)
    df = df.dropna()
    return df
```

### Common Mistakes - Time Series

```python
# ❌ WRONG: Shuffling time series data
DataLoader(dataset, shuffle=True)  # DESTROYS temporal structure

# ✅ RIGHT: Always sequential
DataLoader(dataset, shuffle=False)

# ❌ WRONG: Random train/test split
train_test_split(df, random_state=42)  # Future leaks into past

# ✅ RIGHT: Temporal split
train = df[:'2023-06']
test = df['2023-07':]

# ❌ WRONG: Normalizing on entire dataset
scaler.fit(all_data)  # Uses future stats to normalize past

# ✅ RIGHT: Fit scaler on training data only
scaler.fit(train_data)
val_scaled = scaler.transform(val_data)

# ❌ WRONG: Using future data in features (look-ahead bias)
df['next_day_avg'] = df['value'].shift(-1)  # CHEATING

# ✅ RIGHT: Only use past data
df['prev_day_avg'] = df['value'].shift(1)
```

---

## Pattern 5: Audio Data

### Complete Audio Pipeline

```python
import torch
import torchaudio
from torch.utils.data import Dataset
import os

class AudioClassificationDataset(Dataset):
    """Load audio, resample, convert to mel-spectrogram."""
    
    def __init__(self, file_paths, labels, target_sr=16000, 
                 duration_sec=5.0, n_mels=128, augment=False):
        self.file_paths = file_paths
        self.labels = labels
        self.target_sr = target_sr
        self.target_length = int(target_sr * duration_sec)
        self.n_mels = n_mels
        self.augment = augment
        
        # Mel spectrogram transform
        self.mel_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=target_sr,
            n_fft=1024,
            hop_length=512,
            n_mels=n_mels,
        )
        self.db_transform = torchaudio.transforms.AmplitudeToDB()
    
    def __len__(self):
        return len(self.file_paths)
    
    def _pad_or_trim(self, waveform):
        """Ensure fixed length."""
        if waveform.shape[1] > self.target_length:
            # Random crop during training, center crop during eval
            if self.augment:
                start = torch.randint(0, waveform.shape[1] - self.target_length, (1,))
                waveform = waveform[:, start:start + self.target_length]
            else:
                center = waveform.shape[1] // 2
                half = self.target_length // 2
                waveform = waveform[:, center - half:center + half]
        elif waveform.shape[1] < self.target_length:
            # Zero-pad
            pad_amount = self.target_length - waveform.shape[1]
            waveform = torch.nn.functional.pad(waveform, (0, pad_amount))
        return waveform
    
    def __getitem__(self, idx):
        # Load audio
        waveform, sr = torchaudio.load(self.file_paths[idx])
        
        # Convert to mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        
        # Resample if needed
        if sr != self.target_sr:
            resampler = torchaudio.transforms.Resample(sr, self.target_sr)
            waveform = resampler(waveform)
        
        # Fixed length
        waveform = self._pad_or_trim(waveform)
        
        # Augmentation
        if self.augment:
            # Time stretch (slight speed change)
            if torch.rand(1) < 0.3:
                stretch = torchaudio.transforms.TimeStretch(n_freq=self.n_mels)
                # Apply after mel... (simplified here)
                pass
            # Add noise
            if torch.rand(1) < 0.3:
                noise = torch.randn_like(waveform) * 0.005
                waveform = waveform + noise
        
        # Convert to mel spectrogram
        mel_spec = self.mel_transform(waveform)
        mel_spec_db = self.db_transform(mel_spec)
        
        # Normalize
        mel_spec_db = (mel_spec_db - mel_spec_db.mean()) / (mel_spec_db.std() + 1e-8)
        
        return mel_spec_db, self.labels[idx]
```

### SpecAugment (Standard Audio Augmentation)

```python
class SpecAugment:
    """SpecAugment: mask random time and frequency bands."""
    
    def __init__(self, freq_mask_param=15, time_mask_param=35, num_masks=2):
        self.freq_mask = torchaudio.transforms.FrequencyMasking(freq_mask_param)
        self.time_mask = torchaudio.transforms.TimeMasking(time_mask_param)
        self.num_masks = num_masks
    
    def __call__(self, spec):
        for _ in range(self.num_masks):
            spec = self.freq_mask(spec)
            spec = self.time_mask(spec)
        return spec
```

---

## Pattern 6: Graph Data

### PyTorch Geometric Basics

```python
import torch
from torch_geometric.data import Data, DataLoader as GeoDataLoader

# Single graph
edge_index = torch.tensor([
    [0, 1, 1, 2, 2, 3],  # Source nodes
    [1, 0, 2, 1, 3, 2],  # Target nodes (undirected = both directions)
], dtype=torch.long)

node_features = torch.randn(4, 16)  # 4 nodes, 16 features each
node_labels = torch.tensor([0, 1, 1, 0])

graph = Data(
    x=node_features,
    edge_index=edge_index,
    y=node_labels,
)

# For graph classification (multiple graphs)
from torch_geometric.data import InMemoryDataset

class MoleculeDataset(InMemoryDataset):
    def __init__(self, root, graphs_list):
        self.graphs = graphs_list
        super().__init__(root)
        self.data, self.slices = torch.load(self.processed_paths[0])
    
    @property
    def processed_file_names(self):
        return ['data.pt']
    
    def process(self):
        data, slices = self.collate(self.graphs)
        torch.save((data, slices), self.processed_paths[0])

# Mini-batching graphs (automatically handles variable sizes)
loader = GeoDataLoader(dataset, batch_size=32, shuffle=True)
# Each batch.x has all nodes concatenated; batch.batch tells you which graph each belongs to
```

---

## Pattern 7: Multi-Modal Data

### Image + Text (CLIP-style)

```python
import torch
from torch.utils.data import Dataset
from PIL import Image
from transformers import AutoTokenizer
from torchvision import transforms

class MultiModalDataset(Dataset):
    """Combined image + text dataset."""
    
    def __init__(self, df, img_dir, tokenizer_name='bert-base-uncased',
                 max_text_length=128, img_size=224):
        self.df = df  # Must have: image_path, text, label
        self.img_dir = img_dir
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.max_text_length = max_text_length
        
        self.img_transform = transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
    
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # Image
        img_path = os.path.join(self.img_dir, row['image_path'])
        image = Image.open(img_path).convert('RGB')
        image = self.img_transform(image)
        
        # Text
        encoding = self.tokenizer(
            row['text'],
            max_length=self.max_text_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt',
        )
        
        # Handle missing modality
        has_image = not pd.isna(row.get('image_path', None))
        has_text = not pd.isna(row.get('text', None))
        
        return {
            'image': image,
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'has_image': torch.tensor(has_image, dtype=torch.bool),
            'has_text': torch.tensor(has_text, dtype=torch.bool),
            'label': torch.tensor(row['label'], dtype=torch.long),
        }
```

---

## Memory Optimization Tips (All Patterns)

```python
# 1. Use memory-mapped files for large datasets
import numpy as np
# Save
np.save('features.npy', large_array)
# Load without reading into RAM
features = np.load('features.npy', mmap_mode='r')

# 2. Use HuggingFace datasets for streaming
from datasets import load_dataset
dataset = load_dataset('large_dataset', streaming=True)
for batch in dataset.iter(batch_size=32):
    process(batch)

# 3. Use appropriate dtypes
df['category'] = df['category'].astype('category')  # Huge memory savings
df['count'] = df['count'].astype(np.int16)           # Instead of int64

# 4. Use WebDataset for large-scale training
import webdataset as wds
dataset = (
    wds.WebDataset("data/shards-{000000..000099}.tar")
    .decode("pil")
    .to_tuple("jpg", "json")
    .map_tuple(transform, lambda x: x['label'])
)

# 5. Profile your DataLoader
from torch.utils.data import DataLoader
import time

loader = DataLoader(dataset, batch_size=32, num_workers=4)
start = time.time()
for i, batch in enumerate(loader):
    if i == 100: break
print(f"100 batches in {time.time()-start:.1f}s")
# If loading is slow: increase num_workers, use faster storage, or pre-process
```

---

## Performance Profiling Checklist

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| GPU utilization < 80% | DataLoader too slow | More workers, pre-process, faster storage |
| OOM on GPU | Batch too large | Reduce batch size, gradient accumulation |
| OOM on RAM | Loading full dataset | Streaming, memory mapping, lazy loading |
| Training very slow | Too much augmentation on CPU | Move augmentation to GPU (Kornia) |
| Val metrics inconsistent | Augmenting val data | Separate transforms for val |
| Model doesn't learn | Data loading bug | Visualize a batch before training! |

### The Golden Rule: Always Visualize a Batch

```python
# Before training, ALWAYS check your data pipeline:
batch = next(iter(train_loader))

# Images: display a grid
import matplotlib.pyplot as plt
fig, axes = plt.subplots(2, 4, figsize=(12, 6))
for i, ax in enumerate(axes.flat):
    img = batch[0][i].permute(1, 2, 0).numpy()
    img = img * np.array([0.229, 0.224, 0.225]) + np.array([0.485, 0.456, 0.406])
    ax.imshow(img.clip(0, 1))
    ax.set_title(f"Label: {batch[1][i].item()}")
plt.savefig('batch_check.png')

# Text: decode tokens back
for i in range(4):
    tokens = tokenizer.decode(batch['input_ids'][i], skip_special_tokens=True)
    print(f"Label {batch['label'][i]}: {tokens[:100]}")
```

---

## Quick Reference: Which Pattern to Use

| Data Type | Framework | Key Class | Critical Setting |
|-----------|-----------|-----------|------------------|
| Images (folders) | PyTorch | `ImageFolder` | `num_workers=4, pin_memory=True` |
| Images (custom) | PyTorch | Custom `Dataset` | Lazy load in `__getitem__` |
| Text (classification) | HuggingFace | `Dataset` + tokenizer | Dynamic padding, bucket sampling |
| Text (generation) | HuggingFace | `datasets.load_dataset` | Streaming for large corpora |
| Tabular | sklearn | `ColumnTransformer` | Fit on train only |
| Time series | PyTorch | Custom sliding window | NO SHUFFLE, temporal split |
| Audio | torchaudio | Custom + MelSpectrogram | Fixed sample rate, fixed length |
| Graphs | PyG | `Data` + `DataLoader` | Auto-batching handles variable sizes |
| Multi-modal | PyTorch | Custom combining loaders | Handle missing modalities |
