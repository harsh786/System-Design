# Stage 3: Deep Learning

> Duration: 4-5 months | Output: Paper reimplementations + custom architectures in PyTorch

---

## The Shift

In Stage 2, you learned to solve problems where someone hands you a CSV. Now you enter
the territory where data is raw (pixels, text, audio, video) and the model must learn
its own features. This is where the field exploded post-2012 and where it's still
exploding today.

**The rule for this stage:** Build every architecture from scratch ONCE. Then use
libraries forever after. You cannot debug what you don't understand internally.

---

## PyTorch is Your Weapon

I'm opinionated here: **learn PyTorch first and deeply.** Here's why:

- 90%+ of ML research papers use PyTorch
- If you can read papers and implement them, you're dangerous
- TensorFlow is fine but PyTorch's API matches how you think about neural nets
- Everything else (JAX, Flax, etc.) becomes easy once PyTorch is second nature

You'll learn TensorFlow/JAX at a conceptual level in Stage 5 (production) because
some companies use them. But PyTorch is your primary language.

---

## The Architecture Evolution (Learn In This Order)

```
This is the actual historical progression. Each builds on the last.

    1958          1986          2012          2014          2015          2017
     │             │             │             │             │             │
     ▼             ▼             ▼             ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│Perceptron│  │Backprop │  │ AlexNet │  │  GANs   │  │ ResNet  │  │Transformer│
│         │  │ + MLP   │  │  (CNN)  │  │         │  │         │  │          │
└────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬─────┘
     │             │             │             │             │             │
     │        You built     Convolutions   Adversarial  Skip          Attention
     │        this in       see patterns   training     connections   is all you
     │        Stage 1       in images      (generator   solve depth   need
     │                                     vs critic)   problem
     │
     └── The whole journey started here

                    2018          2020           2022           2024
                     │             │              │              │
                     ▼             ▼              ▼              ▼
                ┌─────────┐  ┌─────────┐   ┌──────────┐  ┌──────────┐
                │  BERT   │  │  GPT-3  │   │ Diffusion│  │  Mixture │
                │         │  │  ViT    │   │  Models  │  │  of Exp. │
                └────┬────┘  └────┬────┘   └────┬─────┘  └────┬─────┘
                     │             │              │              │
                Bidirectional  Scale is    Generate from   Sparse
                pretraining    all you     noise (images,  activation
                               need?       video, audio)   (efficient)
```

---

## Month 1: Neural Network Fundamentals in PyTorch

### Week 1-2: PyTorch Mastery

**This is not "intro to PyTorch." You should already have NumPy fluency from Stage 1.
Now you learn the professional tool.**

```
What to internalize:
├── Tensors
│   ├── .shape, .dtype, .device -- always be aware of these three
│   ├── Views vs copies (.view(), .reshape(), .contiguous())
│   ├── Broadcasting (same rules as NumPy but on GPU)
│   ├── In-place operations (the _ suffix: .add_(), .mul_())
│   └── GPU transfer (.to(device), .cuda(), .cpu())
│
├── Autograd
│   ├── requires_grad, .backward(), .grad
│   ├── Detaching from graph (.detach(), with torch.no_grad())
│   ├── Gradient accumulation (why you call .zero_grad())
│   ├── Gradient clipping (exploding gradients fix)
│   └── Custom autograd Functions (forward + backward)
│
├── nn.Module (the core abstraction)
│   ├── __init__ + forward (that's all you need)
│   ├── .parameters() and .named_parameters()
│   ├── .train() vs .eval() (BatchNorm, Dropout behavior changes!)
│   ├── Hooks (register_forward_hook, register_backward_hook)
│   ├── Saving/loading (state_dict, not pickle the whole model)
│   └── Nested modules (ModuleList, ModuleDict, Sequential)
│
├── Data Pipeline
│   ├── Dataset (map-style: __len__ + __getitem__)
│   ├── IterableDataset (streaming data)
│   ├── DataLoader (num_workers, pin_memory, collate_fn)
│   ├── Transforms (torchvision.transforms, albumentations)
│   └── Samplers (WeightedRandomSampler for imbalanced data)
│
└── Training Loop (write this from scratch, don't hide behind Lightning yet)
    ├── Forward pass
    ├── Loss computation
    ├── Backward pass
    ├── Optimizer step
    ├── Metric tracking
    ├── Validation loop
    ├── Checkpointing
    └── Early stopping
```

**Resources:**

