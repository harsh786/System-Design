# Transfer Learning Cookbook

> "I want to solve MY problem using pretrained models" — which is 90% of real ML work.

This cookbook provides copy-paste recipes for the most common transfer learning scenarios.
Each recipe is battle-tested and includes complete, runnable code.

---

## Table of Contents

1. [Why Transfer Learning](#why-transfer-learning)
2. [Recipe 1: Fine-tuning Image Models](#recipe-1-fine-tuning-image-models)
3. [Recipe 2: Fine-tuning BERT for Text](#recipe-2-fine-tuning-bertdistilbert-for-text)
4. [Recipe 3: Fine-tuning LLMs (LoRA/QLoRA)](#recipe-3-fine-tuning-llms-loraqlorа)
5. [Recipe 4: Fine-tuning for Object Detection](#recipe-4-fine-tuning-for-object-detection)
6. [Recipe 5: Fine-tuning Embedding Models](#recipe-5-fine-tuning-embedding-models)
7. [Common Mistakes](#common-mistakes-in-transfer-learning)
8. [How Much Data Do You Need?](#how-much-data-do-you-need)

---

## Why Transfer Learning

### The Core Insight

Pretrained models have already learned general features from massive datasets:
- **Image models** (trained on ImageNet): edges → textures → parts → objects
- **Language models** (trained on internet text): syntax → semantics → reasoning → world knowledge
- **Audio models**: frequencies → phonemes → words → speech patterns

You don't need to re-learn any of this. You just fine-tune the "last mile" for YOUR specific task.

### Benefits

| Benefit | Impact |
|---------|--------|
| Less data needed | 10-100x less than training from scratch |
| Less compute | Hours instead of weeks |
| Better performance | Pretrained features generalize well |
| Faster iteration | Try new tasks in minutes |
| State-of-the-art access | Use models trained on $millions of compute |

### Decision Tree: What Should You Do?

```
START: Do you have a problem to solve?
│
├── Is there a pretrained model that solves it directly?
│   ├── YES → Use it as-is (API call, no training needed)
│   │         Examples: GPT-4 for text, CLIP for image search
│   └── NO → Continue...
│
├── Is your problem similar to what a pretrained model was trained on?
│   ├── YES → Fine-tune that model (THIS COOKBOOK)
│   │         Examples: Medical image classification using ResNet
│   └── NO → Continue...
│
├── Do you have >100K labeled examples AND unique data modality?
│   ├── YES → Consider training from scratch
│   │         Examples: Protein folding, custom sensor data
│   └── NO → Still try transfer learning first!
│
└── DEFAULT: Fine-tune a pretrained model. It almost always works better.
```

### The Transfer Learning Spectrum

```
Zero-shot          Feature         Fine-tune      Fine-tune       Train from
(no training)      Extraction      Head Only      Full Model      Scratch
     │                │                │               │              │
Use model        Freeze all       Freeze         Unfreeze all    Random init
as-is            layers, train    backbone,      layers,         everything
                 classifier on    train new      lower LR for
                 extracted        head           early layers
                 features
     │                │                │               │              │
Need: 0          Need: 50+       Need: 100+     Need: 1000+     Need: 100K+
examples         examples        examples       examples        examples
```

---

## Recipe 1: Fine-tuning Image Models

### Choosing Your Model

```
Your dataset size → Best model choice:

Small data (<1,000 images):
  → EfficientNet-B0 or ResNet-18
  → Fewer parameters = less overfitting risk

Medium data (1,000 - 100,000 images):
  → ResNet-50 or EfficientNet-B4
  → Good balance of capacity and trainability

Large data (>100,000 images):
  → ViT-B/16 or ConvNeXt-Base
  → Enough data to leverage larger models
```

### The Recipe (Step by Step)

```
Step 1: Choose a pretrained model
Step 2: Replace the classification head
Step 3: Freeze the backbone initially
Step 4: Train head only (lr=1e-3) for 5-10 epochs
Step 5: Unfreeze the backbone
Step 6: Fine-tune full model (lr=1e-5 backbone, lr=1e-3 head)
Step 7: Use discriminative learning rates
```

### Complete PyTorch Code

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import transforms, models, datasets
import os

# ============================================================
# STEP 1: Configuration
# ============================================================
CONFIG = {
    "model_name": "resnet50",       # resnet18, resnet50, efficientnet_b0, vit_b_16
    "num_classes": 10,              # YOUR number of classes
    "batch_size": 32,
    "head_epochs": 10,              # Epochs for head-only training
    "full_epochs": 20,              # Epochs for full fine-tuning
    "head_lr": 1e-3,               # LR for classification head
    "backbone_lr": 1e-5,           # LR for backbone (much smaller!)
    "weight_decay": 1e-4,
    "image_size": 224,
    "data_dir": "./data",           # YOUR data directory
    "device": "cuda" if torch.cuda.is_available() else "cpu",
}

# ============================================================
# STEP 2: Data Preprocessing (MUST match pretrained model!)
# ============================================================
# CRITICAL: Use the SAME normalization as the pretrained model
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(CONFIG["image_size"]),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),  # DON'T SKIP THIS
])

val_transform = transforms.Compose([
    transforms.Resize(CONFIG["image_size"] + 32),
    transforms.CenterCrop(CONFIG["image_size"]),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

# Load data (expects: data_dir/train/class_name/image.jpg structure)
train_dataset = datasets.ImageFolder(
    os.path.join(CONFIG["data_dir"], "train"), transform=train_transform
)
val_dataset = datasets.ImageFolder(
    os.path.join(CONFIG["data_dir"], "val"), transform=val_transform
)

train_loader = DataLoader(train_dataset, batch_size=CONFIG["batch_size"],
                          shuffle=True, num_workers=4, pin_memory=True)
val_loader = DataLoader(val_dataset, batch_size=CONFIG["batch_size"],
                        shuffle=False, num_workers=4, pin_memory=True)

# ============================================================
# STEP 3: Load pretrained model and replace head
# ============================================================
def get_model(model_name, num_classes):
    """Load pretrained model and replace classification head."""
    if model_name == "resnet50":
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
        num_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, num_classes)
        )
    elif model_name == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        num_features = model.fc.in_features
        model.fc = nn.Linear(num_features, num_classes)
    elif model_name == "efficientnet_b0":
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
        num_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, num_classes)
        )
    elif model_name == "vit_b_16":
        model = models.vit_b_16(weights=models.ViT_B_16_Weights.IMAGENET1K_V1)
        num_features = model.heads.head.in_features
        model.heads.head = nn.Linear(num_features, num_classes)
    else:
        raise ValueError(f"Unknown model: {model_name}")
    return model

model = get_model(CONFIG["model_name"], CONFIG["num_classes"])
model = model.to(CONFIG["device"])

# ============================================================
# STEP 4: Freeze backbone, train head only
# ============================================================
def freeze_backbone(model, model_name):
    """Freeze all layers except the classification head."""
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze head
    if model_name in ["resnet50", "resnet18"]:
        for param in model.fc.parameters():
            param.requires_grad = True
    elif model_name == "efficientnet_b0":
        for param in model.classifier.parameters():
            param.requires_grad = True
    elif model_name == "vit_b_16":
        for param in model.heads.parameters():
            param.requires_grad = True

freeze_backbone(model, CONFIG["model_name"])

# Train head only
optimizer = optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()),
    lr=CONFIG["head_lr"],
    weight_decay=CONFIG["weight_decay"]
)
criterion = nn.CrossEntropyLoss()

print("Phase 1: Training classification head only...")
for epoch in range(CONFIG["head_epochs"]):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in train_loader:
        images, labels = images.to(CONFIG["device"]), labels.to(CONFIG["device"])
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    train_acc = 100. * correct / total
    print(f"  Epoch {epoch+1}/{CONFIG['head_epochs']} - "
          f"Loss: {running_loss/len(train_loader):.4f}, Acc: {train_acc:.2f}%")

# ============================================================
# STEP 5 & 6: Unfreeze backbone, fine-tune with discriminative LRs
# ============================================================
print("\nPhase 2: Fine-tuning full model with discriminative learning rates...")

# Unfreeze all parameters
for param in model.parameters():
    param.requires_grad = True

# Discriminative learning rates: lower for earlier layers
def get_param_groups(model, model_name, backbone_lr, head_lr):
    """Create parameter groups with different learning rates."""
    if model_name in ["resnet50", "resnet18"]:
        return [
            {"params": model.conv1.parameters(), "lr": backbone_lr * 0.1},
            {"params": model.bn1.parameters(), "lr": backbone_lr * 0.1},
            {"params": model.layer1.parameters(), "lr": backbone_lr * 0.25},
            {"params": model.layer2.parameters(), "lr": backbone_lr * 0.5},
            {"params": model.layer3.parameters(), "lr": backbone_lr},
            {"params": model.layer4.parameters(), "lr": backbone_lr * 2},
            {"params": model.fc.parameters(), "lr": head_lr},
        ]
    else:
        # Generic: backbone at low LR, head at high LR
        head_params = []
        backbone_params = []
        for name, param in model.named_parameters():
            if "fc" in name or "classifier" in name or "head" in name:
                head_params.append(param)
            else:
                backbone_params.append(param)
        return [
            {"params": backbone_params, "lr": backbone_lr},
            {"params": head_params, "lr": head_lr},
        ]

param_groups = get_param_groups(
    model, CONFIG["model_name"], CONFIG["backbone_lr"], CONFIG["head_lr"]
)
optimizer = optim.AdamW(param_groups, weight_decay=CONFIG["weight_decay"])
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=CONFIG["full_epochs"])

