# HuggingFace Ecosystem

## Overview

HuggingFace is the central hub for modern ML - providing models, datasets, tools, and infrastructure.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HuggingFace Ecosystem                          │
├─────────────────┬───────────────────┬───────────────────────────┤
│   Hub           │   Libraries       │   Infrastructure          │
├─────────────────┼───────────────────┼───────────────────────────┤
│ Models (500k+)  │ Transformers      │ Inference Endpoints       │
│ Datasets (80k+) │ Datasets          │ Spaces (Gradio/Streamlit) │
│ Spaces          │ Tokenizers        │ Text Generation Inference │
│ Model Cards     │ Accelerate        │ AutoTrain                 │
│ Discussions     │ PEFT              │ Inference API             │
│                 │ TRL               │                           │
│                 │ Evaluate          │                           │
└─────────────────┴───────────────────┴───────────────────────────┘
```

## Installation

```bash
pip install transformers datasets tokenizers accelerate peft trl evaluate
pip install torch  # or tensorflow
pip install huggingface_hub
huggingface-cli login  # authenticate with your token
```

---

## 1. HuggingFace Hub

```python
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

api = HfApi()

# Search for models
models = api.list_models(filter="text-generation", sort="downloads", direction=-1, limit=5)
for m in models:
    print(f"{m.id}: {m.downloads} downloads")

# Download specific file
model_path = hf_hub_download(repo_id="meta-llama/Llama-2-7b-hf", filename="config.json")

# Download entire model
snapshot_download(repo_id="bert-base-uncased", local_dir="./bert-model")

# Upload your model
api.upload_folder(folder_path="./my-model", repo_id="username/my-model", repo_type="model")
```

---

## 2. Transformers Library

### AutoModel & AutoTokenizer (The Core Pattern)

```python
from transformers import AutoModel, AutoTokenizer, AutoModelForCausalLM

# The Auto* classes automatically detect model architecture
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
model = AutoModel.from_pretrained("bert-base-uncased")

# Task-specific models
from transformers import (
    AutoModelForSequenceClassification,
    AutoModelForTokenClassification,
    AutoModelForQuestionAnswering,
    AutoModelForCausalLM,
    AutoModelForSeq2SeqLM,
)

# Load with specific configuration
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-2-7b-hf",
    torch_dtype=torch.float16,
    device_map="auto",           # automatic device placement
    load_in_4bit=True,           # 4-bit quantization
    attn_implementation="flash_attention_2",
)
```

### Pipeline API (Quick Inference)

```python
from transformers import pipeline

# Zero-config inference
classifier = pipeline("sentiment-analysis")
result = classifier("HuggingFace is amazing!")
# [{'label': 'POSITIVE', 'score': 0.9998}]

# Text generation
generator = pipeline("text-generation", model="gpt2")
output = generator("The future of AI is", max_length=50, num_return_sequences=3)

# Named Entity Recognition
ner = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english", grouped_entities=True)
entities = ner("Hugging Face is based in New York City.")

# Question Answering
qa = pipeline("question-answering", model="deepset/roberta-base-squad2")
answer = qa(question="What is HuggingFace?", context="HuggingFace is an AI company...")

# Summarization
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
summary = summarizer(long_text, max_length=130, min_length=30)

# Available pipelines: audio-classification, automatic-speech-recognition,
# depth-estimation, feature-extraction, fill-mask, image-classification,
# image-segmentation, image-to-text, object-detection, text-classification,
# text-generation, text2text-generation, token-classification, translation,
# video-classification, visual-question-answering, zero-shot-classification
```

### Fine-tuning with Trainer API

```python
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
)
from datasets import load_dataset
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

# Load dataset and model
dataset = load_dataset("imdb")
tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
model = AutoModelForSequenceClassification.from_pretrained(
    "distilbert-base-uncased", num_labels=2
)

# Tokenize
def tokenize_function(examples):
    return tokenizer(examples["text"], truncation=True, max_length=512)

tokenized_ds = dataset.map(tokenize_function, batched=True)

# Define metrics
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1": f1_score(labels, predictions, average="weighted"),
    }

