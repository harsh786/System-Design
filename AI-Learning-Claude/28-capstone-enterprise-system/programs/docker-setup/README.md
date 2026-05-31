# Docker Setup (Optional)

For containerized deployment of the Enterprise AI System.

## Quick Start

```bash
docker build -t enterprise-ai-system .
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key enterprise-ai-system
```

## docker-compose (future)

A full docker-compose setup would add:
- Redis for rate limiting and session storage
- PostgreSQL for audit logs and cost tracking
- Prometheus + Grafana for observability

This is left as an exercise — the in-memory version demonstrates the same architecture.