best_val_acc = 0.0
for epoch in range(CONFIG["full_epochs"]):
    # Training
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in train_loader:
        images, labels = images.to(CONFIG["device"]), labels.to(CONFIG["device"])
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    scheduler.step()
    train_acc = 100. * correct / total

    # Validation
    model.eval()
    val_correct = 0
    val_total = 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(CONFIG["device"]), labels.to(CONFIG["device"])
            outputs = model(images)
            _, predicted = outputs.max(1)
            val_total += labels.size(0)
            val_correct += predicted.eq(labels).sum().item()

    val_acc = 100. * val_correct / val_total
    print(f"  Epoch {epoch+1}/{CONFIG['full_epochs']} - "
          f"Train Acc: {train_acc:.2f}%, Val Acc: {val_acc:.2f}%")

    # Save best model
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), "best_model.pth")
        print(f"    → Saved best model (val_acc={val_acc:.2f}%)")

print(f"\nDone! Best validation accuracy: {best_val_acc:.2f}%")
```

---

## Recipe 2: Fine-tuning BERT/DistilBERT for Text

### Choosing Your Model

```
Speed priority:      DistilBERT (40% smaller, 60% faster, 97% performance)
Accuracy priority:   RoBERTa-base (best general-purpose)
Multilingual:        XLM-RoBERTa
Long documents:      Longformer (up to 4096 tokens)
```

### The Recipe

```
Step 1: Choose model (DistilBERT for speed, RoBERTa for accuracy)
Step 2: Add classification head (HuggingFace does this automatically)
Step 3: Tokenize data with the MATCHING tokenizer
Step 4: Use AdamW (lr=2e-5, weight_decay=0.01)
Step 5: Linear warmup for 10% of steps, then linear decay
Step 6: Train for 3-5 epochs only (transformers overfit fast!)
Step 7: Gradient accumulation if batch size limited by memory
```

### Complete HuggingFace Code

```python
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, EarlyStoppingCallback
)
from datasets import load_dataset, Dataset
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, classification_report
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "model_name": "distilbert-base-uncased",  # or "roberta-base"
    "num_labels": 2,                          # YOUR number of classes
    "max_length": 256,                        # Max tokens (128-512 typical)
    "batch_size": 16,                         # Reduce if OOM
    "gradient_accumulation": 2,               # Effective batch = 16 * 2 = 32
    "learning_rate": 2e-5,                    # 2e-5 is the sweet spot for BERT
    "num_epochs": 5,
    "warmup_ratio": 0.1,                      # 10% warmup
    "weight_decay": 0.01,
    "output_dir": "./results",
}