# Training arguments
training_args = TrainingArguments(
    output_dir="./results",
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=64,
    num_train_epochs=3,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    push_to_hub=True,
    hub_model_id="username/my-imdb-classifier",
    fp16=True,
    dataloader_num_workers=4,
    gradient_accumulation_steps=2,
    warmup_ratio=0.1,
    logging_steps=100,
    report_to="wandb",  # integrates with W&B
)

# Create Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_ds["train"],
    eval_dataset=tokenized_ds["test"],
    tokenizer=tokenizer,
    data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
    compute_metrics=compute_metrics,
)

# Train
trainer.train()

# Push to Hub
trainer.push_to_hub()
```

### Custom Training Loop (When Trainer Isn't Enough)

```python
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup
from accelerate import Accelerator

accelerator = Accelerator(mixed_precision="fp16", gradient_accumulation_steps=4)

model = AutoModelForCausalLM.from_pretrained("gpt2")
optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
dataloader = DataLoader(dataset, batch_size=8, shuffle=True)

scheduler = get_linear_schedule_with_warmup(
    optimizer, num_warmup_steps=100, num_training_steps=len(dataloader) * 3
)

# Prepare with Accelerate (handles distributed, mixed precision, device placement)
model, optimizer, dataloader, scheduler = accelerator.prepare(
    model, optimizer, dataloader, scheduler
)

model.train()
for epoch in range(3):
    for step, batch in enumerate(dataloader):
        with accelerator.accumulate(model):
            outputs = model(**batch)
            loss = outputs.loss
            accelerator.backward(loss)
            accelerator.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

        if step % 100 == 0:
            accelerator.print(f"Epoch {epoch}, Step {step}, Loss: {loss.item():.4f}")

    # Save checkpoint
    accelerator.save_state(f"checkpoint-epoch-{epoch}")
```

---

## 3. Datasets Library

```python
from datasets import load_dataset, Dataset, DatasetDict, Features, Value

# Load from Hub
dataset = load_dataset("squad")  # Downloads and caches
dataset = load_dataset("json", data_files="train.jsonl")
dataset = load_dataset("csv", data_files={"train": "train.csv", "test": "test.csv"})

# Streaming (for large datasets - no download needed)
dataset = load_dataset("allenai/c4", "en", split="train", streaming=True)
for example in dataset.take(5):
    print(example["text"][:100])

# Preprocessing
def preprocess(examples):
    return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=128)

processed = dataset.map(preprocess, batched=True, num_proc=4, remove_columns=["text"])

# Filtering
filtered = dataset.filter(lambda x: len(x["text"]) > 100)

# Create from pandas/dict
import pandas as pd
df = pd.DataFrame({"text": ["hello", "world"], "label": [0, 1]})
dataset = Dataset.from_pandas(df)

# Push to Hub
dataset.push_to_hub("username/my-dataset")
```

---

## 4. PEFT (Parameter-Efficient Fine-Tuning)

```python
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
import torch

# 4-bit quantization config
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

# Load model in 4-bit
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-2-7b-hf",
    quantization_config=bnb_config,
    device_map="auto",
)
model = prepare_model_for_kbit_training(model)

# LoRA configuration
lora_config = LoraConfig(
    r=16,                        # Rank
    lora_alpha=32,               # Scaling factor
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],  # Which layers to adapt
)

# Apply LoRA
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# trainable params: 4,194,304 || all params: 6,742,609,920 || trainable%: 0.062%

# Train normally with Trainer or custom loop...
# Save only LoRA weights (tiny!)
model.save_pretrained("./lora-weights")  # ~16MB vs 14GB full model

# Load for inference
from peft import PeftModel
base_model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-hf")
model = PeftModel.from_pretrained(base_model, "./lora-weights")
model = model.merge_and_unload()  # Merge LoRA into base for faster inference
```

---

## 5. TRL (Transformer Reinforcement Learning)

```python
from trl import SFTTrainer, DPOTrainer, PPOTrainer, PPOConfig
from datasets import load_dataset

# Supervised Fine-Tuning (SFT)
dataset = load_dataset("timdettmers/openassistant-guanaco")

