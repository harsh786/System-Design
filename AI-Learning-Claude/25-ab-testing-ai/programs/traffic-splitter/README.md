# Traffic Splitter

Implementation of traffic splitting strategies for AI A/B testing.

## Features

- Random splitting (per-request)
- User-based splitting (deterministic hash)
- Session-based splitting
- Traffic distribution verification
- Consistency checks (same user → same variant)

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## What It Demonstrates

- How different splitting strategies work
- That user-based hashing is consistent (same user always gets same variant)
- That traffic distribution matches configured weights
- Trade-offs between splitting approaches
