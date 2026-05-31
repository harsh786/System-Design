# Circuit Breaker for AI Model Endpoints

A circuit breaker implementation that protects AI systems from cascading failures, with automatic fallback to secondary models.

## What This Demonstrates

- **Circuit breaker pattern:** Closed → Open → Half-Open state machine
- **Failure detection:** Counts failures and trips when threshold exceeded
- **Automatic recovery:** Tests the endpoint after timeout, recovers if healthy
- **Fallback models:** When primary fails, seamlessly routes to secondary
- **State logging:** Every transition is logged with timing

## How It Works

1. Primary model endpoint starts healthy (circuit CLOSED)
2. Simulated failures begin (endpoint returns errors)
3. After N failures, circuit OPENS (stops calling primary)
4. Fallback model handles requests
5. After timeout, circuit goes HALF-OPEN (tests one request)
6. If test succeeds, circuit CLOSES (back to normal)

## Running

```bash
pip install -r requirements.txt
python main.py
```

## Configuration

- `failure_threshold`: Failures before opening (default: 3)
- `recovery_timeout`: Seconds before testing recovery (default: 10)
- `success_threshold`: Successes in half-open to close (default: 2)
