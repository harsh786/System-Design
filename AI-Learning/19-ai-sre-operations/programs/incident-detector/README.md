# Incident Detector

Simulates AI incident detection by generating production metrics and applying anomaly detection algorithms.

## Features

- Generates realistic streams of AI production metrics (latency, quality, cost, errors)
- Implements threshold-based and trend-based anomaly detection
- Detects: quality degradation, latency spikes, cost anomalies, error bursts
- Shows alert firing with context (why was this flagged?)

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

Produces an incident timeline with severity assignments and detection context.