# ============================================================
# STEP 1: Load tokenizer and model
# ============================================================
tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])
model = AutoModelForSequenceClassification.from_pretrained(
    CONFIG["model_name"],
    num_labels=CONFIG["num_labels"],
)

# ============================================================
# STEP 2: Prepare your data
# ============================================================
# Option A: Load from HuggingFace datasets
dataset = load_dataset("imdb")  # REPLACE with your dataset

# Option B: Load from pandas DataFrame
# df = pd.read_csv("your_data.csv")
# dataset = Dataset.from_pandas(df)
# dataset = dataset.train_test_split(test_size=0.2)

# ============================================================
# STEP 3: Tokenize (MUST use matching tokenizer!)
# ============================================================
def tokenize_function(examples):
    return tokenizer(
        examples["text"],               # YOUR text column name
        padding="max_length",
        truncation=True,
        max_length=CONFIG["max_length"],
    )

tokenized_datasets = dataset.map(tokenize_function, batched=True)

# ============================================================
# STEP 4: Define metrics
# ============================================================
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1_macro": f1_score(labels, predictions, average="macro"),
        "f1_weighted": f1_score(labels, predictions, average="weighted"),
    }

# ============================================================
# STEP 5: Training arguments (the important hyperparameters)
# ============================================================
training_args = TrainingArguments(
    output_dir=CONFIG["output_dir"],
    num_train_epochs=CONFIG["num_epochs"],
    per_device_train_batch_size=CONFIG["batch_size"],
    per_device_eval_batch_size=CONFIG["batch_size"] * 2,
    gradient_accumulation_steps=CONFIG["gradient_accumulation"],

    # Optimizer settings
    learning_rate=CONFIG["learning_rate"],
    weight_decay=CONFIG["weight_decay"],
    warmup_ratio=CONFIG["warmup_ratio"],
    lr_scheduler_type="linear",         # linear decay after warmup

    # Evaluation
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1_macro",

    # Logging
    logging_steps=50,
    report_to="none",                   # or "wandb" if you use W&B

    # Performance
    fp16=True,                          # Mixed precision (set False for CPU)
    dataloader_num_workers=4,
)

