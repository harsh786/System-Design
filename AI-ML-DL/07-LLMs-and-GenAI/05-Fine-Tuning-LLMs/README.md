# Fine-Tuning LLMs

## When to Fine-Tune vs Prompt vs RAG

```
┌────────────────────────────────────────────────────────────────────────┐
│                     Decision Matrix                                      │
├──────────────────┬──────────────┬───────────────┬──────────────────────┤
│ Need             │ Prompting    │ RAG           │ Fine-Tuning           │
├──────────────────┼──────────────┼───────────────┼──────────────────────┤
│ Custom knowledge │ ✗            │ ✓ (best)      │ △ (can overfit)      │
│ Custom style     │ △ (limited)  │ ✗             │ ✓ (best)             │
│ Custom format    │ ✓ (ok)       │ ✗             │ ✓ (best)             │
│ Reduce latency   │ ✗            │ ✗             │ ✓ (smaller model)    │
│ Reduce cost      │ △            │ ✗ (adds cost) │ ✓ (smaller model)    │
│ Dynamic data     │ ✗            │ ✓ (best)      │ ✗ (static)           │
│ Quick iteration  │ ✓ (best)     │ ✓             │ ✗ (hours/days)       │
│ Citations needed │ ✗            │ ✓ (best)      │ ✗                    │
│ Task-specific    │ △            │ △             │ ✓ (best)             │
│ behavior         │              │               │                      │
└──────────────────┴──────────────┴───────────────┴──────────────────────┘

Decision flow:
1. Try prompting first (always)
2. If knowledge gaps → add RAG
3. If style/format/behavior still wrong → fine-tune
4. Often the answer is: fine-tune + RAG together
```

## Full Fine-Tuning

Update ALL parameters of the model on your dataset.

```python
# Conceptually simple but expensive
for batch in training_data:
    loss = model(batch.input, batch.target)
    loss.backward()
    optimizer.step()  # Updates ALL ~7B parameters
```

**Problems:**
- Requires massive GPU memory (full model + gradients + optimizer states)
- 7B model: ~28GB (params) + ~28GB (gradients) + ~56GB (Adam states) = 112GB+
- Catastrophic forgetting: model loses general capabilities
- Expensive to store (one full copy per fine-tuned version)

## Parameter-Efficient Fine-Tuning (PEFT)

Only update a tiny fraction of parameters. The base model stays frozen.

### LoRA (Low-Rank Adaptation)

**The most important PEFT method.** Used everywhere in practice.

**Key insight**: Weight updates during fine-tuning have low intrinsic rank. Instead of updating the full weight matrix W, decompose the update into two small matrices.

```
Standard fine-tuning:
  W_new = W + ΔW                    ΔW is [d × d] — huge!

LoRA:
  W_new = W + BA                    B is [d × r], A is [r × d]
                                    r << d (rank 8-64 typically)
  
  Parameters:
  Full ΔW: d × d = 4096 × 4096 = 16.7M per layer
  LoRA:    d × r + r × d = 4096×16 + 16×4096 = 131K per layer
  
  Reduction: ~128x fewer trainable parameters!
```

**Math derivation:**

```
Given pre-trained weight matrix W₀ ∈ ℝ^{d×k}

Forward pass with LoRA:
  h = W₀x + ΔWx = W₀x + BAx

Where:
  B ∈ ℝ^{d×r}  (initialized to zeros)
  A ∈ ℝ^{r×k}  (initialized with random Gaussian)
  r << min(d, k)  (the rank — hyperparameter)

At initialization: BA = 0, so model starts from pre-trained weights
During training: only A and B are updated (W₀ is frozen)
At inference: merge W_merged = W₀ + BA (no extra latency!)
```

```python
import torch
import torch.nn as nn

class LoRALinear(nn.Module):
    def __init__(self, original_linear, rank=16, alpha=32):
        super().__init__()
        self.original = original_linear
        self.original.weight.requires_grad = False  # Freeze
        
        d_out, d_in = original_linear.weight.shape
        self.lora_A = nn.Parameter(torch.randn(rank, d_in) * 0.01)
        self.lora_B = nn.Parameter(torch.zeros(d_out, rank))
        self.scaling = alpha / rank
    
    def forward(self, x):
        # Original forward (frozen)
        original_out = self.original(x)
        # LoRA forward
        lora_out = (x @ self.lora_A.T @ self.lora_B.T) * self.scaling
        return original_out + lora_out
    
    def merge(self):
        """Merge LoRA weights into original for inference (no extra cost)."""
        self.original.weight.data += (self.lora_B @ self.lora_A) * self.scaling
```

