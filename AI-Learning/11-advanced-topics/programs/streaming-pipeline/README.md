# Streaming AI Pipeline

## What This Demonstrates

A real-time streaming AI pipeline that shows how new data becomes searchable within seconds — not hours.

**Key concepts:**
- Events arrive continuously (simulated)
- Each event is immediately chunked, embedded, and indexed
- New data is queryable within seconds of arrival
- WebSocket endpoint streams updates to connected clients

## Architecture

```
Event Source → Process → Embed → Index → Searchable (< 5 seconds)
```

```mermaid
flowchart LR
    A[Event Generator] --> B[FastAPI Server]
    B --> C[Chunk & Embed]
    C --> D[In-Memory Index]
    D --> E[Query Endpoint]
    
    B --> F[WebSocket]
    F --> G[Real-time Updates]
```

## How to Run

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## Endpoints

- `POST /ingest` — Add new content (immediately indexed)
- `GET /query?q=...` — Search all indexed content
- `GET /stats` — Pipeline statistics (latency, document count)
- `WS /ws` — WebSocket for real-time notifications
- `POST /start-simulation` — Start simulated event stream

## Key Metrics Tracked

- **Ingest latency:** Time from "received" to "searchable"
- **Document count:** Total indexed documents
- **Query latency:** Time to search and return results
