# Cross-Session Memory Demo

Simulates memory persistence across multiple sessions, demonstrating how an AI agent remembers context from previous conversations.

## Features

- Session 1: User discusses project, preferences are extracted
- Session 2: Agent uses memories from session 1 seamlessly
- Session-end extraction: automatic important fact identification
- Session-start injection: memory context loaded into prompt
- Memory profile evolution over time

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
python main.py
```

## Output

- Memory profile after each session
- Context continuity demonstration
- Extracted preferences and facts
- Session summaries stored for future use
