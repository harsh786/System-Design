# Autonomous System Design Agent

> 🤖 An AI-powered multi-agent system that generates **HLD**, **LLD**, and **Database Design** documents from PRD (Product Requirements Documents) fetched from Confluence.

## Quick Start

### 1. Install dependencies
```bash
cd system-design-agent
pip install -e ".[dev]"
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run the agent

#### Option A: From Confluence PRD URL
```bash
python -m src.main \
  --prd-url "https://your-org.atlassian.net/wiki/spaces/ENG/pages/123456" \
  --context-dir "../" \
  --output-dir "./output/feature-x"
```

#### Option B: From local PRD file
```bash
python -m src.main \
  --prd-file "./sample-prd.md" \
  --context-dir "../" \
  --output-dir "./output/feature-x"
```

### 4. Use as MCP Server (VS Code integration)

Add to your VS Code `settings.json` or `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "system-design-agent": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/path/to/system-design-agent",
      "env": {
        "OPENAI_API_KEY": "your-key",
        "CONFLUENCE_URL": "https://your-org.atlassian.net",
        "CONFLUENCE_TOKEN": "your-token"
      }
    }
  }
}
```

Then in GitHub Copilot Chat, you can use:
- `@system-design-agent generate_system_design` with a PRD URL
- `@system-design-agent review_design` to review existing designs

---

## Architecture

```
INPUT                    PROCESSING                    OUTPUT
┌────────────┐      ┌─────────────────┐      ┌────────────────┐
│ Confluence  │─────▶│ PRD Analyzer    │─────▶│ HLD.md         │
│ PRD Doc     │      │      ↓          │      │ LLD/*.md       │
│             │      │ HLD Generator   │      │ DB_DESIGN.md   │
│ Existing    │─────▶│      ↓          │      │ REVIEW.md      │
│ HLD/LLD    │      │ LLD Generator   │      └────────────────┘
│ Docs        │      │      ↓          │
│             │      │ DB Designer     │
│ DB Schemas  │─────▶│      ↓          │
│             │      │ Review Agent    │
└────────────┘      └─────────────────┘

         RAG Pipeline (ChromaDB)
         ┌─────────────────────┐
         │ Chunk → Embed →     │
         │ Index → Retrieve    │
         └─────────────────────┘
```

## Agent Pipeline

| Agent | Input | Output | Purpose |
|-------|-------|--------|---------|
| PRD Analyzer | Raw PRD | Structured Requirements JSON | Extract & validate requirements |
| HLD Generator | Requirements + Existing HLDs | HLD Markdown + Component List | High-level architecture |
| LLD Generator | HLD + Requirements + Existing LLDs | LLD Markdown per component | Detailed component design |
| DB Designer | Entities + Query Patterns + NFRs | DB Design + DDL Scripts | Database schema & optimization |
| Review Agent | All documents + Requirements | Review Report | Cross-validation & gap analysis |

## Tech Stack

- **LLM**: OpenAI GPT-4o (or Anthropic Claude)
- **Agent Framework**: LangGraph
- **Embeddings**: OpenAI text-embedding-3-large
- **Vector Store**: ChromaDB (local) / Pinecone (production)
- **Document Ingestion**: Confluence REST API + local Markdown parser
- **MCP Server**: For VS Code / Copilot integration

## Project Structure

```
src/
├── agents/                  # Individual agent implementations
│   ├── prd_analyzer.py      # PRD extraction & validation
│   ├── hld_generator.py     # HLD document generation
│   ├── lld_generator.py     # LLD document generation
│   ├── db_design_generator.py # DB schema & DDL generation
│   └── review_agent.py      # Cross-validation & review
├── ingestion/               # Document ingestion pipeline
│   ├── confluence_reader.py # Confluence API integration
│   ├── markdown_parser.py   # Local MD file parser
│   └── chunker.py           # Smart document chunking
├── retrieval/               # RAG pipeline
│   └── vector_store.py      # Embedding & retrieval
├── orchestration/           # Agent workflow
│   ├── graph.py             # LangGraph state machine
│   └── state.py             # Shared agent state
├── mcp_server/              # MCP integration
│   └── server.py            # MCP server for VS Code
├── config/
│   ├── settings.py          # Configuration
│   └── prompts.py           # Prompt templates
└── main.py                  # CLI entry point
```
