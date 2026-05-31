# Tool-Calling Agent

Demonstrates OpenAI's function calling API with a multi-tool customer service agent.

## What This Demonstrates

- OpenAI function calling (structured tool definitions)
- 5 tools simulating an e-commerce backend
- Parallel tool calls (multiple tools in one response)
- Error handling when tools fail
- A complete customer service scenario

## Tools

| Tool | Purpose |
|------|---------|
| `get_weather` | Get weather for shipping estimates |
| `search_products` | Find products in catalog |
| `calculate_price` | Calculate discounts and totals |
| `check_inventory` | Check stock availability |
| `place_order` | Place an order |

## Run

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```
