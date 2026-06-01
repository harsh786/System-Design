# LLMs and Generative AI

## The LLM Revolution

Large Language Models represent the most significant paradigm shift in computing since the internet. They've transformed software engineering from writing explicit rules to steering probabilistic systems that understand and generate human language.

## Timeline of the LLM Era

```
2017 ─── "Attention Is All You Need" (Transformer paper, Google)
│
2018 ─── GPT-1 (117M params, OpenAI) - showed unsupervised pre-training works
│        BERT (340M params, Google) - bidirectional, dominated NLP benchmarks
│
2019 ─── GPT-2 (1.5B params) - "too dangerous to release"
│        T5 (Google) - text-to-text framework
│
2020 ─── GPT-3 (175B params) - few-shot learning emerges, API launch
│        Scaling laws papers (Kaplan et al.)
│
2021 ─── Codex (code generation) → GitHub Copilot
│        DALL-E (text to image)
│        InstructGPT / RLHF
│
2022 ─── ChatGPT (Nov 30) - fastest growing consumer app ever
│        Chinchilla (DeepMind) - optimal scaling
│        Stable Diffusion (open-source image gen)
│        PaLM (540B, Google)
│
2023 ─── GPT-4 (multimodal, March)
│        Claude (Anthropic)
│        Llama 1 & 2 (Meta, open-weight)
│        Mistral 7B (punches above its weight)
│        Mixtral 8x7B (Mixture of Experts)
│
2024 ─── GPT-4o (omni-modal)
│        Claude 3.5 Sonnet (best coding model)
│        Llama 3 (405B)
│        Gemini 1.5 Pro (1M context window)
│        Open-source explosion (Qwen, DeepSeek, Command-R)
│        AI Agents become practical
│
2025 ─── Claude 4 / Opus
│        Reasoning models (o1, o3, DeepSeek-R1)
│        AI coding agents (Cursor, Windsurf, OpenCode)
│        Multi-modal agents
```

## Key Concepts Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLMs & Generative AI                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐     │
│  │ Tokenization │  │  Transformer │  │ Training Pipeline │     │
│  │ & Embeddings │→ │  Architecture│→ │ Pre-train → RLHF  │     │
│  └──────────────┘  └──────────────┘  └───────────────────┘     │
│         │                  │                    │                │
│         ▼                  ▼                    ▼                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐     │
│  │   Prompt     │  │     RAG      │  │   Fine-Tuning     │     │
│  │ Engineering  │  │   Systems    │  │   LoRA/QLoRA      │     │
│  └──────────────┘  └──────────────┘  └───────────────────┘     │
│         │                  │                    │                │
│         └──────────────────┼────────────────────┘               │
│                            ▼                                     │
│                   ┌──────────────────┐                          │
│                   │    AI Agents     │                          │
│                   │  Tool Use, MCP   │                          │
│                   │  Multi-Agent     │                          │
│                   └──────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## How LLMs Changed the Industry

| Before LLMs | After LLMs |
|---|---|
| Rule-based NLP (regex, grammars) | Natural language understanding |
| Task-specific models (train per task) | One model, many tasks (few-shot) |
| Months to build NLP features | Hours with API calls |
| Need ML expertise for every feature | Prompt engineering accessible to all |
| Search = keyword matching | Search = semantic understanding |
| Code = written entirely by humans | Code = AI-assisted pair programming |
| Customer support = scripts | Customer support = AI conversations |

## Section Overview

| # | Topic | Key Takeaway |
|---|---|---|
| 01 | Tokenization & Embeddings | How text becomes numbers the model can process |
| 02 | GPT Architecture Deep Dive | The transformer architecture that powers everything |
| 03 | Prompt Engineering | How to effectively communicate with LLMs |
| 04 | RAG (Retrieval-Augmented Generation) | Grounding LLMs with external knowledge |
| 05 | Fine-Tuning LLMs | Adapting models to specific domains/tasks |
| 06 | AI Agents & Tool Use | Autonomous systems that can reason and act |

## The 80/20 of Working with LLMs

If you're building products today, here's where time is spent:

1. **Prompt Engineering** (40%) - Getting the model to do what you want
2. **RAG / Context Management** (30%) - Feeding the right information
3. **Evaluation & Testing** (15%) - Knowing if it's working
4. **Fine-Tuning / Optimization** (10%) - When prompts aren't enough
5. **Infrastructure** (5%) - Deployment, monitoring, cost management

## Prerequisites

- Understanding of neural networks and backpropagation
- Familiarity with the Transformer architecture (attention mechanism)
- Python programming
- Basic linear algebra (matrix multiplication, dot products)


---

## Recommended Resources

For curated video courses, books, blogs, and practice platforms related to this section, see the comprehensive resources guide:

> **[RESOURCES.md](../RESOURCES.md)** — Organized by learning phase with free and paid options.
