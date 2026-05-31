# MCP Tool Server

A practical MCP server exposing real-world file system and API tools with proper input validation and error handling.

## What This Demonstrates

- Real-world tool implementations (file operations, API calls)
- Input validation and security (path traversal prevention)
- Comprehensive error handling
- Descriptive tool schemas that help AI understand usage
- Logging for all tool invocations

## Prerequisites

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Testing

```bash
npx @modelcontextprotocol/inspector python main.py
```

## Tools Exposed

| Tool | Description |
|------|-------------|
| `search_files` | Search for files matching a glob pattern |
| `read_file` | Read contents of a file (with size limit) |
| `list_directory` | List files and folders in a directory |
| `get_weather` | Get weather for a city (simulated API) |

## Security Features

- Path traversal prevention (restricted to allowed directories)
- File size limits on reads
- Input validation on all parameters
- No write operations exposed