| Resource | Why | Link |
|----------|-----|------|
| Andrej Karpathy: "Neural Nets: Zero to Hero" | THE best DL course. Period. Build everything from scratch. | https://youtube.com/playlist?list=PLAqhIrjkxbuWI23v9cThsA9GvCAUhRvKZ |
| PyTorch official tutorials | Do all of "Learning PyTorch" section | https://pytorch.org/tutorials/ |
| "Deep Learning with PyTorch" (free book) | Official PyTorch book | https://pytorch.org/assets/deep-learning/Deep-Learning-with-PyTorch.pdf |
| fast.ai Part 2: "From the Foundations" | Rebuild fastai/PyTorch from scratch | https://course.fast.ai/Lessons/part2.html |

### Week 3-4: Core Architectures (Build from Scratch)

**Build these yourself. Do NOT use torchvision.models.**

```
BUILD #1: Multi-Layer Perceptron (MLP)
├── Architecture: Linear → ReLU → Linear → ReLU → Linear
├── Train on: MNIST (target: 98%+ accuracy)
├── Experiment with: depth, width, activation functions, dropout
├── Learn: vanishing gradients, dying ReLU, weight initialization (Xavier, He)
└── Deliverable: Notebook showing how each hyperparameter affects training

BUILD #2: Convolutional Neural Network (CNN)
├── Architecture: Conv → BN → ReLU → Pool → ... → FC
├── Train on: CIFAR-10 (target: 90%+ accuracy)
├── Implement yourself: Conv2d (the forward pass with sliding window)
├── Learn: receptive field, stride, padding, pooling, feature maps
├── Then use nn.Conv2d and add: BatchNorm, Dropout, data augmentation
└── Deliverable: Visualize learned filters and feature maps

BUILD #3: Residual Network (ResNet)
├── Implement the residual block (skip connection)
├── Build ResNet-18 from scratch
├── Train on: CIFAR-10 (target: 93%+)
├── Learn: why skip connections solve vanishing gradients
├── Learn: why deeper ≠ better without residual connections
└── Deliverable: Compare ResNet-18 vs plain 18-layer net (same params)
```

---

## Month 2: Sequence Models and Attention

### Week 5-6: Recurrent Networks

```
BUILD #4: Vanilla RNN
├── Implement RNN cell: h_t = tanh(W_hh * h_{t-1} + W_xh * x_t + b)
├── Train on: character-level language model (Shakespeare)
├── Experience: vanishing/exploding gradients firsthand
├── Learn: BPTT (backpropagation through time)
└── Result: generates Shakespeare-like text (badly, and that's fine)

BUILD #5: LSTM
├── Implement LSTM cell (forget gate, input gate, output gate, cell state)
├── Train on: same character-level task (notice it works MUCH better)
├── Also implement GRU (simpler alternative)
├── Learn: why gates solve the vanishing gradient problem
└── Result: noticeably better text generation

BUILD #6: Seq2Seq with Attention
├── Encoder-Decoder architecture
├── Implement Bahdanau attention (additive)
├── Train on: simple translation (numbers to words, or small eng→fra)
├── Visualize attention weights (which input tokens matter for each output)
├── Learn: this is the PRECURSOR to transformers
└── This is where you understand why "Attention is All You Need" was revolutionary
```

**Why still learn RNNs in 2024?** Because:
1. You need to understand WHY transformers replaced them
2. Some production systems still use LSTMs (time series, embedded devices)
3. The concept of hidden state and sequential processing is foundational
4. You'll read papers that reference RNN baselines

### Week 7-8: The Transformer (The Most Important Architecture of the Decade)

```
BUILD #7: Transformer from Scratch
├── Step 1: Scaled dot-product attention
│   └── Q, K, V matrices. softmax(QK^T / sqrt(d_k)) * V
├── Step 2: Multi-head attention
│   └── Multiple attention heads, concatenate, project
├── Step 3: Position encoding
│   └── Sinusoidal (original) or learned embeddings
├── Step 4: Feed-forward network (per-position)
│   └── Two linear layers with ReLU/GELU between
├── Step 5: Layer normalization + residual connections
│   └── Pre-norm vs post-norm (pre-norm is more stable)
├── Step 6: Encoder block (stack N of these)
├── Step 7: Decoder block (add masked self-attention)
├── Step 8: Full encoder-decoder transformer
├── Train on: small machine translation task
├── Train on: character-level language model (compare with LSTM)
└── Deliverable: working transformer with attention visualization

Key insight: The transformer is just:
  - Attention (let tokens look at each other)
  - FFN (process each token independently)
  - Residual + LayerNorm (make it trainable)
  - Stack N times (depth = capacity)

That's it. The genius was REMOVING the recurrence, not adding complexity.
```

