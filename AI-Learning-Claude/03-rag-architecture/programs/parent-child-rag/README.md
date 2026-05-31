# Parent-Child RAG Implementation

Demonstrates hierarchical chunking where:
- **Small child chunks** (100-150 tokens) are used for precise search
- **Large parent chunks** (500+ tokens) provide full context for generation

## The Problem This Solves

With regular RAG, you face a tradeoff:
- Small chunks → precise matches but missing context
- Large chunks → good context but imprecise search (noise)

Parent-child RAG gives you **both**: search precision AND rich context.

## How It Works

```
Document
└── Parent Chunk (full section, ~500 tokens)
    ├── Child Chunk 1 (paragraph, ~100 tokens)  ← search target
    ├── Child Chunk 2 (paragraph, ~100 tokens)  ← search target
    └── Child Chunk 3 (paragraph, ~100 tokens)  ← search target

Query → Match Child → Return Parent as context → Generate
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```
