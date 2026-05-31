# Streaming Basics

A FastAPI server demonstrating the difference between streaming and non-streaming LLM responses.

## What You'll Learn

- How Server-Sent Events (SSE) streaming works
- Why streaming matters for user experience (time-to-first-token)
- How to implement both streaming and non-streaming endpoints
- The measurable latency difference between approaches

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

Server starts at http://localhost:8000

## Endpoints

- `POST /chat` — Non-streaming (waits for full response)
- `POST /chat/stream` — SSE streaming (tokens arrive as generated)
- `GET /compare?prompt=...` — Runs both and compares timing
- `GET /` — Simple HTML client to test both modes

## Key Insight

Non-streaming: User waits 3-10 seconds seeing nothing.
Streaming: User sees first token in ~200ms.
Same total time. Vastly different user experience.
