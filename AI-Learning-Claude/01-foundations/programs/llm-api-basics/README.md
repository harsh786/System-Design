# LLM API Basics

A hands-on program that demonstrates how to call LLM APIs and observe the effects of different parameters.

## What You'll Learn

- How to call the OpenAI API
- The effect of temperature on output variability
- System prompts vs user prompts
- Token usage tracking and timing

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## Run It

```bash
python main.py
```

## Experiments

1. Watch how temperature 0 gives identical outputs every time
2. See temperature 1.0 produce wildly different responses
3. Compare system prompt effects on tone and style