**LoRA hyperparameters:**
| Parameter | Typical Values | Effect |
|---|---|---|
| rank (r) | 8, 16, 32, 64 | Higher = more capacity, more params |
| alpha (α) | 16, 32, 64 | Scaling factor, usually α = 2r |
| target modules | q_proj, v_proj, k_proj, o_proj, gate, up, down | Which layers to adapt |
| dropout | 0.05-0.1 | Regularization |

### QLoRA (Quantized LoRA)

Fine-tune a 4-bit quantized model with LoRA adapters in full precision.

```
Memory savings:
  Full fine-tune 7B:  112 GB (FP32)
  LoRA on 7B:         ~16 GB (FP16 base + FP16 adapters)
  QLoRA on 7B:        ~6 GB  (4-bit base + FP16 adapters)
  
  → Fine-tune a 65B model on a single 48GB GPU!
```

```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# 4-bit quantization config
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",          # NormalFloat4 (better than int4)
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,      # Quantize the quantization constants
)

# Load model in 4-bit
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-2-7b-hf",
    quantization_config=bnb_config,
    device_map="auto",
)

# Prepare for training
model = prepare_model_for_kbit_training(model)

# Add LoRA adapters
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# trainable params: 13,107,200 || all params: 3,540,389,888 || trainable%: 0.37%
```

### Other PEFT Methods

```
┌────────────────────────────────────────────────────────────────────┐
│ Method          │ How it works                    │ Params added   │
├─────────────────┼─────────────────────────────────┼────────────────┤
│ LoRA            │ Low-rank decomposition of ΔW    │ 0.1-1%        │
│ QLoRA           │ LoRA on 4-bit quantized model   │ 0.1-1%        │
│ Adapters        │ Small bottleneck layers inserted│ 1-5%          │
│ Prefix Tuning   │ Learnable prefix tokens in      │ <0.1%         │
│                 │ each attention layer            │                │
│ P-Tuning v2     │ Learnable prompts at every layer│ <0.1%         │
│ IA³             │ Learned vectors that scale      │ <0.01%        │
│                 │ activations                     │                │
└─────────────────┴─────────────────────────────────┴────────────────┘
```

## Quantization

Reduce model precision to save memory and increase inference speed.

```
Precision     Bits/param    7B Model Size    Quality Loss
────────────────────────────────────────────────────────
FP32          32            28 GB            None (baseline)
FP16/BF16     16            14 GB            Negligible
INT8          8             7 GB             Minimal
INT4 (GPTQ)   4            3.5 GB           Small
NF4 (QLoRA)  4             3.5 GB           Very small
2-bit         2             1.75 GB          Noticeable
```

| Method | Description | Best For |
|---|---|---|
| GPTQ | Post-training quantization, layer-by-layer | Inference serving |
| AWQ | Activation-aware, protects salient weights | High quality + small |
| GGUF | CPU-friendly format (llama.cpp) | Local/CPU inference |
| bitsandbytes | Dynamic quantization (NF4, INT8) | Training with QLoRA |

```python
# GPTQ quantization (for inference)
from auto_gptq import AutoGPTQForCausalLM

model = AutoGPTQForCausalLM.from_quantized(
    "TheBloke/Llama-2-7B-GPTQ",
    device="cuda:0",
    use_triton=True,
)

# GGUF with llama-cpp-python (CPU inference)
from llama_cpp import Llama
llm = Llama(model_path="llama-2-7b.Q4_K_M.gguf", n_ctx=4096)
output = llm("Hello, ", max_tokens=100)
```

## Training Infrastructure

| Framework | Best For | Key Feature |
|---|---|---|
| DeepSpeed (Microsoft) | Large-scale training | ZeRO optimizer (stages 1-3) |
| FSDP (PyTorch native) | Multi-GPU training | Full sharding, simpler than DeepSpeed |
| Megatron-LM (NVIDIA) | Very large models | Tensor + pipeline parallelism |
| Axolotl | Easy fine-tuning | YAML config, supports all methods |
| TRL (HuggingFace) | RLHF/DPO training | SFTTrainer, DPOTrainer |