**Resources for Transformers:**

| Resource | Why | Link |
|----------|-----|------|
| "Attention Is All You Need" paper | The original. Read it. | https://arxiv.org/abs/1706.03762 |
| Jay Alammar: "The Illustrated Transformer" | Best visual explanation | https://jalammar.github.io/illustrated-transformer/ |
| Andrej Karpathy: "Let's build GPT" | Build GPT from scratch in 2 hours | https://youtube.com/watch?v=kCc8FmEb1nY |
| Harvard NLP: "The Annotated Transformer" | Paper + PyTorch code side by side | https://nlp.seas.harvard.edu/annotated-transformer/ |
| Lilian Weng: "The Transformer Family" | Comprehensive survey of variants | https://lilianweng.github.io/posts/2023-01-27-the-transformer-family-v2/ |

---

## Month 3: Generative Models + Advanced Training

### Week 9-10: GANs and VAEs

```
BUILD #8: Variational Autoencoder (VAE)
├── Encoder: input → mean, log_var
├── Reparameterization trick (why you need it for backprop)
├── Decoder: latent → reconstruction
├── Loss: reconstruction loss + KL divergence
├── Train on: MNIST (generate handwritten digits)
├── Learn: latent space interpolation, disentanglement
└── Deliverable: interactive latent space explorer

BUILD #9: GAN (Generative Adversarial Network)
├── Generator: noise → fake images
├── Discriminator: images → real/fake probability
├── Training: alternating min-max game
├── Implement: DCGAN (convolutional GAN)
├── Train on: CelebA faces or MNIST
├── Experience: mode collapse, training instability
├── Learn: Wasserstein GAN (WGAN-GP) for stable training
└── Deliverable: face generation with interpolation

BUILD #10: Diffusion Model (simplified)
├── Forward process: gradually add noise to image
├── Reverse process: learn to denoise
├── U-Net architecture for denoising
├── Noise schedule (linear vs cosine)
├── Train on: MNIST or CIFAR-10
├── Learn: the math behind DDPM
└── This is how Stable Diffusion, DALL-E 3, Midjourney work

Papers to read:
- VAE: "Auto-Encoding Variational Bayes" (Kingma, 2013)
- GAN: "Generative Adversarial Nets" (Goodfellow, 2014)
- DDPM: "Denoising Diffusion Probabilistic Models" (Ho, 2020)
```

### Week 11-12: Training at Scale

```
CRITICAL SKILLS:
├── Mixed Precision Training (FP16/BF16)
│   ├── torch.cuda.amp (autocast + GradScaler)
│   ├── When to use FP16 vs BF16 (hardware dependent)
│   └── 2x speedup, half the memory -- use it ALWAYS
│
├── Distributed Training
│   ├── DataParallel (easy but slow -- don't use in production)
│   ├── DistributedDataParallel (DDP) -- learn this properly
│   ├── Model parallelism vs data parallelism
│   ├── FSDP (Fully Sharded Data Parallel) for huge models
│   └── DeepSpeed ZeRO stages (1, 2, 3)
│
├── Memory Optimization
│   ├── Gradient checkpointing (trade compute for memory)
│   ├── Gradient accumulation (simulate larger batches)
│   ├── Activation offloading
│   └── Efficient attention (Flash Attention)
│
├── Training Stability
│   ├── Learning rate warmup (linear or cosine)
│   ├── Gradient clipping (max_norm)
│   ├── Weight decay (decoupled vs L2)
│   ├── Label smoothing
│   └── Learning rate schedules (cosine annealing, one-cycle)
│
└── Experiment Management
    ├── Weights & Biases (logging, sweeps, artifacts)
    ├── Reproducibility (seeds, deterministic mode)
    └── Ablation studies (systematic experimentation)
```

---

## Month 4: Paper Reading + Reimplementation

### The Paper Reading System

From this point forward, you read 2-3 papers per week. Here's how:

```
Paper Reading Protocol:
1. Read abstract + conclusion first (5 min)
2. Look at ALL figures and tables (10 min)
3. Read introduction + related work (15 min)
4. Deep read of method section (30-60 min)
5. Study experiments (what baselines? what ablations?) (20 min)
6. Ask: "Could I implement this?" If yes, do it.

Where to find papers:
- https://paperswithcode.com (papers + code + benchmarks)
- https://arxiv.org/list/cs.LG/recent (ML)
- https://arxiv.org/list/cs.CL/recent (NLP)
- https://arxiv.org/list/cs.CV/recent (Computer Vision)
- Twitter/X: follow researchers in your area
- Conferences: NeurIPS, ICML, ICLR, CVPR, ACL, EMNLP
```

