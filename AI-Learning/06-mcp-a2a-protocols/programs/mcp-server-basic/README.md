# MCP Server Basic

A minimal MCP server demonstrating all three capabilities: **Tools**, **Resources**, and **Prompts**.

## What This Demonstrates

- Creating an MCP server using Python's FastMCP SDK
- Exposing tools (functions the AI can call)
- Exposing resources (data the AI can read)
- Exposing prompt templates
- Full server lifecycle with logging

## Prerequisites

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python main.py
```

## Capabilities Exposed

| Type | Name | Description |
|------|------|-------------|
| Tool | `get_current_time` | Returns current date and time |
| Tool | `calculate_sum` | Adds a list of numbers |
| Resource | `system://info` | System information (OS, Python version) |
| Prompt | `greeting` | Generates a personalized greeting |

## Architecture

```
User (via Claude/Inspector)
    → MCP Client
        → This Server (stdio transport)
            → Tools: get_current_time, calculate_sum
            → Resources: system_info
            → Prompts: greeting
```