```yaml
# Axolotl configuration example
base_model: meta-llama/Llama-2-7b-hf
model_type: LlamaForCausalLM

load_in_4bit: true
adapter: qlora
lora_r: 16
lora_alpha: 32
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj

dataset:
  - path: my_dataset.jsonl
    type: sharegpt

sequence_len: 2048
micro_batch_size: 4
gradient_accumulation_steps: 4
num_epochs: 3
learning_rate: 2e-4
lr_scheduler: cosine
warmup_steps: 100
optimizer: adamw_bnb_8bit

bf16: true
gradient_checkpointing: true
```

## Data Preparation for Fine-Tuning

### Instruction Format (Alpaca-style)

```json
{
  "instruction": "Write a function to find the longest palindrome substring",
  "input": "",
  "output": "```python\ndef longest_palindrome(s):\n    ..."
}
```

### Chat Format (ShareGPT/ChatML)

```json
{
  "conversations": [
    {"from": "system", "value": "You are a helpful coding assistant."},
    {"from": "human", "value": "How do I reverse a linked list?"},
    {"from": "gpt", "value": "Here's how to reverse a linked list:\n```python\n..."}
  ]
}
```

### Data Quality Guidelines

```
✓ DO:
- 1K-100K high-quality examples (quality > quantity)
- Diverse inputs covering edge cases
- Consistent format across examples
- Include examples of saying "I don't know"
- Balance across categories/tasks

