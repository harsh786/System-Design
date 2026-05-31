# Model Router - Intelligent Request Routing

Routes AI requests to the optimal model based on complexity, demonstrating
significant cost savings while maintaining quality.

## What This Demonstrates

- **Complexity classification** using heuristics (simple/medium/complex)
- **Cascade pattern** - try cheap model first, escalate if confidence is low
- **Cost savings tracking** - shows savings vs always using the best model
- **Routing decision logging** - transparency into why each model was chosen

## Running

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## How It Works

1. Request arrives
2. Complexity classifier analyzes the prompt (heuristics-based)
3. Routes to appropriate model:
   - Simple → gpt-3.5-turbo ($0.002/1K tokens)
   - Medium → gpt-4o-mini ($0.00075/1K tokens)
   - Complex → gpt-4o ($0.02/1K tokens)
4. If cascade mode enabled: tries cheap model first, checks confidence
5. Reports cost savings vs always using GPT-4o

## Example Output

```
Query: "What is 2+2?"
Classification: SIMPLE
Routed to: gpt-3.5-turbo
Cost: $0.000045
Savings vs GPT-4o: 97%

Query: "Design a distributed system for real-time fraud detection"
Classification: COMPLEX
Routed to: gpt-4o
Cost: $0.012
Savings vs GPT-4o: 0% (needed the best model)
```
