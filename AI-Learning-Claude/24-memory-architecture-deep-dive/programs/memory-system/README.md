# Memory System - Complete Implementation

A complete memory system demonstrating all 6 memory types (working, short-term, long-term, episodic, semantic, procedural) with multi-backend storage.

## Features

- **Working Memory**: In-context prompt management
- **Short-Term Memory**: Session-scoped with configurable capacity
- **Long-Term Memory**: Persistent file-based storage with semantic search
- **Episodic Memory**: Event-based memories with context and outcomes
- **Semantic Memory**: Entity-relationship knowledge graph
- **Procedural Memory**: Learned patterns and behaviors

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
python main.py
```

## What It Demonstrates

1. Agent conversation with memory across multiple turns
2. Each memory type being populated and retrieved
3. Memory improving response quality over time
4. Full memory state inspection after each interaction