✗ DON'T:
- Use noisy/incorrect data
- Only include easy examples
- Have inconsistent formatting
- Fine-tune on data you want RAG for (it won't memorize well)
```

## Evaluation of Fine-Tuned Models

| Metric | What it measures | When to use |
|---|---|---|
| Perplexity | How well model predicts next token | General quality |
| MMLU | Multi-task knowledge | General capability |
| HumanEval | Code generation correctness | Code models |
| MT-Bench | Multi-turn conversation quality | Chat models |
| Custom eval set | Your specific task performance | Always (most important) |

```python
# Always create a held-out evaluation set BEFORE training
eval_set = load_eval_data("eval.jsonl")  # 100-500 examples

# Evaluate before and after fine-tuning
base_results = evaluate(base_model, eval_set)
finetuned_results = evaluate(finetuned_model, eval_set)

# Compare
print(f"Base model accuracy: {base_results['accuracy']:.2%}")
print(f"Fine-tuned accuracy: {finetuned_results['accuracy']:.2%}")

# Check for regression on general tasks
general_eval = load_eval_data("general_knowledge.jsonl")
regression = evaluate(finetuned_model, general_eval)
print(f"General knowledge retention: {regression['accuracy']:.2%}")
```

## Catastrophic Forgetting

The model loses pre-trained knowledge when fine-tuned on narrow data.

**Mitigations:**
1. **LoRA/PEFT** — freeze base model, only train adapters
2. **Low learning rate** — 1e-5 to 2e-4 (not 1e-3)
3. **Mix in general data** — Add 5-10% general instruction data to training
4. **Short training** — 1-3 epochs, stop early
5. **Regularization** — weight decay, dropout

## Model Merging

Combine multiple fine-tuned models without additional training.

```python
# Linear merge (model soup)
merged_weights = alpha * model_A_weights + (1 - alpha) * model_B_weights

# TIES (Trim, Elect Sign, Merge)
# 1. Trim: zero out small magnitude changes
# 2. Elect sign: resolve sign conflicts by majority vote
# 3. Merge: average remaining parameters

# DARE (Drop And REscale)
# 1. Randomly drop some delta weights (set to 0)
# 2. Rescale remaining weights to compensate
# 3. Merge the sparse deltas
```

```python
# Using mergekit
# config.yaml
"""
models:
  - model: base_model
    parameters:
      weight: 0.5
  - model: math_finetuned
    parameters:
      weight: 0.3
  - model: code_finetuned
    parameters:
      weight: 0.2
merge_method: linear
dtype: bfloat16
"""
```

## Distillation

Train a smaller "student" model to mimic a larger "teacher" model.

```python
def distillation_loss(student_logits, teacher_logits, labels, temperature=2.0, alpha=0.5):
    """
    Combine soft targets (from teacher) with hard targets (ground truth).
    """
    # Soft loss: KL divergence between student and teacher distributions
    soft_student = F.log_softmax(student_logits / temperature, dim=-1)
    soft_teacher = F.softmax(teacher_logits / temperature, dim=-1)
    soft_loss = F.kl_div(soft_student, soft_teacher, reduction='batchmean') * (temperature ** 2)
    
    # Hard loss: standard cross-entropy with ground truth
    hard_loss = F.cross_entropy(student_logits, labels)
    
    # Combined loss
    return alpha * soft_loss + (1 - alpha) * hard_loss
```

## Cost Comparison

| Method | Hardware | Time (7B) | Cost | Quality |
|---|---|---|---|---|
| Full fine-tune | 8× A100 80GB | 1-3 days | $5,000-15,000 | Best |
| LoRA (FP16) | 1× A100 80GB | 4-12 hours | $50-150 | Very good |
| QLoRA (4-bit) | 1× RTX 4090 24GB | 4-12 hours | $10-30 | Good |
| OpenAI API fine-tune | N/A (managed) | 1-4 hours | $25-100 | Good |
| Distillation | 4× A100 | 1-2 days | $2,000-5,000 | Varies |

## Interview Questions

1. **When would you fine-tune vs use RAG vs just prompt engineering?**
   - Prompt first (fast iteration), RAG for dynamic knowledge, fine-tune for style/format/behavior changes.

2. **Explain LoRA — what's the intuition and how does it save memory?**
   - Weight updates are low-rank; decompose ΔW into two small matrices (B×A). Only train these small matrices while keeping the base frozen.

3. **What is QLoRA and how does it enable fine-tuning on consumer GPUs?**
   - Loads base model in 4-bit (NF4), trains LoRA adapters in FP16. Reduces memory from 112GB to ~6GB for 7B model.

4. **How do you prepare data for fine-tuning? What format?**
   - Instruction/chat format, 1K-100K high-quality diverse examples, consistent formatting, include edge cases.

5. **What is catastrophic forgetting and how do you prevent it?**
   - Model loses general knowledge during narrow fine-tuning. Prevent with PEFT, low LR, mixed data, early stopping.

6. **How would you evaluate a fine-tuned model?**
   - Hold-out eval set, compare to base model, check for regression on general tasks, use task-specific metrics + human eval.

7. **What's model merging and when would you use it?**
   - Combining weights from multiple fine-tuned models without retraining. Use to get multi-skill models (code + math + chat).

8. **Explain the difference between GPTQ, AWQ, and GGUF quantization.**
   - GPTQ: post-training layer-wise quantization for GPU. AWQ: protects important weights. GGUF: CPU-optimized format for llama.cpp.

## Exercises

### Exercise 1: QLoRA Fine-Tuning
Fine-tune Llama 2 7B on a custom instruction dataset using QLoRA. Measure quality before and after on your eval set.

### Exercise 2: LoRA Rank Ablation
Train the same model with LoRA ranks 4, 8, 16, 32, 64. Plot quality vs. trainable parameters. Find the sweet spot.

### Exercise 3: Data Quality Experiment
Take 10K training examples. Compare: (a) all 10K low-quality, (b) 1K high-quality curated subset. Which produces a better model?

### Exercise 4: Merge Experiment
Fine-tune two LoRA adapters (one for code, one for creative writing). Merge them and evaluate if the merged model retains both capabilities.

## Common Pitfalls

1. **Fine-tuning when prompting would work** — Always try prompting first; it's 100x faster to iterate
2. **Too few diverse examples** — 100 examples of the same pattern teaches nothing; need diversity
3. **Training too long** — 1-3 epochs is usually enough; more = overfitting
4. **Not evaluating on held-out data** — Training loss going down ≠ model is better
5. **Wrong learning rate** — Too high destroys the model; too low wastes compute. Start at 2e-4 for LoRA
6. **Ignoring base model selection** — A better base model fine-tunes to a better result. Start with the best you can afford
