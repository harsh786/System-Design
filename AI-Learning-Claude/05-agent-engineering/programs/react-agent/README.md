# ReAct Agent from Scratch

A pure implementation of the ReAct (Reasoning + Acting) pattern without any framework.

## What This Demonstrates

- The complete Thought → Action → Observation loop
- Three tools: web_search (simulated), calculator, knowledge_base
- Multi-step reasoning to answer complex questions
- Loop detection (max iterations)
- Clear step-by-step output for learning

## How It Works

1. The agent receives a task
2. It generates a **Thought** (reasoning about what to do)
3. It chooses an **Action** (which tool to call)
4. It receives an **Observation** (tool result)
5. It repeats until it has enough info for a **Final Answer**

## Run

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## Key Learning Points

- ReAct forces explicit reasoning before each action
- The LLM decides which tool to use based on its reasoning
- Loop detection prevents infinite cycling
- Each step is fully visible for debugging
