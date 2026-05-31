# Memory Compression Demo

Demonstrates memory compression strategies: sliding window, progressive summarization, entity extraction, and hierarchical compression.

## Features

- Takes a long conversation (50 messages) and compresses it
- Shows compression ratios at each level
- Demonstrates progressive summarization (detail decreases with age)
- Entity extraction for maximum compression
- Information retention verification

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
python main.py
```

## Output

- Before/after memory sizes
- Compression ratios per strategy
- Information retention check (what facts survived compression)
- Hierarchical memory state visualization
