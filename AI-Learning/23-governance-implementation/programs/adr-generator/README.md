# ADR Generator

Tool for generating and managing Architecture Decision Records (ADRs) for AI systems.

## Features
- Generate properly formatted ADRs from structured input
- Maintain an ADR index
- Demonstrate ADR lifecycle (proposed → accepted → superseded)
- Pre-generates 3 example ADRs

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Commands
- `list` — Show ADR index
- `show <number>` — Display a specific ADR
- `create` — Create a new ADR interactively
- `supersede <number>` — Mark an ADR as superseded
- `generate` — Generate example ADRs
- `quit` — Exit