### Reimplementation Projects (Pick 2-3)

```
CLASSIC PAPERS TO REIMPLEMENT:
├── "Deep Residual Learning" (ResNet) -- you partially did this
├── "Batch Normalization" -- add to your CNN, measure the difference
├── "Dropout: A Simple Way to Prevent Overfitting" -- implement properly
├── "Adam: A Method for Stochastic Optimization" -- implement the optimizer
├── "Layer Normalization" -- implement, compare with BatchNorm
├── "U-Net" -- for image segmentation
├── "Neural Style Transfer" -- Gatys et al.
└── "CLIP" (Contrastive Language-Image Pretraining) -- multimodal

MODERN PAPERS (pick based on interest):
├── "LoRA: Low-Rank Adaptation" -- you'll use this a LOT
├── "Flash Attention" -- understand the IO-awareness concept
├── "DPO: Direct Preference Optimization" -- RLHF alternative
├── "Mamba" (State Space Models) -- potential transformer alternative
└── "Mixture of Experts" -- how modern LLMs scale efficiently
```

---

## Month 4-5: PyTorch Lightning + Professional Practices

### When to Move from Raw PyTorch to Lightning

**Use raw PyTorch when:** learning, debugging, custom research code, tiny projects
**Use Lightning when:** multi-GPU training, reproducibility matters, team projects, production

```
Lightning gives you:
├── Automatic multi-GPU (just change Trainer flag)
├── Automatic mixed precision (just change flag)
├── Automatic logging (TensorBoard, W&B, MLflow)
├── Automatic checkpointing
├── Callbacks (early stopping, LR monitoring, etc.)
├── Reproducibility (seed_everything)
└── Clean separation of research code from engineering code

Learn:
├── LightningModule (training_step, configure_optimizers)
├── LightningDataModule (train/val/test dataloaders)
├── Trainer (gpus, precision, callbacks, logger)
├── Callbacks (write your own)
└── CLI (LightningCLI for config-driven training)
```

---

## Stage 3 Capstone Project

### Project: "Paper2Code" -- Reimplement a Recent Paper

**Choose a paper published in the last 12 months. Reimplement it from scratch.**

```
Requirements:
├── Full paper reimplementation in PyTorch
├── Match reported results within 5% (or explain why not)
├── Clean code with type hints, docstrings, tests
├── Training with W&B logging (loss curves, metrics, samples)
├── Multi-GPU support (at least DDP)
├── Config-driven (Hydra or YAML-based)
├── Ablation study (reproduce at least 2 ablations from paper)
├── Blog post explaining the paper + your implementation
└── Open source on GitHub with clear README + pretrained weights

Good paper choices for this exercise:
├── A vision paper if you're going into CV
├── An NLP paper if you're going into NLP
├── A generative model paper if you're going into GenAI
└── A training efficiency paper if you're going into MLOps
```

---

## Resources Summary

| Resource | Covers | Link |
|----------|--------|------|
| Karpathy: Zero to Hero (full series) | NN fundamentals through GPT | https://youtube.com/playlist?list=PLAqhIrjkxbuWI23v9cThsA9GvCAUhRvKZ |
| fast.ai Part 1 + Part 2 | Practical DL + from foundations | https://course.fast.ai/ |
| Stanford CS231n | CNNs for visual recognition | https://cs231n.stanford.edu/ |
| Stanford CS224n | NLP with deep learning | https://web.stanford.edu/class/cs224n/ |
| "Dive into Deep Learning" (d2l.ai) | Interactive textbook with code | https://d2l.ai/ |
| Papers With Code | Find papers + implementations | https://paperswithcode.com/ |
| The Little Book of Deep Learning | Concise reference (free PDF) | https://fleuret.org/francois/lbdl.html |

---

## Stage 3 Completion Criteria

- [ ] Built CNN, RNN, LSTM, Transformer from scratch (no nn.Transformer)
- [ ] Can implement any standard architecture by reading a paper (no tutorial needed)
- [ ] Trained a model using DDP across multiple GPUs
- [ ] Used mixed precision training and can explain why it works
- [ ] Can read and implement a paper within 1-2 weeks
- [ ] Have at least 2 paper reimplementations on GitHub
- [ ] Comfortable with PyTorch internals (custom autograd, hooks, profiling)
- [ ] Can train a GPT-style language model on custom text data
- [ ] Can explain attention, self-attention, cross-attention, multi-head attention
- [ ] Use W&B/MLflow for all experiments (never train without logging)