# ============================================================
# STEP 6: Train!
# ============================================================
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["test"],
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
)

trainer.train()

# ============================================================
# STEP 7: Evaluate and save
# ============================================================
results = trainer.evaluate()
print(f"\nFinal Results: {results}")

# Save model
trainer.save_model("./final_model")
tokenizer.save_pretrained("./final_model")

# Inference example
from transformers import pipeline
classifier = pipeline("text-classification", model="./final_model")
print(classifier("This movie was absolutely fantastic!"))
```

---

## Recipe 3: Fine-tuning LLMs (LoRA/QLoRA)

### Why LoRA?

Full fine-tuning a 7B parameter model needs ~28GB VRAM just for weights.
LoRA adds tiny trainable matrices (0.1-1% of parameters) that modify behavior.
QLoRA additionally quantizes the base model to 4-bit, so 7B fits in ~6GB VRAM.

### The Recipe

```
Step 1: Choose base model (Llama-2-7B, Mistral-7B, Phi-2)
Step 2: Prepare data in instruction/chat format
Step 3: Configure LoRA (rank=16, alpha=32, target_modules)
Step 4: Use 4-bit quantization (QLoRA) to fit on single GPU
Step 5: Train with SFTTrainer (lr=2e-4, batch=4, grad_accum=4)
Step 6: Merge LoRA weights back to base model
Step 7: Evaluate on held-out test prompts
```

### Complete PEFT/TRL Code

```python
import torch
from transformers import (
    AutoModelForCausalLM, AutoTokenizer,
    BitsAndBytesConfig, TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
from datasets import load_dataset

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "base_model": "mistralai/Mistral-7B-v0.1",  # or meta-llama/Llama-2-7b-hf
    "dataset": "your_dataset",                     # HuggingFace dataset or local
    "output_dir": "./lora-output",
    "lora_rank": 16,              # Higher = more capacity, more VRAM
    "lora_alpha": 32,             # Usually 2x rank
    "lora_dropout": 0.05,
    "max_seq_length": 2048,
    "batch_size": 4,
    "gradient_accumulation": 4,   # Effective batch = 4 * 4 = 16
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "warmup_ratio": 0.03,
}

