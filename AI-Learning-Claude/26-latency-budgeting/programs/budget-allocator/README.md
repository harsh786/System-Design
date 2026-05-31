# Budget Allocator

Interactive latency budget allocation tool for AI pipelines.

## What It Does

- Takes a total latency budget (e.g., 3000ms) and component list
- Allocates budget per component based on priority and necessity
- Shows if total exceeds budget and where to optimize
- Demonstrates what-if analysis (trade-offs between components)
- Prints budget allocation table with slack/over-budget indicators

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- Budget allocation table
- What-if scenarios showing optimization trade-offs
- Slack analysis (how much room per component)