trainer = SFTTrainer(
    model="meta-llama/Llama-2-7b-hf",
    train_dataset=dataset["train"],
    dataset_text_field="text",
    max_seq_length=512,
    peft_config=lora_config,  # Can combine with PEFT
)
trainer.train()

# Direct Preference Optimization (DPO) - simpler than RLHF
dpo_dataset = load_dataset("Anthropic/hh-rlhf")
# Expects columns: prompt, chosen, rejected

dpo_trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,
    train_dataset=dpo_dataset["train"],
    tokenizer=tokenizer,
    beta=0.1,  # KL penalty coefficient
)
dpo_trainer.train()
```

---

## 6. Text Generation Inference (TGI)

```bash
# Deploy with Docker
docker run --gpus all --shm-size 1g -p 8080:80 \
  -v $PWD/data:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id meta-llama/Llama-2-7b-chat-hf \
  --quantize bitsandbytes-nf4 \
  --max-input-length 4096 \
  --max-total-tokens 8192

# Client usage
from huggingface_hub import InferenceClient

client = InferenceClient("http://localhost:8080")
output = client.text_generation(
    "What is deep learning?",
    max_new_tokens=200,
    stream=True,
)
for token in output:
    print(token, end="")
```

---

## 7. Accelerate (Multi-GPU / Distributed)

```bash
# Configure
accelerate config  # Interactive setup

# Launch distributed training
accelerate launch --num_processes 4 train.py
accelerate launch --multi_gpu --mixed_precision fp16 train.py
```

```python
# In your training script - minimal code changes
from accelerate import Accelerator

accelerator = Accelerator()
model, optimizer, dataloader = accelerator.prepare(model, optimizer, dataloader)

# Everything else stays the same!
for batch in dataloader:
    outputs = model(**batch)
    accelerator.backward(outputs.loss)
    optimizer.step()
    optimizer.zero_grad()
```

---

## 8. Gradio (Quick Demos)

```python
import gradio as gr
from transformers import pipeline

classifier = pipeline("sentiment-analysis")

def predict(text):
    result = classifier(text)[0]
    return {result["label"]: result["score"]}

demo = gr.Interface(
    fn=predict,
    inputs=gr.Textbox(placeholder="Enter text..."),
    outputs=gr.Label(),
    title="Sentiment Analysis",
    examples=["I love this!", "This is terrible."],
)
demo.launch(share=True)  # Creates public URL
# Deploy to HuggingFace Spaces with: `gradio deploy`
```

---

## Comparison: HuggingFace vs Raw PyTorch

| Aspect | Raw PyTorch | HuggingFace |
|--------|-------------|-------------|
| Model loading | Manual architecture + weights | `AutoModel.from_pretrained()` |
| Tokenization | Custom implementation | `AutoTokenizer` with fast Rust backend |
| Training loop | 50+ lines boilerplate | `Trainer` API or Accelerate |
| Distributed | `torch.distributed` setup | `accelerate launch` |
| Fine-tuning LLMs | Manual LoRA implementation | `peft` one-liner |
| Serving | Custom Flask/FastAPI | TGI with batching, quantization |
| Experiment tracking | Manual logging | Built-in W&B/TensorBoard |

---

## Common Pitfalls

1. **OOM errors**: Use `device_map="auto"`, `load_in_4bit=True`, gradient checkpointing
2. **Slow tokenization**: Use `batched=True` in `dataset.map()`, fast tokenizers are default
3. **Wrong pad token**: GPT models have no pad token - set `tokenizer.pad_token = tokenizer.eos_token`
4. **Forgetting `model.eval()`**: Always call before inference (disables dropout)
5. **Not using `torch.no_grad()`**: Wrap inference in `with torch.no_grad():` to save memory

## Best Practices

- Always pin model revisions: `from_pretrained("model", revision="abc123")`
- Use `datasets` streaming for large datasets that don't fit in memory
- Start with Pipeline API for prototyping, move to custom code for production
- Use PEFT/LoRA for fine-tuning LLMs - full fine-tuning rarely needed
- Enable Flash Attention 2 when available for 2-4x speedup
- Use `push_to_hub()` for model versioning and sharing