# ============================================================
# STEP 1: Load model with 4-bit quantization (QLoRA)
# ============================================================
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",              # NormalFloat4 (best for LLMs)
    bnb_4bit_compute_dtype=torch.bfloat16,  # Compute in bf16
    bnb_4bit_use_double_quant=True,         # Double quantize for more savings
)

model = AutoModelForCausalLM.from_pretrained(
    CONFIG["base_model"],
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
model.config.use_cache = False  # Required for gradient checkpointing

tokenizer = AutoTokenizer.from_pretrained(CONFIG["base_model"])
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# ============================================================
# STEP 2: Prepare data in instruction format
# ============================================================
# Format your data like this:
PROMPT_TEMPLATE = """### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""

def format_instruction(example):
    """Format each example into instruction format."""
    if example.get("input", ""):
        text = PROMPT_TEMPLATE.format(
            instruction=example["instruction"],
            input=example["input"],
            output=example["output"]
        )
    else:
        text = f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['output']}"
    return {"text": text}

# Load and format dataset
dataset = load_dataset("json", data_files="your_training_data.jsonl")["train"]
dataset = dataset.map(format_instruction)

# ============================================================
# STEP 3: Configure LoRA
# ============================================================
model = prepare_model_for_kbit_training(model)

lora_config = LoraConfig(
    r=CONFIG["lora_rank"],
    lora_alpha=CONFIG["lora_alpha"],
    lora_dropout=CONFIG["lora_dropout"],
    bias="none",
    task_type="CAUSAL_LM",
    # Target modules (model-specific!)
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
        "gate_proj", "up_proj", "down_proj",       # MLP (Mistral/Llama)
    ],
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# → trainable params: 13M || all params: 7B || trainable%: 0.19%

# ============================================================
# STEP 4: Training arguments
# ============================================================
training_args = TrainingArguments(
    output_dir=CONFIG["output_dir"],
    num_train_epochs=CONFIG["num_epochs"],
    per_device_train_batch_size=CONFIG["batch_size"],
    gradient_accumulation_steps=CONFIG["gradient_accumulation"],
    learning_rate=CONFIG["learning_rate"],
    warmup_ratio=CONFIG["warmup_ratio"],
    lr_scheduler_type="cosine",
    weight_decay=0.01,
    fp16=False,
    bf16=True,                        # Use bf16 if GPU supports it
    logging_steps=10,
    save_strategy="epoch",
    optim="paged_adamw_8bit",         # Memory-efficient optimizer
    gradient_checkpointing=True,       # Trade compute for memory
    max_grad_norm=0.3,
    report_to="none",
)

# ============================================================
# STEP 5: Train with SFTTrainer
# ============================================================
trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    max_seq_length=CONFIG["max_seq_length"],
    tokenizer=tokenizer,
    dataset_text_field="text",
    packing=True,  # Pack multiple short examples into one sequence
)

trainer.train()
trainer.save_model(CONFIG["output_dir"])

# ============================================================
# STEP 6: Merge LoRA weights back to base model (for deployment)
# ============================================================
from peft import PeftModel

# Reload base model in full precision
base_model = AutoModelForCausalLM.from_pretrained(
    CONFIG["base_model"],
    torch_dtype=torch.float16,
    device_map="auto",
)

# Load and merge LoRA
model = PeftModel.from_pretrained(base_model, CONFIG["output_dir"])
merged_model = model.merge_and_unload()

# Save merged model
merged_model.save_pretrained("./merged_model")
tokenizer.save_pretrained("./merged_model")

# ============================================================
# STEP 7: Test inference
# ============================================================
from transformers import pipeline

pipe = pipeline("text-generation", model="./merged_model", tokenizer=tokenizer)
result = pipe(
    "### Instruction:\nSummarize the following text.\n\n### Input:\nYour text here.\n\n### Response:\n",
    max_new_tokens=256,
    temperature=0.7,
    do_sample=True,
)
print(result[0]["generated_text"])
```

---

## Recipe 4: Fine-tuning for Object Detection

### YOLO Fine-tuning (Ultralytics)

```python
from ultralytics import YOLO

# Load pretrained YOLOv8
model = YOLO("yolov8m.pt")  # n=nano, s=small, m=medium, l=large, x=xlarge

# Fine-tune on your data
# Expects data in YOLO format: images/ and labels/ with .txt annotation files
results = model.train(
    data="path/to/data.yaml",  # Dataset config file
    epochs=100,
    imgsz=640,
    batch=16,
    lr0=0.01,           # Initial learning rate
    lrf=0.01,           # Final LR = lr0 * lrf
    warmup_epochs=3,
    freeze=10,          # Freeze first 10 layers initially
    patience=20,        # Early stopping patience
    augment=True,
    mosaic=1.0,         # Mosaic augmentation
    mixup=0.1,          # Mixup augmentation
)

# Evaluate
metrics = model.val()
print(f"mAP50: {metrics.box.map50:.4f}")
print(f"mAP50-95: {metrics.box.map:.4f}")

# Inference
results = model("path/to/image.jpg")
results[0].show()
```

**data.yaml format:**
```yaml
path: /path/to/dataset
train: images/train
val: images/val

names:
  0: class_a
  1: class_b
  2: class_c
```

### Faster R-CNN Fine-tuning (torchvision)

```python
import torchvision
from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2, FasterRCNN_ResNet50_FPN_V2_Weights
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

# Load pretrained Faster R-CNN
model = fasterrcnn_resnet50_fpn_v2(weights=FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT)

# Replace head for YOUR number of classes
num_classes = 5 + 1  # YOUR classes + background
in_features = model.roi_heads.box_predictor.cls_score.in_features
model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

# Training loop (detection models take images + targets dict)
optimizer = torch.optim.SGD(model.parameters(), lr=0.005, momentum=0.9, weight_decay=0.0005)
lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.1)

for epoch in range(10):
    model.train()
    for images, targets in train_loader:
        # targets = [{"boxes": tensor, "labels": tensor}, ...]
        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())
        optimizer.zero_grad()
        losses.backward()
        optimizer.step()
    lr_scheduler.step()
```

---

## Recipe 5: Fine-tuning Embedding Models

### Sentence-BERT for Custom Similarity

```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

# Load pretrained embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Prepare training pairs
# Format: (sentence_a, sentence_b, similarity_score)
train_examples = [
    InputExample(texts=["Bug in login page", "Login not working"], label=0.9),
    InputExample(texts=["Bug in login page", "New feature request"], label=0.1),
    # ... your pairs
]

train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

# Choose loss function
# Option A: CosineSimilarityLoss (for similarity scores 0-1)
train_loss = losses.CosineSimilarityLoss(model)

# Option B: ContrastiveLoss (for binary similar/dissimilar)
# train_loss = losses.ContrastiveLoss(model)

# Option C: MultipleNegativesRankingLoss (for positive pairs only - BEST)
# train_examples = [InputExample(texts=["query", "positive_doc"])]
# train_loss = losses.MultipleNegativesRankingLoss(model)

# Train
model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=5,
    warmup_steps=100,
    output_path="./custom_embeddings",
    show_progress_bar=True,
)

# Use fine-tuned model
model = SentenceTransformer("./custom_embeddings")
embeddings = model.encode(["Your custom text"])
```

### Contrastive Learning for Domain-Specific Embeddings

```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator

# For domain adaptation without labeled pairs:
# Use TSDAE (unsupervised) or GPL (generative pseudo-labeling)

# TSDAE: Unsupervised domain adaptation
from sentence_transformers.losses import DenoisingAutoEncoderLoss

model = SentenceTransformer("all-MiniLM-L6-v2")

# Just need unlabeled domain sentences!
train_examples = [
    InputExample(texts=["Your domain-specific sentence", "Your domain-specific sentence"]),
    # The denoising autoencoder corrupts and reconstructs
]

train_dataloader = DataLoader(train_examples, batch_size=8, shuffle=True)
train_loss = DenoisingAutoEncoderLoss(model, decoder_name_or_path="all-MiniLM-L6-v2")

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=1,
    weight_decay=0,
    scheduler="constantlr",
    optimizer_params={"lr": 3e-5},
    show_progress_bar=True,
)
```

---

## Common Mistakes in Transfer Learning

### Mistake 1: Learning Rate Too High

```python
# BAD: Destroys pretrained weights in first few steps
optimizer = Adam(model.parameters(), lr=1e-3)  # Way too high for backbone!

# GOOD: Discriminative learning rates
optimizer = Adam([
    {"params": model.backbone.parameters(), "lr": 1e-5},   # Very low for pretrained
    {"params": model.head.parameters(), "lr": 1e-3},       # Normal for new head
])
```

### Mistake 2: Wrong Preprocessing

```python
# BAD: Your custom normalization (model never saw this during pretraining!)
transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])

# GOOD: Match the pretrained model's normalization
transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])  # ImageNet
```

### Mistake 3: Fine-tuning Too Long

```python
# BAD: 50 epochs of fine-tuning (catastrophic forgetting!)
training_args = TrainingArguments(num_train_epochs=50)

# GOOD: Early stopping + few epochs
training_args = TrainingArguments(
    num_train_epochs=5,
    load_best_model_at_end=True,
)
callbacks = [EarlyStoppingCallback(early_stopping_patience=2)]
```

### Mistake 4: Not Using Discriminative Learning Rates

```python
# BAD: Same LR for entire model
optimizer = Adam(model.parameters(), lr=2e-5)

# GOOD: Gradual unfreezing with increasing LR
# Earlier layers (general features) → very low LR
# Later layers (task-specific features) → higher LR
# New head → highest LR
```

### Mistake 5: Model Too Large for Data Amount

```
Data: 200 images
Model: ViT-Large (304M params)
Result: Massive overfitting, worse than random

Fix: Use EfficientNet-B0 (5.3M params) or even just feature extraction
Rule of thumb: Need at least 10-50x more examples than trainable parameters
             (after freezing backbone, head might have ~50K params → need 500K-2.5M? No!)
             Actually: Need 50-100 examples per class minimum for fine-tuning
```

---

## How Much Data Do You Need?

| Task | Minimum Viable | Recommended | Technique | Expected Performance |
|------|---------------|-------------|-----------|---------------------|
| Image classification | 50-100/class | 1000+/class | Fine-tune ResNet/EfficientNet | 85-95% acc |
| Text classification | 100-500 total | 5000+ total | Fine-tune DistilBERT | 80-95% acc |
| Named Entity Recognition | 500-1000 entities | 5000+ entities | Fine-tune BERT-NER | 75-90% F1 |
| Object detection | 100-500 images | 2000+ images | Fine-tune YOLO/RCNN | 50-80% mAP |
| LLM behavior tuning | 100-500 examples | 1000-10000 | LoRA/QLoRA | Task-dependent |
| Embedding fine-tuning | 1000+ pairs | 10000+ pairs | Contrastive/MNRL | 5-15% improvement |
| Semantic segmentation | 200-500 images | 2000+ images | Fine-tune DeepLab/UNet | 60-85% mIoU |

### Tips for Low-Data Regimes

1. **Use feature extraction first** (freeze everything, train only head)
2. **Data augmentation** (especially for images: flip, rotate, color jitter)
3. **Pseudo-labeling** (use model predictions on unlabeled data)
4. **Few-shot learning** (use CLIP, SetFit, or in-context learning)
5. **Active learning** (label only the most informative examples)

### When to Give Up on Transfer Learning

- Your data modality doesn't exist in pretrained models (e.g., custom sensor data)
- Your task is fundamentally different from pretraining (e.g., reinforcement learning)
- You have 1M+ labeled examples AND enough compute AND a unique architecture need
- Legal/compliance requires no pretrained model usage

Even then, try transfer learning first as a baseline. You'll be surprised how often it wins.

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│              TRANSFER LEARNING QUICK REFERENCE               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  VISION:   ResNet-50 + lr=1e-5 backbone + lr=1e-3 head     │
│  TEXT:     DistilBERT + AdamW + lr=2e-5 + 3 epochs         │
│  LLM:     QLoRA rank=16 + lr=2e-4 + cosine schedule        │
│  DETECT:  YOLOv8m + freeze=10 + lr=0.01 + 100 epochs       │
│  EMBED:   MiniLM + MNRL loss + lr=3e-5 + 5 epochs          │
│                                                             │
│  ALWAYS:  Match preprocessing, use warmup, early stop       │
│  NEVER:   High LR on backbone, train >10 epochs on text    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
