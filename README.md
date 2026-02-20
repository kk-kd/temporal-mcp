# Temporal MCP Server

An MCP (Model Context Protocol) server for debugging Temporal workflows. This server enables LLM-assisted debugging by exposing Temporal workflow inspection tools.

## Features

- **list_workflows** - List workflow executions with optional query filter
- **describe_workflow** - Get detailed info about a specific workflow
- **get_workflow_history** - Fetch event history for debugging

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- A running Temporal server (local or cloud)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd temporal-mcp

# Create virtual environment and install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Configuration

Set environment variables to configure the Temporal connection:

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_ADDRESS` | Temporal server address | `localhost:7233` |
| `TEMPORAL_NAMESPACE` | Temporal namespace | `default` |
| `TEMPORAL_TLS_CERT` | Path to TLS certificate (for Cloud) | - |
| `TEMPORAL_TLS_KEY` | Path to TLS key (for Cloud) | - |
| `TEMPORAL_API_KEY` | API key (for Cloud) | - |

### Local Development

For local development, start Temporal using Docker Compose:

```bash
docker compose up -d temporal temporal-ui
```

This starts:
- Temporal server on `localhost:7233`
- Temporal UI on `http://localhost:8080`

### Temporal Cloud

For Temporal Cloud, set the appropriate environment variables:

```bash
export TEMPORAL_ADDRESS="your-namespace.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_API_KEY="your-api-key"
```

Or with TLS certificates:

```bash
export TEMPORAL_ADDRESS="your-namespace.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_TLS_CERT="/path/to/cert.pem"
export TEMPORAL_TLS_KEY="/path/to/key.pem"
```

## Usage

### With Cursor

Add to your Cursor MCP settings (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "temporal": {
      "command": "uv",
      "args": ["run", "temporal-mcp"],
      "cwd": "/path/to/temporal-mcp",
      "env": {
        "TEMPORAL_ADDRESS": "localhost:7233",
        "TEMPORAL_NAMESPACE": "default"
      }
    }
  }
}
```

### Standalone

```bash
temporal-mcp
```

## Available Tools

### list_workflows

List workflow executions with optional filtering.

```
list_workflows(query="", limit=10)
```

- `query`: Optional Temporal list filter syntax (e.g., `WorkflowType="MyWorkflow" AND ExecutionStatus="Running"`)
- `limit`: Maximum workflows to return (default 10, max 100)

### describe_workflow

Get detailed information about a specific workflow.

```
describe_workflow(workflow_id, run_id="")
```

- `workflow_id`: The workflow ID to describe
- `run_id`: Optional run ID (uses latest if not specified)

### get_workflow_history

Fetch the event history for a workflow execution.

```
get_workflow_history(workflow_id, run_id="", max_events=100)
```

- `workflow_id`: The workflow ID
- `run_id`: Optional run ID (uses latest if not specified)
- `max_events`: Maximum events to return (default 100, max 1000)

## Development

### Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Commands

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src

# Run tests
pytest

# Run all checks
black src tests && ruff check src tests && mypy src && pytest
```

### Project Structure

```
temporal-mcp/
├── pyproject.toml          # Project config and dependencies
├── Dockerfile
├── docker-compose.yml      # Local Temporal setup
├── README.md
├── src/temporal_mcp/
│   ├── __init__.py
│   ├── server.py           # MCP server and tool definitions
│   ├── client.py           # Temporal client wrapper
│   ├── config.py           # Environment-based configuration
│   └── models.py           # Pydantic models
├── tests/
│   ├── conftest.py         # Test fixtures
│   ├── test_config.py
│   ├── test_client.py
│   └── test_server.py
└── docs/
    └── PLAN.txt
```

## License

MIT
