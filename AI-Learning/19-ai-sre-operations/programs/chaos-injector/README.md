# Chaos Injector

Simulates chaos experiments for AI systems, testing resilience against common AI-specific failure modes.

## Experiments

1. **Provider Outage** - Simulates model provider returning errors
2. **Latency Injection** - Adds artificial delay to model responses
3. **Quality Degradation** - Injects low-quality responses
4. **Cache Stampede** - Simulates complete cache invalidation
5. **Token Exhaustion** - Simulates hitting rate limits

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

Generates a chaos experiment report showing which experiments passed (system handles gracefully) vs failed (needs fixing), with recommendations for improvement.
