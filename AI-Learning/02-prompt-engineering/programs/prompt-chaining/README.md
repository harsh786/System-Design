# Prompt Chaining Demo

Demonstrates how breaking complex tasks into a chain of simpler prompts produces better results than a single monolithic prompt.

## What This Shows

1. **Single prompt vs chained prompts** — Quality comparison on complex tasks
2. **Research → Analyze → Summarize** pipeline
3. **Error handling between chains** — What happens when one step fails
4. **Document analysis pipeline** — Extract → Classify → Summarize → Format

## Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
pip install -r requirements.txt
python main.py
```

## Architecture

```
Input Document
    ↓
[Step 1: Extract key facts]
    ↓
[Step 2: Classify and categorize]
    ↓
[Step 3: Analyze relationships]
    ↓
[Step 4: Format final output]
    ↓
Structured Report
```

Each step is a focused prompt that does one thing well.
